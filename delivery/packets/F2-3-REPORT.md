# F2-3 Report — Corridor/Destination Family Extraction

Branch: `packet/f2-3`
Protocol: local commit only; no push. Shared working tree left on frontier; branch ref is the output.

## Scope outcome

- Moved the corridor and destination-entry implementations from `src/tqe/runtime/executor.py` to `src/tqe/runtime/capabilities/corridor_family.py` as pure relocation.
- Relocated node implementations:
  - `relation_geometric_progressive_corridor`
  - `primitive_relation_destination_entry_classification`
- Registry mapping preserved:
  - `geometric_progressive_corridor` and `geometric_progressive_corridor_from_anchor_set` resolve to `relation_geometric_progressive_corridor` in `tqe.runtime.capabilities.corridor_family`.
  - `relation_destination_entry` and `relation_destination_entry_classification` resolve to `primitive_relation_destination_entry_classification` in `tqe.runtime.capabilities.corridor_family`.
- Relocated family-only helpers:
  - `relation_anchor_source`
  - `relation_anchor_results`
  - `normalized_relation_anchor`
  - `relation_anchor_has_required_fields`
  - `relation_anchor_evaluations_from_filtered`
  - `relation_coverage_has_unknown_evidence`
  - `selected_relation_episode`
  - `select_relation_episode`
  - `relation_destination_evaluations`
  - `relation_destination_evaluation_sort_key`
  - `relation_progression_m`
  - `relation_destination_result_sort_key`
  - `relation_side_matches`
  - `opposite_side`
  - `first_ball_entry_into_destination_region`
  - `ball_entry_evaluation_into_destination_region`
  - `experimental_predicate_traces_for_result`
- Updated direct verifier/test imports to the relocated destination implementation/helper without changing verifier semantics.
- No catalog contracts, generated artifacts, frozen expectations, N1D artifacts, or runtime semantics were changed.

## Line count

| File | Before | After | Delta |
|---|---:|---:|---:|
| `src/tqe/runtime/executor.py` | 10,589 | 9,884 | -705 |
| `src/tqe/runtime/capabilities/corridor_family.py` | 0 | 736 | +736 |

## Shared helpers retained in `executor.py`

These are used by the relocated corridor/destination family but remain in `executor.py` because they are shared runtime/kernel helpers or are used by other families too. They are director input for later shared-kernel extraction; F2-3 did not improve or relocate them.

| Helper / symbol | Why it stayed |
|---|---|
| `FRAME_RATE_HZ` | Shared runtime constant used across executor capability families and trace windows. |
| `PeriodState` | Shared executor state type used by all capability implementations. |
| `catalog_input_value` | Generic bound-input resolver. |
| `node_parameter_integer` | Generic node-parameter helper. |
| `node_parameter_number` | Generic node-parameter helper. |
| `node_parameter_text` | Generic node-parameter helper. |
| `optional_int` | Generic coercion helper used outside corridor/destination family. |
| `predicate_traces_for_anchor` | Shared evidence-trace lookup helper used by the experimental trace fabricator. |
| `runtime_anchor_from_record` | Shared runtime-anchor construction helper. |
| `runtime_records` | Generic RuntimeValue record extractor. |
| `typed_enum` | Shared TypedValue helper. |
| `typed_number` | Shared TypedValue helper. |

## Improvement candidates not implemented

Pure relocation only. These were observed but deliberately deferred:

- Extract the generic executor helper/kernel symbols above into stable shared modules so capability modules no longer import shared helpers from `executor.py`.
- Split destination-entry and destination-entry-classification into separate implementation callables if the registry eventually stops sharing one implementation for both catalog refs.
- Rename legacy `primitive_relation_destination_entry_classification` once the naming contract can move without breaking verifier and registry references.
- Move additional corridor-adjacent proof helpers only under a later packet with explicit authority; F2-3 moved only the family implementation/helper surface needed for this extraction.

## Boundary guard updates

- Added a test that `executor.py` does not import or mention `corridor_family`.
- Added registry reachability assertions that `geometric_progressive_corridor`, `geometric_progressive_corridor_from_anchor_set`, `relation_destination_entry`, and `relation_destination_entry_classification` resolve to `tqe.runtime.capabilities.corridor_family`.
- Extended the node-parameter declaration guard so it scans `capabilities/corridor_family.py` in addition to `executor.py` and `capabilities/pass_family.py`.
- Shrank the shared-source freeze by removing destination-classification trace-helper mentions that now live in the relocated family module.

## Pinned-gate drift proof

Committed-tree verification was run from a clean git-backed checkout of commit `28f5375`, with the workspace data root mounted as an ignored symlink. The final local commit after this verification is report-only; no runtime, test, catalog, generated, frozen, N1D, or artifact file changed after the verified code tree.

| Gate | Result | Drift proof |
|---|---|---|
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, `blocking_reasons=[]`. |
| `afl-substrate-q4-verify` | PASS | Frozen expectation unchanged; result count `2`; result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51`. |
| `afl-substrate-q6-verify` | PASS | Frozen expectation unchanged; result count `0`; result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496`. |
| `afl-line-break-support-response-verify` | PASS | Factory comparison PASS; result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f`. |
| `afl-lane-occupancy-verify` | PASS | Verifier PASS; lane occupancy statuses remain PASS. |
| `afl-09a-verify` | PASS | Verifier PASS; factory expectation hashes unchanged: `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f`, `264f0cd1223f9dfa259904a847dfe89d63a7a8cb47ab2aa3980d0cc99f55d72a`. |
| `scp-0-verify` | PASS | Verifier PASS; SCP-0 semantic registry tests PASS during verifier run. |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; generated hash equals stored hash: `95b09da225ca4ba0673497ec2cd72d67016f57c97ff32b6010aed349b33212ad`. |

Changed-file audit relative to the packet base is limited to relocation, registry wiring, direct import updates for moved functions, boundary tests, and this report:

- `delivery/packets/F2-3-REPORT.md`
- `src/tqe/runtime/capabilities/__init__.py`
- `src/tqe/runtime/capabilities/corridor_family.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/verification/m1_1_gate_s2.py`
- `src/tqe/verification/n1b.py`
- `tests/test_executor_boundaries.py`
- `tests/test_m1_1_runtime.py`

## Full-suite table

| Command | Result |
|---|---|
| `PYTHONPATH=/tmp/priori-f2-3-edit.Y3W8ny/src /Users/luisrevilla/code/priori/.venv/bin/python -m py_compile src/tqe/runtime/executor.py src/tqe/runtime/capabilities/__init__.py src/tqe/runtime/capabilities/corridor_family.py src/tqe/verification/n1b.py src/tqe/verification/m1_1_gate_s2.py tests/test_executor_boundaries.py tests/test_m1_1_runtime.py` | PASS |
| `PYTHONPATH=/tmp/priori-f2-3-edit.Y3W8ny/src /Users/luisrevilla/code/priori/.venv/bin/python -m unittest tests.test_executor_boundaries tests.test_m1_1_runtime.M11RuntimeTests.test_relation_destination_entry_evaluates_pass_fail_and_unknown` | PASS, 8 tests in 62.656s |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python n1d1-verify afl-substrate-q4-verify afl-substrate-q6-verify afl-line-break-support-response-verify afl-lane-occupancy-verify afl-09a-verify scp-0-verify afl-passport-verify` | PASS on clean committed-tree checkout |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS, 352 tests in 345.839s on clean committed-tree checkout |
