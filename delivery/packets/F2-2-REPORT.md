# F2-2 Report — Pass-Family Extraction

Branch: `packet/f2-2`
Protocol: local commit only; no push.

## Scope outcome

- Moved the pass-family implementations from `src/tqe/runtime/executor.py` to `src/tqe/runtime/capabilities/pass_family.py` as pure relocation.
- Relocated functions:
  - `primitive_action_event_anchor`
  - `primitive_controlled_pass_episode`
  - `primitive_one_touch_relay_episode`
  - `relation_opponents_bypassed_by_action`
- Pass-bypass / high-bypass registry mapping: no catalog node named
  `pass_bypass` or `high_bypass_completed_pass` has its own executor
  implementation. The runtime relation implementation is
  `relation_opponents_bypassed_by_action`, registered for catalog capability
  `opponents_bypassed_by_action`; high-bypass recipes consume that relation.
- Relocated pass-only helpers:
  - `controlled_pass_anchor_record`
  - `controlled_pass_episode_record`
  - `one_touch_relay_anchor_record`
  - `pass_bypass_anchor_record`
- `primitive_action_event_anchor` moved because its current catalog-supported modes are pass-family coupled: `successful_pass` and `throw_in_successful_pass`. No non-pass action anchor mode is implemented in the function body.
- The dispatch registry in `src/tqe/runtime/capabilities/__init__.py` now resolves those four implementations lazily from `tqe.runtime.capabilities.pass_family`. `executor.py` does not import `pass_family`.
- No catalog contracts, generated artifacts, frozen expectations, N1D artifacts, or runtime semantics were changed.

## Line count

| File | Before | After | Delta |
|---|---:|---:|---:|
| `src/tqe/runtime/executor.py` | 10,999 | 10,589 | -410 |
| `src/tqe/runtime/capabilities/pass_family.py` | 0 | 451 | +451 |

## Shared helpers retained in `executor.py`

These are used by the relocated pass-family functions but remain in `executor.py` because they are shared runtime/kernel helpers or are used by other capability families too. They are director input for later shared-kernel extraction; F2-2 did not improve or relocate them.

| Helper / symbol | Why it stayed |
|---|---|
| `PeriodState` | Shared executor state type used by all capability implementations. |
| `anchor_record_id` | Generic deterministic anchor identity helper. |
| `catalog_input_value` | Generic bound-input resolver. |
| `catalog_output` | Generic catalog output metadata resolver. |
| `frame_match_time_ms` | Generic frame timestamp helper. |
| `node_parameter_event_type_filter` | Generic node-parameter helper for event filter parameters. |
| `node_parameter_number` | Generic node-parameter helper. |
| `node_parameter_text` | Generic node-parameter helper. |
| `optional_int` | Generic coercion helper used outside pass family. |
| `parquet_rows` | Generic runtime data-load helper. |
| `point_from_xy` | Generic point construction helper used by other families. |
| `align_event_to_frame` import in `executor.py` | Still used by `set_piece_structure`; not pass-family-only. |
| `EVENT_COLUMNS` import in `executor.py` | Still used by `set_piece_structure`; not pass-family-only. |
| `attack_x_sign_for` import in `executor.py` | Used by multiple non-pass families; not pass-family-only. |

## Improvement candidates not implemented

Pure relocation only. These were observed but deliberately deferred:

- Extract the generic executor helper/kernel symbols above into stable shared modules so capability modules no longer import shared helpers from `executor.py`.
- Move `primitive_pass_chain_episode` and `primitive_receiver_line_transition_during_pass_leg` in a later pass-family packet if the director wants the full pass family extracted, not just this packet's named slice.
- Split `action_event_anchor` into generic event anchoring plus pass-specific parsing if future non-pass action anchors land.
- Add a stricter no-executor-import target for capability modules after the shared-kernel extraction exists.

## Boundary guard updates

- Added a test that `executor.py` does not import or mention `pass_family`.
- Added a registry reachability assertion that `action_event_anchor`, `controlled_pass_episode`, `one_touch_relay_episode`, and `opponents_bypassed_by_action` resolve to `tqe.runtime.capabilities.pass_family` through the registry.
- Extended the node-parameter declaration guard so it scans both `executor.py` and `capabilities/pass_family.py` implementation bodies.

## Pinned-gate drift proof

Committed-tree verification was run from a clean temporary checkout of commit
`4a3986f` with the workspace data roots mounted read-only. The final local
commit after this verification is report-only; no runtime, test, catalog,
generated, frozen, N1D, or artifact file changed after the verified code tree.

| Gate | Result | Drift proof |
|---|---|---|
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, `blocking_reasons=[]`. |
| `afl-substrate-q4-verify` | PASS | Frozen expectation unchanged; result count `2`; result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51`. |
| `afl-substrate-q6-verify` | PASS | Frozen expectation unchanged; result count `0`; result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496`. |
| `afl-line-break-support-response-verify` | PASS | Factory comparison PASS; result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f`. |
| `afl-lane-occupancy-verify` | PASS | Verifier PASS; accompanying `tests.test_lane_occupancy` PASS, 17 tests. |
| `afl-09a-verify` | PASS | Verifier PASS; accompanying `tests.test_afl_validation_factory` PASS, 4 tests. |
| `scp-0-verify` | PASS | Verifier PASS; accompanying `tests.test_scp0_semantic_registry` PASS, 58 tests. |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; generated hash equals stored hash: `95b09da225ca4ba0673497ec2cd72d67016f57c97ff32b6010aed349b33212ad`; accompanying `tests.test_scp0_semantic_registry` PASS, 58 tests. |

Changed-file audit relative to the packet base is limited to the relocation,
registry wiring, boundary tests, controlled-pass test import updates, and this
report:

- `delivery/packets/F2-2-REPORT.md`
- `src/tqe/runtime/capabilities/__init__.py`
- `src/tqe/runtime/capabilities/pass_family.py`
- `src/tqe/runtime/executor.py`
- `tests/test_controlled_pass_honesty.py`
- `tests/test_executor_boundaries.py`

## Full-suite table

| Command | Result |
|---|---|
| `PYTHONPATH=src .venv/bin/python -m py_compile src/tqe/runtime/executor.py src/tqe/runtime/capabilities/__init__.py src/tqe/runtime/capabilities/pass_family.py tests/test_executor_boundaries.py tests/test_controlled_pass_honesty.py` | PASS |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_executor_boundaries tests.test_controlled_pass_honesty` | PASS, 25 tests in 29.407s |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python n1d1-verify afl-substrate-q4-verify afl-substrate-q6-verify afl-line-break-support-response-verify afl-lane-occupancy-verify afl-09a-verify scp-0-verify afl-passport-verify` | PASS on clean committed-tree checkout |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS, 351 tests in 323.777s on clean committed-tree checkout |
