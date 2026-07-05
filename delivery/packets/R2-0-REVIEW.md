# R2-0 Review — Round 1: ACCEPT-WITH-FIXES

Reviewed 2026-07-05 on packet/r2-0 (240dc90..53ccd9f, base aad394d).
Adversarial review checked all seven declarations clause-by-clause
against certified plans AND the runtime primitives beneath them;
director hand-verified two declarations against plan structures
(thresholds, join keys, settled-possession fields) and confirmed the
plans' own disallowed_claims carry the intent/quality boundaries.

## The semantic acceptance (this review is the correspondence verdict)

No material overreach in any of the seven declarations. Every unit,
threshold, frame field, scope, and relation clause has a corresponding
plan structure; carry_out_of_pressure is stated as a join, never as
escape; support_arrival claims only distance/time/count arrival;
post_regain's "settled" is defined verbatim to the recipe;
shape_expansion attributes the width change to nothing. The appendix
contains no false citations. The seven coverage_row strings match the
ledger's pre-era reachable rows exactly; the two never-claimed targets
are correctly left undeclared. Per ADR 0013 principle 19, this
paragraph is the human acceptance act for these seven declarations.

## Findings and fix list (round 2, mechanical)

1. (F1) The declarations test iterates a hardcoded 7-path list. The
   packet said every committed target file: discover by glob over
   config/compiler-reachability/*.json (skip payloads without a
   targets key) plus the sweep snapshot.
2. (F2) Remove the R2_0_DECLARATION_TARGET_FILE env override from the
   production test path; the mutation test calls the loader with a
   scratch path directly.
3. (F3) Use anchor_source in one sense across all seven declarations
   (the era declarations' upstream sense); where the result anchor is
   meant, name it result_anchor or equivalent.
4. (F5) post_regain_retention: add one clause making explicit that the
   settled segment may begin anywhere in the 8.0-second window (an
   intervening loss before the settled segment does not fail the row).
5. (F4, partial) Add minimum_prior_possession_seconds=0.4 to the
   post_regain declaration — the one omitted constraint a reader would
   care about. Other zero-valued defaults stay in plan-space.
6. (F6) Appendix wording: drop "exactly" or scope it to the declared
   fields.
7. Full-suite table on the new committed tree.

Verdict: ACCEPT-WITH-FIXES. No finding invalidates a declaration.
Round 2 appends to packet/r2-0; the director's sweep (ledger-updating,
evidence-refreshing) follows the fix round at merge — director's act.
