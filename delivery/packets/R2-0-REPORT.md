# R2-0 Report

Branch: `packet/r2-0` from frontier `codex/afl08-passport-loop` at
`aad394d`.

## Progress Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Seven pre-era declarations | DONE_WITH_ROUND_2_FIXES | `config/compiler-reachability/search-targets.v0.json`; appendix below |
| Loads-well-formed test | DONE_WITH_ROUND_2_FIXES | `tests/test_r1_c_checkpoint.py::R1CCheckpointTests.test_committed_target_declarations_are_well_formed` |
| Mutation verification | DONE_WITH_ROUND_2_FIXES | Scratch-copy direct-loader mutation failed as expected; clean rerun passed |
| Full committed-tree suite | PENDING_ROUND_2 | Round-2 `make test` pending |

Fences observed so far: no sweep run, no ledger update, no sealed evidence
edits, no freeze, no re-pin.

## Scope

The seven pre-era compiler-reachable targets enumerated from
`delivery/packets/r1-c-sweep/row-ledger.json` are now declared in
`config/compiler-reachability/search-targets.v0.json`:

| Target | Coverage row |
| --- | --- |
| `search_heldout_carry_displacement_v0` | `carry_displacement` |
| `search_heldout_support_arrival_v0` | `support_arrival_relation` |
| `search_carry_progression_v0` | `carry_progression` |
| `search_direct_pressure_candidate_v0` | `direct_pressure_candidate` |
| `search_post_regain_retention_v0` | `post_regain_retention` |
| `search_heldout_shape_expansion_v0` | `shape_expansion_episode` |
| `search_carry_out_of_pressure_v0` | `carry_out_of_pressure` |

Plan citation convention: all citations below are JSON paths under the named
certified plan bundle in `delivery/packets/r1-c-sweep/plans/`. For each of the
seven bundles, `.documents.home.draft_plan == .documents.away.draft_plan`
was verified; the `home` paths are cited to avoid duplicate path text.

Verification command:

```bash
jq -r '.target_id + " " + ((.documents.home.draft_plan == .documents.away.draft_plan)|tostring)' \
  delivery/packets/r1-c-sweep/plans/search_heldout_carry_displacement_v0.json \
  delivery/packets/r1-c-sweep/plans/search_heldout_support_arrival_v0.json \
  delivery/packets/r1-c-sweep/plans/search_carry_progression_v0.json \
  delivery/packets/r1-c-sweep/plans/search_direct_pressure_candidate_v0.json \
  delivery/packets/r1-c-sweep/plans/search_post_regain_retention_v0.json \
  delivery/packets/r1-c-sweep/plans/search_heldout_shape_expansion_v0.json \
  delivery/packets/r1-c-sweep/plans/search_carry_out_of_pressure_v0.json
```

Result: all seven returned `true`.

## Round 2 Fix List

| Review item | Status | Evidence |
| --- | --- | --- |
| F1 | DONE | Declaration target files are discovered by `config/compiler-reachability/*.json` glob plus `delivery/packets/r1-c-sweep/targets.v0.json`; payloads without `targets` are skipped. |
| F2 | DONE | Removed the production-path environment override; mutation uses `declared_targets_from_files([scratch_path])` directly. |
| F3 | DONE | `anchor_source` now names upstream anchor inputs consistently; result anchors use `result_anchor` or are described as result relations. |
| F4 partial | DONE | `post_regain_retention` declaration includes `minimum_prior_possession_seconds: 0.4`. |
| F5 | DONE | `post_regain_retention` declaration states the settled segment may begin anywhere in the 8.0-second window. |
| F6 | DONE | Appendix wording no longer uses overbroad identity phrasing. |
| Full-suite table | PENDING | Round-2 committed-tree run pending. |

## Declaration Verification Appendix

