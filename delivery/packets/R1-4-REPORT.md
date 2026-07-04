# R1-4 Report - window + trace_back_from_outcome Operator

Branch: `packet/r1-4`
Frontier base: `a0a1709`
Packet: `delivery/packets/R1-4-window-trace-back.md`
ADR: `docs/adr/0013-r1-operator-era.md`, including all addenda
Push: no push, per direct-channel protocol.

## Result

READY FOR REVIEW.

The canonical repository's `.git` directory is not writable from this sandbox,
so this work is committed in the writable clone at
`/private/tmp/priori-r1-4-clone`, branch `packet/r1-4`.

Stage-committed-from-first-commit was satisfied by `0a6a789`.

## Commit Ledger

| Commit | Purpose |
| --- | --- |
| `0a6a789` | Stage-committed the R1-4 report skeleton before implementation. |
| `ad516f2` | Added `window@0.1.0`, registry wiring, search synthesis, target config, and focused tests. |
| `(this commit)` | Finalized the R1-4 report from committed-tree proof and verification. |

## Implementation Summary

### Operator

`window@0.1.0` consumes a declared anchor collection and emits bounded temporal
window records around each anchor. The signature is a registry operator, not a
catalog primitive. It accepts:

- `anchors`: anchor records containing the declared anchor frame/status fields.
- `continuity_evidence`: optional continuity records for policies that require
  context continuity.
- parameters declaring the window mode, frame-rate, anchor frame field,
  truncation policy, continuity policy, continuity field names, and overlap
  policy.

Supported window modes:

- `before`
- `after`
- `around`
- `trace_back_from_outcome`

Supported continuity policies:

- `fixed_duration`: no continuity source is required.
- `same_possession`: the emitted window must be covered by a supplied continuity
  record, or the row becomes `UNKNOWN`.
- `same_team_control`: same declared evidence requirements as
  `same_possession`; it is a policy label over supplied continuity records, not
  an inferred control detector.

Boundary behavior is declared by `truncation_policy`:

- `emit_with_flag`: emit the boundary-clipped window and set
  `truncated_start` / `truncated_end`.
- `unknown`: boundary truncation poisons the claim to `UNKNOWN`.

Units are explicit. Durations are derived from frame spans with the declared
`frame_rate_hz`. Emitted windows are inclusive frame intervals, so a 4.0 second
request at 25 Hz emits 101 frames and `4.04` seconds when the anchor frame is
included.

Claim boundary: the operator claims only the declared bounded window and declared
continuity coverage over supplied records. It does not infer possession value,
clean individual control, pass value, tactical causation, intent, quality, or
optimality.

### Search Synthesis

The compiler search path now supports the `window` composition constraint
through generic operator insertion. The target contract declares field names and
policy values; synthesis applies every key or fails. Provider names are not
accepted as input constraints. Selected provider names appear only as post-hoc
output metadata.

Acceptance target: `r1_4_same_team_control_after_reception_v0`.

Unpinned discovery space:

| Field | Value |
| --- | --- |
| Target concept | `same_team_control_after` |
| Candidate source count | 1 |
| Selected anchor source | `controlled_pass_episode.anchors` |
| Selected continuity source | `possession_segment.episodes` |
| Operator | `window@0.1.0` |
| Providers used | `controlled_pass_episode`, `possession_segment`, `operator:window` |
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
- `truncation_policy=emit_with_flag`
- `continuity_policy=same_possession`
- `continuity_start_frame_field=possession_start_frame_id`
- `continuity_end_frame_field=possession_end_frame_id`
- `continuity_status_field=none`
- `continuity_status_value=PASS`
- `overlap_policy=preserve_all`

## Declaration Edits

| File | Declaration |
| --- | --- |
| `src/tqe/runtime/operators/window.py` | Defines `WINDOW_SIGNATURE` and `execute_window`. |
| `src/tqe/runtime/operators/__init__.py` | Registers the `window` operator signature and lazy implementation mapping. |
| `scripts/coverage_map/compiler_search_reachability.py` | Adds generic search insertion for `kind=window`, field validation, and provider-blind candidate discovery. |
| `config/compiler-reachability/r1-4-window-targets.v0.json` | Declares the held-out acceptance target and claim boundary. |
| `tests/test_r1_4_window.py` | Adds operator, binder, synthesis, and executor-path tests. |
| `tests/test_r1_0_operator_scaffolding.py` | Updates the operator registry ratchet for `window`. |

