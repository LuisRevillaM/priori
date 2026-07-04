# R1-2 Report - delta_across_anchor Operator

Branch: `packet/r1-2`
Frontier base: `834c2c9`
Packet: `delivery/packets/R1-2-delta-across-anchor.md`
ADR: `docs/adr/0013-r1-operator-era.md`
Push: no push, per direct-channel protocol.

## Result

PASS. R1-2 adds `delta_across_anchor@0.1.0`, wires it through the composition
operator registry, generalizes the compiler-search operator insertion point, and
earns a held-out multi-step compiler-reachable target through the generic search
path.

The operator compares declared before/after scalar evidence records for the
same anchor. Missing before/after records or scalar values become `UNKNOWN`;
source status failures remain `FAIL`; successful comparisons emit a signed delta
plus rising/falling edge statuses under declared threshold and hysteresis.

## Implementation Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Report-first commit | PASS | Commit `d316337` created this report before implementation. |
| Operator declaration and implementation | PASS | `src/tqe/runtime/operators/delta_across_anchor.py`; signature, required field parameters, explicit units policy, coverage/witness rule ids, UNKNOWN-on-missing semantics, signed delta, rising/falling edge statuses. |
| Registry citizenship | PASS | `src/tqe/runtime/operators/__init__.py`; signature and implementation registered. R1-0 registry tests updated for two real operators. |
| Generic search insertion | PASS | `scripts/coverage_map/compiler_search_reachability.py`; replaced the single `project_onto_axis` insertion with a registered operator-composition entrypoint. Operator fields are signature-derived by constraint kind; generated operator node outputs are signature-derived by operator name/version. |
| Acceptance target | PASS | `config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json`; reports against existing coverage row `pressure_change_after`, with declared semantic correspondence to nearest-defender-distance change from pass release to reception. |
| Focused tests | PASS | 25 focused R1 tests passed, covering R1-0/R1-1 regression and R1-2 operator/search behavior. |
| Full suite and pinned gates | PASS | Full suite and the standard pinned gates all passed on the committed code tree. |

## Declaration Edits

Tracked declaration/config edits:

- `src/tqe/runtime/operators/__init__.py`: added `delta_across_anchor@0.1.0` signature and implementation registration.
- `config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json`: added the R1-2 acceptance target.
- `scripts/coverage_map/compiler_search_reachability.py`: added supported constraint kind `delta_across_anchor`, signature-derived operator field maps, signature-derived operator output emission, and the generic delta builder.

No existing query-plan hash drift was introduced. The R1-0 hash-invariance spot
test (`test_existing_plan_hashes_are_unchanged_by_operator_scaffolding`) still
passes with the pinned `ball_side_block_shift` plan hashes unchanged.

## Operator Semantics

`delta_across_anchor@0.1.0` inputs:

- `anchors`: anchor collection.
- `before_evaluations`: anchor-keyed scalar evidence records.
- `after_evaluations`: anchor-keyed scalar evidence records.

Required parameters:

- `before_value_field`, `after_value_field`
- `before_status_field`, `after_status_field`
- `required_status_value`
- `edge_threshold`
- `hysteresis_margin`
- `value_unit`

Optional parameter:

- `missing_evidence_policy`, default `unknown`; only allowed value in v0 is
  `unknown`.

Evidence records include source field names, before/after statuses and values,
signed delta, threshold, hysteresis, value unit, source frame ids, source record
hashes, and witness node/output ids.

Behavior:

- Before/after record missing -> `delta_status=UNKNOWN`.
- Before/after scalar missing -> `delta_status=UNKNOWN`.
- Declared source status field missing -> `delta_status=UNKNOWN`.
- Declared source status present but not equal to required value ->
  `delta_status=FAIL`.
- Valid before/after scalars -> `delta_status=PASS` and
  `signed_delta=after-before`.
- Rising edge requires `before <= threshold - hysteresis` and
  `after >= threshold`.
- Falling edge requires `before >= threshold + hysteresis` and
  `after <= threshold`.

The v0 signature realizes the per-record scalar channel path. It does not add a
raw frame-signal sampling mode; frame-derived values must first be expressed as
anchor-keyed before/after evidence records.

## Semantic Correspondence

Acceptance target: `r1_2_pressure_distance_delta_v0`

Coverage-map row: `pressure_change_after`

Declared meaning:

> Signed change in nearest-defender distance from pass release to controlled
> reception for the same controlled-pass anchor.

Source chain:

- Anchor source: `controlled_pass_episode.anchors`.
- Before relation: `pressure_on_carrier.anchor_evaluations` at
  `physical_release_frame_id`.
- After relation: `pressure_on_carrier.anchor_evaluations` at
  `controlled_reception_frame_id`.
- Scalar: `nearest_defender_distance_m`.
- Unit: `metre`.

