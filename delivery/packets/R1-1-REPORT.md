# R1-1 Report - project_onto_axis Operator

Branch: `packet/r1-1`
Frontier base: `8431afb`
Packet: `delivery/packets/R1-1-project-onto-axis.md`
ADR: `docs/adr/0013-r1-operator-era.md`
Push: no push, per direct-channel protocol.

## Scope

Implement the first real R1 operator, `project_onto_axis@0.1.0`, under the
R1-0 operator scaffolding. Acceptance requires at least one previously-gap
semantic program to execute end-to-end and a compiler-reachable delta measured
by the coverage map tooling.

Required fences: additive/operator-scoped edits only; existing plan hashes must
not drift; generated/frozen artifacts are not touched unless explicitly
required by the packet.

## Implementation Ledger

| Step | Status | Evidence |
| --- | --- | --- |
| L1 report first commit | PASS | Commit `7313025` created this report before implementation. |
| Operator declaration | PASS | `project_onto_axis@0.1.0` registered as the sole R1 operator signature/implementation. |
| Operator implementation | PASS | `src/tqe/runtime/operators/project_onto_axis.py` emits witnessed `axis_projection_records`, `axis_projection_status`, `signed_projection_m`, and `angle_between_degrees`. |
| Acceptance composition | PASS | Dedicated R1-1 compiler-search target synthesized `controlled_pass_episode -> project_onto_axis -> eq(PASS)` over J03WOY. |
| Reachability delta | PASS | Map tooling on a copied ledger moved `compiler_reachable` from 7 to 8; `support_depth` changed `handwired -> compiler_reachable`. |
| Full suite and pinned gates | PENDING | Not started. |

## Catalog / IR / Search Edit Enumeration

| Surface | Change | Reason |
| --- | --- | --- |
| `src/tqe/runtime/operators/__init__.py` | Registers exactly one operator: `project_onto_axis@0.1.0`. | R1-1 first operator. |
| `src/tqe/runtime/operators/project_onto_axis.py` | Adds the operator signature and implementation. | Declares typed input/output channels, axis enum, UNKNOWN-on-missing-vector semantics, and source-record witnesses. |
| `scripts/coverage_map/compiler_search_reachability.py` | Adds generic `vector_projection` constraint handling and generated operator node insertion. | Allows compiler-search to discover point-pair providers and compose them through the operator without using coverage gold chains. |
| `config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json` | Adds one packet-local reachability target. | Measures the R1-1 acceptance delta without mutating the broader sample target set. |
| `tests/test_r1_0_operator_scaffolding.py` | Updates registry ratchet from empty to exactly one registered operator. | R1-0 empty-registry invariant is intentionally superseded by R1-1. Existing shared-code leakage guard remains. |

No existing query-plan JSON or frozen generated artifact is edited.

## Acceptance Composition / Reachability Delta

Command:

```text
cp generated/coverage-map.json /private/tmp/r1-1-coverage-map.json &&
PYTHONPATH=src \
TQE_SEARCH_TARGETS=config/compiler-reachability/r1-1-project-onto-axis-targets.v0.json \
TQE_SEARCH_LEDGER=/private/tmp/r1-1-coverage-map.json \
TQE_SEARCH_OUT_DIR=artifacts/autonomous/r1-1-project-onto-axis/compiler-search \
TQE_SEARCH_REPORT=artifacts/autonomous/r1-1-project-onto-axis/compiler-search-report.json \
TQE_SEARCH_MATCH_IDS=J03WOY \
TQE_SEARCH_UPDATE_LEDGER=1 \
TQE_SEARCH_SHARED_NODE_CACHE=1 \
.venv/bin/python scripts/coverage_map/compiler_search_reachability.py
```

Result:

| Metric | Value |
| --- | --- |
| Tool status | `PASS` |
| Target | `r1_1_goalward_axis_projection_v0` |
| Reporting concept row | `support_depth` |
| Concept-name hint used | `false` |
| Gold chain used as input | `false` |
| Pattern dispatch used | `false` |
| Providers used | `controlled_pass_episode`, `operator:project_onto_axis` |
| Rules used | `provider_field_backward_search`, `generic_vector_projection_operator` |
| Execution status | `pass` |
| Result count | 20 |
| Requested evidence failures | 0 |
| Document hash | `e2b6b67bdc680f7c29a7fec265db6771c6906ef74085d6ebf232ee4cc4da6aa6` |
| Runtime trace hash | `f1ed662abd7c9d758aeb4de936af233030e5ad2f4a775be0682d7cd43321bbe7` |

Coverage-map delta measured on `/private/tmp/r1-1-coverage-map.json` by the tool's own update path:

| Ledger | `compiler_reachable` count |
| --- | ---: |
| Baseline `generated/coverage-map.json` | 7 |
| R1-1 copied ledger after search update | 8 |

Changed row:

| Concept | Before | After | Evidence |
| --- | --- | --- | --- |
| `support_depth` | `handwired` | `compiler_reachable` | Target `r1_1_goalward_axis_projection_v0`, result count 20, honest_zero `false`. |

## Verification

Focused unit/executor slice:

| Command | Status | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_r1_0_operator_scaffolding tests.test_r1_1_project_onto_axis` | PASS | 11 tests. Covers explicit registry completeness, shared-code name boundary, mirror symmetry, axis enum completeness, UNKNOWN propagation, 0/90/180 angle boundaries, and real bind/execute on J03WOY. |
| R1-1 compiler-search command above | PASS | One held-out multi-step target became compiler_reachable with 20 rows and zero requested-evidence failures. |
