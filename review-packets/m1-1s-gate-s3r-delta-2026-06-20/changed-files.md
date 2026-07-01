# Changed Files

Commit under review:

`9febb97 Implement M1.1S Gate S3R anchor contract`

## Source/runtime

- `src/tqe/runtime/ir.py`
- `src/tqe/runtime/binder.py`
- `src/tqe/runtime/catalog.py`
- `src/tqe/runtime/values.py`
- `src/tqe/runtime/executor.py`

## Verification

- `src/tqe/verification/m1_1_gate_s3r.py`
- `src/tqe/verification/m1_1_gate_r5.py`
- `src/tqe/verification/m1_1_gate_s2.py`
- `src/tqe/verification/m1_1_gate_s3.py`

## Plans/configs

- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`

## Generated contracts

- `generated/capability-catalog.json`
- `generated/tactical-query-plan.schema.json`
- `generated/tactical-query-plan.types.ts`

## Delivery docs/evidence

- `delivery/ledger.jsonl`
- `delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md`
- `delivery/m1.1/status.yaml`
- `delivery/m1.1/reviews/gate-s3r-controller-review.md`
- `docs/reviews/2026-06-20-m1-1s-gate-s3-external-review.md`
- `docs/learnings/2026-06-20-m1-1s-gate-s3r-explicit-anchor-contract.md`

See `commands/git-show-head-stat.txt` for the full stat and `diffs/commit-9febb97-full.patch` for the exact patch.

