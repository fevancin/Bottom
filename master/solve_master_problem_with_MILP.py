import os
import json
from datetime import datetime

from pyomo.environ import ConcreteModel, SolverFactory, maximize, TerminationCondition, value
from pyomo.environ import Set, Var, Objective, Constraint
from pyomo.environ import Boolean

if __name__ == "__main__":
    start_time = datetime.now()

# reading of the filenames file
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isfile("filenames.json"):
    raise FileNotFoundError("The filenames file was not found")
with open("filenames.json", "r") as file:
    filenames = json.loads(file.read())

# reading of the operators file
if not os.path.isdir(filenames['instance']['folder']):
    raise FileNotFoundError("The instance folder was not found")
os.chdir(filenames['instance']['folder'])
if not os.path.isfile(filenames['instance']['full_input']):
    raise FileNotFoundError("The full input file was not found")
with open(filenames['instance']['full_input'], "r") as file:
    full_input = json.loads(file.read())

# moving in the master folder
if not os.path.isdir(os.path.join("..", filenames['master']['folder'])):
    raise FileNotFoundError("The master folder was not found")
os.chdir(os.path.join("..", filenames['master']['folder']))

care_units_touched_by_packet = dict()
for packet_name, packet in full_input['abstract_packet'].items():
    care_units = set()
    for service_name in packet:
        care_units.add(full_input['services'][service_name]['careUnit'])
    care_units_touched_by_packet[packet_name] = care_units

# indexes for each necessary name (no useless info)
x_indexes = set()
l_indexes = set()
epsilon_indexes = set()

x_and_l_indexes = set()
capacity_indexes = set()
interdiction_indexes = set()
necessity_indexes = set()

for patient_name, patient in full_input['pat_request'].items():
    # patient_priority = patient['priority_weight']
    for protocol_name, protocol in patient.items():
        if protocol_name == "priority_weight":
            continue
        for iteration_name, iteration in protocol.items():
            initial_offset = iteration[1]
            for protocol_packet in iteration[0]:
                packet_name = protocol_packet['packet_id']
                for perfect_day in range(protocol_packet['start_date'] + initial_offset, protocol_packet['existence'][1] + initial_offset + 1, protocol_packet['freq']):
                    if perfect_day < protocol_packet['existence'][0] or perfect_day > protocol_packet['existence'][1]:
                        continue
                    there_is_at_least_one_day = False
                    min_day = 10000
                    max_day = -10000
                    for day_name in range(perfect_day - protocol_packet['tolerance'], perfect_day + protocol_packet['tolerance'] + 1):
                        if day_name >= full_input['horizon']:
                            continue
                        if day_name < protocol_packet['existence'][0] or day_name > protocol_packet['existence'][1]:
                            continue
                        is_packet_assignable = True
                        temp_l_indexes = set()
                        for service_name in full_input['abstract_packet'][packet_name]:
                            service_care_unit = full_input['services'][service_name]['careUnit']
                            service_duration = full_input['services'][service_name]['duration']
                            if service_duration > full_input['capacity'][str(day_name)][service_care_unit]:
                                is_packet_assignable = False
                                break
                            temp_l_indexes.add((patient_name, service_name, day_name))
                        if is_packet_assignable:
                            x_indexes.add((patient_name, packet_name, day_name))
                            l_indexes.update(temp_l_indexes)
                            for care_unit_name in care_units_touched_by_packet[packet_name]:
                                capacity_indexes.add((day_name, care_unit_name))
                            for patient_name1, service_name1, day_name1 in temp_l_indexes:
                                x_and_l_indexes.add((patient_name1, packet_name, service_name1, day_name1))
                            there_is_at_least_one_day = True
                            if day_name < min_day:
                                min_day = day_name
                            if day_name > max_day:
                                max_day = day_name
                    if there_is_at_least_one_day:
                        epsilon_indexes.add((patient_name, packet_name, f"{protocol_name}__{iteration_name}__{min_day}__{max_day}"))

for service_name1, necessities in full_input['necessity'].items():
    for service_name2, times in necessities.items():
        if times[0] - 1 > full_input['interdiction'][service_name1][service_name2]:
            full_input['interdiction'][service_name1][service_name2] = times[0] - 1
        for patient_name3, service_name3, day_name3 in l_indexes:
                for patient_name4, service_name4, _ in l_indexes:
                    if service_name3 == service_name1 and patient_name3 == patient_name4 and service_name4 == service_name2:
                        necessity_indexes.add((patient_name3, service_name1, service_name2, day_name3))

for service_name1, interdictions in full_input['interdiction'].items():
    for service_name2, time in interdictions.items():
        if time > 0:
            for patient_name3, service_name3, day_name3 in l_indexes:
                for patient_name4, service_name4, _ in l_indexes:
                    if service_name3 == service_name1 and patient_name3 == patient_name4 and service_name4 == service_name2:
                        interdiction_indexes.add((patient_name3, service_name1, service_name2, day_name3))

