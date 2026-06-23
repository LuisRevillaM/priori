# M2A-S1C High-Bypass Completed Pass Verification

Decision: **PASS**

Runtime artifact hash: `832803de7c3efb6df955950793c95615477d7aea688c2f10c74a7debddd80278`

## Upstream Hashes

- S0 contract: `ffa4c63bd127eb9ba232e6666bafc8e96c7a371f347d8fe6cac05d7466119ef7`
- S1A controlled-pass artifact: `fff166b583eb55fb349bdace6283ad6bf72f035d96bf684e21f32209889e8ea4`
- S1B pass-bypass artifact: `edfbeae2957622eca06cf89a4e4a1a0ceb89395a826964483c7c511e9d484b6c`

## Checks

- `runtime_schema`: **PASS** - m2a.high_bypass_completed_pass.v1
- `real_results_emitted`: **PASS** - 7 results
- `expected_positive_pass_episodes`: **PASS** - ['J03WOY:firstHalf:home:188:DFL-OBJ-002G5J:DFL-OBJ-002FXT', 'J03WOY:firstHalf:away:227:DFL-OBJ-00286X:DFL-OBJ-00019R', 'J03WOY:firstHalf:home:331:DFL-OBJ-0028FW:DFL-OBJ-002FXT', 'J03WOY:secondHalf:home:102:DFL-OBJ-002GM9:DFL-OBJ-002FXT', 'J03WOY:secondHalf:away:172:DFL-OBJ-002FZB:DFL-OBJ-0028IJ', 'J03WOY:secondHalf:home:356:DFL-OBJ-002GMO:DFL-OBJ-0026RH', 'J03WOY:secondHalf:away:385:DFL-OBJ-0025BB:DFL-OBJ-0001IG']
- `query_result_shape`: **PASS** - all rows expose QueryResult-shaped fields
- `classification_label`: **PASS** - ['HIGH_BYPASS_COMPLETED_PASS']
- `requested_evidence_complete`: **PASS** - failure_count=0
- `predicate_traces_attached`: **PASS** - results=7 traces=21
- `thresholds_applied_in_recipe_layer`: **PASS** - all emitted rows satisfy S1C thresholds
- `opponent_denominator_complete_for_positive_results`: **PASS** - all positives have 10 expected/evaluated defending outfield players
- `deterministic_result_identity`: **PASS** - ['m2a_result_bdb8bdcbf0afed49', 'm2a_result_2a739a63cd8e3dca', 'm2a_result_67c2413aebc7ea4a', 'm2a_result_a6e16da7547a65ce', 'm2a_result_f7c4ebc8eb308e1a', 'm2a_result_c8c93428d9aad271', 'm2a_result_4e905f64ee6f35c2']
- `threshold_mutation_changes_inclusion`: **PASS** - minimum_bypassed_opponents=8 produced 0 results
- `scope_boundaries_preserved`: **PASS** - {'match_ids': ['J03WOY'], 'periods': ['firstHalf', 'secondHalf'], 'all_corpus_execution': 'blocked_until_m2a_active_player_policy_extends_beyond_j03woy', 'hermes_exposure': 'blocked_until_human_visual_review_accepts_m2a'}

## Runtime Summary

- Result count: 7
- Classification counts: `{'HIGH_BYPASS_COMPLETED_PASS': 7}`
- Non-match reason counts: `{'controlled_pass_not_proven': 186, 'forward_progression_below_threshold': 371, 'opponents_bypassed_below_threshold': 75}`
- Requested evidence failure count: 0
- Predicate trace count: 21

## Boundary

- This emits `high_bypass_completed_pass_v1` QueryResult-shaped rows for the J03WOY accepted scope only.
- It does not expose M2A to Hermes.
- It does not run the all-corpus path.
- Replay UI integration and human visual review remain future slices.

## Sample Results

- m2a_result_bdb8bdcbf0afed49 J03WOY firstHalf row=188 DFL-OBJ-002G5J->DFL-OBJ-002FXT progression=22.6m bypassed=7
- m2a_result_2a739a63cd8e3dca J03WOY firstHalf row=227 DFL-OBJ-00286X->DFL-OBJ-00019R progression=37.410000000000004m bypassed=6
- m2a_result_67c2413aebc7ea4a J03WOY firstHalf row=331 DFL-OBJ-0028FW->DFL-OBJ-002FXT progression=45.92m bypassed=6
- m2a_result_a6e16da7547a65ce J03WOY secondHalf row=102 DFL-OBJ-002GM9->DFL-OBJ-002FXT progression=24.49m bypassed=5
- m2a_result_f7c4ebc8eb308e1a J03WOY secondHalf row=172 DFL-OBJ-002FZB->DFL-OBJ-0028IJ progression=46.019999999999996m bypassed=5

## Sample Non-Matches

- J03WOY firstHalf row=0 status=UNKNOWN reason=controlled_pass_not_proven
- J03WOY firstHalf row=115 status=UNKNOWN reason=controlled_pass_not_proven
- J03WOY firstHalf row=140 status=UNKNOWN reason=controlled_pass_not_proven
- J03WOY firstHalf row=16 status=UNKNOWN reason=controlled_pass_not_proven
- J03WOY firstHalf row=17 status=UNKNOWN reason=controlled_pass_not_proven
