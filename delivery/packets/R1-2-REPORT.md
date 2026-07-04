# R1-2 Report - delta_across_anchor Operator

Branch: `packet/r1-2`
Frontier base for original packet: `834c2c9`
Round-2 review source: `delivery/packets/R1-2-REVIEW.md` on the frontier
ADR: `docs/adr/0013-r1-operator-era.md`, including Addendum 2
Push: no push, per direct-channel protocol.

## Result

PASS. R1-2 adds `delta_across_anchor@0.1.0`, wires it through the
composition operator registry, and earns the `pressure_change_after` held-out
target through the generic compiler-search path.

Round 2 corrected the evidence substance behind the booked result. The target
still returns 20 rows, but those rows now match the declared meaning:

> signed change in nearest-opponent distance from the passer at physical
> release to the receiver at controlled reception for the same controlled-pass
> anchor.

The booked rows now enforce controlled-pass anchor status, use distinct
release/reception evaluation frames, bind the before relation to `passer_id`,
bind the after relation to `receiver_id`, and record the actual source frames
and subject ids in evidence.

## Round-2 Review Fixes

| Finding | Status | Fix |
| --- | --- | --- |
| B1: receiver-to-self rows / wrong team pressure context | PASS | `pressure_on_carrier` now computes the defending side relative to each anchor's `team_role`, so home anchors evaluate away defenders and away anchors evaluate home defenders. The delta target declares before subject `passer_id` and after subject `receiver_id`, and evidence records both subject fields and ids. |
| B2: declared anchor-status constraint was not enforced | PASS | `delta_across_anchor` now accepts `anchor_status_field` and `anchor_status_value`, emits `anchor_status`, and fails/unknowns rows whose anchor does not prove the declared status. The acceptance target requires `pass_status == PASS`. |
| B3: missing declared frames fell back to same-frame anchor deltas | PASS | Relation evaluation no longer silently falls back to `anchor_frame_id` when a declared `frame_field` is missing. The operator also rejects missing or identical before/after source frames as `UNKNOWN`. |
| B4: evidence frame ids were misreported | PASS | Source frame extraction now prefers relation-specific evaluation frame fields before generic anchor fields. All booked rows report the physical release frame for before and the controlled reception frame for after. |
| B5: banned provider-name bonus pattern / second builder path | PASS | Provider-name scoring bonuses were removed from both the R1-2 search path and the grandfathered change-composition path. Operator field lists are derived from signatures, and declared constraints are either consumed or fail synthesis. |
| B6: before/after compiler_reachable proof not published | PASS | This report publishes the rejected round-1 evidence hash, the corrected round-2 evidence hash, the unchanged result count, and the row-level audit showing the substance change. |

## Addendum-2 Teeth

| Tooth | Status | Evidence |
| --- | --- | --- |
| T1: no provider-name literals in candidate scoring | PASS | Added a regression test that scans `compiler_search_reachability.py`; provider names remain in declarations and dispatch, not score bonuses. |
| T2: every accepted constraint key is enforced or synthesis fails | PASS | Nested `before_input_context` and `after_input_context` are normalized and validated. Unknown or conflicting context keys raise synthesis failure instead of being ignored. |
| T3: every operator report carries a booked-evidence audit table | PASS | See "Booked-Evidence Audit" below. |
| T4: both-teams anchors are a named house-standard test | PASS | Focused tests cover `pressure_defending_team_role` for both home and away anchors. |
| T5: ledger flips require semantic correspondence | PASS | `row_result` carries the target's `semantic_correspondence`; `update_coverage_rows` refuses to flip a target that lacks it and records the correspondence in evidence. |

## Implementation Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Stage commits | PASS | Round-2 commits: `ef3cd7c` evidence contract, `4c68f96` catalog-drift attempt, `64d56c0` catalog restoration. This report is the final round-2 report commit. |
| Operator declaration and implementation | PASS | `src/tqe/runtime/operators/delta_across_anchor.py`; signature, anchor-status gate, subject evidence, source-frame evidence, signed delta, edge statuses, UNKNOWN-on-missing/same-frame semantics. |
| Registry citizenship | PASS | `src/tqe/runtime/operators/__init__.py`; `delta_across_anchor@0.1.0` remains registered from round 1. |
| Generic search insertion | PASS | `scripts/coverage_map/compiler_search_reachability.py`; generic operator insertion consumes target-declared contexts before synthesis and no longer uses provider-name score bonuses. |
| Acceptance target | PASS | `config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json`; now declares release-frame passer pressure before, reception-frame receiver pressure after, anchor status, pressure thresholds, and semantic correspondence. |
| Focused tests | PASS | 31 focused R1 tests passed, including R1-0/R1-1 regression and R1-2 round-2 probes. |
| Full suite and pinned gates | PASS | Full suite and pinned gate bundle passed on the committed tree. |

