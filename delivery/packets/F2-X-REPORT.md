# F2-X Report — Kill List & Legacy Quarantine

Branch: `packet/f2-x`  
Final code commit: `a8146e0` (`Quarantine legacy M1 profile helpers`)  
Base: `fb37e70` (`Author work packet F2-X: kill list and legacy quarantine`)

## Summary

F2-X completed the kill-list pass with five staged commits:

| Item | Commit | Outcome |
| --- | --- | --- |
| 1. Noop dispatch registrations | `1baa612` | Deleted. |
| 2. Dead duplicate predicate family | `58e51b6` | Deleted. |
| 3. Fabricated experimental traces | `c2a1390` | Left standing after live-consumer proof. |
| 4. `select_proof_results` M1 labels | `3f546f0` | Moved to legacy quarantine. |
| 5. Legacy M1 profile branches | `a8146e0` | Moved to `tqe.runtime.legacy_m1`; executor delegates only behind the explicit compatibility profile. |

Executor size moved from `3715` lines to `3227` lines. The new quarantine module is `395` lines.

Fences held: no catalog file, generated projection, frozen expectation, N1D, or artifact file changed.

## Proof By Item

### 1. Noop dispatch registrations

Deleted from `src/tqe/runtime/capabilities/__init__.py`:

- `wide_channel_dwell`
- `shift_persistence`
- `robust_team_width`
- `analysis_rate`

Deleted `primitive_noop` from `src/tqe/runtime/executor.py` and removed the legacy noop allowlist from the registry-boundary test. The registry test now asserts exact equality between catalog primitives and primitive dispatch names; there is no remaining noop debt list.

Proof:

- These names were already absent from the runtime catalog.
- `make m1-1-gate-r1-verify` passed on the final tree: `56` pass, `0` fail.
- `tests.test_executor_boundaries` passed on the final tree.

### 2. Dead duplicate predicate family

Deleted the registered-but-bypassed predicate registry:

- `PREDICATE_IMPLEMENTATION_NAMES`
- `build_predicate_registry`
- `self.predicates`
- `predicate_gt`, `predicate_gte`, `predicate_lte`, `predicate_eq`, `predicate_neq`, `predicate_persists_for`, `predicate_exists`, `predicate_count_at_least`

The live path remains `execute_predicate_with_resolved_inputs`, with the supported operator set declared as `SUPPORTED_PREDICATE_OPERATORS`. Verifier helpers that had directly executed the old registry now call the live dispatcher with resolved runtime inputs.

Proof:

- Source search on the final tree finds no `build_predicate_registry`, `PREDICATE_IMPLEMENTATION_NAMES`, `self.predicates`, or deleted predicate implementation imports.
- `tests.test_predicate_truth_series` passed on the final tree.
- `tests.test_executor_boundaries` passed on the final tree.
- `m1-1-gate-s3r-verify` passed: `13` pass, `0` fail.

### 3. Fabricated experimental traces

No deletion. The helper `experimental_predicate_traces_for_result` is still live.

Consumer chain found:

- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json` uses `relation_destination_entry_classification`.
- `primitive_relation_destination_entry_classification` in `tqe.runtime.capabilities.corridor_family` calls `experimental_predicate_traces_for_result` on the trusted wrapper/classification output path.
- M1.1/M1.2 experimental gates and workshop flows still consume this trusted-wrapper behavior, including `m1_1_gate_e`, `m1_1_gate_s7`, and `workshop/m1_2.py`.
- The coach service excludes `relation_destination_entry_classification` from coach-authored allowed refs, so this remains a fenced internal/experimental path rather than a public coach surface.

Decision: left standing and reported for director decision, per the packet instruction.

### 4. `select_proof_results` M1 labels

`select_proof_results` is reachable, but only from legacy M1 proof/parity tooling. It was moved from shared executor code into `src/tqe/runtime/legacy_m1.py`.

Updated consumers:

- `src/tqe/inspector/m1_1.py`
- `src/tqe/verification/m1_1_gate_b.py`
- `tests/test_m1_1_runtime.py`

The shared executor no longer contains the M1 selection labels or `proof_selected` policy.

Proof:

- `tests.test_m1_1_runtime` passed on the final tree.
- `make m1-1-gate-b-verify` passed on the final tree: `14` pass, `0` fail.
- `tests.test_executor_boundaries` passed and no longer freezes `select_proof_results` labels as shared-executor helper leaks.

### 5. Legacy M1 profile quarantine

Moved legacy M1 parity implementation bodies into `src/tqe/runtime/legacy_m1.py`:

- legacy M1 `persists_for` record adapter
- legacy M1 frame-signal adapter
- accepted-result predicate trace synthesis from `_predicate_status`
- legacy proof selection
- legacy default/experimental M1 runners
- legacy result sorting by `block_shift_score`
- legacy `_runtime_result` target lookup

The executor now keeps only explicit profile-gated delegation to `legacy_m1`. Generic execution remains in the executor and generic `predicate_traces_for_anchor` delegates to legacy trace merging only when `compatibility_profile == legacy_m1.LEGACY_M1_PARITY_PROFILE`.

Proof:

- `tests.test_m1_1_runtime` passed on the final tree.
- `make m1-1-gate-b-verify` passed: `14` pass, `0` fail.
- `make m1-1-gate-c-verify` passed: `10` pass, `0` fail.
- `make m1-1-gate-s3r-verify` passed: `13` pass, `0` fail.

Disclosure:

- `make m1-verify` is not runnable in the verification worktree because `artifacts/m1/gate-c/evaluation-report.json` is absent.
- `make m1-1-gate-s3-verify` still fails stale approved-plan/near-miss parity assertions (`result_count=119`, `trace_count=747` against older pins), but its candidate-state independence check reports `uses_state_candidates: false`; S3R is green and is the stronger temporal/profile gate for this packet.

## Pinned-Gate Drift Proof

Executed on git-backed clean worktree `/tmp/priori-f2-x-git-final.83sJRR` at final commit `a8146e0`; only `data` was an untracked symlink.

| Target | Result | Drift evidence |
| --- | --- | --- |
| `n1d1-verify` | PASS | `attestation_status=VERIFIED`, no blocking reasons. |
| `afl-substrate-q4-verify` | PASS | result signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`; expectation hash `a2ff7342e6ff113cdcf77acc4d70c0046bebcc9564bcf395b74aaf5639e7bd51`. |
| `afl-substrate-q6-verify` | PASS | result signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; expectation hash `4fefcf35c221923db4ae83c5bd7dad85f1ae8bb43b23aa1938567de22a2c2496`. |
| `afl-line-break-support-response-verify` | PASS | result signature `7a3e0e16c1ce3e32f4a83f3c9fef89f60f7e3b04fc16f2e219a3337172c35227`; expectation hash `b114d793eba25a481b0e2563abd1430f79cd371bb69cc1c8d54a8d77be83816f`. |
| `afl-lane-occupancy-verify` | PASS | Verifier PASS; `tests.test_lane_occupancy` ran 17 tests, OK. |
| `afl-09a-verify` | PASS | Verifier PASS; `tests.test_afl_validation_factory` ran 4 tests, OK. |
| `scp-0-verify` | PASS | Verifier PASS; `tests.test_scp0_semantic_registry` ran 58 tests, OK. |
| `afl-passport-verify` | PASS | `scp0_parity_status=PASS`; generated hash equals stored hash `95b09da225ca4ba0673497ec2cd72d67016f57c97ff32b6010aed349b33212ad`; `tests.test_scp0_semantic_registry` reran 58 tests, OK. |

## Full-Suite Table

Executed on the same final git-backed worktree at `a8146e0`.

| Command | Result |
| --- | --- |
| `PYTHONPATH=/tmp/priori-f2-x-git-final.83sJRR/src .venv/bin/python -m py_compile src/tqe/runtime/executor.py src/tqe/runtime/legacy_m1.py src/tqe/verification/m1_1_gate_r3.py tests/test_executor_boundaries.py tests/test_m1_1_runtime.py tests/test_predicate_truth_series.py` | PASS |
| `PYTHONPATH=/tmp/priori-f2-x-git-final.83sJRR/src .venv/bin/python -m unittest tests.test_executor_boundaries tests.test_m1_1_runtime tests.test_predicate_truth_series` | PASS, 27 tests in 176.053s |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python n1d1-verify afl-substrate-q4-verify afl-substrate-q6-verify afl-line-break-support-response-verify afl-lane-occupancy-verify afl-09a-verify scp-0-verify afl-passport-verify` | PASS |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python m1-1-gate-r1-verify` | PASS, 56 checks |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python m1-1-gate-b-verify m1-1-gate-c-verify` | PASS, Gate B 14 checks; Gate C 10 checks |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python m1-1-gate-s3r-verify` | PASS, 13 checks |
| `make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS, 356 tests in 320.226s; attestation `VERIFIED` |

Sandbox warnings observed during data-backed gates:

- Arrow CPU-info `sysctlbyname` warnings under sandbox.
- Matplotlib temporary cache warning because `~/.matplotlib` is not writable.

Neither affected gate results.

## Fences And Cleanliness

Changed tracked files are limited to runtime boundary/quarantine code, M1 verifier import/source updates, and runtime tests:

- `src/tqe/runtime/capabilities/__init__.py`
- `src/tqe/runtime/executor.py`
- `src/tqe/runtime/legacy_m1.py`
- M1 verifier/workshop/inspector imports and verifier source-contract updates
- `tests/test_executor_boundaries.py`
- `tests/test_m1_1_runtime.py`

No fenced path changed:

- no runtime catalog file
- no `generated/`
- no frozen expectations
- no N1D bundle
- no artifacts

Shared frontier worktree remains clean except for the pre-existing untracked `docs/visual-explainers/tactical-compilation-concept.png`.
