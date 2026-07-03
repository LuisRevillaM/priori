# F2-6 Report — Team-Shape & Defending Family Extraction

Branch: `packet/f2-6`
Base frontier: `029db29` (`codex/afl08-passport-loop`)
Code commit: `1d9c69e` — extract team-shape family capabilities

## Scope Outcome

Complete. The team-shape/defending family was relocated from `executor.py` to
`src/tqe/runtime/capabilities/teamshape_family.py` with registry-only executor
wiring. No defaults, thresholds, catalog declarations, frozen expectations, or
runtime semantics were intentionally changed.

## Relocated Implementations

Node functions moved:

- `primitive_team_compactness`
- `primitive_change_across_anchor`
- `primitive_cover_shadow`
- `primitive_ball_lateral_fraction`
- `primitive_defensive_outfield_centroid`
- `primitive_signed_lateral_shift`
- `relation_pressure_on_carrier`
- `relation_team_press`
- `relation_local_number`

Family helpers moved:

- `team_compactness_anchor_record`
- `change_across_anchor_record`
- `cover_shadow_anchor_record`
- `lane_projection`
- `pressure_on_carrier_anchor_record`
- `team_press_anchor_record`
- `team_press_evidence_at_frame`
- `pressure_angle_spread`
- `pressure_evidence_at_frame`
- `pressure_duration_ending_at_frame`
- `vector_angle_degrees`
- `local_number_anchor_record`
- `wide_entry_candidates`
- `wide_entry_candidates_from_episodes`
- `episode_start_index`
- `episode_end_index`
- `records_by_anchor_id`

Registry mappings added:

- `primitive_team_compactness -> tqe.runtime.capabilities.teamshape_family`
- `primitive_change_across_anchor -> tqe.runtime.capabilities.teamshape_family`
- `primitive_cover_shadow -> tqe.runtime.capabilities.teamshape_family`
- `primitive_ball_lateral_fraction -> tqe.runtime.capabilities.teamshape_family`
- `primitive_defensive_outfield_centroid -> tqe.runtime.capabilities.teamshape_family`
- `primitive_signed_lateral_shift -> tqe.runtime.capabilities.teamshape_family`
- `relation_pressure_on_carrier -> tqe.runtime.capabilities.teamshape_family`
- `relation_team_press -> tqe.runtime.capabilities.teamshape_family`
- `relation_local_number -> tqe.runtime.capabilities.teamshape_family`

Direct verifier imports updated:

- `src/tqe/verification/afl_cover_shadow.py`
- `src/tqe/verification/afl_team_press.py`
- `src/tqe/verification/m1_1_gate_s2.py`

Boundary guard added:

- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_teamshape_family_relocation_is_registry_only`
- `implementation_source_paths()` now includes `capabilities/teamshape_family.py`

## Line Counts

| File | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `src/tqe/runtime/executor.py` | 7,920 | 6,487 | -1,433 |
| `src/tqe/runtime/capabilities/teamshape_family.py` | 0 | 1,422 | +1,422 |

## Shared Helpers Retained

The following helpers remain in `executor.py` because they are shared
runtime-kernel state/utilities or are still used by remaining inline
capabilities:

- `PeriodState`
- `FRAME_RATE_HZ`
- `PITCH_HALF_WIDTH_M`
- `anchor_record_id`
- `anchor_reference_point`
- `ball_point_at_frame`
- `cached_observed_outfield_positions_at_frame`
- `cached_observed_player_point_at_frame`
- `catalog_input_value`
- `catalog_output`
- `node_parameter_text`
- `node_parameter_number`
- `node_parameter_integer`
- `optional_float`
- `optional_int`
- `outfield_player_ids`
- `player_records_at_frame_for_team`
- `point_from_xy`
- `runtime_records`
- `time_to_arrival_candidates`
- `tracked_point_at_frame`

## Remaining-Inline Census for F2-7

Registered capability node functions still inline in `executor.py` after F2-6:

### Legacy/noop dispatch debt

- `primitive_noop` (`wide_channel_dwell`, `shift_persistence`,
  `robust_team_width`, `analysis_rate`)

### Possession, transition, zones, set pieces, and outcomes

- `primitive_possession_segment`
- `primitive_transition_anchor`
- `primitive_structured_zone`
- `primitive_space_region_generation`
- `primitive_outcome_window`
- `primitive_set_piece_structure`
- `primitive_outcome_classification`

### Action/sequence and switch/carry

- `primitive_action_chain`
- `primitive_switch_of_play`
- `primitive_carry_episode`
- `primitive_pass_chain_episode`

### Tracking, proximity, and kinematics

- `primitive_tracking_quality`
- `primitive_pairwise_distance`
- `primitive_velocity`
- `primitive_acceleration`

### Composition and lane occupancy

- `primitive_join_episode_sets`
- `primitive_lane_occupancy`

No registered `relation_*` implementation remains inline. The only remaining
`relation_`-prefixed function in `executor.py` is
`relation_anchor_evaluation_records`, a shared helper rather than a registered
relation implementation.

## Improvement Candidates Not Implemented

These were observed during extraction and deliberately left out of scope:

- Extract shared runtime helpers into a shared-kernel module so family modules
  no longer import executor internals.
- Decide whether `time_to_arrival_candidates` remains a shared helper or moves
  with a future cover-shadow/time-arrival ownership cleanup.
- Split the remaining inline registered functions into a final F2-7 sweep or
  into smaller families if review wants a narrower risk profile.
- Quarantine or delete legacy noop capabilities in the later F2-X kill-list
  packet, not in this pure relocation.

## Pinned-Gate Proof

Executed on a clean git-backed checkout of code commit `1d9c69e`; only `data`
was an untracked symlink. The branch tip adds this report only.

| Target | Result | Drift Evidence |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons |
| `afl-substrate-q4-verify` | PASS | result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51` |
| `afl-substrate-q6-verify` | PASS | result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496` |
| `afl-line-break-support-response-verify` | PASS | result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f` |
| `afl-lane-occupancy-verify` | PASS | report status `PASS`; `tests.test_lane_occupancy` ran 17 tests in 0.002s, OK |
| `afl-09a-verify` | PASS | validation factories PASS; `tests.test_afl_validation_factory` ran 4 tests in 0.808s, OK |
| `scp-0-verify` | PASS | report status `PASS`; `tests.test_scp0_semantic_registry` ran 58 tests in 29.316s, OK |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; passport count 44; passport revision `e1a26b4369d928b8575f3b171bd406e8e359bd6e2b2c7822c68a53cc88913796`; `tests.test_scp0_semantic_registry` reran 58 tests in 28.705s, OK |

## Full Suite

Executed on the same clean git-backed checkout of code commit `1d9c69e`. The
branch tip adds this report only.

| Command | Result |
| --- | --- |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS — `Ran 355 tests in 409.515s`, OK; final attestation `VERIFIED` |

## Clean-Tree Note

The shared frontier worktree was not modified by this packet execution. All
work was performed through branch commits on `packet/f2-6` and temporary
checkouts.
