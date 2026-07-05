# R1-C Review — Round 1: REVISE

Reviewed 2026-07-04 on packet/r1-c (3d2c9cb..bf8624f, base 54e1263).
Adversarial review with execution-verified findings; director's suite run
green on the committed tree; sweep identity spot-checked by hand
(sweep-reachable set == ledger's 12, exactly; the two negatives were
never claimed).

## What survived attack

- The unified sweep is real, coherent, and fence-clean: one run, 14
  targets byte-identical to committed config, delivery copies
  byte-identical to generated outputs, the r1_5 plan reproducing the
  frontier acceptance document_hash, decomposition exactly 7 pre-era +
  5 era rows.
- Fences held everywhere: coverage-map byte-identical to frontier,
  sealed evidence untouched, zero pin/freeze/lock files in the diff.
- C2's rejection tests are load-bearing (guard deleted in a scratch
  copy → all three named tests fail).
- C3a is genuine: the continuity_team_role == anchor_team_role
  assertion is independently sourced from the selected continuity
  record and would trip a PASS-status-with-wrong-team canon bug that
  the status assertions alone would not. Verified against real
  canonical data.
- Report stage-committed from the first commit, per the law.

## Findings

**F1 (BLOCKING).** The C2 guard enforces "correspondence declared,"
not "correspondence sound": executed against a result carrying
`semantic_correspondence: "FAIL"`, the row flipped to
compiler_reachable and recorded the FAIL into evidence. The
declaration's `coverage_row` is also never checked against the row's
concept — a declaration for a different concept passes. The report
presents C2 as DONE without disclosing the presence-vs-verdict gap.

**F2 (BLOCKING).** The committed population-audit generator provably
did not produce the sealed audit: its scope follows the copy-proof
bundle's pinned match_ids (one match → 1006 rows) vs the sealed
audit's 7 matches / 8414 rows, and the sealed audit's recorded
source_plan_bundle_hash does not equal the tool's own stable_hash of
the bundle at the recorded path. The report claims the generator can
rebuild the full audit; as committed, it cannot. (Corroborating note:
per-period numbers for the one overlapping match match the sealed
audit exactly — the engine agrees; the scope and provenance are what's
wrong.)

**F3 (NON-BLOCKING).** The sweep report's "Correspondence status:
PASS" column relabels "declaration present" as a verdict. No evaluated
verdict exists in the machine evidence.

**F4 (NON-BLOCKING).** The data manifest is not verified against any
recorded expectation (git tracking is the only pin), and the report
does not state the residual risk: a same-size content tamper passes
the default gate (deep verify catches it; verified).

**F5 (NOTE).** The sweep evidence is not self-attesting (no tree SHA
or timestamps in the machine artifacts; the pin lives in report
prose). F6 (NOTE): the C4 timing table measured a target that never
exercises the changed code path; the real win (per-instantiation
tree-hash of ~2.6GB removed) is unquantified. F7 (NOTE): 11 of 12
sweep plans differ by document_hash from the plans that earned the
original flips (fresh derivation on one tree is the checkpoint's
point; the divergence belongs in the report). F8 (NOTE):
update_coverage_rows dedups results by concept last-wins; unreachable
with unique-concept targets today.

## Director's rulings (round 2 implements these, not interpretations)

**R-Q (on F1).** Correspondence in this schema IS a declaration, and
that is the truth the guard must protect — do NOT invent a
machine-emitted verdict field: correspondence verdicts are human
acceptance acts recorded in review files, and a machine field named
PASS would launder judgment into fake attestation. The guard must
therefore: (a) require the declaration to be a dict with at minimum
`coverage_row` and `meaning` keys; (b) require
`declaration.coverage_row == row concept`; (c) RAISE on any
non-conforming value — strings (including "PASS"/"FAIL"), wrong
concept, missing keys. Tri-state: only a well-formed declaration for
THIS row flips; everything else is UNKNOWN and UNKNOWN raises. The
presence-vs-verdict distinction gets a named paragraph in the report
and rides to the ADR at merge (director's act).

**R-R (on F2).** The sealed audit stays sealed — it is corroborated,
not replaced. The generator must accept explicit full-corpus scope
(all canonical matches), regenerate the audit from the committed R1-5
plan bundle, and the smoke test must compare the regenerated
per-period numbers against the SEALED audit.json numbers-identically
across all 7 matches. The regenerated audit (with provenance fields
that are true of ITS run, including a bundle reference whose
stable_hash matches what it records) is committed under
`delivery/packets/r1-c-sweep/population-audit/`. If the sealed
audit's recorded bundle hash cannot be reproduced from any committed
artifact, say so in one honest sentence in the report — the numbers
matching across 8414 rows is the corroboration that matters; the
provenance defect is recorded, not hidden.

**R-S (on F3).** Reword the column to "Correspondence: DECLARED".
Wherever the report says PASS about correspondence, it means DECLARED.

**R-T (on F4).** State the same-size-tamper residual and the
unpinned-manifest status in the report as declared debt. Pinning the
manifest hash into governance artifacts is the director's act at
merge, not the packet's.

## Fix list (numbered, exhaustive — nothing else changes)

1. Harden the guard per R-Q; extend the rejection tests: FAIL-string
   raises, wrong-coverage_row raises, well-formed declaration flips.
   Mutation standard applies.
2. Generator + regenerated audit per R-R; smoke test compares against
   sealed numbers across all 7 matches.
3. Report wording per R-S, R-T; add the F7 divergence note and the F6
   honest correction (changed code path is not exercised by
   scp-0-verify; state what IS exercised and where the win lands).
4. Full-suite table on the new committed tree, per the standing bar.

Round 2 appends commits to packet/r1-c. Nothing is force-pushed;
history is append-only.

## Debt recorded (director's ledger)

- Pre-era correspondence declarations (7 rows) must be authored before
  any future ledger-updating unified sweep — the hardened guard will
  correctly crash on them (spec-mandated tri-state). R2-era entry work.
- Manifest hash pinning into governance artifacts — director, at merge.
- F8 dedup semantics — revisit only if duplicate-concept targets appear.
