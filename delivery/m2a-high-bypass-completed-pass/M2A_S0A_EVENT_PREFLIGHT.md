# M2A-S0A Event/Tracking Preflight

Status: preliminary real-data preflight evidence. This report does not freeze M2A contracts.

## Key Counts

- Candidate completed pass events: 639
- Controlled pass status: `{'PASS': 593, 'UNKNOWN': 35, 'FAIL': 11}`
- Release control status: `{'PASS': 604, 'FAIL': 33, 'UNKNOWN': 2}`
- Reception control status: `{'PASS': 593, 'UNKNOWN': 35, 'FAIL': 11}`
- Failure reasons: `{'passer_not_in_control_near_event': 33, 'receiver_control_not_found_after_release': 11, 'event_timestamp_did_not_align_to_frame': 2}`

## Timing And Alignment

- Event-to-frame offset ms: `{'count': 637, 'min': -20.0, 'p50': 0.0, 'p90': 16.0, 'p95': 18.0, 'max': 19.0}`
- Physical release delta from event seconds: `{'count': 604, 'min': -1.0, 'p50': 1.08, 'p90': 2.12, 'p95': 2.32, 'max': 3.0}`
- Controlled reception delta from release seconds: `{'count': 593, 'min': 0.04, 'p50': 1.72, 'p90': 3.4, 'p95': 3.76, 'max': 5.16}`

## Physical Endpoint Distances

- Release ball distance m: `{'count': 604, 'min': 0.010000000000000009, 'p50': 0.4491102314577125, 'p90': 0.7186793443532389, 'p95': 0.7778174593052017, 'max': 2.129342621561876}`
- Reception ball distance m: `{'count': 593, 'min': 1.3827870407260832, 'p50': 2.3400000000000007, 'p90': 2.466617116619439, 'p95': 2.479233752593733, 'max': 2.4999599996799917}`

## Initial Interpretation

- IDSSE event timestamps align tightly to tracking frame timestamps, but they should not be treated as the physical pass release frame.
- The preflight searches for physical release control near the event and controlled receiver possession after release.
- S0C must still integrate active-player denominator proof and pure bypass measurement before runtime implementation begins.

## Sample PASS Records

- J03WOY firstHalf row 5 DFL-OBJ-002GM9->DFL-OBJ-0028FW event_frame=11319 release=11365 reception=11403 reason=None
- J03WOY firstHalf row 6 DFL-OBJ-0028FW->DFL-OBJ-002GMO event_frame=11392 release=11442 reception=11476 reason=None
- J03WOY firstHalf row 7 DFL-OBJ-002GMO->DFL-OBJ-0000NZ event_frame=11459 release=11508 reception=11530 reason=None
- J03WOY firstHalf row 8 DFL-OBJ-0000NZ->DFL-OBJ-002GMO event_frame=11511 release=11559 reception=11610 reason=None
- J03WOY firstHalf row 9 DFL-OBJ-002GMO->DFL-OBJ-0028FW event_frame=11568 release=11618 reception=11663 reason=None

## Sample FAIL Records

- J03WOY firstHalf row 18 DFL-OBJ-0028KZ->DFL-OBJ-0001IG event_frame=12418 release=12482 reception=None reason=receiver_control_not_found_after_release
- J03WOY firstHalf row 130 DFL-OBJ-J01KJ5->DFL-OBJ-00028V event_frame=28546 release=28617 reception=None reason=receiver_control_not_found_after_release
- J03WOY firstHalf row 114 DFL-OBJ-002FXA->DFL-OBJ-002GLL event_frame=35928 release=35942 reception=None reason=receiver_control_not_found_after_release
- J03WOY firstHalf row 118 DFL-OBJ-00019R->DFL-OBJ-J0196K event_frame=36740 release=36815 reception=None reason=receiver_control_not_found_after_release
- J03WOY firstHalf row 207 DFL-OBJ-0025BB->DFL-OBJ-0028KZ event_frame=52069 release=52124 reception=None reason=receiver_control_not_found_after_release

## Sample UNKNOWN Records

- J03WOY firstHalf row 0 DFL-OBJ-002FXA->DFL-OBJ-0025BB event_frame=None release=None reception=None reason=event_timestamp_did_not_align_to_frame
- J03WOY firstHalf row 16 DFL-OBJ-J0196K->DFL-OBJ-J01KGY event_frame=12362 release=None reception=None reason=passer_not_in_control_near_event
- J03WOY firstHalf row 17 DFL-OBJ-J01KGY->DFL-OBJ-0028KZ event_frame=12390 release=None reception=None reason=passer_not_in_control_near_event
- J03WOY firstHalf row 19 DFL-OBJ-0001IG->DFL-OBJ-0028KZ event_frame=12472 release=None reception=None reason=passer_not_in_control_near_event
- J03WOY firstHalf row 19 DFL-OBJ-J01KJ5->DFL-OBJ-002G5J event_frame=13002 release=None reception=None reason=passer_not_in_control_near_event
