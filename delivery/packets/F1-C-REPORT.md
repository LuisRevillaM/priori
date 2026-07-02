# F1-C Corridor Episode Honesty Report

Branch: `packet/f1-c`
Packet: `delivery/packets/F1-C-corridor-episode-honesty.md`
Base packet commit: `0d817b5`

## Summary

Implemented the corridor-honesty fixes in the progressive-corridor runtime without editing the N1 frozen hero history or regenerating tracked projections.

The implementation changes the corridor episode semantics in five places:

1. Missing tracking frames are emitted as per-target `UNKNOWN` corridor states instead of being skipped and bridged across.
2. `UNKNOWN` and `INVALID` states close open episodes with `closed_on_missing_evidence`; only observed `FAIL` states can close with `closed_after_failures`.
3. Anchor evaluations now carry coverage fields and return `UNKNOWN` when absent or partial evidence could change the answer.
4. Episode duration is now elapsed frame span using canonical 25 Hz frame IDs; `pass_frame_count` is retained as a separate evidence field.
5. Missing attacking orientation now produces an `UNKNOWN` anchor evaluation instead of raising.

No N1 frozen artifacts, generated projections, semantic registry files, or frozen expectations were deliberately updated.

## Changed Files

| File | Lines | Change |
| --- | ---: | --- |
| `src/tqe/runtime/relations.py` | 54-68 | Missing orientation now routes to an `UNKNOWN` anchor evaluation with `orientation_unavailable`. |
| `src/tqe/runtime/relations.py` | 164-177, 364-379 | Missing tracking frames emit per-target `UNKNOWN` states instead of being silently skipped. |
| `src/tqe/runtime/relations.py` | 210-265 | Anchor evaluations expose `total_state_count`, `known_state_count`, `unknown_state_count`, `unknown_state_ratio`, and `coverage_status`; partial/absent coverage returns `UNKNOWN` when no relation is proven. |
| `src/tqe/runtime/relations.py` | 397-521 | Hysteresis now treats observed FAIL and UNKNOWN/INVALID distinctly; missing evidence closes as `closed_on_missing_evidence`; duration is elapsed frame span and `pass_frame_count` is separate evidence. |
| `src/tqe/runtime/catalog.py` | 4333-4373, 4466-4485, 5279-5319, 5412-5428 | Catalog declarations now include `pass_frame_count` and anchor coverage fields for both corridor relation variants and duration-filter relation evidence. |
| `tests/test_m2a_bypass.py` | 177-336 | Added corridor episode honesty unit coverage while preserving the existing M2A bypass tests. |

## M1.1 Corridor Episode Delta

The M1.1 corpus was measured before from `0d817b5` and after from this branch using `execute_default_plan()` plus `evaluate_geometric_progressive_corridors()`.

| Metric | Before (`0d817b5`) | After (`packet/f1-c`) | Delta |
| --- | ---: | ---: | ---: |
| Execution rows | 180 | 180 | 0 |
| Episode count | 165 | 165 | 0 |
| Result count with episode | 75 | 75 | 0 |
| Match count with episode | 4 | 4 | 0 |
| State counts | `FAIL=28359`, `PASS=1301` | `FAIL=28359`, `PASS=1301` | 0 |
| Close reasons | `closed_after_failures=83`, `window_end=82` | `closed_after_failures=83`, `window_end=82` | 0 |
| Episodes >= 0.8s | 115 | 100 | -15 |
| Old >= 0.8s -> new < 0.8s | n/a | 15 | +15 |
| Old < 0.8s -> new >= 0.8s | n/a | 0 | 0 |

Interpretation: the M1.1 corpus path contains no missing corridor frames under this run, so the dropout/UNKNOWN fixes are exercised by unit and synthetic executor tests rather than by changed corpus state counts. The duration fix changes threshold membership: 15 episodes that were exactly `4 pass frames / 5 Hz = 0.8s` are now elapsed-span `0.6s` because their canonical frame span is `15 / 25 Hz`.

## Verification

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m2a_bypass` | PASS | 17 tests, including restored M2A bypass coverage and new corridor honesty tests. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m2a_bypass tests.test_m1_1_runtime` | PASS | 29 tests in 189.699s. |
| `make n1c-verify` | PASS | `fail=0`, `pass=8`. |
| `make n1d-verify` | FAIL (expected frozen drift) | `fail=2`, `pass=13`; failures are `n1d.no_artifact_or_runtime_drift` and `n1d.runtime_matches_claim`, both due current runtime/catalog/result identity differing from the pinned N1D manifest. Frozen artifacts were not regenerated. |
| `make n1d1-verify` | PASS | `attestation_status=VERIFIED`. |
| `make n1i-verify` | FAIL (projection drift) | `fail=1`, `pass=10`; `n1i.tracked_projections_match_regeneration` reports drift in generated capability/knowledge-pack projections. Projections were not regenerated. |
| `make m1-1-gate-a-verify` | FAIL (projection drift) | `generated.capability-catalog.json` is stale after adding catalog evidence fields. |
| `make m1-1-verify` | FAIL (expected ripple) | Aggregate `fail=8`, `pass=481`; root failure is stale capability catalog, with precondition cascades and old `relation.episode_shape` expectations that still treat short elapsed-span episodes as invalid. |
| `make m1-2-verify` | INTERRUPTED / BLOCKED | Ran for about 8.5 minutes, then blocked in `m1_2_gate_s2` on external Hermes HTTPS model response; interrupted with stack in `urllib.request.urlopen`. No corridor-runtime failure observed. |
| `make afl-substrate-q4-verify` | PASS | Report status `PASS`; result count 2; requested evidence failures 0; observed PASS/FAIL/UNKNOWN proof-carrying rows. |

No AFL verifier directly consuming `geometric_progressive_corridor` was found by source search. `afl-substrate-q4-verify` was run because it is the only AFL verifier with a directly discoverable pass-corridor reference and remains clean.

## Changed Pins / Frozen Artifacts

No pins were changed.

Expected follow-up regeneration points after review:

- `generated/capability-catalog.json`
- `generated/capability-context.json`
- `generated/tactical-knowledge-pack.json`
- `generated/tactical-knowledge-pack.md`
- M1.1 relation-shape expectations that still assume pass-frame-count duration semantics
- N1D frozen runtime/result identity, if the reviewer chooses to refresh N1 after accepting this runtime change

## Missed / Deferred

- The M1.1 live corpus did not exercise missing-frame UNKNOWN state counts; that behavior is covered by direct unit tests and a synthetic executor relation-node test.
- `make m1-2-verify` could not complete because it waited on an external Hermes model request. The command was interrupted and is reported as blocked, not green.
- No N1 or generated projection write target was run; this packet intentionally reports drift rather than canonizing new pins.
