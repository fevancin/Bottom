% less(Less, LessStart, LessDuration).
% more(More, MoreStart, MoreDuration).

% choose variables for each Less operator contained in More
{ choose(Less, More) } :-
    less(Less, LessStart, LessDuration),
    more(More, MoreStart, MoreDuration),
    LessStart >= MoreStart,
    LessStart + LessDuration <= MoreStart + MoreDuration.

% every Less operator must choose exactly one More
:- #count { More : choose(Less, More) } != 1, less(Less, _, _).

% it's impossible that two Less choose the same More if they overlap
:- choose(Less1, More), choose(Less2, More), Less1 != Less2,
    less(Less1, LessStart1, LessDuration1),
    less(Less2, LessStart2, _),
    LessStart1 <= LessStart2,
    LessStart1 + LessDuration1 > LessStart2.

#show choose/2.