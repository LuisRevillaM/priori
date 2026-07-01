# Scope

## Target

M1.1S Gate S3R3: explicit compatibility profile, single temporal implementation, and generic PASS/FAIL/UNKNOWN target traces.

## Decision requested

Return one of:

- `APPROVE_S4_UNBLOCKED`
- `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4`
- `REJECT_KEEP_S4_BLOCKED`

## In scope

- Generic vs legacy M1 compatibility profile selection.
- Generic execution refusing legacy adapters regardless of record shape.
- Single shared temporal implementation.
- UNKNOWN interval preservation.
- Generic target tracing without `_runtime_result` / `_predicate_status`.
- Actual generic predicate-node execution proof.
- PASS/FAIL/UNKNOWN end-to-end target traces.
- M1 parity preservation under explicit legacy profile.

## Out of scope

- S4 implementation.
- S5/S6/S7 implementation.
- UI/demo work.
- Priori integration.
- Dataset acquisition.
- Removing legacy M1 compatibility code.

