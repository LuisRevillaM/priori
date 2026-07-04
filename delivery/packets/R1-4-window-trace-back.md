# Work Packet R1-4 — Operator: window + trace_back_from_outcome

Issued: 2026-07-04 by the project director. Fourth operator of the R1 era.
Governing: ADR 0013 with all addenda (16 rules + the T1 structural ratchet
now covering constraint-key channels). Case law: R1-1/2/3 REVIEW files —
note R1-3's shape (candidate-set provider + independently-selecting
operator, output-metadata-only provider references) as the model.

## Ground rules (standing; sandbox clone-and-commit route sanctioned)

Branch `packet/r1-4` off the frontier (tip 4dddfc4 or later). Report
stage-committed from commit one; no push.

## The operator

`window@0.1.0`: consume an anchor set and emit bounded temporal windows —
`before` / `after` / `around` an anchor with declared durations — as an
episode-set channel usable by downstream operators and predicates. PLUS the
signature variant `trace_back_from_outcome`: from each outcome anchor,
the PRECEDING window bounded by a declared continuity policy (same
possession, same team control, or fixed duration — declared enum, each
policy's evidence requirements stated).

Semantics laws:
- Window truncation at period/data boundaries -> the truncation is
  RECORDED (truncated_start/truncated_end evidence) and the policy for
  truncated windows is declared (emit-with-flag vs UNKNOWN) — no silent
  clipping (F1-B case law).
- Continuity policies resolve from declared evidence only: same-possession
  requires possession-segment evidence covering the span; where coverage
  is missing, UNKNOWN per could-change-answer (a gap in possession
  evidence could break continuity).
- Witnesses: each window references its generating anchor; trace-back
  windows also reference the continuity evidence that bounded them.
- Determinism: declared tie/overlap policies; no iteration-order effects.
- Both-teams correctness; no field whitelists; required parameters; units
  explicit; degenerate inputs (zero-duration, anchor at boundary) declared.

## Acceptance composition

Realize an atlas `*_within` or `*_after`-class row whose ledger meaning a
window composition genuinely delivers — e.g. an outcome-window row
(shot/entry within N seconds of X) or a trace-back row — chosen per the
census, correspondence declared, discovery honest, proof on the committed
tree with reproducible hashes, before=10/after measured on a ledger copy,
real flip left to the director. Booked-evidence audit table covering ALL
rows (rule 12, as R1-3 round 2 finally delivered).

## Required tests

House standard + case law: truncation at both boundaries (recorded, policy
honored); continuity break mid-window (trace-back must bound there);
possession-coverage gap -> UNKNOWN; zero-duration and boundary anchors;
overlap policy determinism by shuffle; both-teams at composition level;
executor-path through real bind->execute; frozen-plan hash invariance.

## Deliverables

Branch `packet/r1-4` (or clone route); the operator; the earned delta on a
copy; full audit table; declaration enumeration; full-suite table;
pinned-gate proof; `delivery/packets/R1-4-REPORT.md`.
