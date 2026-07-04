# ADR 0013 — R1: The Operator Era

Date: 2026-07-04. Status: ACCEPTED (project director). Builds on ADR 0012
(the honest kernel) and the atlas strategic review (docs/audits/
ATLAS_STRATEGIC_REVIEW_2026-07-01.md): the compiler grows by GRAMMAR, not
by more hand-built detectors. R1 delivers the first five compositional
operators; R2 follows with the aggregation/dossier layer. KPI:
`compiler_reachable` (currently 7 of 741 atlas concepts).

## The five R1 operators

1. **`typed_join`** — join two capability outputs on declared identity
   (same anchor, same episode overlap, same entity) under explicit
   composition constraints (same-team-perspective, frame alignment,
   entity-identity-preserved). The single largest unlock (~109 atlas rows
   name it). Fragile-possession-state (CAR-0) is its acceptance
   composition.
2. **`extremum_over_set`** — argmin/argmax/min/max/top-k/nearest over
   entities or records, with declared tie-breakers, witness references to
   the selected element, and UNKNOWN when set membership coverage is
   incomplete and could change the selection.
3. **`project_onto_axis`** — vector→signed scalar under a declared axis or
   frame (goal-ward, ball-carrier-relative, lane-normal), plus
   angle-between. Unlocks the support-geometry family the coverage map
   inflated.
4. **`window`** — bounded temporal windows BEFORE or after an anchor,
   including `trace_back_from_outcome`: outcome anchor → preceding
   sequence under declared same-possession/continuity policy. Chance
   genealogy (question bank A3) is its acceptance composition.
5. **`delta_across_anchor` + edge detection** — change of any typed signal
   across an anchor or window; rising/falling edges with declared
   hysteresis. Collapses the atlas's 18 dual pairs.

## Architecture (each principle inherits an F2 guarantee)

- **Operators are registry citizens, not executor residents.** A new
  `src/tqe/runtime/operators/` package with the same explicit-registry
  pattern as capabilities. `executor.py` gains dispatch only. The boundary
  tests extend: zero operator names in shared code.
- **Typed signatures against channel types.** An operator declares the
  temporal types it consumes and emits (episode set / frame signal /
  anchor evaluations / scalar — the envelope's vocabulary). The binder
  validates operator nodes against declared signatures exactly as it
  validates capability parameters: unknown operator, wrong channel type,
  or missing composition constraint = typed bind-time rejection.
- **Coverage propagates by declaration.** Every operator declares its
  UNKNOWN-propagation rule against the F2-Y CoverageDeclaration machinery:
  the default is could-change-the-answer semantics (UNKNOWN members poison
  a selection/join only when the known members do not already decide it).
  No operator may silently drop UNKNOWN inputs.
- **Witnesses thread through.** Operator outputs carry witness references
  to their contributing inputs (the join's matched pair, the extremum's
  selected element, the window's anchor), extending the declared witness
  chain so composed evidence still decomposes to moments.
- **Determinism as law:** declared tie-breakers, stable orderings, no
  iteration-order dependence; the same hashing discipline as everything
  else.
- **IR: one new node kind** (`operator`), additive — existing plans'
  hashes untouched; new node kind versioned from day one.

## Acceptance regime

Every operator packet ships: adversarial tests at the house standard
(including coverage-poisoning and tie cases), at least one NEW semantic
program that was previously a typed gap becoming executable end-to-end,
and the coverage-map delta (`compiler_reachable` before/after) measured by
the map's own tooling, not asserted. R1 closes with a General-Compiler
checkpoint: re-run the compiler-reachability sweep and publish the new
count with per-operator attribution.

## Sequencing

```text
R1-0  scaffolding: operator node kind (IR+binder), operators/ package +
      registry + boundary ratchets, signature validation, ZERO operators;
      zero behavior change, zero hash drift for existing plans
R1-1  project_onto_axis (smallest surface, pure per-record math)
R1-2  delta_across_anchor + edges
R1-3  extremum_over_set
R1-4  window + trace_back_from_outcome
R1-5  typed_join + composition constraints (largest; lands last on the
      firmest ground; CAR-0 fragile_possession_state as its acceptance)
R1-C  checkpoint: reachability sweep, coverage-map regeneration,
      compiler_reachable published with genealogy
```

Backlog items scheduled into this era (from F2 reviews): FrameSignal
sparse-signal trap (R1-4's window work touches that code); fabricated-
trace deletion coupled to opposite-corridor plan retirement (R1-C
cleanup); stale R3/S2 gate pins re-pin decision (R1-C); count-field vs
multiplicity limits review (R1-3).
