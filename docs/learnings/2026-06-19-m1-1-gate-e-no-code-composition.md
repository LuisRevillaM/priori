# M1.1 Gate E No-Code Composition

## Fact

`opposite_corridor_after_shift.experimental.v1.json` now executes as an external experimental plan over canonical IDSSE data and produces relation-backed tactical results without adding a Python detector under `src/tqe/query`.

## Decision

The runtime may add catalog-level primitive implementations that are generic across plans. It must not branch on query ID, recipe ID, or plan ID, and the executor must not import recipe modules. The experimental plan is the behavior boundary for this composition.

## Learning

No-code composition does not mean the executor needs a universal expression language yet. For M1.1, a practical middle ground works: the plan composes approved primitives, a relation node, and a generic relation-destination classifier. This is enough to prove that future Hermes-authored plans can bind to known capabilities without hidden per-query detector code.

## Evidence

- `make m1-1-gate-e-verify` passes with 21/0/0.
- `artifacts/m1.1/experimental-query-results.json` records 41 experimental results across all four Fortuna evaluation matches.
- Result classes: 24 `DESTINATION_ENTERED`, 17 `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY`.
- `artifacts/m1.1/experimental-evidence-manifest.json` records replay/evidence bundles for every experimental result.
- `delivery/m1.1/reviews/gate-e-controller-review.md`

## Follow-Up

Gate F should expose this plan and its results through the developer inspector without hardcoding M1 result shapes. The inspector should make the experimental status visible and avoid recomputing expensive relation evidence unnecessarily when reading existing proof artifacts.
