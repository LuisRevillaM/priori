# M1.1R Gate R2 Controller Review

Reviewed at: 2026-06-19T23:55:00-05:00

## Decision

ACCEPTED_CONTROLLER_ONLY for Gate R2.

## Scope Reviewed

- `BoundQueryPlan` invocation semantics are honored by the executor.
- `bind_only` returns no match results and does not enter match execution.
- `dry_run` returns no match results and records dry-run provenance.
- `execute` runs the match executor.
- `max_results` truncates results deterministically.
- Runtime node outputs are wrapped in typed `RuntimeValue` objects and checked against bound catalog output contracts.

## Evidence

- `make m1-1-gate-r2-verify` passes with 4 passing checks, zero failures, and zero not-ready checks.
- `tests.test_m1_1_runtime` passes 9 tests.

## Acceptance Rationale

Gate R2 makes invocation behavior operational and adds a typed runtime-value conformance layer around the existing executor. This directly fixes the external review's contract violation around `bind_only`, `dry_run`, and `max_results`, and begins enforcing catalog/runtime output agreement.

## Remaining Blocking Work

- The executor still has compatibility normalization for legacy raw outputs.
- Predicate execution still consumes raw `state.signals`, not typed runtime values.
- Classification rules, requested evidence, and unknown policy are not yet plan-driven.
- Relation execution is still coupled to M1 accepted results until Gate R4.
