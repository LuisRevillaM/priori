# R2-2 Review — Round 1: REVISE

Reviewed 2026-07-05 on packet/r2-2 (c742920..25d3b66, base e1e2f3c).
Director's full suite green. Adversarial review recomputed all 14
flagship rows' six-way partitions and all three bounds independently
from the committed audit: zero mismatches. Every constructor attack
raised (external bounds in all combinations, subset violations
including hidden-in-mixed-groups, negative counts, fourth statuses,
replace()). The bounds law is implemented exactly as specified.

## Findings

**F1 (BLOCKING) — sound recomposition, silent deviation.** The spec's
flagship populations were degenerate — verified empirically: all 145
spec-numerator rows ARE the denominator's PASS rows (retention is
baked into fragile_possession_state's terminal join:
left_status_field=window_status required PASS) — and un-bindable
under the spec's own subset invariant. The executor recomposed to the
sound structure (denominator = right_status PASS, the
pressure-without-support condition; numerator = typed_join_status
PASS, those that additionally sustained the continuity window) but
the report contains no deviation section, no degeneracy statement, no
ratification request — and the spec's "denominators must be the SAME
14 rows" reconciliation, unsatisfiable under the recomposition, was
silently replaced by weaker (individually true, precisely labeled)
claims under the same heading. ADR 0014 principle 21: changing the
denominator is changing the question. Questions are the director's.

**F2 (BLOCKING) — CAR name on a team-level table.** All flagship
surfaces (filenames, plan ids, node ids, population_expression baked
into evidence, titles, commit title). Root cause is the director's
own spec text ("This is CAR-0 v0"), written before the owner's
correction and against docs/CAR_NORTH_STAR.md's standing law ("no
milestone may claim CAR until every layer below is verified"). The
executor followed the brief; the brief was wrong.

**F3 (BLOCKING) — share mode cannot express a share.** It computes
per-key RATES and asserts they sum to 1 (per-key rates don't; shares
do); a genuine share query has no code path; the sum assertion is not
load-bearing (deleting its call fails no test); no positive share
fixture exists.

F4 (LOW): runtime status-field typos fail open (mitigated at bind;
the generator path bypasses the binder check). F5 (LOW): flagship
computed from the committed audit rather than plan execution —
disclosed honestly, R2-1 precedent accepted, R-W identity-field debt
still carried. F6 (INFO): D1-only populations yield
PASS-with-observed-None and hardcoded [0, 0]. F7 (INFO): empty
populations emit zero rows instead of a typed row.

## Director's rulings

**R-AA (on F1).** The recomposed populations are hereby RATIFIED as
the flagship question: fragility-condition → retention-outcome is
what the spec meant, and the evidence proves the spec's letter could
not have been built honestly. The process failure stands corrected:
when a spec cannot be implemented as written, the deviation is
FLAGGED in the report with a ratification request — silently building
the right thing is still building an unratified thing (the same
boundary as R1-5's flip: correctness does not transfer authority).
Round 2 adds the deviation section: the degeneracy, its root cause in
the R1-5 terminal join, the ratified populations, and an honest
reconciliation heading stating what correspondence IS claimed and why
the spec's version was unsatisfiable. Era note recorded: the
condition-side concept (pressure-without-support, the true CAR-ladder
denominator) deserves registration as a named concept in a later
packet rather than living implicitly as right_status.

**R-AB (on F2).** Rename every CAR-named surface: table files to
fragile_retention_rate_table.*, plan/node/invocation ids to
fragile_retention_*, population_expression text to "fragile-condition
retention rate". The director amends his own spec's flagship language
in the same stroke (committed alongside this review). Standing law
restated: CAR is a PLAYER metric; nothing team-level ships under the
name; the CAR ladder is baseline (this packet) → player residual →
spatially-conditioned replacement.

**R-AC (on F3).** Amputate share — the R-U precedent applies. The
operator registers as `rate@0.1.0` (rename from rate_and_share:
an operator name may not advertise an unimplemented mode — the same
law as capability surfaces). Ratchet and registry follow the rename.
Share's correct semantics are declared future work in the
limitations: key-partition COUNTS over one COMMON denominator,
observed shares summing to 1 over known rows, interval-typed.

**R-AD (on F6, F7).** D1-only populations: status UNKNOWN with the
[0, 0] bounds preserved (status reflects that nothing was observed;
bounds keep what is still knowable) — with a test. Empty populations
emit the typed UNKNOWN degenerate row, not silence — with a test.
F4/F5 recorded as carried debt (R-W identity-field declaration at
source remains the standing entry on the ledger).

## Fix list

1. Deviation + ratification section and honest reconciliation heading
   per R-AA.
2. Full rename per R-AB (files, ids, expressions, md titles; note the
   original commit title stands in history — the report notes the
   rename).
3. Share amputation + operator rename to `rate` per R-AC, ratchet and
   registry updated, limitations naming the future share semantics.
4. D1-only and empty-population behavior per R-AD, with tests.
5. Full-suite table on the new committed tree.

Round 2 appends to packet/r2-2.
