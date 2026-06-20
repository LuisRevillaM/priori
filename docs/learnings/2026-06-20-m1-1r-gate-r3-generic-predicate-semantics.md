# M1.1R Gate R3 Generic Predicate Semantics

Date: 2026-06-20

## Fact

Frame-signal runtime values now preserve `None` as unknown instead of dropping it during normalization. This lets predicate operators consume tri-state values through the typed runtime graph.

## Decision

Predicate implementations record reusable predicate-status facts as they execute. Accepted-result traces are serialized from those records before falling back to the legacy reconstruction path.

## Learning

The important R3 proof is behavioral, not just structural. The gate must show that changing classification rules changes results, changing requested evidence changes projection, and changing unknown policy changes execution semantics.

## Evidence

- `make m1-1-gate-r3-verify`: 9 pass, 0 fail, 0 not-ready.
- `make m1-1-gate-r2-verify`: 4 pass, 0 fail, 0 not-ready.
- `make test`: 26 tests passed.

## Follow-Up

Gate R4 must decouple relation execution from implicit M1 accepted results. Gate R5 must remove the remaining approved-recipe predicate-ID literals from the generic executor source and prove node-ID opacity end to end.
