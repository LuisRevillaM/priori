# M1.1 Gate B Runtime Parity

## Fact
The M1.1 runtime now executes the approved bound plan over canonical IDSSE data and reproduces the frozen M1 evaluation output.

## Decision
Gate B compares the runtime against the full legacy accepted evaluation output, not only the 16 selected proof results. It also verifies the selected baseline manifest, deterministic repeated execution, replay-window traceability, legacy source hash, and absence of query/recipe/plan identity branches in the executor.

## Learning
The parity gate caught a boundary mismatch: M1 uses strict `>` for wide-channel entry, while the first IR plan used `gte`. Adding a versioned `gt` operator and using it only for wide entry restored complete parity. This is exactly why Gate B needed full-output parity instead of only selected proof examples.

## Evidence
- `make m1-1-build`
- `make m1-1-gate-a-verify`
- `make m1-1-gate-b-verify`
- `artifacts/m1.1/parity-report.json`
- `artifacts/m1.1/runtime-execution.json`
- `src/tqe/runtime/executor.py`
- `src/tqe/verification/m1_1_gate_b.py`
