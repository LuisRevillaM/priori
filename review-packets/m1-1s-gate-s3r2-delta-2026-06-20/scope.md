# Scope

## Target

M1.1S Gate S3R2: correction after external rejection of S3R.

## Decision requested

Return one of:

- `APPROVE_S4_UNBLOCKED`
- `APPROVE_WITH_REQUIRED_CHANGES_BEFORE_S4`
- `REJECT_KEEP_S4_BLOCKED`

## In scope

- Semantic anchor identity enforcement.
- Anchor dedupe under conflicting supplied IDs.
- Invalid producer-supplied anchor ID rejection.
- Frame-signal temporal identity requirements.
- Predicate execution through resolved input/parameter mappings.
- Pure generic `persists_for` semantics.
- Legacy M1 persistence isolation.
- Non-M1 PASS/FAIL target traces from declared runtime outputs.
- Regression preservation for M1 parity and prior gates.

## Out of scope

- Implementing S4.
- Implementing S5/S6/S7.
- UI/demo work.
- Priori integration.
- Dataset acquisition.
- Removing all legacy M1 code.

