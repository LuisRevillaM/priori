# R2-4 Report: sequence_pattern

Branch: `packet/r2-4`

Frontier base: `104e373` (`codex/afl08-passport-loop`)

Clone-route provenance: main-workspace branch creation failed with
`.git/refs/heads/packet/r2-4.lock` EPERM, so work is being committed in
`/private/tmp/priori-r2-4-single-20260705095024`. Director recovery should
use this clone's commit SHAs via `format-patch`.

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet read | DONE | `delivery/packets/R2-4-sequence-pattern.md` |
| ADR 0013 read | DONE | Operator-era template and addenda govern. |
| ADR 0014 read | DONE | Aggregation principles 20-22 govern downstream counts/rates. |
| ADR 0015 read | DONE | Bridge principles 23-25 govern the meaning-expression fixture. |
| Branch | DONE_CLONE | `packet/r2-4` from `104e373` in `/private/tmp/priori-r2-4-single-20260705095024`. |
| Fences | ACTIVE | No ledger touch; no atlas; no sealed evidence; no autonomous artifacts. SCP-0 generated projections/lock refreshed after the sequence runtime contract delta; coverage ledgers untouched. |
| Push | NOT_DONE | Local commits only. |

## Implementation Log

| Commit | Contents |
| --- | --- |
| `198e0d7` | Report scaffold and clone-route provenance. |
| `93bf39a` | sequence_pattern operator, registry, pack delta, focused tests. |
| `c40a008` | Possession-continuity evidence, compiler-search sequence builder, R2-4 meaning-expression fixture, bridge regression test. |
| `4d74bd0` | Byte-reproducing flagship generator, synthesized sequence+rate plan, counterattack initiation table, provenance. |
| `2d2a3e1` | Mutation evidence and restore check. |
| `PENDING` | Generated contract refresh and final verification table. |

## Pack Delta

| Item | Before | After | Evidence |
| --- | ---: | ---: | --- |
| Composition operators | 7 | 8 | `sequence_pattern@0.1.0` appears in `generated/tactical-knowledge-pack.json`. |
| Composition constraint kinds | 14 | 15 | `sequence_pattern` constraint kind is registry-derived. |

The bridge schema was not extended. The meaning-expression vocabulary now sees `sequence_pattern` through the existing R-AE composition grammar path.

## Focused Evidence

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=/private/tmp/priori-r2-4-single-20260705095024/src UV_CACHE_DIR=/private/tmp/uv-cache-priori /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r2_4_sequence_pattern tests.test_r1_0_operator_scaffolding tests.test_scp2_1_meaning_to_target` | PASS | 32 tests in `0.066s`; includes R2-4 registry-to-pack-to-synthesis fixture. |

## Bridge Fixture

| Item | Evidence |
| --- | --- |
| Fixture | `delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_chain_count.v0.json` |
| Vocabulary path | Accepted by `load_meaning_expression_from_path` using generated pack SHA. |
| Synthesis path | `synthesize_and_bind` returns `operator:aggregate_over` with `population_terminal=operator:sequence_pattern`. |
| Document hash | `7e876649b73fd502e79291389b76ef028a229e8fa83bd3b39a4d224c10489dc7` |
| Schema change | No bridge schema extension; `stage_N_required_fields` and `possession_continuity_source` are registry-derived composition/operator parameters. |

## Flagship Evidence

| Item | Evidence |
| --- | --- |
| Generator | `scripts/packets/r2_4_flagship_generator.py` |
| Command | `TQE_DATA_ROOT=/Users/luisrevilla/code/priori/data/canonical/v1 TQE_RAW_ROOT=/Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 PYTHONPATH=/private/tmp/priori-r2-4-single-20260705095024/src UV_CACHE_DIR=/private/tmp/uv-cache-priori /Users/luisrevilla/code/priori/.venv/bin/python scripts/packets/r2_4_flagship_generator.py --canonical-root /Users/luisrevilla/code/priori/data/canonical/v1 --raw-root /Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 --long-threshold-seconds 300` |
| Result | PASS; 14 role-match rows; 28 period records. |
| Long execution | TRUE; elapsed `344.786s` recorded only in uncommitted `delivery/packets/r2-4-flagship/run-sidecar.local.json`. |
| Plan | `delivery/packets/r2-4-flagship/counterattack_initiation_v0.json` (`65654d53e23bb8757d454a34e9657f325db3acf9ab0dd53842ab741f5d956a10`) |
| Table | `delivery/packets/r2-4-flagship/counterattack_initiation_table.json` (`64ddb4ed5c1a4d923e5f2385b8b536485206cf762535afdec85dee2ecbc32fee`) |
| Totals | Completed chains `1`; population rows `2811`; unknown chain rows `2810`; rate interval `1.000 [0.0003557452863749555, 1.000]`. |
| Denominator reconciliation | All 14 chain populations match rate denominators; all 14 completed-chain counts match rate A counts. |
| Timestamp fence | Committed plan/table/provenance contain no run timestamp; timing data is in the uncommitted local sidecar. |

## Mutation Evidence

| Guard | Temporary mutation | Expected failing test | Result |
| --- | --- | --- | --- |
| Truncated successor windows remain UNKNOWN | Replaced `UNKNOWN if window_truncated else FAIL` with `FAIL if window_truncated else FAIL`. | `tests.test_r2_4_sequence_pattern.SequencePatternOperatorTests.test_truncated_window_is_unknown_not_fail` | FAIL observed: expected `UNKNOWN`, got `FAIL`; restored. |
| Continuity violations are excluded | Disabled `_continuity_satisfied(...)` filtering with `False and`. | `tests.test_r2_4_sequence_pattern.SequencePatternOperatorTests.test_continuity_violation_is_excluded` | FAIL observed: expected stage-2 empty-window failure, got stage-3 empty-window failure; restored. |
| Restore check | `PYTHONPATH=/private/tmp/priori-r2-4-single-20260705095024/src UV_CACHE_DIR=/private/tmp/uv-cache-priori /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r2_4_sequence_pattern tests.test_scp2_1_meaning_to_target` | N/A | PASS; 26 tests in `0.054s`. |


## Generated Contract Refresh

| Item | Evidence |
| --- | --- |
| Trigger | Full-suite stale-artifact guards found runtime/registry drift after `sequence_pattern` added `possession_id` / `team_role` evidence for continuity. |
| M1.1 artifacts | `scripts/m1_1/build_gate_a_artifacts.py` regenerated `generated/capability-catalog.json`; focused stale-artifact guard passed. |
| SCP-0 artifacts | Existing product/AI waivers for denied `join_episode_sets` updated to observed baseline hash `4464b25fda2f2c4b2b109bc1779a38c3f3aa46ce37fadf223b09c38901f83a22`; `TQE_WRITE=1 PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python -m tqe.verification.scp0` regenerated semantic projections and lock with status `PASS`. |
| Drift check | `check_scp0_artifacts()` returned `PASS`, zero findings, zero drift. |
| Protected paths | `git diff --name-only | grep -E '(^generated/coverage-map|^artifacts/autonomous|r1-5|R1-5)'` returned no paths. |
| Focused guard suite | `PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_m1_1_binder tests.test_scp0_semantic_registry tests.test_verifier_write_mode tests.test_r2_4_sequence_pattern tests.test_scp2_1_meaning_to_target` passed 110 tests in `33.301s`. |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make test` | PENDING | Must run on committed tree. |

