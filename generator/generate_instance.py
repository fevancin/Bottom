import os
import json
import random
from datetime import datetime

if __name__ == "__main__":
    start_time = datetime.now()

# reading of the filenames file
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isfile("filenames.json"):
    raise FileNotFoundError("The filenames file was not found")
with open("filenames.json", "r") as file:
    filenames = json.loads(file.read())

# reading of the generator configuration file
os.chdir(filenames['generator']['folder'])
if not os.path.isfile(filenames['generator']['configuration']):
    raise FileNotFoundError("The configuration file for the generation process was not found")
with open(filenames['generator']['configuration'], "r") as file:
    configuration = json.loads(file.read())

prefixes = {
    'day': '',
    'care_unit': 'cu',
    'operator': 'op',
    'service': 'srv',
    'packet': 'pkt',
    'patient': 'pat',
    'protocol': 'prot',
    'iteration': 'iter'
}

random.seed(configuration['seed'])

# operators generation (day -> care_unit -> [start, duration])
def generate_operators():
    operators = dict()
    for day_index in range(configuration['day']['number']):
        day = dict()
        for care_unit_index in range(configuration['care_unit']['number']):
            care_unit = dict()
            care_unit_size = random.randint(configuration['care_unit']['size']['min'], configuration['care_unit']['size']['max'])
            for operator_index in range(care_unit_size):
                care_unit[f"{prefixes['operator']}{operator_index:02}"] = {
                    'start': random.randint(configuration['operator']['start']['min'], configuration['operator']['start']['max']),
                    'duration': random.randint(configuration['operator']['duration']['min'], configuration['operator']['duration']['max'])
                }
            day[f"{prefixes['care_unit']}{care_unit_index:02}"] = care_unit
        operators[f"{prefixes['day']}{day_index:02}"] = day
    return operators

# services generation
def generate_services():
    services = dict()
    for service_index in range(configuration['service']['number']):
        care_unit_index = random.randint(0, configuration['care_unit']['number'] - 1)
        services[f"{prefixes['service']}{service_index:02}"] = {
            'careUnit': f"{prefixes['care_unit']}{care_unit_index:02}",
            'duration': random.randint(configuration['service']['duration']['min'], configuration['service']['duration']['max']),
            'cost': random.randint(configuration['service']['cost']['min'], configuration['service']['cost']['max'])
        }
    return services

# packets generation
def generate_packets():
    packets = dict()
    packet_index = 0
    window = configuration['packet']['number'] // 2
    packet_size = configuration['packet']['size']['min']
    while packet_index < configuration['packet']['number']:
        if window == 0: window = 1
        for _ in range(window):
            service_indexes = random.sample(range(configuration['service']['number']), packet_size)
            packet = []
            for service_index in sorted(service_indexes):
                packet.append(f"{prefixes['service']}{service_index:02}")
            packets[f"{prefixes['packet']}{packet_index:02}"] = packet
            packet_index += 1
        window = window // 2
        if packet_size + 1 <= configuration['packet']['size']['max']:
            packet_size += 1
    return packets

# timestamp creation
def generate_timestamp():
    timestamp = datetime.now().strftime("%a-%d-%b-%Y-%H-%M-%S")
    return timestamp

# sum of operator durations for each day and care unit (day -> care_unit)
def generate_total_care_units_duration(operators):
    total_care_units_duration = dict()
    for day_name, day in operators.items():
        daily_total_care_units_duration = dict()
        for care_unit_name, care_unit in day.items():
            total_care_unit_duration = 0
            for operator in care_unit.values():
                total_care_unit_duration += operator['duration']
            daily_total_care_units_duration[care_unit_name] = total_care_unit_duration
        total_care_units_duration[day_name] = daily_total_care_units_duration
    return total_care_units_duration

# list of all care unit names
def generate_care_unit_names():
    care_unit_names = []
    for care_unit_index in range(configuration['care_unit']['number']):
        care_unit_names.append(f"{prefixes['care_unit']}{care_unit_index:02}")
    return care_unit_names

# incompatibility windows generation (service -> service)
def generate_interdictions():
    interdictions = dict()
    for service_index in range(configuration['service']['number']):
        service_interdictions = dict()
        for other_service_index in range(configuration['service']['number']):
            if service_index == other_service_index:
                continue
            if random.random() >= configuration['interdiction']['probability']:
                service_interdictions[f"{prefixes['service']}{other_service_index:02}"] = 0
                continue
            service_interdictions[f"{prefixes['service']}{other_service_index:02}"] = random.randint(configuration['interdiction']['duration']['min'], configuration['interdiction']['duration']['max'])
        interdictions[f"{prefixes['service']}{service_index:02}"] = service_interdictions
    return interdictions