## Semantic Correspondence

Acceptance target: `r1_2_pressure_distance_delta_v0`

Coverage-map row: `pressure_change_after`

Declared meaning:

> Signed change in nearest-opponent distance from the passer at physical release
> to the receiver at controlled reception for the same controlled-pass anchor.

Source chain:

- Anchor source: `controlled_pass_episode.anchors`.
- Required anchor status: `pass_status == PASS`.
- Before relation: `pressure_on_carrier.anchor_evaluations` at
  `physical_release_frame_id`, with `carrier_id_field=passer_id`.
- After relation: `pressure_on_carrier.anchor_evaluations` at
  `controlled_reception_frame_id`, with `carrier_id_field=receiver_id`.
- Scalar: `nearest_defender_distance_m`.
- Unit: `metre`.

Claim boundary:

> Observed signed change in nearest-defender distance across declared
> release/reception frames only; no pressure quality, pass value, tactical
> causation, defender intent, or reception-success claim.

## Compiler-Reachable Proof

Command:

```bash
rm -rf /private/tmp/priori-r1-2-r2-search /private/tmp/priori-r1-2-r2-report.json
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_OUT_DIR=/private/tmp/priori-r1-2-r2-search \
TQE_SEARCH_REPORT=/private/tmp/priori-r1-2-r2-report.json \
PYTHONPATH=/private/tmp/priori-r1-2-r2/src \
/Users/luisrevilla/code/priori/.venv/bin/python \
  scripts/coverage_map/compiler_search_reachability.py
```

Result:

| Field | Round 1 rejected book | Round 2 corrected book |
| --- | --- | --- |
| Target | `r1_2_pressure_distance_delta_v0` | `r1_2_pressure_distance_delta_v0` |
| Coverage row | `pressure_change_after` | `pressure_change_after` |
| Result | `compiler_reachable` | `compiler_reachable` |
| Result count | `20` | `20` |
| Requested evidence failures | `0` | `0` |
| Terminal provider | `operator:delta_across_anchor` | `operator:delta_across_anchor` |
| Rules used | `generic_delta_across_anchor_operator`, `provider_field_backward_search` | `generic_delta_across_anchor_operator`, `provider_field_backward_search` |
| Document hash | `cd70182462a8cf9888822a76a4cb6c942dfd1fab47cf77754d8647cbc60c07a2` | `fa547d1821472a27554fc4fbbc0f53fe899c2674ed29f7aa8e37c68cf3e1a735` |
| Runtime trace hash | `43a69cbdaa2583b9d2cd0676495958baecaf567fd9639d0b3366c8607191cd3d` | `f00e18c1ac0cb4b60c8131384c927e041909f89274691f5da92cfd89120e5d77` |
| Runtime value count | `196` | `196` |

Round-2 corpus summary:

| Field | Value |
| --- | --- |
| Held-out success | `1 / 1` |
| Multi-step success | `1 / 1` |
| Global compiler-reachable rows | `7` |
| Global compiler-reachable pct | `0.9` |
| Global supported rows | `362` |
| Global supported pct | `48.9` |
| Delta discovery-space count | `1` |
| Selected anchor provider | `controlled_pass_episode` |
| Selected evaluator provider | `pressure_on_carrier` |
| Before frame field | `physical_release_frame_id` |
| After frame field | `controlled_reception_frame_id` |
| Before subject field | `passer_id` |
| After subject field | `receiver_id` |
| Value field | `nearest_defender_distance_m` |

The search target is non-updating (`TQE_SEARCH_UPDATE_LEDGER=0`). It proves
reachability without mutating the shared coverage ledger or generated compiler
search outputs.

## Booked-Evidence Audit

Round 1 booked 20 rows but failed substance review: 5/20 receiver-to-self or
wrong-team pressure rows, 9/20 uncontrolled anchors, 5/20 same-frame fallback
deltas, and 20/20 misreported evidence frames.

