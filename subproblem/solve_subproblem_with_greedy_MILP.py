import os
import json
from datetime import datetime

from pyomo.environ import ConcreteModel, SolverFactory, maximize, TerminationCondition, value
from pyomo.environ import Set, Var, Objective, Constraint
from pyomo.environ import Boolean, NonNegativeIntegers

if __name__ == "__main__":
    start_time = datetime.now()

# reading of the filenames file
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isfile("filenames.json"):
    raise FileNotFoundError("The filenames file was not found")
with open("filenames.json", "r") as file:
    filenames = json.loads(file.read())

# reading of the input files
if not os.path.isdir(filenames['instance']['folder']):
    raise FileNotFoundError("The instance folder was not found")
os.chdir(filenames['instance']['folder'])
with open(filenames['instance']['operators'], "r") as file:
    operators = json.loads(file.read())
with open(filenames['instance']['services'], "r") as file:
    services = json.loads(file.read())
with open(filenames['instance']['packets'], "r") as file:
    packets = json.loads(file.read())
with open(filenames['instance']['priorities'], "r") as file:
    priorities = json.loads(file.read())
if not os.path.isdir(os.path.join("..", filenames['master']['folder'])):
    raise FileNotFoundError("The master folder was not found")
os.chdir(os.path.join("..", filenames['master']['folder']))
with open(filenames['master']['output_file'], "r") as file:
    requests = json.loads(file.read())

# moving in the subproblem folder
if not os.path.isdir(os.path.join("..", filenames['subproblem']['folder'])):
    raise FileNotFoundError("The subproblem folder was not found")
os.chdir(os.path.join("..", filenames['subproblem']['folder']))

