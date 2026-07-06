# Work Packet PRUNE-1: legacy retirement — one source of truth

**Branch**: `packet/prune-1` off the frontier
**Ground rules**: unchanged (stage-committed report at
`delivery/packets/PRUNE-1-REPORT.md`; full-suite table on the
committed tree; commit locally, never push; R-AZ evidence law;
deviation law; DELIVERED-with-evidence language).

**Fences**: all sealed packet evidence and review files (history is
never rewritten); the ledger; the atlas + PROVENANCE.md; docs/design/;
ADRs (dated records — header notes only); generated/ (regenerable,
director handles at merge); anything hash-pinned (flag, never touch).

## Headline risk

Deleting something that is quietly load-bearing, or keeping so much
that the prune changes nothing. The discipline is INVENTORY FIRST:
nothing is removed until the classified inventory is committed and
every DELETE row carries evidence of non-reference.

## Scope

1. **The classified inventory (committed before any removal).**
   Sweep the tree for legacy surfaces and classify each: KEEP (live,
   load-bearing — cite the reference), RETIRE (dead — cite the
   evidence of zero references: grep, import graph, Makefile,
   CI), QUARANTINE (ambiguous or historically valuable — moved under
   docs/archive/ with a one-line provenance header), FLAG (pinned or
   governance-coupled — director decides at merge). Candidate areas,
   not exhaustive: stale top-level state docs (KNOWN_ISSUES.md,
   CURRENT_STATE.md, MILESTONES.md — known to drift; the truth lives
   in delivery/ and the ledgers); M1-era workbench documentation and
   audit artifacts under docs/audits/ and any tracked generated/audits
   remnants; superseded architecture docs describing the pre-operator
   catalog era as if current; dead scripts under scripts/ with no
   Makefile/CI/import references; the legacy predicate-operator
   DOCUMENTATION anywhere it presents gt/lte/persists_for as the
   composition grammar (the pack's legacy `operators` key itself is
   LIVE machinery — KEEP, but docs must not present it as the
   grammar). Untracked working files in the repo root (findings.md,
   progress.md, review-packets/, docs/learnings.zip and similar) are
   NOT yours to delete: inventory them with a recommendation column
   for the owner.
2. **Execute the retirement** per the inventory: RETIRE rows deleted,
   QUARANTINE rows moved with headers, KEEP rows untouched, FLAG rows
   listed for the director.
3. **The README and any surviving top-level docs** point to the
   current sources of truth (delivery/, ADRs, design charter,
   knowledge pack) and nothing else.

## Tests
Full suite green on the committed tree; if a test references a
retired surface, retire or rewrite the test WITH its surface and say
so in the inventory row.

## Deliverables
The committed classified inventory (the report's core); the executed
prune; stage-committed report with full-suite table. Nothing pushed.
