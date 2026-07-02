# F1-C Acceptance Review — Round 1: REVISE (merge blocked on 2 items)

Reviewed 2026-07-02, branch `packet/f1-c` commit `61b5d62`, independent
adversarial pass plus director verification. Overall verdict
ACCEPT-WITH-FIXES: the implemented semantics are honest and every
quantitative claim in F1-C-REPORT.md reproduced exactly (the 115→100
threshold change, the 0-delta state counts, the byte-identical restoration
of the bypass tests, the gate drift shapes). Merge is blocked until R1 and
R2 below land on the same branch.

## Verified and settled (no action)

- The suspected test_m1_1_runtime contradiction dissolved: the audit's 0.4
  value is an inert input fixture (never read by its consumer), the live
  assertion is an inequality over rows the executor pre-filters with the NEW
  duration, and there is a single duration source consumed by executor and
  gate alike. T4 is fully fixed.
- T3a/T3b/T3c behavior verified by independent probes, including the
  no-UNKNOWN-inflation matrix (full-coverage-no-episodes stays FAIL).
- Duration math correct at 5 Hz and 25 Hz (canonical frame ids make the
  analysis rate drop out); all 165 corpus episodes satisfy elapsed-span
  exactly.
- Director attribution of the unreported full-suite failure (see R3):
  the attested-hero workbench contract test now finds 11 live results vs
  the pinned 14 — the pinned bundle shows the lost results sat at exactly
  0.8s under the old counting (0.6s honest). Legitimate truth-ripple;
  governance handling (test re-pin + surface disclosure wording) is the
  director's at merge.

## Required for round 2 (same branch, append commits)

**R1 — close the per-target bridge (the substantive one).**
`relations.py:181-201`: a target absent from an *available* frame produces
no state, so an episode silently spans the gap and elapsed duration counts
untracked time (probe: target tracked at 100,105, absent 110, tracked
115,120 → one bridged episode, duration 0.8s — across the hero threshold).
Emit per-target UNKNOWN for in-window frames where the frame exists but the
target (or ball, as applicable) lacks a usable position, so the missing-
evidence hysteresis and coverage fields apply uniformly. Add the probe as a
test, plus a boundary case (absence at window open/close). Re-run the M1.1
corpus delta and report if any number moves (currently 0 interior
per-target gaps exist in-corpus, so expect no change — verify, don't
assume).

**R2 — declare the new semantics.** The packet required declared rules, not
accidents: (a) declare the `close_reason` evidence field in the catalog for
both corridor variants, with its full value enum including
`closed_on_missing_evidence`; (b) state the coverage rule ("no witness +
any UNKNOWN state → anchor evaluation UNKNOWN") in the catalog entry
description or a declared parameter; (c) document reopen-after-gap and the
FAIL×2-vs-missing-evidence close asymmetry in the module docstring and
catalog limitation text. No semantic changes — declarations only.

**R3 — run the FULL suite and report it.** The report's verification table
omitted the full-suite run the packet required; it would have surfaced the
attested-hero failure (14→11) that the director found instead. Round 2's
report must include the full-suite result with every failure enumerated and
attributed. This is the second consecutive packet where an unrun
verification hid a downstream effect — it is now a standing acceptance
bar: no full-suite table, no review.

## Ride-along (optional in round 2, otherwise next packet)

- Orientation-unavailable path fabricates a synthetic UNKNOWN state
  (`total_state_count=1` for an unevaluated window) and pollutes global
  state counts; the empty counter already yields UNKNOWN (`relations.py:55-66`).
- Promote the single-node executor-path test to full `execute()`
  end-to-end.
- Move the 11 corridor tests out of `tests/test_m2a_bypass.py` into their
  own module (the packet's "house standard" wording invited the misread —
  clarified for future packets: the file is the style model, never the
  destination).

Fences and environment notes unchanged from the packet. The n1c-verify
failure observed in this working copy is environmental (two untracked
workshop handle files), not caused by this diff.

---

# F1-C Acceptance Review — Round 2: ACCEPTED

Reviewed 2026-07-02, commits `f1a18ca` + `6a475b7`, merged as `a0c9732`.
R1 verified empirically (the round-1 probe now yields two episodes split by
closed_on_missing_evidence; 16 independent probes including NaN positions,
reopen-requires-fresh-PASS, and boundary absences all pass; corpus
byte-identical before/after). R2 declarations conform in both catalog
variants and the module docstring. R3 full-suite table matches reality —
exactly the six expected failures, independently reproduced.

Director acceptance actions in the merge batch: contracts regenerated
(parity PASS, 0 findings); attested-hero contract test re-pinned 14 -> 11
with the duration-honesty rationale (the attestation remains valid history);
m1_1_gate_d episode-shape expectation corrected to elapsed-span semantics
((N-1)/rate minimum). Ride-alongs carried to the F1-D/F2 backlog:
orientation synthetic-UNKNOWN fabrication, executor-path test promotion,
corridor-test relocation, and one round-2 semantic note (whole-missing-frame
UNKNOWN emission scoped to window-present targets — defensible, needs a
declaration line).