Round 2 books 20 rows with the following distribution:

| Check | Value |
| --- | --- |
| `delta_status` counts | `PASS: 20` |
| `delta_reason` counts | `delta_observed: 20` |
| Anchor status | `PASS: 20` |
| Missing before/after frame rows | `0` |
| Same-frame rows | `0` |
| Rows with declared subject correspondence | `20 / 20` |

Per-row audit:

| # | Delta m | Before: passer pressure at release | After: receiver pressure at reception | Anchor | Correspondence |
| --- | ---: | --- | --- | --- | --- |
| 1 | 3.024 | frame `14490`, `passer_id=DFL-OBJ-J01CP5`, 6.267m | frame `14515`, `receiver_id=DFL-OBJ-J014UG`, 9.291m | PASS | PASS |
| 2 | -5.652 | frame `14523`, `passer_id=DFL-OBJ-J014UG`, 7.799m | frame `14567`, `receiver_id=DFL-OBJ-002FXT`, 2.147m | PASS | PASS |
| 3 | 3.416 | frame `15033`, `passer_id=DFL-OBJ-J014UG`, 11.265m | frame `15081`, `receiver_id=DFL-OBJ-0028FW`, 14.681m | PASS | PASS |
| 4 | -5.057 | frame `15111`, `passer_id=DFL-OBJ-0028FW`, 8.445m | frame `15146`, `receiver_id=DFL-OBJ-J0130T`, 3.388m | PASS | PASS |
| 5 | 13.532 | frame `15153`, `passer_id=DFL-OBJ-J0130T`, 3.125m | frame `15190`, `receiver_id=DFL-OBJ-J014UG`, 16.657m | PASS | PASS |
| 6 | 9.281 | frame `15672`, `passer_id=DFL-OBJ-00268T`, 1.034m | frame `15756`, `receiver_id=DFL-OBJ-002GNH`, 10.315m | PASS | PASS |
| 7 | 4.583 | frame `17667`, `passer_id=DFL-OBJ-J014UG`, 8.822m | frame `17719`, `receiver_id=DFL-OBJ-00006V`, 13.405m | PASS | PASS |
| 8 | 0.449 | frame `18810`, `passer_id=DFL-OBJ-J01CP5`, 0.665m | frame `18826`, `receiver_id=DFL-OBJ-002GM1`, 1.114m | PASS | PASS |
| 9 | 2.021 | frame `20445`, `passer_id=DFL-OBJ-00006V`, 7.568m | frame `20464`, `receiver_id=DFL-OBJ-0000NZ`, 9.589m | PASS | PASS |
| 10 | 8.053 | frame `23224`, `passer_id=DFL-OBJ-0028FW`, 9.470m | frame `23259`, `receiver_id=DFL-OBJ-J014UG`, 17.523m | PASS | PASS |
| 11 | -2.297 | frame `23301`, `passer_id=DFL-OBJ-J014UG`, 11.674m | frame `23335`, `receiver_id=DFL-OBJ-0028FW`, 9.377m | PASS | PASS |
| 12 | 1.828 | frame `23664`, `passer_id=DFL-OBJ-0027XP`, 0.875m | frame `23670`, `receiver_id=DFL-OBJ-002651`, 2.703m | PASS | PASS |
| 13 | 7.448 | frame `23735`, `passer_id=DFL-OBJ-002651`, 0.459m | frame `23745`, `receiver_id=DFL-OBJ-002GEE`, 7.907m | PASS | PASS |
| 14 | 13.442 | frame `23809`, `passer_id=DFL-OBJ-002GEE`, 1.547m | frame `23881`, `receiver_id=DFL-OBJ-002GNH`, 14.989m | PASS | PASS |
| 15 | 2.193 | frame `24135`, `passer_id=DFL-OBJ-0000F8`, 0.582m | frame `24137`, `receiver_id=DFL-OBJ-J0130T`, 2.775m | PASS | PASS |
| 16 | 21.514 | frame `25813`, `passer_id=DFL-OBJ-00268T`, 5.377m | frame `25882`, `receiver_id=DFL-OBJ-002GNH`, 26.891m | PASS | PASS |
| 17 | -9.947 | frame `25997`, `passer_id=DFL-OBJ-002GNH`, 14.344m | frame `26032`, `receiver_id=DFL-OBJ-0027VS`, 4.397m | PASS | PASS |
| 18 | 8.942 | frame `26072`, `passer_id=DFL-OBJ-0027VS`, 0.576m | frame `26109`, `receiver_id=DFL-OBJ-0026UQ`, 9.518m | PASS | PASS |
| 19 | 5.121 | frame `26297`, `passer_id=DFL-OBJ-0026UQ`, 2.297m | frame `26301`, `receiver_id=DFL-OBJ-0027VS`, 7.418m | PASS | PASS |
| 20 | 4.126 | frame `26613`, `passer_id=DFL-OBJ-J01CP5`, 1.754m | frame `26615`, `receiver_id=DFL-OBJ-002GM1`, 5.880m | PASS | PASS |