### `search_heldout_carry_displacement_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_heldout_carry_displacement_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: carry_displacement` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: carry episode with observed control | `.documents.home.draft_plan.nodes[node_id=carry_episode]`; `.documents.home.draft_plan.requested_evidence[alias=carry_status]`; predicate `predicate_1` on `carry_status == PASS` | The certified plan anchors the result on `carry_episode` and requires `carry_status` PASS. |
| Displacement between carry start/end frames | Requested evidence aliases `carry_start_frame_id`, `carry_end_frame_id`, `displacement_m` from `carry_episode` | The plan emits the frame witnesses and displacement scalar from the carry episode. |
| Threshold `displacement_m >= 3.0` | `nodes[node_id=predicate_2].input.output_name=displacement_m`; `predicate_2.compare.value=3.0`; `predicate_2.compare.unit=metre` | The classification requires the observed displacement scalar to be at least 3 metres. |
| `source_relation`, upstream `anchor_source`, and `result_anchor` | Node `carry_episode.inputs.controlled_pass_anchors.source_node_id=controlled_pass_team_keyed_anchors`; `.documents.home.draft_plan.anchor_source.source_node_id=carry_episode` | The upstream anchor input is `controlled_pass_team_keyed_anchors.anchors`; the result anchor is the carry episode's `anchor_evaluations`. |
| `scalar`/`unit` | Requested evidence alias `displacement_m`; `predicate_2.compare.unit=metre` | The scalar and unit are plan-emitted and predicate-typed. |
| `claim_boundary` | `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe allows only observed movement-under-control displacement and disallows intent, causation, decision quality, optimality, and target-specific inference claims. |

### `search_heldout_support_arrival_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_heldout_support_arrival_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: support_arrival_relation` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning, `source_relation`, and upstream `anchor_source` | Node `support_arrival_relation.inputs.anchors.source_node_id=controlled_pass_team_keyed_anchors`; requested evidence `support_arrival_status`; predicate `predicate_1` on `support_arrival_status == PASS` | The plan computes support arrival from `controlled_pass_team_keyed_anchors.anchors` and classifies PASS support-arrival rows. |
| Anchor frame `controlled_reception_frame_id` | `nodes[node_id=support_arrival_relation].parameters.anchor_frame_field.value=controlled_reception_frame_id` | The support relation is evaluated at controlled reception. |
| Candidate scope `perspective_outfield` | `support_arrival_relation.parameters.candidate_scope.value=perspective_outfield` | The candidate supporting players are perspective outfield players. |
| Region mode `WITHIN_DISTANCE_OF_REFERENCE_POINT` | `support_arrival_relation.parameters.support_region_mode.value=WITHIN_DISTANCE_OF_REFERENCE_POINT`; requested evidence `support_region_mode` | The support region is explicitly the distance-to-reference-point mode. |
| Thresholds: 3.0 seconds, 8.0 metres, at least 1 player | `maximum_arrival_seconds=3.0 second`; `maximum_support_distance_m=8.0 metre`; `minimum_supporting_players=1.0 count` under `support_arrival_relation.parameters` | The declaration's timing, distance, and count thresholds are the declared plan parameters. |
| Supporting-player evidence | Requested evidence `supporting_player_ids`, `support_anchor_frame_id`, `coverage_status` | The plan asks for the supporting players, support anchor frame, and coverage status. |
| `claim_boundary` | `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe allows only observed support arrival under frozen distance/timing parameters and disallows intent, causation, decision quality, and optimality claims. |

