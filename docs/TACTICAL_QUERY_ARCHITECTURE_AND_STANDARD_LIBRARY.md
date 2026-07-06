# Tactical Query Architecture Pointer

PRUNE-1 retired the June 23 architecture brief from current-guidance status
because it documented legacy predicate/operator grammar as composition guidance.
The archived original is preserved at
`docs/archive/prune-1/architecture/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md`.

Current architecture sources:

- `README.md` for the active source-of-truth map and product boundaries.
- `semantic-registry/` for registered capability/passport facts.
- `src/tqe/runtime/` and `src/tqe/semantic_compiler/` for executable runtime
  and compiler behavior.
- `docs/adr/0013-r1-operator-era.md`, `docs/adr/0014-r2-aggregation-era.md`,
  and `docs/adr/0015-scp2-bridge-era.md` for ratified era boundaries.
- Current packet reports under `delivery/packets/` for evidence-backed changes.

The legacy `operators` key in checked-in plans remains live machinery. This
pointer retires only the obsolete prose that presented those operators as the
current composition grammar.
