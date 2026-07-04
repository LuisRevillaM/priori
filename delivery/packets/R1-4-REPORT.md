# R1-4 Report - window + trace_back_from_outcome Operator

Branch: `packet/r1-4`
Frontier base: `a0a1709`
Packet: `delivery/packets/R1-4-window-trace-back.md`
Round-2 review: `delivery/packets/R1-4-REVIEW.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including addenda and director rulings R-I..R-K
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW.

The canonical repository's `.git` directory is not writable from this sandbox, so
this work is committed in the writable clone at `/private/tmp/priori-r1-4-clone`,
branch `packet/r1-4`.

Stage-committed-from-first-commit was satisfied by `0a6a789`.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `0a6a789` | Stage-committed the R1-4 report skeleton before implementation. |
| `ad516f2` | Added `window@0.1.0`, registry wiring, search synthesis, target config, and focused tests. |
| `bf34f60` | Finalized the round-1 report. |
| `45c2171` | Enforced team-keyed R1-4 continuity and implemented R-I/R-K runtime fixes. |
| `7155e00` | Declared the team-key adapter relations in the semantic registry and regenerated SCP artifacts. |
| `2a09c72` | Refreshed the binder capability catalog after the wrapper relations entered the runtime catalog. |
| `f40feb1` | Declared product-projection waivers for the internal team-key adapters and regenerated SCP artifacts. |
| `(this commit)` | Replaced the report with round-2 committed-tree proof, audit, and verification evidence. |

## Round-2 Fix Summary

| Review item | Resolution |
| --- | --- |
| R-I / B1 / B2 - team dimension | `window` continuity now supports declared `anchor_team_role_field`, `continuity_team_role_field`, and `team_binding_policy=equal_team_role`. Opponent-team continuity can no longer cover an anchor and produce PASS. |
| Harness home hardcode | `compiler_search_reachability.py` now accepts `TQE_SEARCH_PERSPECTIVE_TEAM_ROLES`; the acceptance proof ran `home,away` and emits `execution_perspective_team_role` in results/evidence. |
| R-J - hashes | Only reproducing non-mutating proof hashes are published below. Copied-ledger hashes are intentionally not published. |
| R-K - phantom windows | Anchors outside observed frame bounds now return `UNKNOWN` with `anchor_outside_observed_bounds`; no fabricated one-frame windows. |
| R-K - fixed-duration fallback | Period bounds are derived from observed state frame ids and anchors only; continuity records are not used as a hidden fallback. |
| R-K - continuity labels | Non-fixed continuity records start as `UNKNOWN/continuity_not_evaluated` until real continuity evidence decides them. |
| R-K - truncation order | Trace-back continuity is bounded before truncation is judged, so truncation is evaluated on the continuity-backed window. |
| R-K - overlap policy | `continuity_overlap_policy` is declared. `latest_start` is deterministic; `unknown_on_ambiguous` returns UNKNOWN for ambiguous same-team overlaps. |
| R-K - break vs gap | Same-team continuity break inside the requested window returns FAIL. Missing same-team coverage returns UNKNOWN. Opponent-only continuity at the anchor returns FAIL via `continuity_team_mismatch`. |

## Implementation Summary

### Operator

`window@0.1.0` consumes declared anchor records and emits bounded temporal
window records around each anchor. It is a registry operator, not a catalog
primitive. It now accepts:

- `anchors`: anchor records containing declared frame/status/team fields.
- `continuity_evidence`: optional continuity records for policies requiring context continuity.
- parameters declaring window mode, frame-rate, anchor frame/status fields,
  truncation policy, continuity policy, continuity field names, team-binding
  fields, team-binding policy, and overlap policy.

Supported window modes:

- `before`
- `after`
- `around`
- `trace_back_from_outcome`

Supported continuity policies:

- `fixed_duration`: no continuity source is required.
- `same_possession`: supplied continuity records must cover the window under the declared policy.
- `same_team_control`: same declared evidence requirements as `same_possession`; it is a policy label over supplied continuity records, not an inferred clean-control detector.

Supported team-binding policy:

- `none`
- `equal_team_role`

Supported continuity overlap policy:

- `latest_start`
- `unknown_on_ambiguous`

Claim boundary: the operator claims only a declared bounded window and declared
continuity coverage over supplied records. It does not infer possession value,
clean individual control, pass value, tactical causation, intent, quality, or
optimality.

### Team-Key Adapters

The existing `controlled_pass_episode` and `possession_segment` primitive output
surfaces were not expanded. That avoided frozen plan-hash drift. Instead, two
internal adapter relations expose team-role fields for the R1-4 composition:

- `controlled_pass_team_keyed_anchors`: copies controlled-pass anchors and exposes the provider event `team_role`.
- `possession_segment_team_keyed_episodes`: copies possession segments and annotates the execution perspective `team_role`.

Both adapters are registered as internal helpers in the semantic registry:
`semantic=PROPOSED`, `product=NOT_EXPOSED`, and product/AI exposure denied. They
are not standalone coach-facing claims.

### Search Synthesis

The compiler search path supports generic `window` operator insertion. The
target declares all field names and policy values; synthesis applies every key or
fails. Provider names are not accepted as input constraints. Selected provider
names appear only as output metadata for audit.

Acceptance target: `r1_4_same_team_control_after_reception_v0`.

Unpinned discovery space:

| Field | Value |
| --- | --- |
| Target concept | `same_team_control_after` |
| Candidate source count | 1 |
| Selected anchor source | `controlled_pass_team_keyed_anchors.anchors` |
| Selected continuity source | `possession_segment_team_keyed_episodes.episodes` |
| Operator | `window@0.1.0` |
| Providers used | `controlled_pass_episode`, `controlled_pass_team_keyed_anchors`, `possession_segment`, `possession_segment_team_keyed_episodes`, `operator:window` |
| Rules used | `generic_window_operator`, `provider_field_backward_search` |
| Concept-name hint | `false` |
| Provider-name hint | `false` |

The generated operator constraint consumed:

- `window_mode=after`
- `anchor_frame_field=controlled_reception_frame_id`
- `before_duration_seconds=0.0`
- `after_duration_seconds=4.0`
- `frame_rate_hz=25.0`
- `anchor_status_field=controlled_pass_status`
- `anchor_status_value=PASS`
- `anchor_team_role_field=team_role`
- `continuity_policy=same_possession`
- `continuity_start_frame_field=possession_start_frame_id`
- `continuity_end_frame_field=possession_end_frame_id`
- `continuity_status_field=none`
- `continuity_status_value=PASS`
- `continuity_team_role_field=team_role`
- `team_binding_policy=equal_team_role`
- `continuity_overlap_policy=latest_start`
- `truncation_policy=emit_with_flag`
- `overlap_policy=preserve_all`

## Acceptance Proof

The final non-mutating proof ran on committed tree `f40feb1` with both team
perspectives:

```bash
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-4-window-targets.v0.json \
TQE_SEARCH_OUT_DIR=/private/tmp/r1-4-final-proof/out \
TQE_SEARCH_REPORT=/private/tmp/r1-4-final-proof/report.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_SHARED_NODE_CACHE=0 \
TQE_SEARCH_PERSISTENT_NODE_CACHE=0 \
TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away \
PYTHONPATH=src \
UV_CACHE_DIR=/private/tmp/uv-cache \
uv run python scripts/coverage_map/compiler_search_reachability.py
```

| Field | Value |
| --- | --- |
| Report status | PASS |
| Concept | `same_team_control_after` |
| Target | `r1_4_same_team_control_after_reception_v0` |
| Result | `compiler_reachable` |
| Result count | 40 |
| Requested evidence failures | 0 |
| Document hash | `0592e94a1f1bf20ccd0e0ccd10f3b3dc2d51088d9ecd0dd5c882130ae267c973` |
| Runtime trace hash | `269c94dc5a1243981fe17ad3951c6ce39e4c0499ae53a6ee83d9fc33daa6dfe0` |
| Runtime value count | 336 |
| Node-cache misses | 112 |
| Row-ledger hash | `6ca1fe83a7860dded7008c8d63b5ce7b57113ba357676861296d2a8862c73dbe` |
| Report hash | `8e821af1d54e6b7dc5049d30731bafd6f386943a10b7b7c91228d4222af29ef4` |

Ledger-copy delta was also run against a copied `generated/coverage-map.json`
with ledger mutation enabled. It moved compiler-reachable count `10 -> 11` on
the copied ledger only, with target result count `40` and requested evidence
failures `0`. Per R-J, no copied-ledger report or ledger hash is published.

## Canonical Counterexample

The review's canonical away-reception-covered-by-home-possession case no longer
PASSes.

Case: `J03WN1`, `secondHalf`, anchor frame `167670`, anchor team `away`.

| Execution role | Window status | Reason | Anchor team | Continuity team |
| --- | --- | --- | --- | --- |
| `away` | UNKNOWN | `continuity_evidence_not_covering_anchor` | `away` | none |
| `home` | FAIL | `continuity_team_mismatch` | `away` | `home` |

This proves the team dimension is active: the home possession segment cannot
cover the away controlled-pass anchor as a same-team PASS.

## Full Booked-Evidence Audit

Audit artifacts:

- `/private/tmp/r1-4-r2-window-audit.json`
- `/private/tmp/r1-4-r2-window-audit.md`

Population counts:

| Metric | Value |
| --- | --- |
| Window records audited | 8378 |
| Accepted rows | 40 |
| Status distribution | FAIL 1420, PASS 2274, UNKNOWN 4684 |
| Status by execution perspective | away: FAIL 696, PASS 1009, UNKNOWN 2484; home: FAIL 724, PASS 1265, UNKNOWN 2200 |
| Status by anchor team | away: FAIL 690, PASS 1009, UNKNOWN 2121; home: FAIL 730, PASS 1265, UNKNOWN 2563 |
| Accepted by anchor team | away 20, home 20 |

All 40 accepted rows have `anchor_team == continuity_team`, `window_status=PASS`,
`continuity_status=PASS`, and continuity coverage for the emitted window.

| n | result_id | exec_role | anchor_team | continuity_team | anchor_frame | window | continuity | seconds | status | team_ok | coverage_ok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `72f5f2233d60d43f` | away | away | away | 23670 | 23670-23770 | `e460200bf1fc9def` 23515-23985 | 4.04 | PASS/PASS | True | True |
| 2 | `33e9f4eb0f5be158` | away | away | away | 23745 | 23745-23845 | `e460200bf1fc9def` 23515-23985 | 4.04 | PASS/PASS | True | True |
| 3 | `1c4ac796df86e7c8` | away | away | away | 23881 | 23881-23981 | `e460200bf1fc9def` 23515-23985 | 4.04 | PASS/PASS | True | True |
| 4 | `eda58f9bb0c1fa7a` | away | away | away | 25882 | 25882-25982 | `1785a7cf98ea7898` 25725-26510 | 4.04 | PASS/PASS | True | True |
| 5 | `b6f232953c0b5a64` | away | away | away | 26032 | 26032-26132 | `1785a7cf98ea7898` 25725-26510 | 4.04 | PASS/PASS | True | True |
| 6 | `e876b094d67fe3cf` | away | away | away | 26109 | 26109-26209 | `1785a7cf98ea7898` 25725-26510 | 4.04 | PASS/PASS | True | True |
| 7 | `6af9504aca34aade` | away | away | away | 26301 | 26301-26401 | `1785a7cf98ea7898` 25725-26510 | 4.04 | PASS/PASS | True | True |
| 8 | `cc1c9ca1856fac42` | away | away | away | 27191 | 27191-27291 | `f495e90e926b5fb9` 27150-27345 | 4.04 | PASS/PASS | True | True |
| 9 | `e81d9e0166b8c5f1` | away | away | away | 44470 | 44470-44570 | `961113ff9aed1fcf` 44385-44705 | 4.04 | PASS/PASS | True | True |
| 10 | `84eb9fc2c0cd8b55` | away | away | away | 44535 | 44535-44635 | `961113ff9aed1fcf` 44385-44705 | 4.04 | PASS/PASS | True | True |
| 11 | `1890db46946f5520` | away | away | away | 46018 | 46018-46118 | `4827eabcf1a2eef7` 45890-46340 | 4.04 | PASS/PASS | True | True |
| 12 | `4f27321d1d9227b3` | away | away | away | 46123 | 46123-46223 | `4827eabcf1a2eef7` 45890-46340 | 4.04 | PASS/PASS | True | True |
| 13 | `99a4b913c0d3620e` | away | away | away | 46166 | 46166-46266 | `4827eabcf1a2eef7` 45890-46340 | 4.04 | PASS/PASS | True | True |
| 14 | `b02c6088c97ed04a` | away | away | away | 46205 | 46205-46305 | `4827eabcf1a2eef7` 45890-46340 | 4.04 | PASS/PASS | True | True |
| 15 | `06eb06bc3e13daea` | away | away | away | 47316 | 47316-47416 | `af38c9a35695a7d5` 47270-47690 | 4.04 | PASS/PASS | True | True |
| 16 | `cde428a7fc6c4e24` | away | away | away | 47551 | 47551-47651 | `af38c9a35695a7d5` 47270-47690 | 4.04 | PASS/PASS | True | True |
| 17 | `294235b226c4ce70` | away | away | away | 54081 | 54081-54181 | `e656c658a15dd0f9` 53925-54455 | 4.04 | PASS/PASS | True | True |
| 18 | `15d17c65616ea310` | away | away | away | 54184 | 54184-54284 | `e656c658a15dd0f9` 53925-54455 | 4.04 | PASS/PASS | True | True |
| 19 | `ba4e3de9bb80f707` | away | away | away | 56801 | 56801-56901 | `db944628e62b7e29` 56770-56970 | 4.04 | PASS/PASS | True | True |
| 20 | `bd3f3fd4df2befc9` | away | away | away | 59144 | 59144-59244 | `9f884cec410239c8` 59045-59270 | 4.04 | PASS/PASS | True | True |
| 21 | `dbc036d98a7dad6e` | home | home | home | 14515 | 14515-14615 | `1c886c450398078a` 14425-14640 | 4.04 | PASS/PASS | True | True |
| 22 | `8f4b95a8275e1364` | home | home | home | 15081 | 15081-15181 | `0789565b02b02d0b` 14990-15320 | 4.04 | PASS/PASS | True | True |
| 23 | `87c5c138e4bfe89c` | home | home | home | 15146 | 15146-15246 | `0789565b02b02d0b` 14990-15320 | 4.04 | PASS/PASS | True | True |
| 24 | `17c2772dc1ee97f6` | home | home | home | 15190 | 15190-15290 | `0789565b02b02d0b` 14990-15320 | 4.04 | PASS/PASS | True | True |
| 25 | `f03c82875106d2ab` | home | home | home | 17719 | 17719-17819 | `1e935c309e35a17f` 17620-17950 | 4.04 | PASS/PASS | True | True |
| 26 | `be6fc912bf1c901e` | home | home | home | 20464 | 20464-20564 | `2bedb750d007105d` 20355-20700 | 4.04 | PASS/PASS | True | True |
| 27 | `d89f89053592ea93` | home | home | home | 23259 | 23259-23359 | `69d6e4448e95db2d` 22940-23410 | 4.04 | PASS/PASS | True | True |
| 28 | `1eac9f8d0d894806` | home | home | home | 26615 | 26615-26715 | `6b46abfd64734332` 26515-26735 | 4.04 | PASS/PASS | True | True |
| 29 | `f1b00ebb39ea9d75` | home | home | home | 28220 | 28220-28320 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 30 | `6d9864d1c2161852` | home | home | home | 28299 | 28299-28399 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 31 | `753da64c0979922f` | home | home | home | 28387 | 28387-28487 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 32 | `7404fdbab5f91da6` | home | home | home | 28451 | 28451-28551 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 33 | `7e48d55f8c04dfbb` | home | home | home | 28550 | 28550-28650 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 34 | `ec6dfdcc8d053473` | home | home | home | 28639 | 28639-28739 | `6064d9504e58186d` 27965-28965 | 4.04 | PASS/PASS | True | True |
| 35 | `29a69dd86b7fa30c` | home | home | home | 29859 | 29859-29959 | `7258ea1474fb3b50` 29550-30085 | 4.04 | PASS/PASS | True | True |
| 36 | `478f1d35189f3e9f` | home | home | home | 29883 | 29883-29983 | `7258ea1474fb3b50` 29550-30085 | 4.04 | PASS/PASS | True | True |
| 37 | `cd3a9b772ec7e18f` | home | home | home | 30266 | 30266-30366 | `8041aa58d38ec291` 30160-30420 | 4.04 | PASS/PASS | True | True |
| 38 | `33c6499aa3c6687f` | home | home | home | 31121 | 31121-31221 | `b6f376935d31cada` 31030-31425 | 4.04 | PASS/PASS | True | True |
| 39 | `40b83327c439a762` | home | home | home | 31215 | 31215-31315 | `b6f376935d31cada` 31030-31425 | 4.04 | PASS/PASS | True | True |
| 40 | `ab918f9e9acf4026` | home | home | home | 31300 | 31300-31400 | `b6f376935d31cada` 31030-31425 | 4.04 | PASS/PASS | True | True |

## Behavioral Boundaries

- A trace-back window is a claim about unbroken declared context, not a visual clip span.
- Missing same-team continuity coverage yields UNKNOWN.
- Opponent-team continuity at the anchor yields FAIL, not PASS.
- Provider names are not synthesis inputs. Search-selected providers are retained only as output metadata for audit.
- Boundary truncation is visible in evidence and policy controlled.
- The operator does not create continuity evidence; it evaluates supplied continuity records under declared policy.
- The internal team-key adapter relations are not product-exposed claims.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run python -m unittest tests.test_r1_4_window tests.test_r1_0_operator_scaffolding -v` | PASS | 24 tests in 9.155s; focused runtime/operator coverage. |
| `TQE_SEARCH_TARGETS=config/compiler-reachability/r1-4-window-targets.v0.json ... TQE_SEARCH_PERSPECTIVE_TEAM_ROLES=home,away uv run python scripts/coverage_map/compiler_search_reachability.py` | PASS | `compiler_reachable`, 40 rows, 0 requested evidence failures; reproducing hashes published above. |
| Ledger-copy compiler proof | PASS | Compiler-reachable count `10 -> 11` on copied ledger only; hashes intentionally unpublished per R-J. |
| Full booked-evidence audit | PASS | 8378 records audited; accepted rows split away 20 / home 20; all accepted rows same-team and continuity-covered. |
| Canonical counterexample probe | PASS | J03WN1 secondHalf 167670: away execution UNKNOWN, home execution FAIL; never PASS. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make afl-substrate-q6-verify` | PASS | Honest-zero intact; runtime trace hash `b9e24dabc23931c0de15ee665d39fcd15a6ce30de02c0fa932a012f332695f8c`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make scp-0-verify` | PASS | SCP-0 status PASS; 58 tests OK; no registry findings or generated drift. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make m1-1-gate-a-verify` | PASS | 450 binder validation rows pass after capability-catalog refresh. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make test` | PASS | 435 tests in 347.681s; runtime attestation `VERIFIED`, blocking reasons `[]`. |