No catalog primitive behavior was changed.

## Acceptance Proof

Two non-mutating proof runs were executed from the committed tree in different
temp directories:

- `/private/tmp/r1-4-proof-a`
- `/private/tmp/r1-4-proof-b`

Both used:

```bash
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-4-window-targets.v0.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_SHARED_NODE_CACHE=0 \
TQE_SEARCH_PERSISTENT_NODE_CACHE=0 \
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
| Result count | 20 |
| Requested evidence failures | 0 |
| Document hash | `7e7ccc335b9bdd5ae166839282b06729d70993bb2af8a4b449e10674fc90dd4f` |
| Runtime trace hash | `0862072f0efdace2621656c74a58cb7d3bc6ee98cfde26c3b826d76950d27dc1` |
| Row-ledger hash, both temp dirs | `cbb140b7992b6450bd15604c373dbc3a423e685c132b263397a4efceaa0025b2` |
| Report hash, both temp dirs | `b9b5186dac65e6aa204eee5c9b3f651ee09c2b4815239ed929b03478d359dc51` |
| Unpinned discovery count | 1 |

Ledger-copy delta command used the same target against a copied
`generated/coverage-map.json` with ledger mutation enabled.

| Field | Value |
| --- | --- |
| Temp dir | `/private/tmp/r1-4-proof` |
| Before compiler-reachable count | 10 |
| After compiler-reachable count | 11 |
| Supported count | 362 / 741 (48.9%) |
| After compiler-reachable pct | 1.5% |
| Target result count | 20 |
| Target requested evidence failures | 0 |
| Runtime trace hash | `0862072f0efdace2621656c74a58cb7d3bc6ee98cfde26c3b826d76950d27dc1` |
| Ledger-copy hash | `a785227efea29aeedf461534bbfeccce6c95dfd977cc54f4cfdfdea9f690d6c2` |
| Row-ledger hash | `cbb140b7992b6450bd15604c373dbc3a423e685c132b263397a4efceaa0025b2` |
| Report hash | `653884b6e33ce494cf15fdccfa6674482c56ac442ddd0bea39c35acfa3bf3b21` |

No tracked coverage ledger was mutated; the real flip remains a director action.

## Full Booked-Evidence Audit

Audit artifact source: `/private/tmp/r1-4-window-audit.json` and
`/private/tmp/r1-4-window-audit.md`.

Method: execute the generated proof plan, then for every emitted result row
verify the requested window bounds, emitted window bounds, continuity evidence
id, continuity segment bounds, truncation flags, and PASS statuses. All 20 rows
had `requested == window`, `window_start >= continuity_start`,
`window_end <= continuity_end`, `window_status=PASS`, and
`continuity_status=PASS`.

| n | result_id | anchor_frame | requested | window | seconds | continuity | status | trunc | coverage_ok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `7297ec690a10d34a` | 14515 | 14515-14615 | 14515-14615 | 4.04 | `1c886c450398078a` 14425-14640 | PASS/PASS | False/False | True |
| 2 | `4c38ca6fed51f9ab` | 15081 | 15081-15181 | 15081-15181 | 4.04 | `0789565b02b02d0b` 14990-15320 | PASS/PASS | False/False | True |
| 3 | `8c3a06079e58f7e4` | 15146 | 15146-15246 | 15146-15246 | 4.04 | `0789565b02b02d0b` 14990-15320 | PASS/PASS | False/False | True |
| 4 | `11b4c5c861c1596b` | 15190 | 15190-15290 | 15190-15290 | 4.04 | `0789565b02b02d0b` 14990-15320 | PASS/PASS | False/False | True |
| 5 | `c82a69c8ba12d9e3` | 17719 | 17719-17819 | 17719-17819 | 4.04 | `1e935c309e35a17f` 17620-17950 | PASS/PASS | False/False | True |
| 6 | `c8cb858497eebb3a` | 20464 | 20464-20564 | 20464-20564 | 4.04 | `2bedb750d007105d` 20355-20700 | PASS/PASS | False/False | True |
| 7 | `6b3e188e8dd6330a` | 23259 | 23259-23359 | 23259-23359 | 4.04 | `69d6e4448e95db2d` 22940-23410 | PASS/PASS | False/False | True |
| 8 | `2480fba99cb7a1d6` | 26615 | 26615-26715 | 26615-26715 | 4.04 | `6b46abfd64734332` 26515-26735 | PASS/PASS | False/False | True |
| 9 | `e5fe800944bb10d5` | 28220 | 28220-28320 | 28220-28320 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 10 | `35904419c25b15a5` | 28299 | 28299-28399 | 28299-28399 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 11 | `5e49e11718adfccf` | 28387 | 28387-28487 | 28387-28487 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 12 | `e5ad6d3e462d150f` | 28451 | 28451-28551 | 28451-28551 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 13 | `6d81c01a1c4b4449` | 28550 | 28550-28650 | 28550-28650 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 14 | `f77497c533933246` | 28639 | 28639-28739 | 28639-28739 | 4.04 | `6064d9504e58186d` 27965-28965 | PASS/PASS | False/False | True |
| 15 | `cab19bc3f5979ac4` | 29859 | 29859-29959 | 29859-29959 | 4.04 | `7258ea1474fb3b50` 29550-30085 | PASS/PASS | False/False | True |
| 16 | `8ef75d1f484c1702` | 29883 | 29883-29983 | 29883-29983 | 4.04 | `7258ea1474fb3b50` 29550-30085 | PASS/PASS | False/False | True |
| 17 | `2b5957229c65bf1c` | 30266 | 30266-30366 | 30266-30366 | 4.04 | `8041aa58d38ec291` 30160-30420 | PASS/PASS | False/False | True |
| 18 | `c32345896c66eedb` | 31121 | 31121-31221 | 31121-31221 | 4.04 | `b6f376935d31cada` 31030-31425 | PASS/PASS | False/False | True |
| 19 | `d3febd99d6d24d1f` | 31215 | 31215-31315 | 31215-31315 | 4.04 | `b6f376935d31cada` 31030-31425 | PASS/PASS | False/False | True |
| 20 | `b8322a39474ee8cc` | 31300 | 31300-31400 | 31300-31400 | 4.04 | `b6f376935d31cada` 31030-31425 | PASS/PASS | False/False | True |

## Behavioral Boundaries

- A trace-back window is a claim about unbroken declared context, not a visual
  clip span. Missing continuity coverage yields `UNKNOWN`.
- Provider names are not synthesis inputs. The search-selected providers are
  retained only as output metadata for audit.
- Boundary truncation is visible in evidence and policy controlled.
- The operator preserves both home and away anchors without collapsing witness
  identity.
- The operator does not create continuity evidence; it only evaluates the
  supplied continuity record under the declared policy.

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/uv-cache uv run python -m unittest tests.test_r1_4_window tests.test_r1_0_operator_scaffolding -v` | PASS | 18 tests in 10.184s. |
| Non-mutating compiler proof, two temp dirs | PASS | `compiler_reachable`, 20 rows, 0 requested evidence failures; row-ledger/report hashes reproduced exactly. |
| Ledger-copy compiler proof | PASS | Compiler-reachable count 10 -> 11 on copied ledger only. |
| Full booked-evidence audit | PASS | All 20 window rows covered by declared continuity evidence. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make afl-substrate-q6-verify` | PASS | Honest-zero remains intact; runtime trace hash `b9e24dabc23931c0de15ee665d39fcd15a6ce30de02c0fa932a012f332695f8c`. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make scp-0-verify` | PASS | SCP-0 status PASS; 58 tests OK; no tracked generated drift. |
| `UV_CACHE_DIR=/private/tmp/uv-cache make test` | PASS | 429 tests in 366.817s; runtime attestation `VERIFIED`, blocking reasons `[]`. |
