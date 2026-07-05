# Work Packet R2-0: Pre-era correspondence declarations — the era's entry toll

**Era**: R2 open (first packet)
**Branch**: `packet/r2-0` off the frontier
**Executor ground rules**: commit locally in stages, never push; report
file `delivery/packets/R2-0-REPORT.md` created WITH the first item
commit; full-suite table (`make test`) on the committed tree in the
final report, every failure enumerated and attributed.

**Fences (do not touch)**:
- `generated/coverage-map.json` / `.csv` — ledger flips and maturity
  values are the director's alone. R2-0 adds declarations to TARGET
  files; it never touches the tracked ledger.
- `semantic-registry/atlas/` raw manifest; `artifacts/autonomous/`;
  all sealed evidence under `delivery/packets/r1-5-*` and
  `delivery/packets/r1-c-sweep/`.
- No freezes, no re-pins.

## Headline risk (the one argument this packet must win)

R1-C's hardened guard raises on the seven pre-era rows because their
targets carry no `semantic_correspondence` declaration (tri-state:
UNKNOWN cannot flip). Until declarations exist, no future
ledger-updating unified sweep can run. The risk is authoring
declarations that are *plausible prose* rather than *true statements
of what each certified plan computes* — a wrong declaration laundered
into the guard's trust is worse than no declaration.

## Scope

For each of the seven pre-era compiler_reachable rows (the sweep's
reachable set minus the five era rows — enumerate them from
`delivery/packets/r1-c-sweep/row-ledger.json`):

1. Read the row's certified plan in
   `delivery/packets/r1-c-sweep/plans/` and its target entry in
   `config/compiler-reachability/search-targets.v0.json` (or
   `targets.v0.json` — locate each row's actual target file).
2. Author a `semantic_correspondence` declaration in the target file,
   following the five era declarations as the house pattern
   (see the era targets: `coverage_row`, `meaning`,
   `source_relation`/`composition`, units, orientation fields, and a
   `claim_boundary` sentence where the row's language could overreach —
   fragile_possession_state's declaration is the reference for
   boundary-writing).
3. The `meaning` must be derived from what the certified plan ACTUALLY
   computes — evidence relations, anchor sources, frames, units — not
   from the concept's atlas name. Where the plan computes less than the
   concept name suggests, the declaration says the lesser true thing
   (ADR 0013 principles 15 and 19; product language cannot exceed
   evidence strength).
4. Per-declaration verification appendix in the report: plan section
   references (which relation, which fields) justifying every clause
   of the declaration. This appendix is what the director's semantic
   acceptance reviews — a declaration whose clause lacks a plan
   citation will bounce the round.

Tests: extend the guard's test module with a case that validates every
declaration in every committed target file loads as well-formed under
`validated_semantic_correspondence` (shape + row-identity for its own
concept). Mutation standard: corrupt one committed declaration's
coverage_row in a scratch copy, watch the named test fail, restore.

Do NOT run a ledger-updating sweep. That is the director's act, after
semantic acceptance of the declarations (the review IS the
correspondence verdict, per principle 19).

## Expected legitimate ripples
Target-file hashes change → any artifact that pins target file hashes
may drift; report, don't refreeze.

## Deliverables
`delivery/packets/R2-0-REPORT.md` with the per-declaration verification
appendix; seven authored declarations in their target files; the
loads-well-formed test. Nothing pushed.
