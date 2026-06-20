# Next Steps

1. External reviewer inspects this packet.
2. Reviewer returns one of:
   - `APPROVE`
   - `APPROVE_WITH_REQUIRED_CHANGES`
   - `REJECT`
3. If approved, unblock M1.2 planning/implementation.
4. If required changes are returned, integrate them under M1.1R and rerun relevant gates.
5. If rejected, update `delivery/m1.1/CORRECTIVE_SPEC.md` or add a new corrective spec before further implementation.

Recommended review order:

1. `source-excerpts/delivery/m1.1/CORRECTIVE_SPEC.md`
2. `diffs/commit-12eb91a.patch`
3. `source-excerpts/src/tqe/verification/m1_1_gate_r5.py`
4. `artifacts/m1.1/gate-r5-verification-report.json`
5. `source-excerpts/src/tqe/runtime/executor.py`
6. `source-excerpts/src/tqe/runtime/catalog.py`
7. `source-excerpts/config/query-plans/ball_side_block_shift.ir.v1.json`
8. `source-excerpts/delivery/m1.1/status.yaml`
