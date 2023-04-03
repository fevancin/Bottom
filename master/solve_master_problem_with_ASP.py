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

# accumulators for each necessary name (no useless info in the input ASP file)
patient_names = set()
service_names = set()
packet_names = set()
care_unit_names = set()

with open(filenames['master']['ASP_input_program'], "w") as file:
    for patient_name, patient in full_input['pat_request'].items():
        patient_names.add(patient_name)
        for protocol_name, protocol in patient.items():
            if protocol_name == "priority_weight":
                continue
            for iteration_name, iteration in protocol.items():
                initial_offset = iteration[1]
                for protocol_packet in iteration[0]:
                    packet_name = protocol_packet['packet_id']
                    packet_names.add(packet_name)
                    for service_name in full_input['abstract_packet'][packet_name]:
                        service_names.add(service_name)
                        care_unit_names.add(full_input['services'][service_name]['careUnit'])
                    file.write(f"patient_requests_protocol({patient_name}, {protocol_name}, {iteration_name}, {packet_name}, {protocol_packet['start_date'] + initial_offset}, {protocol_packet['existence'][0] + initial_offset}, {protocol_packet['existence'][1] + initial_offset}, {protocol_packet['freq']}, {protocol_packet['tolerance']}).\n")

patient_names = sorted(patient_names)
service_names = sorted(service_names)
packet_names = sorted(packet_names)
care_unit_names = sorted(care_unit_names)

with open(filenames['master']['ASP_input_program'], "a") as file:
    for patient_name in patient_names:
        file.write(f"patient_has_priority({patient_name}, {full_input['pat_request'][patient_name]['priority_weight']}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    for service_name in service_names:
        file.write(f"service({service_name}, {full_input['services'][service_name]['careUnit']}, {full_input['services'][service_name]['duration']}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    for packet_name in packet_names:
        for service_name in full_input['abstract_packet'][packet_name]:
            file.write(f"packet_has_service({packet_name}, {service_name}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    for day_name, day in full_input['capacity'].items():
        for care_unit_name in care_unit_names:
            file.write(f"care_unit_has_daily_capacity({care_unit_name}, {int(day_name)}, {day[care_unit_name]}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    for service_name in service_names:
        for other_service_name, duration in full_input['interdiction'][service_name].items():
            if duration == 0 or other_service_name not in service_names:
                continue
            file.write(f"service_is_incompatible_with({service_name}, {other_service_name}, {duration}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    for service_name in service_names:
        for other_service_name, window in full_input['necessity'][service_name].items():
            file.write(f"service_has_necessity_of({service_name}, {other_service_name}, {window[0]}, {window[1]}).\n")

with open(filenames['master']['ASP_input_program'], "a") as file:
    file.write(f"day(0..{full_input['horizon']}).\n")

# solve master problem
with open(filenames['master']['ASP_output_program'], "w") as file:
    subprocess.run(["clingo", filenames['master']['ASP_input_program'], filenames['master']['ASP_program']], stdout=file, stderr=subprocess.DEVNULL)

requests = dict()

# decoding solver answer
with open(filenames['master']['ASP_output_program'], "r") as file:
    rows = file.read().split("Answer")[-1].split("\n")[1].split("do(")[1:]
    rows[-1] += " "
    for row in rows:
        tokens = row.split(",")
        tokens[2] = tokens[2][:-2]
        day_name = f"{int(tokens[2]):02}"
        if day_name not in requests:
            requests[day_name] = dict()
        if tokens[0] not in requests[day_name]:
            requests[day_name][tokens[0]] = []
        requests[day_name][tokens[0]].append(tokens[1])

# removing of temporary files
# if os.path.isfile(filenames['master']['ASP_input_program']):
#     os.remove(filenames['master']['ASP_input_program'])
# if os.path.isfile(filenames['master']['ASP_output_program']):
#     os.remove(filenames['master']['ASP_output_program'])

# TEMPORARY CODE _______________________________________________________________
# import random
# random.seed(42)

# requests = dict()
# packet_names = []
# for packet_name in full_input['abstract_packet'].keys():
#     packet_names.append(packet_name)
# patient_names = []
# for patient_name in full_input['pat_request'].keys():
#     patient_names.append(patient_name)
# for day_name in full_input['daily_capacity'].keys():
#     daily_requests = dict()
#     patient_number = random.randint(1, 5)
#     for patient_index in range(patient_number):
#         packet_number = random.randint(1, 2)
#         daily_requests[patient_names[patient_index]] = {
#             'packets': random.sample(packet_names, packet_number)
#         }
#         daily_requests[patient_names[patient_index]]['packets'].sort()
#     requests[day_name] = daily_requests
# END OF TEMPORARY CODE ________________________________________________________

# writing of the requests file
with open(filenames['master']['output_file'], "w") as file:
    file.write(json.dumps(requests, indent=4, sort_keys=True))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))