def solve_day(day_name):
    # accumulators for each necessary index (no useless info)
    x_indexes = set()
    chi_indexes = set()
    packet_indexes = set()
    packet_consistency_indexes = set()
    aux1_indexes = set()
    aux2_indexes = set()
    max_time = 0

    patient_priorities = set()

    daily_requests = requests[day_name]

    if len(daily_requests) == 0:
        return []

    for patient_name, patient in daily_requests.items():
        for packet_name in patient['packets']:
            is_packet_satisfiable = True
            temp_x_indexes = set()
            temp_chi_indexes = set()
            temp_max_time = 0
            for service_name in packets[packet_name]:
                is_service_satisfiable = False
                care_unit_name = services[service_name]['careUnit']
                service_duration = services[service_name]['duration']
                for operator_name, operator in operators[day_name][care_unit_name].items():
                    if service_duration <= operator['duration']:
                        is_service_satisfiable = True
                        temp_chi_indexes.add((patient_name, service_name, f"{operator_name}__{care_unit_name}"))
                        if operator['start'] + operator['duration'] > max_time:
                            temp_max_time = operator['start'] + operator['duration']
                if not is_service_satisfiable:
                    is_packet_satisfiable = False
                    break
                temp_x_indexes.add((patient_name, service_name))
            if is_packet_satisfiable:
                x_indexes.update(temp_x_indexes)
                chi_indexes.update(temp_chi_indexes)
                packet_indexes.add((patient_name, packet_name))
                patient_priorities.add(priorities[patient_name])
                if temp_max_time > max_time:
                    max_time = temp_max_time
    
    if len(packet_indexes) == 0:
        return []

    for packet_index in packet_indexes:
        for service_name in packets[packet_index[1]]:
            packet_consistency_indexes.add((packet_index[0], packet_index[1], service_name))
    
    x_indexes = sorted(x_indexes)
    chi_indexes = sorted(chi_indexes)
    packet_indexes = sorted(packet_indexes)
    packet_consistency_indexes = sorted(packet_consistency_indexes)

    for index1 in range(len(x_indexes) - 1):
        for index2 in range(index1 + 1, len(x_indexes)):
            if x_indexes[index1][0] == x_indexes[index2][0]:
                aux1_indexes.add((x_indexes[index1][0], x_indexes[index1][1], x_indexes[index2][1]))
    
    for index1 in range(len(chi_indexes) - 1):
        for index2 in range(index1 + 1, len(chi_indexes)):
            if chi_indexes[index1][2] == chi_indexes[index2][2]:
                aux2_indexes.add((chi_indexes[index1][2], chi_indexes[index1][0], chi_indexes[index1][1], chi_indexes[index2][0], chi_indexes[index2][1]))

    aux1_indexes = sorted(aux1_indexes)
    aux2_indexes = sorted(aux2_indexes)

    patient_priorities = sorted(patient_priorities, reverse=True)

    # solve subproblem problem
    model = ConcreteModel()

    model.x_indexes = Set(initialize=x_indexes)
    model.chi_indexes = Set(initialize=chi_indexes)
    model.packet_indexes = Set(initialize=packet_indexes)
    model.packet_consistency_indexes = Set(initialize=packet_consistency_indexes)
    model.aux1_indexes = Set(initialize=aux1_indexes)
    model.aux2_indexes = Set(initialize=aux2_indexes)

    del x_indexes, chi_indexes, packet_indexes, packet_consistency_indexes, aux1_indexes, aux2_indexes

    model.x = Var(model.x_indexes, domain=Boolean)
    model.t = Var(model.x_indexes, domain=NonNegativeIntegers)
    model.chi = Var(model.chi_indexes, domain=Boolean)
    model.packet = Var(model.packet_indexes, domain=Boolean)
    model.aux1 = Var(model.aux1_indexes, domain=Boolean)
    model.aux2 = Var(model.aux2_indexes, domain=Boolean)

    def f(model):
        return (100 * sum( model.packet[patient_name, packet_name] * priorities[patient_name] for patient_name, packet_name in model.packet_indexes) - 
            sum([model.x[patient_name, service_name] for patient_name, service_name in model.x_indexes]))
    model.objective = Objective(rule=f, sense=maximize)

    def f1(model, patient_name, service_name):
        return model.t[patient_name, service_name] <= model.x[patient_name, service_name] * max_time
    model.t_and_x = Constraint(model.x_indexes, rule=f1)

    def f2(model, patient_name, service_name):
        return model.t[patient_name, service_name] >= model.x[patient_name, service_name]
    model.x_and_t = Constraint(model.x_indexes, rule=f2)

    def f3(model, patient_name, service_name):
        return sum(model.chi[p, s, o] for p, s, o in model.chi_indexes if patient_name == p and service_name == s) == model.x[patient_name, service_name]
    model.x_and_chi = Constraint(model.x_indexes, rule=f3)

    def f4(model, patient_name, service_name, compound_name):
        operator_name, care_unit_name = compound_name.split("__")
        start = operators[day_name][care_unit_name][operator_name]['start']
        return start <= model.t[patient_name, service_name] + (1 - model.chi[patient_name, service_name, compound_name]) * max_time
    model.respect_start = Constraint(model.chi_indexes, rule=f4)

    def f5(model, patient_name, service_name, compound_name):
        operator_name, care_unit_name = compound_name.split("__")
        start = operators[day_name][care_unit_name][operator_name]['start']
        end = start + operators[day_name][care_unit_name][operator_name]['duration']
        service_duration = services[service_name]['duration']
        return model.t[patient_name, service_name] + service_duration <= end + (1 - model.chi[patient_name, service_name, compound_name]) * max_time
    model.respect_end = Constraint(model.chi_indexes, rule=f5)

    def f6(model, patient_name, packet_name, service_name):
        return model.packet[patient_name, packet_name] <= model.x[patient_name, service_name]
    model.packet_consistency = Constraint(model.packet_consistency_indexes, rule=f6)

    def f7(model, patient_name, service_name1, service_name2):
        service_duration = services[service_name1]['duration']
        return (model.t[patient_name, service_name1] + service_duration <= model.t[patient_name, service_name2] +
            (2 - model.x[patient_name, service_name1] - model.x[patient_name, service_name2] +
            model.aux1[patient_name, service_name1, service_name2]) * max_time)
    model.patient_not_overlaps1 = Constraint(model.aux1_indexes, rule=f7)

    def f8(model, patient_name, service_name1, service_name2):
        service_duration = services[service_name2]['duration']
        return (model.t[patient_name, service_name2] + service_duration <= model.t[patient_name, service_name1] +
            (3 - model.x[patient_name, service_name1] - model.x[patient_name, service_name2] -
            model.aux1[patient_name, service_name1, service_name2]) * max_time)
    model.patient_not_overlaps2 = Constraint(model.aux1_indexes, rule=f8)

    def f9(model, operator_name, patient_name1, service_name1, patient_name2, service_name2):
        service_duration = services[service_name1]['duration']
        return (model.t[patient_name1, service_name1] + service_duration <= model.t[patient_name2, service_name2] +
            (2 - model.chi[patient_name1, service_name1, operator_name] - model.chi[patient_name2, service_name2, operator_name] +
            model.aux2[operator_name, patient_name1, service_name1, patient_name2, service_name2]) * max_time)
    model.operator_not_overlaps1 = Constraint(model.aux2_indexes, rule=f9)

    def f10(model, operator_name, patient_name1, service_name1, patient_name2, service_name2):
        service_duration = services[service_name2]['duration']
        return (model.t[patient_name2, service_name2] + service_duration <= model.t[patient_name1, service_name1] +
            (3 - model.chi[patient_name1, service_name1, operator_name] - model.chi[patient_name2, service_name2, operator_name] -
            model.aux2[operator_name, patient_name1, service_name1, patient_name2, service_name2]) * max_time)
    model.operator_not_overlaps2 = Constraint(model.aux2_indexes, rule=f10)

    for index in model.x_indexes:
        model.x[index].fix(0)
        model.t[index].fix(0)
    model.t_and_x.deactivate()
    model.x_and_t.deactivate()
    model.x_and_chi.deactivate()
    for index in model.chi_indexes:
        model.chi[index].fix(0)
    model.respect_start.deactivate()
    model.respect_end.deactivate()
    for index in model.packet_indexes:
        model.packet[index].fix(0)
    model.packet_consistency.deactivate()
    for index in model.aux1_indexes:
        model.aux1[index].fix(0)
    model.patient_not_overlaps1.deactivate()
    model.patient_not_overlaps2.deactivate()
    for index in model.aux2_indexes:
        model.aux2[index].fix(0)
    model.operator_not_overlaps1.deactivate()
    model.operator_not_overlaps2.deactivate()

    for priority in patient_priorities:
        for (patient_name, service_name) in model.x_indexes:
            if priorities[patient_name] == priority:
                model.x[patient_name, service_name].fixed = False
                model.t[patient_name, service_name].fixed = False
                model.t_and_x[patient_name, service_name].activate()
                model.x_and_t[patient_name, service_name].activate()
                model.x_and_chi[patient_name, service_name].activate()
        for (patient_name, service_name, operator_name) in model.chi_indexes:
            if priorities[patient_name] == priority:
                model.chi[patient_name, service_name, operator_name].fixed = False
                model.respect_start[patient_name, service_name, operator_name].activate()
                model.respect_end[patient_name, service_name, operator_name].activate()
        for (patient_name, packet_name) in model.packet_indexes:
            if priorities[patient_name] == priority:
                model.packet[patient_name, packet_name].fixed = False
        for (patient_name, packet_name, service_name) in model.packet_consistency_indexes:
            if priorities[patient_name] == priority:
                model.packet_consistency[patient_name, packet_name, service_name].activate()
        for (patient_name, service_name1, service_name2) in model.aux1_indexes:
            model.aux1[patient_name, service_name1, service_name2].fixed = False
            model.patient_not_overlaps1[patient_name, service_name1, service_name2].activate()
            model.patient_not_overlaps2[patient_name, service_name1, service_name2].activate()
        for (operator_name, patient_name1, service_name1, patient_name2, service_name2) in model.aux2_indexes:
            model.aux2[operator_name, patient_name1, service_name1, patient_name2, service_name2].fixed = False
            model.operator_not_overlaps1[operator_name, patient_name1, service_name1, patient_name2, service_name2].activate()
            model.operator_not_overlaps2[operator_name, patient_name1, service_name1, patient_name2, service_name2].activate()

        opt = SolverFactory('glpk')
        result = opt.solve(model)

        for (patient_name, service_name) in model.x_indexes:
            if priorities[patient_name] == priority:
                model.x[patient_name, service_name].fixed = True
                model.t[patient_name, service_name].fixed = True
        for (patient_name, service_name, operator_name) in model.chi_indexes:
            if priorities[patient_name] == priority:
                model.chi[patient_name, service_name, operator_name].fixed = True
        for (patient_name, packet_name) in model.packet_indexes:
            if priorities[patient_name] == priority:
                model.packet[patient_name, packet_name].fixed = True
        for (patient_name, service_name1, service_name2) in model.aux1_indexes:
            model.aux1[patient_name, service_name1, service_name2].fixed = True
        for (operator_name, patient_name1, service_name1, patient_name2, service_name2) in model.aux2_indexes:
            model.aux2[operator_name, patient_name1, service_name1, patient_name2, service_name2].fixed = True

    # decoding solver answer
    if result.solver.termination_condition == TerminationCondition.infeasible:
        return []

    daily_scheduled_services = []
    for patient_name, service_name, compound_name in model.chi_indexes:
        if value(model.chi[patient_name, service_name, compound_name]):
            operator_name, care_unit_name = compound_name.split("__")
            daily_scheduled_services.append({
                'patient': patient_name,
                'service': service_name,
                'operator': operator_name,
                'care_unit': care_unit_name,
                'start': int(value(model.t[patient_name, service_name]))
            })

    return daily_scheduled_services

