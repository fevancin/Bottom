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

results = dict()

for day_name, daily_requests in requests.items():
    if len(daily_requests) == 0:
        continue
    
    # accumulators for each necessary name (no useless info in the input ASP file)
    patient_names = set()
    service_names = set()
    packet_names = set()
    care_unit_names = set()

    with open(filenames['subproblem']['ASP_input_program'], "w") as file:
        for patient_name, patient in daily_requests.items():
            patient_names.add(patient_name)
            for packet_name in patient['packets']:
                packet_names.add(packet_name)
                for service_name in packets[packet_name]:
                    service_names.add(service_name)
                    care_unit_names.add(services[service_name]['careUnit'])
                file.write(f"patient_requests_packet({patient_name}, {packet_name}).\n")

    patient_names = sorted(patient_names)
    service_names = sorted(service_names)
    packet_names = sorted(packet_names)
    care_unit_names = sorted(care_unit_names)

    with open(filenames['subproblem']['ASP_input_program'], "a") as file:
        for patient_name in patient_names:
            file.write(f"patient_has_priority({patient_name}, {priorities[patient_name]}).\n")

    with open(filenames['subproblem']['ASP_input_program'], "a") as file:
        for service_name in service_names:
            file.write(f"service({service_name}, {services[service_name]['careUnit']}, {services[service_name]['duration']}).\n")

    with open(filenames['subproblem']['ASP_input_program'], "a") as file:
        for packet_name in packet_names:
            for service_name in packets[packet_name]:
                file.write(f"packet_has_service({packet_name}, {service_name}).\n")

    max_time = 0

    with open(filenames['subproblem']['ASP_input_program'], "a") as file:
        for care_unit_name in care_unit_names:
            for operator_name, operator in operators[day_name][care_unit_name].items():
                if operator['start'] + operator['duration'] > max_time:
                    max_time = operator['start'] + operator['duration']
                file.write(f"operator({operator_name}, {care_unit_name}, {operator['start']}, {operator['duration']}).\n")

    with open(filenames['subproblem']['ASP_input_program'], "a") as file:
        file.write(f"time(0..{max_time}).\n")

    # solve subproblem problem
    with open(filenames['subproblem']['ASP_output_program'], "w") as file:
        subprocess.run(["clingo", filenames['subproblem']['ASP_input_program'], filenames['subproblem']['ASP_program'], "--time-limit=1"], stdout=file, stderr=subprocess.DEVNULL)

    # decoding solver answer
    daily_scheduled_services = []
    with open(filenames['subproblem']['ASP_output_program'], "r") as file:
        rows = file.read().split("Answer")[-1].split("\n")[1].split("do(")[1:]
        if len(rows) > 0:
            rows[-1] += " "
            for row in rows:
                tokens = row.split(",")
                tokens[4] = tokens[4][:-2]
                daily_scheduled_services.append({
                    'patient': tokens[0],
                    'service': tokens[1],
                    'operator': tokens[2],
                    'care_unit': tokens[3],
                    'start': int(tokens[4])
                })

    # list all not satisfied packets
    not_scheduled_packets = dict()
    for patient_name, patient in daily_requests.items():
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

# removing of temporary files
if os.path.isfile(filenames['subproblem']['ASP_input_program']):
    os.remove(filenames['subproblem']['ASP_input_program'])
if os.path.isfile(filenames['subproblem']['ASP_output_program']):
    os.remove(filenames['subproblem']['ASP_output_program'])

# writing of the results file
with open(filenames['subproblem']['output_file'], "w") as file:
    file.write(json.dumps(results, indent=4))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))