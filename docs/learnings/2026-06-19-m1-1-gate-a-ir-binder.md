# M1.1 Gate A IR Binder

## Fact
M1.1 Gate A now has a typed Pydantic IR, default primitive/relation/operator catalog, deterministic binder, generated JSON Schema, generated TypeScript type surface, and generated capability catalog.

## Decision
The binder is intentionally validation-only. It creates a deterministic `BoundQueryPlan` and stable hashes, but it does not execute the plan, evaluate predicates, or replace the legacy M1 detector. M1 parity remains a Gate B responsibility.

## Learning
The most important S1 behavior is visible failure. Invalid primitive names, unit mismatches, cardinality misuse, scalar-number persistence, team/player scope mismatch, unsupported evidence fields, unresolved temporal references, and complexity-limit violations all fail at bind time with structured issue codes.

## Evidence
- `make m1-1-build`
- `make m1-1-gate-a-verify`
- `make test`
- `config/query-plans/ball_side_block_shift.ir.v1.json`
- `generated/tactical-query-plan.schema.json`
- `generated/tactical-query-plan.types.ts`
- `generated/capability-catalog.json`
- `artifacts/m1.1/binder-validation-report.json`
