# Changed Files

| Source Path | Why It Matters |
| --- | --- |
| `src/tqe/runtime/executor.py` | Generic rule emitter, evidence projection, generic temporal source-record propagation |
| `src/tqe/verification/m1_1_gate_s4.py` | S4 hard-gate verifier |
| `tests/test_m1_1_runtime.py` | Regression proving generic helper emits real rows |
| `Makefile` | Adds `m1-1-gate-s4-verify` |
| `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md` | Adds S4 acceptance contract |
| `delivery/m1.1/status.yaml` | Marks Gate S4 controller-accepted |
| `delivery/ledger.jsonl` | Records S4 transition and evidence |
| `delivery/m1.1/reviews/gate-s4-controller-review.md` | Controller review record |
| `docs/learnings/2026-06-20-m1-1s-gate-s4-rule-emission.md` | Durable implementation learning |

See `diffs/commit-e5f6618.patch` for exact changes.
