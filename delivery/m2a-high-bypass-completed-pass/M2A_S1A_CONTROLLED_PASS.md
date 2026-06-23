# M2A-S1A Controlled Pass Runtime Verification

Decision: **PASS**

S0 contract SHA-256: `ffa4c63bd127eb9ba232e6666bafc8e96c7a371f347d8fe6cac05d7466119ef7`
Runtime artifact hash: `fff166b583eb55fb349bdace6283ad6bf72f035d96bf684e21f32209889e8ea4`

## Checks

- `s0_contract_allows_s1`: **PASS** - PROCEED_TO_S1
- `runtime_schema`: **PASS** - m2a.controlled_pass_episode.v1
- `episodes_exist`: **PASS** - 453 PASS episodes
- `anchor_evaluations_cover_events`: **PASS** - evaluations=639 candidates=639
- `required_fields_present`: **PASS** - anchor_id,controlled_pass_status,controlled_reception_frame_id,controlled_reception_status,evaluation_status,event_anchor_frame_id,event_to_release_offset_ms,forward_progression_m,pass_episode_id,passer_id,physical_release_frame_id,possession_continuity_status,receiver_id,release_control_status,release_detection_reason,release_detection_status
- `event_anchor_not_collapsed_to_physical_release`: **PASS** - at least one PASS row has distinct event_anchor_frame_id and physical_release_frame_id
- `non_pass_rows_have_reasons`: **PASS** - 186 non-PASS rows

## Runtime Summary

- Candidate events: 639
- PASS episodes: 453
- Controlled pass status counts: `{'FAIL': 135, 'PASS': 453, 'UNKNOWN': 51}`
- Release detection status counts: `{'FAIL': 33, 'PASS': 555, 'UNKNOWN': 51}`
- Reception status counts: `{'FAIL': 102, 'PASS': 453, 'UNKNOWN': 84}`
- Reason counts: `{'another_player_controlled_first': 35, 'missing_tracking': 2, 'possession_definitively_broke': 67, 'release_contradicted': 33, 'release_not_confirmed': 84, 'unique_release_transition_not_found': 49}`
- Event-to-release offset ms: `{'count': 555, 'min': -1000.0, 'p50': 1880.0, 'p90': 2600.0, 'p95': 2760.0, 'max': 2880.0}`
- Release-to-reception seconds: `{'count': 453, 'min': 0.04, 'p50': 0.84, 'p90': 1.76, 'p95': 2.16, 'max': 3.16}`
- Forward progression m: `{'count': 453, 'min': -25.06, 'p50': 0.5300000000000011, 'p90': 11.01, 'p95': 15.36, 'max': 46.019999999999996}`

## Boundary

- This verifies `controlled_pass_episode` only.
- It does not wire `opponents_bypassed_by_action` to real pass episodes.
- It does not emit `high_bypass_completed_pass_v1` results.
- It remains scoped to the S0C accepted match `J03WOY`.
- Hermes exposure and all-corpus execution remain blocked.

## Sample PASS Episodes

- J03WOY firstHalf row 5 DFL-OBJ-002GM9->DFL-OBJ-0028FW anchor=11319 release=11367 reception=11403 progression=-12.779999999999998
- J03WOY firstHalf row 6 DFL-OBJ-0028FW->DFL-OBJ-002GMO anchor=11392 release=11445 reception=11476 progression=7.940000000000005
- J03WOY firstHalf row 7 DFL-OBJ-002GMO->DFL-OBJ-0000NZ anchor=11459 release=11512 reception=11530 progression=8.489999999999998
- J03WOY firstHalf row 8 DFL-OBJ-0000NZ->DFL-OBJ-002GMO anchor=11511 release=11579 reception=11610 progression=-11.68
- J03WOY firstHalf row 9 DFL-OBJ-002GMO->DFL-OBJ-0028FW anchor=11568 release=11622 reception=11663 progression=-6.530000000000001

## Sample Non-PASS Evaluations

- J03WOY firstHalf row 0 status=UNKNOWN release_reason=missing_tracking reception_reason=release_not_confirmed
- J03WOY firstHalf row 16 status=FAIL release_reason=release_not_confirmed reception_reason=release_contradicted
- J03WOY firstHalf row 17 status=FAIL release_reason=release_not_confirmed reception_reason=release_contradicted
- J03WOY firstHalf row 19 status=FAIL release_reason=release_not_confirmed reception_reason=release_contradicted
- J03WOY firstHalf row 19 status=FAIL release_reason=release_not_confirmed reception_reason=release_contradicted