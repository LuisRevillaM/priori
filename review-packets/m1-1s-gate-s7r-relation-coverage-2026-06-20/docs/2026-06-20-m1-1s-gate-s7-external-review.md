# M1.1S Gate S7 External Review

## Decision

`APPROVE_WITH_REQUIRED_CHANGES_BEFORE_M1_2`

The external reviewer approved the core M1.1S architecture but blocked M1.2 until a focused semantic gap is closed.

## Blocking Findings

- Collection absence must not be treated as `UNKNOWN` when a relation was fully evaluated and produced zero qualifying episodes.
- Relation predicates need per-anchor coverage with `PASS`, `FAIL`, and `UNKNOWN`.
- Relation evidence needs an explicit witness relation ID; requested evidence must not depend on episode list order.
- `count_at_least` must be anchor-relative and tri-state, or withheld from the agent-exposed catalog.
- Agent-safety limits declared in the IR must be enforced or removed from the normative contract. At minimum, relation expansion must be capped per anchor.
- `INCLUDE_WITH_WARNING` must preserve the actual warning rule decision and unknown predicates.

## Required Corrective Gate

The controller opened S7R: Relation Coverage And Witness Semantics.

M1.2 remains blocked until S7R is implemented, controller-verified, and either externally approved or any further required changes are integrated and re-reviewed.
