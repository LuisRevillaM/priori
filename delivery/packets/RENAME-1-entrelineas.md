# Work Packet RENAME-1: Priori → Entrelíneas

**Context**: the project has carried the name of the external company
that inspired it. The owner has chosen its own name: **Entrelíneas**
— between the tactical lines, and between the lines of the film.
Styling law: "Entrelíneas" (with accent) wherever humans read;
"entrelineas" (bare) wherever machines do (package ids, CLI, paths,
keys).

**Branch**: `packet/rename-1` off the frontier
**Executor ground rules**: unchanged (stage-committed report at
`delivery/packets/RENAME-1-REPORT.md`; full-suite table on the
committed tree; commit locally, never push; deviation law: STOP, flag,
request ratification).

## The two laws of this packet (its headline risk is violating them)

**Law 1 — history is never rewritten.** Dated records stay exactly as
written: everything under `delivery/packets/*-REPORT.md`, `*-REVIEW.md`,
prior packet briefs, `delivery/ledger.jsonl`, ADR body text that
records past decisions, committed evidence directories, review-packets/.
A rename that edits history is falsification. ADRs may gain a one-line
header note ("project renamed Entrelíneas, 2026-07-05") but their
recorded text stands.

**Law 2 — attribution never disappears.** The 741-concept atlas under
`semantic-registry/atlas/` derives from Priori (the company)'s authored
material. Its provenance must remain documented AT the atlas: add/update
a PROVENANCE.md in that directory stating origin plainly. The README
gains an honest one-paragraph history: inspired by an exchange with
Priori (the company), built independently on public data, renamed
Entrelíneas. The company's name appears exactly where truth requires
it — attribution and history — and nowhere else.

## Scope (living surfaces only)

1. Inventory first, commit the inventory: `grep -ri priori` across the
   tree, classified into (a) living surface → rename; (b) historical
   record → keep, list; (c) attribution → keep per Law 2; (d) pinned or
   hash-anchored artifact → DO NOT touch; flag with the pin's location
   for the director's merge-time regeneration. The classified inventory
   goes in the report before any rename lands.
2. Rename living surfaces: README (rewrite title/intro; add the history
   paragraph), docs/ (except dated ADR record text — header notes only),
   src/ comments and docstrings, tests, scripts, Makefile strings,
   config keys/values where not hash-pinned, knowledge-pack SOURCE
   strings (regenerable), any UI/product strings. The `tqe` package
   name stays (name-neutral). "Hermes" stays.
3. Regenerable artifacts: do NOT hand-edit generated/; note which
   regeneration commands the director runs at merge to flow renamed
   source strings through the sanctioned write paths.
4. OUT of scope: the GitHub repository name and the local folder name
   (the director/owner performs both after merge — they break working
   directories); the vision repo (its own follow-up); Modal app names;
   anything under Law 1 or the pinned class.

## Tests
Full suite green on the committed tree. If any test asserts on a
renamed string, rename test and source together and say so. If any
gate pins a surface containing the old name, FLAG it (class d) — do
not refreeze.

## Deliverables
The classified inventory; the renamed living surfaces; atlas
PROVENANCE.md; README history paragraph; stage-committed report with
full-suite table. Nothing pushed.
