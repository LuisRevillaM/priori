# M1.1 Gate E Controller Review

Reviewed at: 2026-06-19T22:22:37-05:00

## Decision

ACCEPTED_CONTROLLER_ONLY for proceeding to M1.1 Gate F.

## Scope Reviewed

- External experimental plan file `opposite_corridor_after_shift.experimental.v1.json`.
- Generic executor loading of an external bound plan file.
- Relation-node execution for `geometric_progressive_corridor`.
- Generic `relation_destination_entry_classification` primitive.
- Experimental result evidence and replay bundles.
- Architecture checks preventing query/recipe/plan identity branches and executor imports from recipe modules.
- Explicit experimental status in reports, result evidence, and bundle manifests.

## Evidence

- `make m1-1-gate-e-verify` passes with 21 passing checks, zero failures, and zero not-ready checks.
- `artifacts/m1.1/experimental-query-results.json` records 41 experimental results.
- Classification spread: `DESTINATION_ENTERED` 24, `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY` 17.
- Match spread: J03WOY 10, J03WPY 18, J03WQQ 6, J03WR9 7.
- `artifacts/m1.1/experimental-evidence-manifest.json` records one replay and evidence bundle per experimental result.
- `make test` passes 20 tests.
- `make m1-1-verify` reports zero failures, one not-ready downstream gate, and 105 passing checks.
- `make m1-verify` still passes M1 Gate A, Gate B, and Gate C.

## Acceptance Rationale

Gate E proves the relation layer can be consumed through plan data rather than through a new detector module. The experimental plan reuses the approved M1 block-shift spine, adds a relation node for opposite-side corridors, and composes a generic destination-entry classifier. The verifier executes from the external plan file and canonical Parquet sources, writes fresh experimental results, generates replay/evidence bundles, and confirms every result is explicitly marked experimental.

## Non-Blocking Concerns

- Gate E does not include the developer-facing inspector; Gate F must make validation, result lists, coordinate replay, predicate traces, non-match tests, and raw evidence inspectable.
- The current relation execution recomputes relation geometry per period; acceptable for the proof, but Gate F should avoid unnecessary recomputation in interactive inspector paths.
- Experimental predicate traces are sufficient for proof and bundles, but Gate F should present them in a clearer developer-facing surface.
- Full M1.1 remains not ready until Gate F is implemented and reviewed.
