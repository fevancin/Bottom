% patient_requests_protocol(Patient, Protocol, Iteration, Packet, StartDay, ExistenceStart, ExistenceEnd, Frequency, Tolerance).
% patient_has_priority(Patient, Priority).
% service(Service, CareUnit, Duration).
% packet_has_service(Packet, Service).
% care_unit_has_daily_capacity(CareUnit, Day, Capacity).
% service_is_incompatible_with(Service1, Service2, DayWindow).
% service_has_necessity_of(Service1, Service2, WindowStart, WindowEnd).
% day(0..N).

{ do(Patient, Packet, Day) } :-
    patient_requests_protocol(Patient, _, _, Packet, StartDay, ExistenceStart, ExistenceEnd, Frequency, Tolerance),
    day(Day), Day >= ExistenceStart, Day <= ExistenceEnd,
    (Day - StartDay + Tolerance) \ Frequency <= (Tolerance * 2).

protocol_window_done(Patient, Protocol, Iteration, 1..N, Packet) :-
    patient_requests_protocol(Patient, Protocol, Iteration, Packet, StartDay, ExistenceStart, ExistenceEnd, Frequency, _),
    N = (ExistenceEnd - StartDay + 1) / Frequency.

% protocol_iteration_packet_done(Patient, Protocol, Iteration, Packet) :-
%     patient_requests_protocol(Patient, Protocol, Iteration, Packet, StartDay, ExistenceStart, ExistenceEnd, Frequency, Tolerance),

% :- care_unit_has_daily_capacity(CareUnit, Day, Capacity),
%     #sum { Duration,Patient,Service :
%         do(Patient, Packet, Day),
%         packet_has_service(Packet, Service),
%         service(Service, CareUnit, Duration) } > Capacity.

% :- do(Patient, Packet1, Day1), do(Patient, Packet2, Day2),
%     packet_has_service(Packet1, Service1), packet_has_service(Packet2, Service2),
%     service_is_incompatible_with(Service1, Service2, DayWindow),
%     Day2 - Day1 < DayWindow.

% :- do(Patient, Packet1, Day1), not do(Patient, Packet2, Day2), day(Day2),
%     packet_has_service(Packet1, Service1), packet_has_service(Packet2, Service2),
%     service_has_necessity_of(Service1, Service2, WindowStart, WindowEnd),
%     % Day2 >= Day1, maybe implied by the next two..
%     Day2 - Day1 >= WindowStart, Day2 - Day1 <= WindowEnd.

:~ do(Patient, Packet, Day), patient_has_priority(Patient, Priority). [-1@Priority,Patient,Packet,Day]

#show do/3.