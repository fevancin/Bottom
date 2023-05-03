import os
import json
from datetime import datetime

from pyomo.environ import ConcreteModel, SolverFactory, maximize, TerminationCondition
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
os.chdir(filenames['instance']['folder'])
if not os.path.isfile(filenames['instance']['operators']):
    raise FileNotFoundError("The operators file was not found")
with open(filenames['instance']['operators'], "r") as file:
    operators = json.loads(file.read())

# moving in the subsumptions folder
if not os.path.isdir(os.path.join("..", filenames['subsumptions']['folder'])):
    raise FileNotFoundError("The subsumption folder was not found")
os.chdir(os.path.join("..", filenames['subsumptions']['folder']))

# get all the care unit names in the input
def get_care_unit_names():
    care_unit_names = set()
    for day in operators.values():
        for care_unit_name in day.keys():
            care_unit_names.add(care_unit_name)
    return sorted(care_unit_names)

def is_program_satisfiable(more_operators, less_operators):
    x_indexes = []
    for more_operator_name, more_operator in more_operators.items():
        for less_operator_name, less_operator in less_operators.items():
            if more_operator['start'] <= less_operator['start'] and more_operator['start'] + more_operator['duration'] >= less_operator['start'] + less_operator['duration']:
                x_indexes.append((less_operator_name, more_operator_name))
    less_indexes = []
    for less_operator_name in less_operators.keys():
        less_indexes.append(less_operator_name)
    overlap_indexes = []
    for index1 in range(len(x_indexes) - 1):
        for index2 in range(index1 + 1, len(x_indexes)):
            if x_indexes[index1][1] != x_indexes[index2][1] or x_indexes[index1][0] == x_indexes[index2][0]:
                continue
            if ((less_operators[x_indexes[index1][0]]['start'] <= less_operators[x_indexes[index2][0]]['start'] and
                less_operators[x_indexes[index1][0]]['start'] + less_operators[x_indexes[index1][0]]['duration'] > less_operators[x_indexes[index2][0]]['start']) or
                (less_operators[x_indexes[index2][0]]['start'] <= less_operators[x_indexes[index1][0]]['start'] and
                 less_operators[x_indexes[index2][0]]['start'] + less_operators[x_indexes[index2][0]]['duration'] > less_operators[x_indexes[index1][0]]['start'])):
                overlap_indexes.append((x_indexes[index1][0], x_indexes[index2][0], x_indexes[index1][1]))
    model = ConcreteModel()
    model.x_indexes = Set(initialize=x_indexes)
    model.choose_one_indexes = Set(initialize=less_indexes)
    model.not_overlap_indexes = Set(initialize=overlap_indexes)
    model.x = Var(model.x_indexes, domain=Boolean)
    def f(model):
        return sum([model.x[l, m] for l, m in model.x_indexes])
    model.objective = Objective(rule=f, sense=maximize)
    def f1(model, less_operator_index):
        return sum([model.x[l, m] for l, m in model.x_indexes if l == less_operator_index]) == 1
    model.choose_one = Constraint(model.choose_one_indexes, rule=f1)
    def f2(model, less_operator_index1, less_operator_index2, more_operator_index):
        return model.x[less_operator_index1, more_operator_index] + model.x[less_operator_index2, more_operator_index] == 1
    model.not_overlap = Constraint(model.not_overlap_indexes, rule=f2)
    opt = SolverFactory('glpk')
    results = opt.solve(model)
    if results.solver.termination_condition == TerminationCondition.infeasible:
        return False
    return True

def compute_subsumptions():
    subsumptions = dict()
    for care_unit_name in get_care_unit_names(): # for each care unit
        care_unit_subsumptions = dict()
        for more_day_name, more_day in operators.items(): # for each more day
            if len(more_day) == 0:
                continue
            less_day_names = set()
            more_total_duration = 0
            for more_operator in more_day[care_unit_name].values(): # write the input program
                more_total_duration += more_operator['duration'] # sum the operators' duration
            for less_day_name, less_day in operators.items(): # for each less day
                if more_day_name == less_day_name: # symmetric check
                    continue
                if len(less_day) == 0:
                    continue
                if less_day_name in less_day_names: # if already in the less list
                    continue
                less_total_duration = 0
                all_less_operators_are_satisfiable = True
                for less_operator in less_day[care_unit_name].values(): # write che input program
                    less_total_duration += less_operator['duration'] # sum the operators' duration
                    is_operator_satisfiable = False
                    for more_operator in more_day[care_unit_name].values(): # search at least one more operator that contains the less one
                        if more_operator['start'] <= less_operator['start'] and more_operator['start'] + more_operator['duration'] >= less_operator['start'] + less_operator['duration']:
                            is_operator_satisfiable = True
                            break
                    if not is_operator_satisfiable:
                        all_less_operators_are_satisfiable = False
                        break
                if less_total_duration > more_total_duration: # check for impossibility regarding the total durations
                    continue
                if not all_less_operators_are_satisfiable: # check for impossibility regarding operators satisfiability
                    continue
                if len(less_day[care_unit_name]) == 1:
                    less_day_names.add(less_day_name) # add the subsumption if a match exists
                    if less_day_name in care_unit_subsumptions: # relation transitivity check
                        less_day_names.update(care_unit_subsumptions[less_day_name])
                less_operator_list = list(less_day[care_unit_name].values())
                there_is_overlap = False
                for index1 in range(len(less_operator_list) - 1):
                    for index2 in range(index1 + 1, len(less_operator_list)):
                        if less_operator_list[index1]['start'] <= less_operator_list[index2]['start'] and less_operator_list[index1]['start'] + less_operator_list[index1]['duration'] > less_operator_list[index2]['start'] + less_operator_list[index2]['duration']:
                            there_is_overlap = True
                            break
                        if less_operator_list[index2]['start'] <= less_operator_list[index1]['start'] and less_operator_list[index2]['start'] + less_operator_list[index2]['duration'] > less_operator_list[index1]['start'] + less_operator_list[index1]['duration']:
                            there_is_overlap = True
                            break
                    if there_is_overlap:
                        break
                if not there_is_overlap or is_program_satisfiable(more_day[care_unit_name], less_day[care_unit_name]):
                    less_day_names.add(less_day_name) # add the subsumption if a match exists
                    if less_day_name in care_unit_subsumptions: # relation transitivity check
                        less_day_names.update(care_unit_subsumptions[less_day_name])
            if len(less_day_names) > 0:
                care_unit_subsumptions[more_day_name] = sorted(less_day_names)
        subsumptions[care_unit_name] = care_unit_subsumptions
    return subsumptions

subsumptions = compute_subsumptions()

# writing of the subsumptions file
with open(filenames['subsumptions']['output_file'], "w") as file:
    file.write(json.dumps(subsumptions, indent=4))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))