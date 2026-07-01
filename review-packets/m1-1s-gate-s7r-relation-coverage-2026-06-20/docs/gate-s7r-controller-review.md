# Gate S7R Controller Review

## Decision

`ACCEPTED_CONTROLLER_ONLY_PENDING_EXTERNAL_REVIEW`

S7R closes the focused semantic gap identified by the external S7 review. It does not reopen the runtime architecture.

## Evidence

- `make m1-1-gate-s7r-verify` passes `10/0/0`.
- `make m1-1-gate-s6-verify` still passes `8/0/0`.
- `artifacts/m1.1/gate-s7r-verification-report.json` records canonical PASS/FAIL relation coverage, tightened-threshold FAIL behavior, explicit UNKNOWN coverage semantics, witness-stable evidence, anchor-relative count semantics, generic non-match FAIL inspection, agent-safety limit failures, and warning-rule preservation.

## Accepted Scope

S7R added declared `anchor_evaluations` relation output records and routed the S6 `exists` predicate through those records instead of raw relation episodes. `exists` and `count_at_least` now consume per-anchor relation coverage as tri-state predicates.

Requested relation evidence still resolves from declared `episodes`, but the selected relation is the predicate witness, not the first matching list item. Reordering relation episodes does not change projected evidence.

The binder now enforces `max_nesting_depth` and `max_execution_cost`, while runtime relation execution enforces `max_relations_per_anchor` with an explicit failure message.

## Remaining Gate

M1.2 remains blocked pending external review of S7R.