### `search_carry_progression_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_carry_progression_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: carry_progression` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: carry episode with observed control | Node `carry_episode`; requested evidence `carry_status`; predicate `predicate_1` on `carry_status == PASS` | The plan classifies PASS carry episodes. |
| Forward progression between carry start/end frames | Requested evidence aliases `carry_start_frame_id`, `carry_end_frame_id`, and `carry_forward_progression_m`; `carry_forward_progression_m.source.output_name=forward_progression_m` | The plan emits the frame witnesses and maps the declared field to the `forward_progression_m` output. |
| Threshold `forward_progression_m >= 3.0` | `nodes[node_id=predicate_2].input.output_name=forward_progression_m`; `predicate_2.compare.value=3.0`; `predicate_2.compare.unit=metre` | The classification requires at least 3 metres of forward progression. |
| `source_relation`, upstream `anchor_source`, and `result_anchor` | Node `carry_episode.inputs.controlled_pass_anchors.source_node_id=controlled_pass_team_keyed_anchors`; `.documents.home.draft_plan.anchor_source.source_node_id=carry_episode` | The upstream anchor input is `controlled_pass_team_keyed_anchors.anchors`; the result anchor is the carry episode's `anchor_evaluations`. |
| `scalar`/`unit` | Requested evidence alias `carry_forward_progression_m`; `predicate_2.compare.unit=metre` | The scalar and unit are plan-emitted and predicate-typed. |
| `claim_boundary` | `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe allows only observed movement-under-control with a forward component and disallows intent, causation, decision quality, and optimality claims. |

### `search_direct_pressure_candidate_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_direct_pressure_candidate_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: direct_pressure_candidate` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: pressure_on_carrier PASS at controlled reception for the receiver | Node `pressure_on_carrier`; `parameters.carrier_id_field.value=receiver_id`; `parameters.frame_field.value=controlled_reception_frame_id`; predicate `predicate_1` on `pressure_status == PASS` | The plan evaluates pressure on the receiver at controlled reception and classifies PASS pressure rows. |
| Source relation, upstream `anchor_source`, and result relation | `pressure_on_carrier.inputs.anchors.source_node_id=controlled_pass_episode`; `.documents.home.draft_plan.anchor_source.source_node_id=pressure_on_carrier` | The upstream anchor input is `controlled_pass_episode.anchors`; the result relation is `pressure_on_carrier`. |
| Candidate scope `defending_outfield` | `pressure_on_carrier.parameters.candidate_scope.value=defending_outfield` | Nearest-defender evidence is drawn from defending outfield candidates. |
| Distance/speed/angle/lookback thresholds | `maximum_pressure_distance_m=4.0`; `minimum_closing_speed_mps=0.2`; `maximum_approach_angle_degrees=100.0`; `lookback_seconds=0.4` under `pressure_on_carrier.parameters` | The declaration's pressure components are the plan's pressure parameters. |
| Evidence fields | Requested evidence aliases `nearest_defender_id`, `nearest_defender_distance_m`, `closing_speed_mps`, `approach_angle_degrees`, `coverage_status` | The declared pressure components and coverage status are plan-emitted fields. |
| `claim_boundary` | `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe allows only observed nearest-defender pressure components and disallows intent, causation, decision quality, optimality, and probability claims. |

