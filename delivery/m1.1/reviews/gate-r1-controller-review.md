# M1.1R Gate R1 Controller Review

Reviewed at: 2026-06-19T23:36:00-05:00

## Decision

ACCEPTED_CONTROLLER_ONLY for Gate R1.

## Scope Reviewed

- `DraftCatalogNode.inputs` and `BoundCatalogNode.inputs/input_types`.
- Catalog input signatures for M1-dependent primitives and the corridor relation.
- Catalog parameter schemas with allowed names, units, bounds, and enum values.
- Binder rejection for unknown node parameters, missing inputs, input type mismatches, invalid parameter ranges, invalid enum values, and classification label mismatches.
- Removal of advertised no-op capabilities from the default catalog.
- `BoundQueryPlan` now carries `max_results` and `execution_mode`.

## Evidence

- `make m1-1-build` passes.
- `make m1-1-gate-a-verify` passes with 64 passing checks, zero failures, and zero not-ready checks.
- `make m1-1-gate-r1-verify` passes with 19 passing checks, zero failures, and zero not-ready checks.
- `make test` passes 24 tests.

## Acceptance Rationale

Gate R1 closes the first binder-level hole identified by external review. Plans now expose current graph dependencies explicitly, and the binder rejects several classes of plans that previously bound successfully despite being semantically invalid or unsupported.

## Remaining Blocking Work

- Runtime still does not consume bound node inputs generically.
- Runtime values are not yet first-class typed graph values.
- `execution_mode`, `max_results`, classification rules, evidence projection, and unknown policy are not yet operational.
- Corridor execution still needs anchor decoupling in Gate R4.