results = dict()

for day_name in requests.keys():

    daily_scheduled_services = solve_day(day_name)

    # list all not satisfied packets
    not_scheduled_packets = dict()
    for patient_name, patient in requests[day_name].items():
        for packet_name in patient['packets']:
            is_packet_satisfied = True
            for service_name in packets[packet_name]:
                is_service_done = False
                for scheduled_service in daily_scheduled_services:
                    if scheduled_service['patient'] == patient_name and scheduled_service['service'] == service_name:
                        is_service_done = True
                        break
                if not is_service_done:
                    is_packet_satisfied = False
                    break
            if not is_packet_satisfied:
                if patient_name not in not_scheduled_packets:
                    not_scheduled_packets[patient_name] = []
                not_scheduled_packets[patient_name].append(packet_name)
        if patient_name in not_scheduled_packets:
            not_scheduled_packets[patient_name].sort()
    
    # list all unused operators
    unused_operators = dict()
    for care_unit_name, care_unit in operators[day_name].items():
        for operator_name in care_unit.keys():
            is_operator_used = False
            for scheduled_service in daily_scheduled_services:
                if scheduled_service['care_unit'] == care_unit_name and scheduled_service['operator'] == operator_name:
                    is_operator_used = True
                    break
            if not is_operator_used:
                if care_unit_name not in unused_operators:
                    unused_operators[care_unit_name] = []
                unused_operators[care_unit_name].append(operator_name)

    results[day_name] = {
        'scheduledServices': sorted(daily_scheduled_services, key=lambda r: r['patient'] + r['service']),
        'notScheduledPackets': not_scheduled_packets,
        'unusedOperators': unused_operators
    }

# writing of the results file
with open(filenames['subproblem']['output_file'], "w") as file:
    file.write(json.dumps(results, indent=4))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))