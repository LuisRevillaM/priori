# M2A-S0B Active-Player Timeline Preflight

Status: preliminary active-player denominator evidence. This report does not freeze M2A contracts.

## Summary

- Tracked player intervals: 368
- Active-set change markers: 736
- Frame/team count deviations from 11 players: 183934
- Stored deviation samples: 100
- Unknown tracked-player metadata IDs: `[]`
- Substitution event rows, duplicates included: 128

## Pass Window Impact

- Status: `PASS`
- Controlled pass windows checked: 593
- Windows with active-set change: 0
- Windows with empty/unusable defending outfield denominator: 0

## Policy Implication

- The expected opposition denominator should be the active defending outfield set at release and reception.
- Full roster counts must not be used as expected evidence.
- A reduced active outfield denominator can be valid after a dismissal; S0C must distinguish dismissals from tracking gaps before freezing accepted match windows.
- If the active set changes inside a pass window, the pass/bypass coverage should become UNKNOWN.
- If goalkeeper metadata is missing, the affected denominator is UNKNOWN.

## Sample Period Summaries

- J03WMX firstHalf home: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WMX firstHalf away: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WMX secondHalf home: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WMX secondHalf away: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WN1 firstHalf home: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WN1 firstHalf away: unique=11 start=11 end=10 outfield_start=10 outfield_end=9 intervals=11
- J03WN1 secondHalf home: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WN1 secondHalf away: unique=12 start=10 end=10 outfield_start=9 outfield_end=9 intervals=12
- J03WOH firstHalf home: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WOH firstHalf away: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WOH secondHalf home: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WOH secondHalf away: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WOY firstHalf home: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WOY firstHalf away: unique=12 start=11 end=11 outfield_start=10 outfield_end=10 intervals=12
- J03WOY secondHalf home: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16
- J03WOY secondHalf away: unique=14 start=11 end=11 outfield_start=10 outfield_end=10 intervals=14
- J03WPY firstHalf home: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WPY firstHalf away: unique=11 start=11 end=11 outfield_start=10 outfield_end=10 intervals=11
- J03WPY secondHalf home: unique=15 start=11 end=11 outfield_start=10 outfield_end=10 intervals=15
- J03WPY secondHalf away: unique=16 start=11 end=11 outfield_start=10 outfield_end=10 intervals=16

## Active-Set Change Samples

- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0000IA
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0000IA
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0002AU
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0002AU
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0002DR
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0002DR
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0002F5
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0002F5
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0026PM
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0026PM
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0027G0
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0027G0
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0027G6
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0027G6
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-0027KL
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-0027KL
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-J017RE
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-J017RE
- J03WMX firstHalf away frame=10000 IN DFL-OBJ-J01APO
- J03WMX firstHalf away frame=80708 OUT DFL-OBJ-J01APO

## Incomplete Period/Role Samples

- J03WN1 firstHalf away: start=11 end=10 outfield_start=10 outfield_end=9
- J03WN1 secondHalf away: start=10 end=10 outfield_start=9 outfield_end=9
- J03WQQ secondHalf away: start=11 end=10 outfield_start=10 outfield_end=9

## Frame Count Deviation Samples

- J03WN1 firstHalf away frame=20616 active_players=10
- J03WN1 firstHalf away frame=20617 active_players=10
- J03WN1 firstHalf away frame=20618 active_players=10
- J03WN1 firstHalf away frame=20619 active_players=10
- J03WN1 firstHalf away frame=20620 active_players=10
- J03WN1 firstHalf away frame=20621 active_players=10
- J03WN1 firstHalf away frame=20622 active_players=10
- J03WN1 firstHalf away frame=20623 active_players=10
- J03WN1 firstHalf away frame=20624 active_players=10
- J03WN1 firstHalf away frame=20625 active_players=10
- J03WN1 firstHalf away frame=20626 active_players=10
- J03WN1 firstHalf away frame=20627 active_players=10
- J03WN1 firstHalf away frame=20628 active_players=10
- J03WN1 firstHalf away frame=20629 active_players=10
- J03WN1 firstHalf away frame=20630 active_players=10
- J03WN1 firstHalf away frame=20631 active_players=10
- J03WN1 firstHalf away frame=20632 active_players=10
- J03WN1 firstHalf away frame=20633 active_players=10
- J03WN1 firstHalf away frame=20634 active_players=10
- J03WN1 firstHalf away frame=20635 active_players=10

## Pass Window Change Samples

- none