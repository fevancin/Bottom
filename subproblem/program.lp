% patient_requests_packet(Patient, Packet).
% patient_has_priority(Patient, Priority).
% service(Service, CareUnit, ServiceDuration).
% packet_has_service(Packet, Service).
% operator(Operator, CareUnit, OperatorStart, OperatorDuration).
% time(1..T).

% variable for the assignment of services
{ do(Patient, Service, Operator, CareUnit, Time) } :-
    patient_requests_packet(Patient, Packet),                       % the patient must request a packet..
    packet_has_service(Packet, Service),                            % ..that contains a service..
    service(Service, CareUnit, ServiceDuration),                    % ..of the care unit..
    operator(Operator, CareUnit, OperatorStart, OperatorDuration),  % ..that is the same of the operator.
    ServiceDuration <= OperatorDuration,                            % service must be satisfiable.
    Time >= OperatorStart,                                          % the operator interval must be respected.
    Time + ServiceDuration <= OperatorStart + OperatorDuration,
    time(Time).

% a service cannot be satisfied more than once
:- patient_requests_packet(Patient, Packet), packet_has_service(Packet, Service),
    #count { Operator,CareUnit,Time : do(Patient, Service, Operator, CareUnit, Time) } > 1.

% the same patient cannot be in two places at the same time
:- do(Patient, Service1, _, _, Time1), do(Patient, Service2, _, _, Time2),
    Service1 != Service2,
    service(Service1, _, ServiceDuration1),
    Time1 <= Time2, Time1 + ServiceDuration1 > Time2.

% the same operator cannot satisfy two requests if they overlap in time
:- do(Patient1, Service1, Operator, CareUnit, Time1), do(Patient2, Service2, Operator, CareUnit, Time2),
    #count { p : Patient1 == Patient2 ; s : Service1 == Service2 } 1, % the patient or the service can be the same, but not both at the same time
    service(Service1, _, ServiceDuration1),
    Time1 <= Time2, Time1 + ServiceDuration1 > Time2.

% true if the entire packet is satisfied
{ packet_done(Patient, Packet) } :- patient_requests_packet(Patient, Packet).

% a packet must be satisfied in its entirety
:- packet_done(Patient, Packet), packet_has_service(Packet, Service), not do(Patient, Service, _, _, _).

% every service must be linked with at least one satisfied packets (no useless services)
:- do(Patient, Service, _, _, _), #count { Packet : packet_has_service(Packet, Service), packet_done(Patient, Packet) } = 0.

% try to maximize the number of packets done, weighted by the patient priority
:~ packet_done(Patient, Packet), patient_has_priority(Patient, Priority). [-10@Priority,Patient,Packet]

#show do/5.