# necessity windows generation (service -> service -> [start, duration])
def generate_necessities():
    necessities = dict()
    for service_index in range(configuration['service']['number']):
        if random.random() >= configuration['necessity']['probability']:
            necessities[f"{prefixes['service']}{service_index:02}"] = dict()
            continue
        necessity_size = random.randint(configuration['necessity']['size']['min'], configuration['necessity']['size']['max'])
        service_indexes = random.sample(range(configuration['service']['number']), necessity_size)
        service_necessities = dict()
        for other_service_index in sorted(service_indexes):
            if other_service_index == service_index:
                continue
            start = random.randint(configuration['necessity']['start']['min'], configuration['necessity']['start']['max'])
            duration = random.randint(configuration['necessity']['duration']['min'], configuration['necessity']['duration']['max'])
            service_necessities[f"{prefixes['service']}{other_service_index:02}"] = [
                start,
                start + duration
            ]
        necessities[f"{prefixes['service']}{service_index:02}"] = service_necessities
    return necessities

# patient's protocols generation
def generate_patients():
    patients = dict()
    protocol_index = 0
    for patient_index in range(configuration['patient']['number']):
        patient = dict()
        protocol_number = random.randint(configuration['patient']['protocol']['min'], configuration['patient']['protocol']['max'])
        for _ in range(protocol_number):
            protocol = dict()
            iteration = []
            packet_number = random.randint(configuration['iteration']['packet_size']['min'], configuration['iteration']['packet_size']['max'])
            packet_indexes = random.sample(range(configuration['packet']['number']), packet_number)
            for packet_index in sorted(packet_indexes):
                existence_start = random.randint(configuration['protocol_packet']['existence']['start']['min'], configuration['protocol_packet']['existence']['start']['max'])
                existence_duration = random.randint(configuration['protocol_packet']['existence']['duration']['min'], configuration['protocol_packet']['existence']['duration']['max'])
                iteration.append({
                    'packet_id': f"{prefixes['packet']}{packet_index:02}",
                    'start_date': random.randint(existence_start, existence_start + existence_duration),
                    'freq': random.randint(configuration['protocol_packet']['frequency']['min'], configuration['protocol_packet']['frequency']['max']),
                    'since': "start_date",
                    'tolerance': random.randint(configuration['protocol_packet']['tolerance']['min'], configuration['protocol_packet']['tolerance']['max']),
                    'existence': [
                        existence_start,
                        existence_start + existence_duration
                    ]
                })
            iteration_number = random.randint(configuration['iteration']['number']['min'], configuration['iteration']['number']['max'])
            for interation_index in range(iteration_number):
                initial_shift = random.randint(configuration['iteration']['initial_shift']['min'], configuration['iteration']['initial_shift']['max'])
                protocol[f"{prefixes['iteration']}{interation_index:02}"] = [
                    iteration,
                    initial_shift
                ]
            patient[f"{prefixes['protocol']}{protocol_index:02}"] = protocol
        patient['priority_weight'] = random.randint(configuration['patient']['priority']['min'], configuration['patient']['priority']['max'])
        patients[f"{prefixes['patient']}{patient_index:02}"] = patient
    return patients

# priorities generation
def generate_priorities(patients):
    priorities = dict()
    for patient_name, patient in patients.items():
        priorities[patient_name] = patient['priority_weight']
    return priorities

# full input generation
def generate_full_input(operators, services, packets, patients):
    timestamp = generate_timestamp()
    care_unit_names = generate_care_unit_names()
    total_care_units_duration = generate_total_care_units_duration(operators)
    interdictions = generate_interdictions()
    necessities = generate_necessities()
    full_input = {
        'datecode' : timestamp,
        'horizon': configuration['day']['number'],
        'resources': care_unit_names,
        'capacity' : total_care_units_duration,
        'daily_capacity' : operators,
        'services': services,
        'interdiction': interdictions,
        'necessity': necessities,
        'abstract_packet': packets,
        'pat_request': patients
    }
    return full_input

operators = generate_operators()
services = generate_services()
packets = generate_packets()
patients = generate_patients()
priorities = generate_priorities(patients)
full_input = generate_full_input(operators, services, packets, patients)

# moving or creation of the instance folder
if not os.path.isdir(os.path.join("..", filenames['instance']['folder'])):
    os.mkdir(os.path.join("..", filenames['instance']['folder']))
os.chdir(os.path.join("..", filenames['instance']['folder']))

# writing of the instance files
with open(filenames['instance']['operators'], "w") as file:
    file.write(json.dumps(operators, indent=4))
with open(filenames['instance']['services'], "w") as file:
    file.write(json.dumps(services, indent=4))
with open(filenames['instance']['packets'], "w") as file:
    file.write(json.dumps(packets, indent=4))
with open(filenames['instance']['priorities'], "w") as file:
    file.write(json.dumps(priorities, indent=4))
with open(filenames['instance']['full_input'], "w") as file:
    file.write(json.dumps(full_input, indent=4))

if __name__ == "__main__":
    end_time = datetime.now()
    print("Time elapsed: " + str(end_time - start_time))