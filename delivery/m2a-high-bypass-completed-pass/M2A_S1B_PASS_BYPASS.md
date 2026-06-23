# M2A-S1B Pass Bypass Measurement Verification

Decision: **PASS**

Runtime artifact hash: `edfbeae2957622eca06cf89a4e4a1a0ceb89395a826964483c7c511e9d484b6c`

## Checks

- `runtime_schema`: **PASS** - m2a.opponents_bypassed_by_action.v1
- `anchor_count_matches_controlled_pass_source`: **PASS** - controlled=639 bypass=639
- `complete_measurements_exist`: **PASS** - 453 complete measurements
- `required_fields_present`: **PASS** - anchor_id,bypassed_player_ids,candidate_goal_side_ids,controlled_reception_frame_id,coverage_status,evaluated_opponent_ids,evaluation_status,event_anchor_frame_id,expected_active_opponent_ids,failure_reason,match_id,missing_active_opponent_ids,opponents_bypassed_count,pass_episode_id,period,physical_release_frame_id
- `defending_outfield_denominator_is_complete`: **PASS** - all complete measurements have 10 expected/evaluated defending outfield players
- `unknown_rows_have_reasons`: **PASS** - 186 UNKNOWN rows
- `measurement_has_future_recipe_headroom_without_classifying`: **PASS** - max measured opponents_bypassed_count=7

## Runtime Summary

- Controlled anchor evaluations: 639
- Bypass anchor evaluations: 639
- Evaluation status counts: `{'PASS': 453, 'UNKNOWN': 186}`
- Coverage status counts: `{'COMPLETE': 453, 'UNKNOWN': 186}`
- Failure reason counts: `{'controlled_pass_not_proven': 186}`
- Opponents bypassed distribution: `{'0': 360, '1': 41, '2': 25, '3': 16, '4': 4, '5': 3, '6': 3, '7': 1}`
- Max measured opponents bypassed: 7

## Boundary

- This verifies `opponents_bypassed_by_action` measurement wiring only.
- It does not emit `high_bypass_completed_pass_v1` QueryResult rows.
- Raw `opponents_bypassed_count` values remain measurement evidence for the next recipe gate.
- Hermes exposure and all-corpus execution remain blocked.

## Sample Largest Bypass Measurements

- J03WOY firstHalf row 188 DFL-OBJ-002G5J->DFL-OBJ-002FXT count=7 bypassed=['DFL-OBJ-00019R', 'DFL-OBJ-0001IG', 'DFL-OBJ-0026ZT', 'DFL-OBJ-00286X', 'DFL-OBJ-002FXA', 'DFL-OBJ-002GLL', 'DFL-OBJ-J01KGY']

## Sample UNKNOWN Measurements

- J03WOY firstHalf row 0 reason=controlled_pass_not_proven
- J03WOY firstHalf row 16 reason=controlled_pass_not_proven
- J03WOY firstHalf row 17 reason=controlled_pass_not_proven
- J03WOY firstHalf row 19 reason=controlled_pass_not_proven
- J03WOY firstHalf row 19 reason=controlled_pass_not_proven