## Focused Tests

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=/private/tmp/priori-r1-2-r2/src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r1_2_delta_across_anchor` | PASS | 15 tests in 9.964s. Covers operator behavior, anchor-status enforcement, same-frame UNKNOWN, evidence frame/subject reporting, both-team pressure role selection, context enforcement, and provider-name scoring guard. |
| `PYTHONPATH=/private/tmp/priori-r1-2-r2/src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_2_delta_across_anchor tests.test_r1_1_project_onto_axis -v` | PASS | 31 tests in 24.320s. Covers R1-0/R1-1 regression plus R1-2 round-2 probes. |

## Full Suite

| Command | Status | Notes |
| --- | --- | --- |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 402 tests in 345.210s. Attestation status `VERIFIED`, blocking reasons `[]`. |

## Pinned Gates

| Gate | Status | Notes |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `afl-substrate-q4-verify` | PASS | Frozen expectation comparison PASS; result count 2; requested evidence failures 0; runtime trace hash `c145a74cdba96536d5f294b60296bb1533abe04468cda28c7a265a85415425f6`. |
| `afl-substrate-q6-verify` | PASS | Frozen expectation comparison PASS; honest zero; requested evidence failures 0; runtime trace hash `11b9c4e6ead1c7799100da0be3cffd67eec9426c406f950b196f643502d80a7f`. |
| `afl-line-break-support-response-verify` | PASS | Frozen expectation comparison PASS; result count 1; requested evidence failures 0; runtime trace hash `30aad11448a29a990d80dc889aea7b62ef84754f9b5e0e8c7343104f8164c6e0`. |
| `afl-lane-occupancy-verify` | PASS | Report status PASS; lane occupancy tests 17 OK; runtime trace hash `39a0e3ddec60dd598d6d7392d4c046fd2fb2e032adac11e67d00ec759495aa61`. |
| `afl-09a-verify` | PASS | Included in pinned gate bundle; bundle exited 0. |
| `scp-0-verify` | PASS | Included in pinned gate bundle; semantic registry tests 58 OK. |
| `afl-passport-verify` | PASS | Report status PASS; passport generated hash matched stored hash `c92bcd1a94dd3636b5acbe985e7b157b61bd96d6024ea7efb5b005a6fed2f323`; semantic registry tests 58 OK. |

No pinned gate hash drift was introduced by the R1-2 round-2 commits.

## File Footprint

Tracked files changed relative to round-1 report commit `0116fa3`:

- `config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json`
- `delivery/packets/R1-2-REPORT.md`
- `scripts/coverage_map/compiler_search_reachability.py`
- `src/tqe/runtime/capabilities/teamshape_family.py`
- `src/tqe/runtime/operators/delta_across_anchor.py`
- `tests/test_r1_2_delta_across_anchor.py`

The round-2 catalog-drift correction leaves no diff in
`src/tqe/runtime/catalog.py` relative to `0116fa3`.

Local verification-only artifacts were not committed:

- temporary `data` symlink into the canonical corpus
- non-updating `/private/tmp/priori-r1-2-r2-search` proof output
- non-updating `/private/tmp/priori-r1-2-r2-report.json` proof report

## Summary

R1-2 round 2 is complete. The operator remains reachable through the generic
compiler-search path, but the booked evidence now proves the intended football
meaning instead of merely returning arithmetic rows. The target is still
`compiler_reachable` with 20 rows and zero requested-evidence failures; every
row now has controlled-pass anchor status, declared release/reception frames,
declared before/after subjects, and correspondence to the target semantics.
Full suite and pinned gates are green. No push was performed.
