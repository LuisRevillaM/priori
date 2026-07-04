# R1-1 Report - project_onto_axis Operator

Branch: `packet/r1-1`
Frontier base: `8431afb`
Packet: `delivery/packets/R1-1-project-onto-axis.md`
ADR: `docs/adr/0013-r1-operator-era.md`
Push: no push, per direct-channel protocol.

## Result

R1-1 is complete. `project_onto_axis@0.1.0` is registered as the first real
R1 operator, the round-2 semantic review items are implemented, and the
acceptance concept `support_depth` now executes through a true compiler
composition:

```text
controlled_pass_episode
  -> support_arrival_point_pair
  -> operator:project_onto_axis
  -> eq(PASS)
```

The copied coverage ledger moved from 7 to 8 `compiler_reachable` rows. The
existing frozen `line_break_support_response` plan hash/result id were restored
after the additive point-pair design, so existing query plans do not drift.
Round 3 fixes the proof-plan synthesis path: declared `relation_on_anchor`
constraints are applied to the generated proof plan, unsupported constraint keys
fail synthesis, and the regenerated proof still earns the 8.

## Scope

The packet implements the first operator-era composition without changing
existing capability behavior. Round 2 corrected the operator semantics and the
acceptance composition:

- Goalward orientation is declared and evidence-backed by acting team.
- `toward_point` no longer fabricates a `(0, 0)` fallback.
- All declared axes are tested.
- The acceptance composition realizes the actual `support_depth` meaning:
  the first observed supporter's goalward depth relative to the carrier/reference
  point.
- The discovery space is reported honestly from the compiler-search output.
- Round 3 applies the target's declared relation constraints during proof-plan
  synthesis instead of letting catalog defaults stand in.
- Tool-side point-field defaults (`release_ball_point` / `reception_ball_point`)
  were removed from vector-projection synthesis.
- The compiler-search projection field list is derived from
  `PROJECT_ONTO_AXIS_SIGNATURE`.
- Angle policy is explicit: `angle_between_degrees` is emitted in degrees, and
  every projection record carries `angle_unit: "degrees"` including UNKNOWN
  records. The operator does not emit radians.

## Commit Ledger

| Commit | Status | Contents |
| --- | --- | --- |
| `7313025` | PASS | Initial report-first commit for R1-1. |
| `1360958` | PASS | Added `project_onto_axis` operator and tests. |
| `c0279b0` | PASS | Added reachability target and compiler-search composition. |
| `9ec670c` | PASS | Reported round-1 verification. |
| `3357da7` | PASS | Round-2 report-first commit. |
| `05d658f` | PASS | Fixed support-depth projection semantics and operator field validation. |
| `5605d3a` | PASS | Regenerated semantic projections for the first round-2 shape. |
| `c2002be` | PASS | Moved support point-pair fields to additive `support_arrival_point_pair`. |
| `15abb98` | PASS | Regenerated projections after the additive point-pair design. |
| `853cf27` | PASS | Reported round-2 remediation and verification. |
| `7df33ad` | PASS | Applied declared proof constraints in synthesis and added round-3 probes. |

This final report commit is report-only.