x_indexes = sorted(x_indexes)
l_indexes = sorted(l_indexes)
epsilon_indexes = sorted(epsilon_indexes)
x_and_l_indexes = sorted(x_and_l_indexes)
capacity_indexes = sorted(capacity_indexes)
interdiction_indexes = sorted(interdiction_indexes)
necessity_indexes = sorted(necessity_indexes)

# solve master problem
model = ConcreteModel()

model.x_indexes = Set(initialize=x_indexes)
model.l_indexes = Set(initialize=l_indexes)
model.epsilon_indexes = Set(initialize=epsilon_indexes)
model.x_and_l_indexes = Set(initialize=x_and_l_indexes)
model.capacity_indexes = Set(initialize=capacity_indexes)
model.interdiction_indexes = Set(initialize=interdiction_indexes)
model.necessity_indexes = Set(initialize=necessity_indexes)

del x_indexes, l_indexes, epsilon_indexes, x_and_l_indexes, capacity_indexes, interdiction_indexes, necessity_indexes

model.x = Var(model.x_indexes, domain=Boolean)
model.l = Var(model.l_indexes, domain=Boolean)
model.epsilon = Var(model.epsilon_indexes, domain=Boolean)

def f(model):
    return sum(model.epsilon[patient_name, packet_name, window_name] for patient_name, packet_name, window_name in model.epsilon_indexes)
model.objective = Objective(rule=f, sense=maximize)

def f1(model, patient_name, packet_name, service_name, day_name):
    return model.x[patient_name, packet_name, day_name] <= model.l[patient_name, service_name, day_name]
model.x_and_l = Constraint(model.x_and_l_indexes, rule=f1)

def f2(model, patient_name, packet_name, window_name):
    _, _, min_day, max_day = window_name.split("__")
    return sum([model.x[patient_name, packet_name, day_name] for day_name in range(int(min_day), int(max_day) + 1) if (patient_name, packet_name, day_name) in model.x]) == model.epsilon[patient_name, packet_name, window_name]
model.x_and_epsilon = Constraint(model.epsilon_indexes, rule=f2)

def f3(model, day_name, care_unit_name):
    return (sum([model.l[patient_name, service_name, day_name] * full_input['services'][service_name]['duration']
        for patient_name, service_name, day_name1 in model.l_indexes
        if day_name1 == day_name and full_input['services'][service_name]['careUnit'] == care_unit_name]) <=
        full_input['capacity'][str(day_name)][care_unit_name])
model.respect_capacity = Constraint(model.capacity_indexes, rule=f3)

def f4(model, patient_name, service_name1, service_name2, day_name):
    time = full_input['interdiction'][service_name1][service_name2]
    day_names = []
    for day_name2 in range(day_name + 1, day_name + time + 1):
        if (patient_name, service_name2, day_name2) in model.l:
            day_names.append(day_name2)
    if len(day_names) == 0:
        return Constraint.Skip
    return sum([model.l[patient_name, service_name2, day_name2] for day_name2 in day_names]) <= (1 - model.l[patient_name, service_name1, day_name]) * len(day_names)
model.interdictions = Constraint(model.interdiction_indexes, rule=f4)

impossible_assignments = set()

def f5(model, patient_name, service_name1, service_name2, day_name):
    times = full_input['necessity'][service_name1][service_name2]
    day_names = []
    for day_name2 in range(day_name + times[0], day_name + times[1] + 1):
        if (patient_name, service_name2, day_name2) in model.l:
            day_names.append(day_name2)
    if len(day_names) == 0:
        impossible_assignments.add((patient_name, service_name1, day_name))
        return Constraint.Skip
    return sum([model.l[patient_name, service_name2, day_name2] for day_name2 in day_names]) >= model.l[patient_name, service_name1, day_name]
model.necessities = Constraint(model.necessity_indexes, rule=f5)

for patient_name, service_name, day_name in impossible_assignments:
    model.l[patient_name, service_name, day_name].fix(0)
    for patient_name1, packet_name, day_name1 in model.x_indexes:
        if patient_name1 == patient_name and day_name1 == day_name and service_name in full_input['abstract_packet'][packet_name]:
            model.x[patient_name, packet_name, day_name].fix(0)

# model.pprint()
# exit(0)

opt = SolverFactory('glpk')
result = opt.solve(model)

requests = dict()

# decoding solver answer
if result.solver.termination_condition == TerminationCondition.infeasible:
    requests = {}
else:
    for patient_name, packet_name, day_name in model.x_indexes:
        if value(model.x[patient_name, packet_name, day_name]) == 0:
            continue
        if day_name not in requests:
            requests[day_name] = dict()
        if patient_name not in requests[day_name]:
            requests[day_name][patient_name] = {
                'packets': []
            }
        requests[day_name][patient_name]['packets'].append(packet_name)

# writing of the requests file
with open(filenames['master']['output_file'], "w") as file:
    file.write(json.dumps(requests, indent=4, sort_keys=True))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))