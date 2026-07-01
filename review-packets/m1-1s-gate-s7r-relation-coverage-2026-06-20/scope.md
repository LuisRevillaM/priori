# Scope

## In Scope

- S7 external review findings that blocked M1.2.
- Relation coverage semantics for `geometric_progressive_corridor`.
- The declared `anchor_evaluations` relation output.
- Generic `exists` and `count_at_least` behavior over relation coverage.
- Witness relation ID propagation into predicate traces.
- Requested evidence projection against the witness relation.
- Static and runtime enforcement of declared complexity limits.
- Controller verification and durable delivery records for S7R.

## Out Of Scope

- M1.2 Hermes implementation.
- Any frontend or UI work.
- New tactical primitives beyond the existing corridor relation.
- New data ingestion or canonical data changes.
- Priori SDK/API integration.
- Video integration.
- Deployment.

## Assumptions

- The reviewer does not have repo access.
- This packet is for inspection and decision support, not standalone reproduction.
- Existing packet artifacts from prior gates are intentionally left outside this focused packet except where directly needed.