## Implementation Ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Operator registry | PASS | `src/tqe/runtime/operators/__init__.py` registers `project_onto_axis@0.1.0`. |
| Operator signature | PASS | Input is `EPISODE_SET / ANCHOR_REF / COLLECTION / ANCHOR`; outputs are witnessed projection records plus status/scalar frame signals. |
| Orientation basis | PASS | Parameters include `orientation_basis` with default `acting_team`; evidence records emit `orientation_basis`, `orientation_team_role`, and `attack_x_sign`. |
| Acting-team goalward axis | PASS | Goalward projection resolves attack direction from the source record's `acting_team_field`; tests cover home and away mirror behavior. |
| `toward_point` fabrication fix | PASS | Missing reference point now returns UNKNOWN with reason `reference_point_missing`; no `(0, 0)` fallback remains. |
| Lane-normal axis | PASS | `along_lane_normal` uses record-backed lane start/end fields and returns UNKNOWN on zero-length lane geometry. |
| Zero-length source vector | PASS | Source point-pair with no vector returns UNKNOWN with reason `zero_length_source_vector`. |
| Required source status | PASS | Operator can require source status/value before projection; acceptance target requires `support_point_pair_status == PASS`. |
| Field-parameter binder guard | PASS | Operator `_field` parameters are validated against source output/evidence fields; undeclared fields fail bind with `operator_field_parameter_not_in_input`. |
| Additive support point-pair view | PASS | New `support_arrival_point_pair@0.1.0` exposes the first supporter/reference point pair while leaving `support_arrival_relation` frozen. |
| True support-depth target | PASS | Target declares source `support_arrival_point_pair.anchor_evaluations`, point pair `first_support_reference_point -> first_supporter_point`, axis `acting-team goalward`, and orientation team field `candidate_team_role`. |
| Relation constraint application | PASS | Synthesized `support_arrival_point_pair` node now carries the target's 30m distance, 3s arrival, 0s duration, and upstream `controlled_pass_status == PASS` parameters. |
| Unapplied constraint guard | PASS | Unsupported `relation_on_anchor` keys now raise a synthesis `missing_constraint` failure instead of being dropped. |
| Vector field defaults removed | PASS | `start_point_field`, `end_point_field`, and goalward `acting_team_field` must be declared by the vector-projection constraint; no pass-field fallback is allowed. |
| Signature-derived field list | PASS | Search's `PROJECT_ONTO_AXIS_FIELDS` is derived from `PROJECT_ONTO_AXIS_SIGNATURE.outputs`; tests assert parity. |
| Angle-units policy | PASS | Projection records use numeric `angle_between_degrees` and `angle_unit: "degrees"`; no radians path exists. |
| Existing plan drift | PASS | Frozen `line_break_support_response` plan uses the original relation and restored its original bound plan hash/result id. |

## Catalog / IR / Search Edit Enumeration

| Surface | Change | Reason |
| --- | --- | --- |
| `src/tqe/runtime/operators/project_onto_axis.py` | Adds the operator signature and implementation. | R1-1 operator. |
| `src/tqe/runtime/operators/__init__.py` | Registers the operator explicitly. | R1 operator registry. |
| `src/tqe/runtime/binder.py` | Validates operator field parameters against source outputs/evidence. | Prevents silently binding projections to fields not produced by the input channel. |
| `src/tqe/runtime/capabilities/offball_family.py` | Adds `relation_support_arrival_point_pair`. | Additive support point-pair view for the acceptance composition. |
| `src/tqe/runtime/capabilities/__init__.py` | Registers the support point-pair capability implementation. | Runtime wiring. |
| `src/tqe/runtime/catalog.py` | Declares `support_arrival_point_pair@0.1.0`. | Catalog visibility for compiler search. |
| `semantic-registry/registry.yaml` | Adds semantic registry binding and AI projection waiver for the additive view. | Semantic projection consistency. |
| `scripts/coverage_map/compiler_search_reachability.py` | Adds generic `vector_projection` composition, discovery metadata, round-3 relation-constraint enforcement, required vector field declarations, and signature-derived operator fields. | Lets search discover point-pair providers and compose them through the operator without dropping declared target constraints. |
| `config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json` | Declares the acceptance target and semantic correspondence. | R1-1 reachability proof. |
| `tests/test_r1_0_operator_scaffolding.py` | Updates the operator registry ratchet from zero to one. | R1-1 supersedes R1-0 empty registry while preserving boundary guards. |
| `tests/test_r1_1_project_onto_axis.py` | Adds the operator, end-to-end composition, synthesis constraint, unapplied-key, and signature-field parity tests. | Round-2 and round-3 semantic coverage. |

Generated semantic artifacts were regenerated after the additive point-pair
design:

- `generated/capability-catalog.json`
- `generated/semantic-registry/*.json`
- `semantic-registry/registry.lock.json`
- `artifacts/scp-0/verification-report.json`

## Acceptance Composition / Reachability Delta

Non-updating proof command:

```text
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json \
TQE_SEARCH_UPDATE_LEDGER=0 \
TQE_SEARCH_OUT_DIR=/private/tmp/priori-r1-1-search-r3 \
TQE_SEARCH_REPORT=/private/tmp/priori-r1-1-search-r3-report.json \
PYTHONPATH=src ./.venv/bin/python scripts/coverage_map/compiler_search_reachability.py
```

