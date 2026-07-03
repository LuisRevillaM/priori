# F2-7 Report — Final Sweep Extraction

Branch: `packet/f2-7`
Base frontier: `01d3cb1` (`codex/afl08-passport-loop`)
Code commit: `13814b3` — extract final inline capability families

## Scope Outcome

Complete. The final registered inline capability implementations were moved
out of `executor.py` into three family modules with registry-only executor
wiring. No defaults, thresholds, catalog declarations, frozen expectations, or
runtime semantics were intentionally changed.

After this packet, `executor.py` contains no registered inline capability
implementations except the four `LEGACY_NOOP_CAPABILITIES` registrations that
remain explicitly fenced for F2-X.

## Relocated Implementations

`src/tqe/runtime/capabilities/possession_family.py`:

- `primitive_possession_segment`
- `primitive_transition_anchor`
- `primitive_structured_zone`
- `primitive_space_region_generation`
- `primitive_outcome_window`
- `primitive_set_piece_structure`
- `primitive_outcome_classification`

`src/tqe/runtime/capabilities/sequence_family.py`:

- `primitive_action_chain`
- `primitive_switch_of_play`
- `primitive_carry_episode`
- `primitive_pass_chain_episode`

`src/tqe/runtime/capabilities/kinematics_family.py`:

- `primitive_tracking_quality`
- `primitive_pairwise_distance`
- `primitive_velocity`
- `primitive_acceleration`
- `primitive_join_episode_sets`
- `primitive_lane_occupancy`

Direct verifier imports updated:

- `src/tqe/verification/afl_space_region_generation.py`
- `src/tqe/verification/m1_1_gate_s2.py`

Boundary guard updates:

- `tests.test_executor_boundaries.ExecutorRegistryBoundaryTests.test_final_sweep_leaves_no_registered_inline_capability_implementations`
- `implementation_source_paths()` now includes `possession_family.py`,
  `sequence_family.py`, and `kinematics_family.py`
- shared executor leak freezes updated to the post-sweep state

## Line Counts

| File | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `src/tqe/runtime/executor.py` | 6,487 | 3,715 | -2,772 |
| `src/tqe/runtime/capabilities/possession_family.py` | 0 | 1,204 | +1,204 |
| `src/tqe/runtime/capabilities/sequence_family.py` | 0 | 796 | +796 |
| `src/tqe/runtime/capabilities/kinematics_family.py` | 0 | 1,009 | +1,009 |

`executor.py` remaining `primitive_`/`relation_` function definitions:

- `relation_anchor_evaluation_records` — shared helper consumed by predicate
  execution, not a registered relation implementation
- `primitive_noop` — legacy noop dispatcher for the four F2-X fenced names

## Zero Inline Implementation Proof

`tests.test_executor_boundaries` ran on code commit `13814b3`:

- `Ran 11 tests in 0.208s`, OK
- the new final-sweep test proves every catalog primitive/relation
  implementation is relocated except legacy noops
- every non-legacy primitive and every relation registry callable resolves to a
  module outside `tqe.runtime.executor`

## F2-X Leak Census

Remaining capability-name leaks in shared `executor.py` after removing all
registered inline implementations:

| Capability name | Shared executor line |
| --- | --- |
| `relation_destination_entry` | `if node.catalog_ref != "relation_destination_entry":` |
| `time_to_arrival` | `raise RuntimeError(f"Unsupported time_to_arrival candidate_scope: {candidate_scope}")` |

Remaining non-catalog shared helper leak counts from the boundary freeze:

| Frozen leak | Count |
| --- | ---: |
| `frame_id=optional_int(record.get("destination_entry_frame_id"))` | 1 |
| `or optional_int(record.get("outcome_frame_id"))` | 1 |
| `or optional_int(record.get("anchor_frame_id"))` | 1 |
| `def select_proof_results` | 1 |
| `"proof_selected": True` | 1 |
| `"SWITCHED"` | 1 |
| `"RETAINED_NO_SWITCH"` | 1 |
| `"LOST_BEFORE_SWITCH"` | 1 |

Legacy noop capability debt still registered for F2-X:

- `wide_channel_dwell`
- `shift_persistence`
- `robust_team_width`
- `analysis_rate`

## Shared Helpers Retained

Shared runtime-kernel utilities remain in `executor.py` and are imported by
family modules as before: `PeriodState`, runtime parameters, frame/point lookup
caches, catalog input/output helpers, `node_parameter_*`, anchor helpers,
`parquet_rows`, `segment_true`, and related low-level utilities.

One helper was deliberately retained during implementation review:

- `cached_player_position_at_frame` remains shared because the existing
  `lines_family` and the new `sequence_family` both use it.

## Improvement Candidates Not Implemented

These were observed during extraction and deliberately left out of scope:

- Extract shared runtime helpers into a shared-kernel module so family modules
  no longer import executor internals.
- Resolve the F2-X leak census: destination-entry name conditioning,
  time-to-arrival helper leak, proof-selection traces, outcome labels, and
  legacy noop registrations.
- Review whether `primitive_join_episode_sets` and `primitive_lane_occupancy`
  should move from the straggler `kinematics_family.py` into narrower future
  composition/lane modules after the pure-relocation phase.
- Replace verifier direct helper imports with public test support APIs where
  appropriate.

## Pinned-Gate Proof

Executed on a clean git-backed checkout of code commit `13814b3`; only `data`
was an untracked symlink. The branch tip adds this report only.

| Target | Result | Drift Evidence |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons |
| `afl-substrate-q4-verify` | PASS | result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51` |
| `afl-substrate-q6-verify` | PASS | result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496` |
| `afl-line-break-support-response-verify` | PASS | result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f` |
| `afl-lane-occupancy-verify` | PASS | report status `PASS`; `tests.test_lane_occupancy` ran 17 tests in 0.002s, OK |
| `afl-09a-verify` | PASS | validation factories PASS; `tests.test_afl_validation_factory` ran 4 tests in 0.401s, OK |
| `scp-0-verify` | PASS | report status `PASS`; `tests.test_scp0_semantic_registry` ran 58 tests in 28.419s, OK |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; passport count 44; passport revision `e1a26b4369d928b8575f3b171bd406e8e359bd6e2b2c7822c68a53cc88913796`; `tests.test_scp0_semantic_registry` reran 58 tests in 28.397s, OK |

## Full Suite

Executed on the same clean git-backed checkout of code commit `13814b3`. The
branch tip adds this report only.

| Command | Result |
| --- | --- |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS — `Ran 356 tests in 328.758s`, OK; final attestation `VERIFIED` |

## Clean-Tree Note

The shared frontier worktree was not modified by this packet execution. All
work was performed through branch commits on `packet/f2-7` and temporary
checkouts.
