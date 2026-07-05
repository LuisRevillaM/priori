# R2-4 Report: sequence_pattern

Branch: `packet/r2-4`

Frontier base: `104e373` (`codex/afl08-passport-loop`)

Round 1 clone-route provenance, retained for history: main-workspace branch
creation failed with `.git/refs/heads/packet/r2-4.lock` EPERM, so round 1
was recovered from `/private/tmp/priori-r2-4-single-20260705095024`. Round 2
committed directly on the recovered in-workspace branch.

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet and case law read | DONE | `R2-4-REVIEW.md`, packet spec, ADR 0013/0014/0015, `SCP2-1-REVIEW.md`, `R2-2-REVIEW.md` |
| Branch | DONE | Existing checked-out `packet/r2-4` |
| Fences | ACTIVE | No ledger, atlas, sealed evidence, autonomous artifacts, freezes, or re-pins touched |
| Push | NOT_DONE | Local commits only |
| Deviations | NONE | No ratification request needed in round 2 |

## Round 2 Commit Log

| Commit | Contents |
| --- | --- |
| `4d3d4ed` | R-AL/R-AM/R-AN/R-AO/F3 implementation fixes, regenerated flagship artifacts |
| report commit | This stage-committed report update |

## R-AL Correction

Round 1 did **not** produce a synthesized sequence+rate plan. It synthesized a
sequence-pattern chain-count document
(`counterattack_initiation_chain_count.v0.json`, document hash
`7e876649b73fd502e79291389b76ef028a229e8fa83bd3b39a4d224c10489dc7`), then
the generator deep-copied that document and hand-inserted the rate node. The
round-1 plan hash `65654d53e23bb8757d454a34e9657f325db3acf9ab0dd53842ab741f5d956a10`
was honest as an artifact hash, but it was not the unmodified synthesized
document.

Round 2 replaces that with one meaning expression carrying the sequence and
rate ask: `delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json`.
`synthesize_and_bind` now returns `operator:rate` with
`population_terminal=operator:sequence_pattern` and companion aggregate node
`aggregate_over`. The generator executes the returned bundle unmodified; the
committed plan hash equals the synthesized document hash:
`bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749`.

## Round 2 Fixes

| Ruling | Result | Evidence |
| --- | --- | --- |
| R-AL | Full sequence+rate expression; generator consumes synthesized document unmodified | `scripts/coverage_map/compiler_search_reachability.py`, generator, new meaning fixture |
| R-AM | Ratchet extended with `sequence_pattern`; two binder messages are name-free | `tests.test_r1_0_operator_scaffolding` |
| R-AN | Missing numeric threshold values route to UNKNOWN; flagship rerun completed | `test_missing_numeric_threshold_candidate_is_unknown_not_fail`, flagship table |
| R-AO | Five missing fixtures added with count assertions | sequence fixture table below |
| F3/notes | Zero-width limitation declared; non-overlap reason is `policy_excluded`; possession identity uses shared helper | `src/tqe/runtime/possession_identity.py`, sequence tests |

Round 2 did not require a generated contract refresh. The generated/stale guard
suite passed unchanged.

## Bridge Fixture

| Item | Evidence |
| --- | --- |
| Fixture | `delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json` |
| Meaning hash | `4c11f6699e3788951d4e4f33ee4cb7c8f54f7375ee333dda7df88362008f146e` |
| Terminal provider | `operator:rate` |
| Population terminal | `operator:sequence_pattern` |
| Companion count node | `aggregate_over` |
| Document/plan hash | `bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749` |
| Schema change | None; uses existing R-AE composition grammar vocabulary |

## Flagship Evidence

