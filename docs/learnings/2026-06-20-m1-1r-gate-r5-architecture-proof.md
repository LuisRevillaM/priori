# M1.1R Gate R5 Architecture Proof

Date: 2026-06-20

## Fact

The final R5 proof initially failed because accepted result rows leaked predicate node IDs through fields such as `not_stoppage_passed`. Renaming nodes preserved result count but changed public row shape.

## Decision

Predicate pass/fail state now remains in typed predicate outputs and hidden `_predicate_status` trace records. The runtime no longer adds `{predicate_id}_passed` public fields, and `persists_for` reads the upstream typed boolean values directly.

## Learning

Node-ID opacity needs a full result-shape metamorphic check, not only a source scan for approved predicate IDs. Public evidence fields are part of the contract: if they vary with arbitrary node names, the plan graph is still leaking implementation identity.

## Evidence

- `make m1-1-gate-r5-verify`: 10 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r4-verify`: 8 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r3-verify`: 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify`: 4 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r1-verify`: 19 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-c-verify`: 10 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-b-verify`: 14 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-e-verify`: 21 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-f-verify`: 13 pass, 0 fail, 0 not-ready.
- `make test`: 26 tests passed.
- `git diff --check`: passed.

## Follow-Up

Prepare an external review packet for M1.1R. Do not start M1.2 implementation until the external decision is approve, or required changes are integrated and re-reviewed.