### `search_post_regain_retention_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_post_regain_retention_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: post_regain_retention` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: regain transition PASS plus outcome window PASS | Node `transition_anchor_2.parameters.transition_type.value=regain`; predicate `predicate_1` on `transition_status == PASS`; node `outcome_window`; predicate `predicate_2` on `outcome_window_status == PASS` | The plan requires a regain transition anchor and a PASS outcome window. |
| Transition frame/type evidence | Requested evidence aliases `transition_type`, `transition_frame_id`, `transition_status` from `transition_anchor_2` | The plan emits the regain transition frame and type witnesses. |
| Upstream `anchor_source` and `source_relation` | `outcome_window.inputs.anchors.source_node_id=transition_anchor_2`; `.documents.home.draft_plan.anchor_source.source_node_id=outcome_window` | The outcome window is anchored from the transition anchor; the result relation is `outcome_window`. |
| Minimum prior possession | `transition_anchor_2.parameters.minimum_prior_possession_seconds.value=0.4`; unit `second` | A transition can PASS only after the declared 0.4-second prior possession condition. |
| Outcome-window duration | `outcome_window.parameters.maximum_window_seconds.value=8.0`; `outcome_window.parameters.minimum_settled_possession_seconds.value=4.0` | The retention meaning is bounded to a 4-second settled-possession threshold within an 8-second outcome window. |
| Settled segment may begin anywhere in the window | `src/tqe/runtime/capabilities/possession_family.py` `outcome_window_anchor_record`: `segment_true(retained_mask, settled_frames)` and `settled_segment = segments[0] if segments else None`; `src/tqe/runtime/catalog.py` `maximum_window_seconds` description | The runtime searches for any retained-possession segment meeting the settled-frame threshold inside the window, not only a segment beginning at the transition frame. |
| Required anchor status for outcome window | `outcome_window.parameters.required_anchor_status_field.value=transition_status`; `required_anchor_status_value.value=PASS` | The outcome window is only evaluated from PASS transition anchors. |
| `unit` | `minimum_prior_possession_seconds`, `maximum_window_seconds`, and `minimum_settled_possession_seconds` parameter units are `second` | The time values are seconds in the plan. |
| `claim_boundary` | `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe allows only settled retention for the frozen duration threshold and disallows intent, causation, decision quality, and optimality claims. |

### `search_heldout_shape_expansion_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_heldout_shape_expansion_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: shape_expansion_episode` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: defending-outfield width increase, not generic shape | Nodes `team_compactness` and `team_compactness_2`; `change_across_anchor.parameters.before_value_field.value=team_width_m`; `after_value_field.value=team_width_m` | The certified plan compares `team_width_m` only, so the declaration is narrowed to width. |
| Upstream `anchor_source` | Nodes `team_compactness.inputs.anchors.source_node_id=controlled_pass_episode`, `team_compactness_2.inputs.anchors.source_node_id=controlled_pass_episode`, and `change_across_anchor.inputs.anchors.source_node_id=controlled_pass_episode` | The upstream anchor input for the compactness and change measurements is `controlled_pass_episode.anchors`. |
| Before/after frames | `team_compactness.parameters.frame_field.value=physical_release_frame_id`; `team_compactness_2.parameters.frame_field.value=controlled_reception_frame_id` | The before and after compactness measurements are fixed to release and reception frames. |
| Change relation | Node `change_across_anchor.inputs.before_evaluations.source_node_id=team_compactness`; `after_evaluations.source_node_id=team_compactness_2`; `anchors.source_node_id=controlled_pass_episode` | The plan computes the across-anchor before/after change from those two compactness relations. |
| Threshold and mode | `change_across_anchor.parameters.change_mode.value=increase_at_least`; `minimum_change_m.value=4.0`; `maximum_before_value_m.value=80.0`; predicate `predicate_1` on `change_status == PASS` | The width change must increase by at least 4 metres from a before value not exceeding 80 metres and classify PASS. |
| Measurement policy | `team_compactness.parameters.player_scope.value=defending_outfield`; `minimum_observed_players=8.0`; `maximum_team_width_m=45.0`; `maximum_team_depth_m=35.0`; same values on `team_compactness_2` | The plan's width measurement is limited to observed defending outfield players under these compactness thresholds. |
| Evidence fields | Requested evidence `before_value`, `after_value`, `delta_value`, `before_value_field`, `after_value_field`, `minimum_change_m` from `change_across_anchor` | The declared fields are emitted by the change relation. |
| `claim_boundary` | Value-field citations above; `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | Because the plan compares only `team_width_m`, it does not support depth or area expansion claims; the recipe also disallows intent, causation, decision quality, and optimality claims. |

### `search_carry_out_of_pressure_v0`

Plan: `delivery/packets/r1-c-sweep/plans/search_carry_out_of_pressure_v0.json`