Claim boundary:

> Observed signed change in nearest-defender distance across declared
> release/reception frames only; no pressure quality, pass value, tactical
> causation, defender intent, or reception-success claim.

## Compiler-Reachable Proof

Command:

```bash
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_OUT_DIR=/private/tmp/priori-r1-2/generated/r1-2-search \
TQE_SEARCH_REPORT=/private/tmp/priori-r1-2/artifacts/autonomous/r1-2-search-report.json \
PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python \
  scripts/coverage_map/compiler_search_reachability.py
```

Result:

| Field | Value |
| --- | --- |
| Target | `r1_2_pressure_distance_delta_v0` |
| Coverage row | `pressure_change_after` |
| Result | `compiler_reachable` |
| Held-out success | `1 / 1` |
| Multi-step success | `1 / 1` |
| Result count | `20` |
| Requested evidence failures | `0` |
| Terminal provider | `operator:delta_across_anchor` |
| Rules used | `generic_delta_across_anchor_operator`, `provider_field_backward_search` |
| Providers used | `controlled_pass_episode`, `pressure_on_carrier`, `operator:delta_across_anchor` |
| Document hash | `cd70182462a8cf9888822a76a4cb6c942dfd1fab47cf77754d8647cbc60c07a2` |
| Runtime trace hash | `43a69cbdaa2583b9d2cd0676495958baecaf567fd9639d0b3366c8607191cd3d` |
| Runtime value count | `196` |

Discovery space:

| Field | Value |
| --- | --- |
| Delta discovery-space count | `1` |
| Candidate anchor provider | `controlled_pass_episode` |
| Candidate evaluator provider | `pressure_on_carrier` |
| Before frame field | `physical_release_frame_id` |
| After frame field | `controlled_reception_frame_id` |
| Before value field | `nearest_defender_distance_m` |
| After value field | `nearest_defender_distance_m` |

The search target is non-updating. It proves reachability without mutating the
shared coverage ledger or generated compiler-search outputs.

## Focused Tests

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_2_delta_across_anchor tests.test_r1_1_project_onto_axis -v` | PASS | 25 tests in 25.042s. Covers operator registry, no operator-name leakage into binder/executor, existing plan hash invariance, signed delta, rising/falling edges, hysteresis flicker suppression, missing after evidence UNKNOWN, source status FAIL, field-parameter bind rejection, real bind/execute, signature-derived search fields, generic search synthesis, unapplied delta constraint failure, and R1-1 regression tests. |

## Full Suite

| Command | Status | Notes |
| --- | --- | --- |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 396 tests in 347.018s. Attestation status `VERIFIED`, blocking reasons `[]`. |

## Pinned Gates

| Gate | Status | Notes |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `scp-0-verify` | PASS | Report status PASS; findings `[]`; semantic registry tests 58 OK. |
| `afl-passport-verify` | PASS | Report status PASS; passport generated hash matched stored hash `c92bcd1a94dd3636b5acbe985e7b157b61bd96d6024ea7efb5b005a6fed2f323`; registry tests 58 OK. |
| `afl-lane-occupancy-verify` | PASS | Report status PASS; 20 results; requested evidence failures 0; lane occupancy tests 17 OK. |
| `afl-line-break-support-response-verify` | PASS | Frozen expectation comparison PASS; result count 1; requested evidence failures 0; expectation file unchanged. |
| `afl-09a-verify` | PASS | Validation factory report PASS; line-break support and relative-position frozen targets PASS; validation factory tests 4 OK. |
| `afl-substrate-q4-verify` | PASS | Frozen expectation comparison PASS; result count 2; requested evidence failures 0; expectation file unchanged. |
| `afl-substrate-q6-verify` | PASS | Frozen expectation comparison PASS; honest zero; requested evidence failures 0; expectation file unchanged. |

## File Footprint

Tracked files changed relative to `834c2c9`:

- `config/compiler-reachability/r1-2-delta-across-anchor-targets.v0.json`
- `delivery/packets/R1-2-REPORT.md`
- `scripts/coverage_map/compiler_search_reachability.py`
- `src/tqe/runtime/operators/__init__.py`
- `src/tqe/runtime/operators/delta_across_anchor.py`
- `tests/test_r1_0_operator_scaffolding.py`
- `tests/test_r1_2_delta_across_anchor.py`

Local verification-only artifacts were not committed:

- temporary `data` symlink into the canonical corpus
- non-updating `generated/r1-2-search/` proof output

## Summary

R1-2 is complete. The operator is implemented, registry-bound, tested, and
reachable through the generalized compiler-search operator insertion path. The
acceptance target proves a real held-out multi-step composition against the
existing `pressure_change_after` coverage row, with complete evidence and no
ledger mutation. Full suite and pinned gates are green. No push was performed.