| Item | Evidence |
| --- | --- |
| Generator | `scripts/packets/r2_4_flagship_generator.py` |
| Command | `TQE_DATA_ROOT=/Users/luisrevilla/code/priori/data/canonical/v1 TQE_RAW_ROOT=/Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 PYTHONPATH=src .venv/bin/python scripts/packets/r2_4_flagship_generator.py --canonical-root /Users/luisrevilla/code/priori/data/canonical/v1 --raw-root /Users/luisrevilla/code/priori/data/raw/idsse/figshare-28196177-v1 --long-threshold-seconds 300` |
| Result | PASS; 14 role-match rows; 28 period records |
| Long execution | TRUE; elapsed `359.077s` in uncommitted `delivery/packets/r2-4-flagship/run-sidecar.local.json` |
| Plan | `delivery/packets/r2-4-flagship/counterattack_initiation_v0.json` (`bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749`) |
| Table | `delivery/packets/r2-4-flagship/counterattack_initiation_table.json` (`49bf6720be24f417b179d17abfe2e4ee9231ce2fcab55194109697fa17def411`) |
| Totals | A=`1`, B=`0`, C=`2261`, D1=`0`, D2=`549`, E=`0`; population `2811`; unknown `2810` |
| Rate interval | observed `1.000`; bounds `[0.0003557452863749555, 1.000]` |
| Denominator reconciliation | All 14 chain populations match rate denominators; all 14 completed-chain counts match rate A |

Degeneracy remark: B and D1 are zero because this corpus/run produced no
observed completed-denominator chain failures; nearly every non-completed
regain remains UNKNOWN under the sequence law. The interval will narrow only
when successor windows are fully observed and threshold/pass evidence resolves
UNKNOWN rows into observed PASS or FAIL outcomes.

Zero-width-window limitation: with the declared exclusive-start/inclusive-end
boundary, a zero-second successor window is vacuous and currently fails as a
fully observed empty window.

## Sequence Fixtures

| Fixture | Count assertion | Result |
| --- | --- | --- |
| Coverage gap UNKNOWN | `test_coverage_gap_window_is_unknown_not_fail` emits exactly 1 chain | PASS |
| Both-teams case law | `test_both_team_patterns_are_preserved` emits exactly 2 chains, home and away | PASS |
| Non-overlap policy | `test_non_overlapping_policy_excludes_reused_successors_with_policy_reason` emits exactly 2 chains, second `stage_2_policy_excluded` | PASS |
| Window edge+1 exclusion | `test_successor_at_window_edge_plus_one_is_excluded` emits exactly 1 FAIL with 0 candidates | PASS |
| Observed possession stream | `test_observed_possession_stream_supplies_continuity_identity` emits exactly 1 PASS | PASS |

## Mutation Evidence

| Guard | Temporary mutation | Expected failing test | Result |
| --- | --- | --- | --- |
| Truncated windows stay UNKNOWN | Replaced `UNKNOWN if window_truncated else FAIL` with `FAIL if window_truncated else FAIL` | `test_truncated_window_is_unknown_not_fail` | FAIL observed: expected `UNKNOWN`, got `FAIL`; restored |
| Continuity violations excluded | Disabled `_continuity_satisfied(...)` filtering with `False and` | `test_continuity_violation_is_excluded` | FAIL observed: expected stage-2 failure, got stage-3 failure; restored |
| Missing numeric threshold is UNKNOWN | Returned `FAIL` for missing/unparseable numeric threshold | `test_missing_numeric_threshold_candidate_is_unknown_not_fail` | FAIL observed: expected `UNKNOWN`, got `FAIL`; restored |
| Non-overlap reason is policy-specific | Reverted policy-excluded reason to fully-observed-empty-window | `test_non_overlapping_policy_excludes_reused_successors_with_policy_reason` | FAIL observed: expected `stage_2_policy_excluded`; restored |
| Shared-code ratchet catches name literal | Reintroduced `sequence_pattern` in a binder validator message | `test_r1_operator_names_do_not_leak_into_shared_runtime_code` | FAIL observed: `sequence_pattern leaked into tqe.runtime.binder`; restored |
| Restore suite | Focused suite after all mutations | PASS | 57 tests in `0.104s` |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_r2_4_sequence_pattern tests.test_r1_0_operator_scaffolding tests.test_scp2_1_meaning_to_target tests.test_r2_2_rate` | PASS | 57 tests in `0.104s` |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_m1_1_binder tests.test_scp0_semantic_registry tests.test_verifier_write_mode` | PASS | 84 tests in `33.620s`; no round-2 generated refresh required |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | Committed implementation tree `4d3d4ed`; 532 tests in `459.344s`; attestation `VERIFIED`; long execution flagged |

Uncommitted local files intentionally not staged: `delivery/packets/r2-4-flagship/run-sidecar.local.json`
and the pre-existing unrelated `docs/visual-explainers/tactical-compilation-concept.png`.