| Declaration clause | Plan citation | Justification |
| --- | --- | --- |
| `coverage_row: carry_out_of_pressure` | Bundle `.target_id`; target file target entry `concept` | Row identity matches the target being declared. |
| Meaning: carry joined to pressure-distance increase | Node `join_episode_sets.inputs.left_episodes.source_node_id=carry_episode`; `right_episodes.source_node_id=change_across_anchor`; predicate `predicate_1` on `join_status == PASS` | The final classifier is the same-anchor join of carry evidence and a pressure-distance change. |
| Upstream `anchor_source` and `result_anchor` | Nodes `carry_episode.inputs.controlled_pass_anchors.source_node_id=controlled_pass_team_keyed_anchors` and `join_episode_sets` final anchor source; `.documents.home.draft_plan.anchor_source.source_node_id=join_episode_sets` | The upstream carry anchor input is `controlled_pass_team_keyed_anchors.anchors`; the result anchor is `join_episode_sets.anchor_evaluations`. |
| Same-anchor composition | `join_episode_sets.parameters.left_key_field.value=anchor_id`; `right_key_field.value=anchor_id`; `left_status_field=carry_status`; `right_status_field=change_status`; `required_status_value=PASS` | The join requires the carry and pressure-change evidence to share `anchor_id` and PASS statuses. |
| Before pressure relation | Node `pressure_on_carrier.parameters.frame_field.value=carry_start_frame_id`; `carrier_id_field.value=carrier_id`; `candidate_scope.value=defending_outfield` | The before pressure measurement is on the carry carrier at carry start. |
| After pressure-distance relation | Node `pressure_on_carrier_2.parameters.frame_field.value=carry_end_frame_id`; `carrier_id_field.value=carrier_id`; `candidate_scope.value=defending_outfield` | The after distance measurement is on the same carrier field at carry end. |
| Change scalar and threshold | `change_across_anchor.parameters.before_value_field.value=nearest_defender_distance_m`; `after_value_field.value=nearest_defender_distance_m`; `change_mode=increase_at_least`; `minimum_change_m=2.0`; `maximum_before_value_m=4.0`; `before_status_field=pressure_status`; `required_status_value=PASS` | The plan only asserts nearest-defender distance increased by at least 2 metres from a pressured starting point. |
| After-status boundary | `change_across_anchor.parameters.after_status_field.value=none` | The declaration explicitly avoids claiming the end frame is pressure-free; the plan does not require an after pressure-status PASS/FAIL. |
| Evidence fields | Requested evidence `carry_status`, `carrier_id`, `carry_start_frame_id`, `carry_end_frame_id`, `change_status`, `before_value`, `after_value`, `delta_value` | The declared composition's witnesses are requested by the plan. |
| `claim_boundary` | After-status citation above; `.documents.home.recipe.allowed_claims[]`; `.documents.home.recipe.disallowed_claims[]` | The recipe and parameters support only observed nearest-defender distance increase, not pressure-breaking quality, defender bypass, intent, or causation. |

## Verification

Initial checks:

| Command | Result | Notes |
| --- | --- | --- |
| `jq empty config/compiler-reachability/search-targets.v0.json` | PASS | Target JSON remains valid. |
| Home/away draft-plan equality command above | PASS | All seven bundles returned `true`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r1_c_checkpoint.R1CCheckpointTests.test_committed_target_declarations_are_well_formed -v` | PASS | Validates all declarations in committed target files through `validated_semantic_correspondence`; asserts all seven R2-0 pre-era targets are declared. |
| Mutation: corrupt `coverage_row` for `search_heldout_carry_displacement_v0` in workspace scratch copy `.r2-0-search-targets-mutated.json`, then call `declared_targets_from_files([scratch_path])` directly | FAIL as expected | Raised `coverage_row does not match coverage row`; scratch file removed; clean checkpoint module rerun passed. |
| `UV_CACHE_DIR=/private/tmp/uv-cache uv run --no-sync python -m unittest tests.test_r1_c_checkpoint -v` | PASS | 12 checkpoint tests, including existing R1-C guards and the new declaration loader. |

Full-suite table, run on committed tree `de39f6b` before this final
report-only update:

| Command | Result | Tests | Runtime | Attestation | Failures |
| --- | --- | ---: | ---: | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache /usr/bin/time -p make PYTHON="uv run --no-sync python" test` | PASS | 463 | 442.205s (`real 443.35`) | `VERIFIED`, blocking reasons `[]` | None |

Failure attribution: no full-suite failures.

## Local Commits

| Commit | Scope |
| --- | --- |
| `240dc90` | R2-0 declarations plus verification appendix report |
| `de39f6b` | Declaration-loader test, mutation evidence, and report update |

No push performed.
