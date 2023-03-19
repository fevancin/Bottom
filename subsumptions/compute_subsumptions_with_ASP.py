import os
import json
from datetime import datetime
import subprocess

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

# true if it exists a match
def is_program_satisfiable(input_program):
    with open(filenames['subsumptions']['ASP_input_program'], "w") as file:
        file.write(input_program)
    with open(filenames['subsumptions']['ASP_output_program'], "w") as file:
        subprocess.run(["clingo", filenames['subsumptions']['ASP_input_program'], filenames['subsumptions']['ASP_program']], stdout=file, stderr=subprocess.DEVNULL)
    with open(filenames['subsumptions']['ASP_output_program'], "r") as file:
        if "UNSATISFIABLE" not in file.read():
            return True
    return False

def compute_subsumptions():
    subsumptions = dict()
    for care_unit_name in get_care_unit_names(): # for each care unit
        care_unit_subsumptions = dict()
        for more_day_name, more_day in operators.items(): # for each more day
            less_day_names = set()
            more_total_duration = 0
            more_program = ""
            for more_operator_name, more_operator in more_day[care_unit_name].items(): # write the input program
                more_program += f"more({more_operator_name}, {more_operator['start']}, {more_operator['duration']}).\n"
                more_total_duration += more_operator['duration'] # sum the operators' duration
            for less_day_name, less_day in operators.items(): # for each less day
                if more_day_name == less_day_name: # symmetric check
                    continue
                if less_day_name in less_day_names: # if already in the less list
                    continue
                less_total_duration = 0
                input_program = more_program
                all_less_operators_are_satisfiable = True
                for less_operator_name, less_operator in less_day[care_unit_name].items(): # write che input program
                    input_program += f"less({less_operator_name}, {less_operator['start']}, {less_operator['duration']}).\n"
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
                if len(less_day[care_unit_name]) == 1 or is_program_satisfiable(input_program):
                    less_day_names.add(less_day_name) # add the subsumption if a match exists
                    if less_day_name in care_unit_subsumptions: # relation transitivity check
                        less_day_names.update(care_unit_subsumptions[less_day_name])
            if len(less_day_names) > 0:
                care_unit_subsumptions[more_day_name] = sorted(less_day_names)
        subsumptions[care_unit_name] = care_unit_subsumptions
    # removing of temporary working files
    if os.path.isfile(filenames['subsumptions']['ASP_input_program']):
        os.remove(filenames['subsumptions']['ASP_input_program'])
    if os.path.isfile(filenames['subsumptions']['ASP_output_program']):
        os.remove(filenames['subsumptions']['ASP_output_program'])
    return subsumptions

subsumptions = compute_subsumptions()

# writing of the subsumptions file
with open(filenames['subsumptions']['output_file'], "w") as file:
    file.write(json.dumps(subsumptions, indent=4))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))