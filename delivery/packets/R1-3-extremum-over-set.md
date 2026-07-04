# Work Packet R1-3 — Operator: extremum_over_set

Issued: 2026-07-04 by the project director. Third operator of the R1 era.
Governing: ADR 0013 WITH ALL THREE ADDENDA (sixteen rules, all binding).
Case law: R1-1-REVIEW.md and R1-2-REVIEW.md in full — two operators'
rejections are your syllabus; the classes that bit twice (acting-team vs
perspective keying, whitelisted-but-unenforced constraints, unaudited
booked evidence) will be checked first.

## Ground rules (standing; all laws; sandbox note)

Branch `packet/r1-3` off the frontier (tip 679992e or later). Report
stage-committed from commit one. If your sandbox blocks git index locks,
clone to /private/tmp and commit there as you did in R1-2 round 3 — the
director recovers via format-patch; note it in the report.

## The operator

`extremum_over_set@0.1.0`: consume an anchor-evaluation channel (per-record
sets) or entity-valued records; emit the selected element per anchor under
a declared criterion — argmin/argmax over a declared value field, top-k,
nearest-to-declared-reference — with:

- declared tie-breakers (total order; no iteration-order dependence);
- witness reference to the SELECTED element (its record/entity id and
  frame) — the extremum's whole point is naming who/what won;
- UNKNOWN when set-membership coverage is incomplete AND the known members
  do not already decide the selection (could-change-answer: a missing
  candidate poisons argmin only if it could have been smaller — for
  bounded-below fields like distance >= 0 this is decidable; reason
  explicitly about your field's bounds and declare the policy);
- both-teams correctness by construction (T4 house-standard test);
- all field parameters bind-validated against the input's declared
  evidence fields (rule 2 — no whitelists);
- subject identity in evidence (whose extremum, relative to what).

## Acceptance composition

Target an atlas extremum-class row whose ledger meaning the composition
realizes and DECLARE the correspondence (the flip is gated on it). Per the
R1-0 census, candidates include nearest-defender/nearest-entity-class rows
realized over pressure or support evidence. Requirements per the teeth:
booked-evidence audit table (value distribution + per-row correspondence,
subjects verified), enforced constraints as plan elements (T2), proof run
on the COMMITTED tree with reproducing hashes (rule 16), discovery space
honest, compiler_reachable before=9/after measured on a ledger copy, real
flip left to the director.

## Required tests

House standard + case law: tie at the extremum (declared breaker decides,
deterministically, proven by shuffle); missing-member poisoning both ways
(decidable and undecidable cases); both-teams anchors at composition level
(not just the helper); top-k boundary (k > set size -> declared behavior);
selected-witness threading (the review will walk one selection back to
raw parquet); executor-path through real bind->execute.

## Deliverables

Branch `packet/r1-3`; the operator; the earned delta on a copy;
booked-evidence audit table; enumeration of declaration edits; full-suite
table; pinned-gate proof; `delivery/packets/R1-3-REPORT.md`.