Copied-ledger update command:

```text
cp generated/coverage-map.json /private/tmp/r1-1-coverage-map-r3.json
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json \
TQE_SEARCH_LEDGER=/private/tmp/r1-1-coverage-map-r3.json \
TQE_SEARCH_UPDATE_LEDGER=1 \
TQE_SEARCH_OUT_DIR=/private/tmp/priori-r1-1-search-r3-update \
TQE_SEARCH_REPORT=/private/tmp/priori-r1-1-search-r3-update-report.json \
PYTHONPATH=src ./.venv/bin/python scripts/coverage_map/compiler_search_reachability.py
```

Result:

| Metric | Value |
| --- | --- |
| Target | `r1_1_goalward_axis_projection_v0` |
| Concept row | `support_depth` |
| Result | `compiler_reachable` |
| Result count | 20 |
| Requested evidence failures | 0 |
| Providers used | `controlled_pass_episode`, `support_arrival_point_pair`, `operator:project_onto_axis` |
| Terminal provider | `operator:project_onto_axis` |
| Rules used | `generic_relation_on_anchor`, `generic_vector_projection_operator`, `provider_field_backward_search`, `typed_anchor_provider_discovery` |
| Failure taxonomy | `null` |
| Discovery-space count | 1 |
| Candidate output | `support_arrival_point_pair.anchor_evaluations` |
| Candidate fields | `candidate_team_role`, `first_support_reference_point`, `first_supporter_point`, `support_point_pair_status` |
| Selected output | `support_arrival_point_pair.anchor_evaluations` |
| Document hash | `5158d67088773ac758a2c59eb8d6de32456f334e0a4883dcea6d156b72360521` |
| Runtime trace hash | `adc3a14f095e2318c605bd593a00cac4d29edf197adc72d4d0a79126ab59ca0e` |

Applied `relation_on_anchor` parameters in the regenerated proof plan:

| Parameter | Value |
| --- | --- |
| `anchor_frame_field` | `controlled_reception_frame_id` |
| `candidate_scope` | `perspective_outfield` |
| `support_region_mode` | `WITHIN_DISTANCE_OF_REFERENCE_POINT` |
| `maximum_arrival_seconds` | `3.0` |
| `minimum_duration_seconds` | `0.0` |
| `maximum_support_distance_m` | `30.0` |
| `minimum_supporting_players` | `1.0` |
| `required_anchor_status_field` | `controlled_pass_status` |
| `required_anchor_status_value` | `PASS` |

Reachability delta measured by the copied-ledger update path:

| Ledger | `compiler_reachable` count | `compiler_reachable` pct | Supported count | Supported pct |
| --- | ---: | ---: | ---: | ---: |
| Baseline generated ledger | 7 | n/a | 362 | 48.9 |
| Copied ledger after R1-1 round-3 update | 8 | 1.1 | 362 | 48.9 |

Sample/held-out counters from the target-specific run:

| Counter | Value |
| --- | ---: |
| `sample_target_count` | 1 |
| `sample_compiler_reachable_count` | 1 |
| `sample_compiler_reachable_pct` | 100.0 |
| `held_out_target_count` | 1 |
| `held_out_compiler_reachable_count` | 1 |
| `held_out_compiler_reachable_pct` | 100.0 |
| `held_out_multi_step_target_count` | 1 |
| `held_out_multi_step_compiler_reachable_count` | 1 |

The non-updating report still shows the generated ledger's global
`compiler_reachable_count` of 7 because `TQE_SEARCH_UPDATE_LEDGER=0`. The
copied-ledger update run is the measured delta proof.

## Existing Plan / Hash Drift Proof

The final design avoids changing `support_arrival_relation`; it adds
`support_arrival_point_pair` as a new source for the R1-1 acceptance target.
That restored the frozen `line_break_support_response` result:

| Field | Value |
| --- | --- |
| Gate | `afl-line-break-support-response-verify` |
| Status | PASS |
| Bound plan hash | `999fb9ce9e5d89be3f83475ea0f2c8813ce3bfbfe3792f2ce390c7bc276df108` |
| Result id | `f3b2568e54f1a32a` |
| Result signature hash | `c330d685d65bff2221a8ed920f10d8987d51dfd1f069778298fdd27d584e1ea9` |
| Requested evidence failures | 0 |

