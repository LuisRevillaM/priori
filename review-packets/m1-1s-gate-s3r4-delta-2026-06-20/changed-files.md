# Changed Files

Committed files in `4a351fb`:

| Source Path | Why It Matters |
| --- | --- |
| `src/tqe/runtime/executor.py` | Main S3R4 runtime changes: default profile, duration normalization, temporal intervals, target trace UNKNOWN behavior |
| `src/tqe/runtime/values.py` | `FrameSignal` unknown-mask invariant |
| `src/tqe/verification/m1_1_gate_s3r.py` | Required S3R4 proof tests |
| `src/tqe/verification/m1_1_gate_c.py` | Legacy parity profile made explicit for gate C |
| `src/tqe/verification/m1_1_gate_r5.py` | Legacy parity profile made explicit for R5 compatibility checks |
| `tests/test_m1_1_runtime.py` | Runtime tests updated for explicit legacy parity call sites |
| `delivery/m1.1/reviews/gate-s3r4-controller-review.md` | Controller acceptance record |
| `docs/reviews/2026-06-20-m1-1s-gate-s3r3-external-review.md` | External review decision that triggered S3R4 |
| `docs/learnings/2026-06-20-m1-1s-gate-s3r4-temporal-correctness.md` | Durable learning about UNKNOWN temporal semantics |
| `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md` | Source-of-truth milestone spec update |
| `delivery/m1.1/status.yaml` | Milestone status update |
| `delivery/ledger.jsonl` | Durable ledger entry |

See `diffs/commit-4a351fb.patch` for exact changes.
