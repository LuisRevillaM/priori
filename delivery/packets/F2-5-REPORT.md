# F2-5 Report — Off-Ball Family Extraction

Branch: `packet/f2-5`
Base frontier: `71d4948` (`codex/afl08-passport-loop`)
Code commits:

- `8cd3bbf` — backfill F2-4 packet report
- `bfa7b80` — extract off-ball family capabilities
- `051581a` — retain shared time-to-arrival candidate helper

## Scope Outcome

Complete. The off-ball family was relocated from `executor.py` into
`src/tqe/runtime/capabilities/offball_family.py` with registry-only executor
wiring. No defaults, thresholds, catalog declarations, frozen expectations, or
runtime semantics were intentionally changed.

`delivery/packets/F2-4-REPORT.md` was backfilled first on this branch, per the
packet obligation.

## Relocated Implementations

Node functions moved:

- `primitive_marking`
- `primitive_off_ball_run`
- `primitive_off_ball_run_type`
- `primitive_time_to_arrival`
- `relation_support_arrival`

Family helpers moved:

- `marking_anchor_record`
- `marking_target_team_role`
- `marking_candidate_team_role`
- `off_ball_run_anchor_record`
- `off_ball_run_candidate_team_role`
- `off_ball_run_excluded_player_ids`
- `off_ball_run_candidate_record`
- `off_ball_run_type_anchor_record`
- `point_tuple_from_payload`
- `observed_opposition_line_x`
- `is_beyond_line`
- `time_to_arrival_anchor_record`
- `time_to_arrival_target_point`
- `support_arrival_anchor_record`
- `support_arrival_prefilter_record`
- `cached_observed_outfield_positions_between_frames`

Registry mappings added:

- `primitive_marking -> tqe.runtime.capabilities.offball_family`
- `primitive_off_ball_run -> tqe.runtime.capabilities.offball_family`
- `primitive_off_ball_run_type -> tqe.runtime.capabilities.offball_family`
- `primitive_time_to_arrival -> tqe.runtime.capabilities.offball_family`
- `relation_support_arrival -> tqe.runtime.capabilities.offball_family`

Boundary guard added:

- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_offball_family_relocation_is_registry_only`
- `implementation_source_paths()` now includes `capabilities/offball_family.py`

## Line Counts

| File | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `src/tqe/runtime/executor.py` | 9,183 | 7,920 | -1,263 |
| `src/tqe/runtime/capabilities/offball_family.py` | 0 | 1,260 | +1,260 |

## Shared Helpers Retained

The following remain in `executor.py` because they are shared executor/runtime
kernel helpers or are still used by non-off-ball implementations:

- `PeriodState`
- `FRAME_RATE_HZ`
- `catalog_input_value`
- `catalog_output`
- `node_parameter_text`
- `node_parameter_number`
- `node_parameter_integer`
- `runtime_records`
- `optional_int`
- `anchor_record_id`
- `point_from_xy`
- `ball_point_at_frame`
- `tracked_point_at_frame`
- `player_records_at_frame`
- `player_records_at_frame_for_team`
- `cached_observed_outfield_positions_at_frame`
- `cached_observed_player_point_at_frame`
- `outfield_player_ids`
- `parquet_rows`
- `anchor_reference_point`
- `time_to_arrival_candidates`

`time_to_arrival_candidates` is deliberately retained as shared because
`cover_shadow_anchor_record` in `executor.py` still calls it. The off-ball
family imports that shared helper rather than owning it.

## Improvement Candidates Not Implemented

These were observed during extraction and deliberately left out of scope:

- Move shared runtime helpers into a dedicated shared-kernel module in a later
  packet, rather than continuing family modules importing them from
  `executor.py`.
- Revisit `time_to_arrival_candidates` ownership when `cover_shadow` is
  extracted or a shared candidate-scope utility exists.
- Consider a narrower support-arrival position-window cache helper name once
  support-arrival and local-number/pressure families are extracted.

## Pinned-Gate Proof

Executed on a clean git-backed checkout of final code commit `051581a`; only
`data` was an untracked symlink. The branch tip adds this report only.

| Target | Result | Drift Evidence |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons |
| `afl-substrate-q4-verify` | PASS | result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51` |
| `afl-substrate-q6-verify` | PASS | result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496` |
| `afl-line-break-support-response-verify` | PASS | result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f` |
| `afl-lane-occupancy-verify` | PASS | report status `PASS`; `tests.test_lane_occupancy` ran 17 tests in 0.002s, OK |
| `afl-09a-verify` | PASS | validation factories PASS; `tests.test_afl_validation_factory` ran 4 tests in 1.098s, OK |
| `scp-0-verify` | PASS | report status `PASS`; `tests.test_scp0_semantic_registry` ran 58 tests in 28.014s, OK |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; passport count 44; passport revision `e1a26b4369d928b8575f3b171bd406e8e359bd6e2b2c7822c68a53cc88913796`; `tests.test_scp0_semantic_registry` reran 58 tests in 28.198s, OK |

## Full Suite

Executed on the same clean git-backed checkout of final code commit `051581a`.
The branch tip adds this report only.

| Command | Result |
| --- | --- |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS — `Ran 354 tests in 315.974s`, OK; final attestation `VERIFIED` |

## Clean-Tree Note

The shared frontier worktree was not modified by this packet execution. All
work was performed through branch commits on `packet/f2-5` and temporary
checkouts.