This proves the new acceptance composition is additive and existing frozen
plans do not silently move to the new view.

## Verification

Focused tests:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src ./.venv/bin/python -m unittest tests.test_r1_1_project_onto_axis -v` | PASS | 10 tests in 13.818s. Covers all axes, acting-team orientation, `toward_point` UNKNOWN, lane-normal zero length UNKNOWN, source zero length UNKNOWN, field-param bind rejection, real bind/execute composition, declared relation-constraint application, unapplied-key failure, and signature-derived projection fields. |
| R1-1 compiler-search non-updating proof | PASS | Target became `compiler_reachable`; 20 results; zero requested evidence failures. |
| R1-1 copied-ledger update proof | PASS | Copied ledger moved `compiler_reachable` from 7 to 8. |

Full suite on the committed code tree:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHON=.venv/bin/python make test` | PASS | 387 tests in 329.358s; attestation `VERIFIED`; no blockers. |

Pinned gates on the committed code tree:

| Gate | Status | Notes |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`; no blocking reasons. |
| `scp-0-verify` | PASS | Report status PASS. |
| `afl-passport-verify` | PASS | Report status PASS. |
| `afl-lane-occupancy-verify` | PASS | Report status PASS. |
| `afl-line-break-support-response-verify` | PASS | Frozen expectation comparison PASS; hash/result proof above. |
| `afl-09a-verify` | PASS | Validation factory report PASS. |
| `afl-substrate-q4-verify` | PASS | Frozen expectation comparison PASS. |
| `afl-substrate-q6-verify` | PASS | Frozen expectation comparison PASS. |

Semantic registry verification:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHON=.venv/bin/python make scp-0-verify` | PASS | Findings `[]`; runtime capabilities bound 45/45; operators semantically defined 8/8; registry tests 58 OK. |

SCP-0 hashes after regeneration:

| Field | Value |
| --- | --- |
| Registry lock hash | `8a621555917b425dfcfb3b3bec931017a91062252e999089b5c6ebc3ce95856c` |
| Registry revision | `f0b72489f384bae0042784cb6b197ede893864f45375f257a23f58897feefde4` |
| Runtime manifest revision | `50d399ef8b47bf7eac9a615c59c32fc6ce01a9589dfd2717fcb89ba26321dcc7` |

## File Footprint

Tracked files changed relative to the frontier base:

- `artifacts/scp-0/verification-report.json`
- `config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json`
- `delivery/packets/R1-1-REPORT.md`
- `generated/capability-catalog.json`
- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/capability-passport-projection.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/runtime-manifest.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `scripts/coverage_map/compiler_search_reachability.py`
- `semantic-registry/registry.lock.json`
- `semantic-registry/registry.yaml`
- `src/tqe/runtime/binder.py`
- `src/tqe/runtime/capabilities/__init__.py`
- `src/tqe/runtime/capabilities/offball_family.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/operators/__init__.py`
- `src/tqe/runtime/operators/project_onto_axis.py`
- `tests/test_r1_0_operator_scaffolding.py`
- `tests/test_r1_1_project_onto_axis.py`

The only untracked file present during this packet was the unrelated
`docs/visual-explainers/tactical-compilation-concept.png`; it was not staged.

## Summary

R1-1 lands the operator era's first real composition. The operator is typed,
declared, witnessed, and UNKNOWN-preserving for missing vector evidence. Round
2 corrected the semantics that matter for `support_depth`: goalward orientation
is acting-team-backed and recorded in evidence, `toward_point` no longer
fabricates an axis, all axes are tested, and the acceptance target now composes
from a real supporter-relative point pair. Round 3 corrected the proof
synthesis boundary so the target's relation constraints are applied in the
generated plan, unsupported constraint keys fail synthesis, vector point fields
must be declared, and the operator evidence field list is signature-derived.
The compiler-search target is held out and multi-step, returns 20 results with
zero requested-evidence failures, and moves a copied coverage ledger from 7 to
8 compiler-reachable rows.

No push was performed.
