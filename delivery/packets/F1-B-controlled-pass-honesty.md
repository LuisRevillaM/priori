# Work Packet F1-B — Controlled-Pass Tri-State Honesty

Issued: 2026-07-02 by the project director. Self-contained brief for an
external executor. Read this file fully before writing code.

## Ground rules (non-negotiable)

- Work on a dedicated branch: `packet/f1-b` off
  `codex/afl08-passport-loop`. Do NOT commit to the frontier branch directly;
  acceptance review gates the merge.
- Read first: `docs/audits/FOUNDATION_AUDIT_2026-07-01.md` (findings T1, T2,
  G9, G10 context), `delivery/m2a-high-bypass-completed-pass/SPEC.md` (the
  contract this module violates), `docs/CASE_STUDY.md` (public narrative that
  quotes this module's numbers), and `KNOWN_ISSUES.md`.
- Tri-state doctrine: UNKNOWN = evidence insufficient/contradictory to
  decide; FAIL = positively observed contradiction. Missing evidence must
  NEVER become FAIL or PASS.
- Every `make <gate>-verify` target is a read-only check. Never run anything
  with `TQE_WRITE=1` and never modify files under
  `delivery/autonomous/afl09a/frozen-expectations/`, `delivery/n1d/`, or
  `artifacts/` — expectation re-freezes are a governance action performed by
  the director at acceptance, not by this packet.
- Do NOT edit `docs/CASE_STUDY.md` or `apps/workbench-alpha/src/CaseStudy.tsx`
  even though their quoted numbers will become stale — the narrative update
  is a separate director decision informed by your report.
- Python env: `.venv/bin/python`, `PYTHONPATH=src`. Full suite:
  `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` (requires
  local canonical data under `data/canonical/v1`; ~6 min).
  Note: `tests/test_afl_validation_factory.py` fails by design while
  `src/tqe/runtime` has uncommitted changes — it goes green after you commit.

## Scope — four behavioral fixes in `src/tqe/runtime/controlled_pass.py`

(Field/output renames are explicitly OUT of scope — they are contract changes
with registry/projection blast radius, reserved for a later packet. Opponent-
aware control semantics (audit G1) is also OUT of scope.)

### 1. T1 — truncated reception window → UNKNOWN (audit: `controlled_pass.py:410-481`)

A reception search window clipped by period end currently returns
`FAIL/"reception_window_expired"` even with zero frames inspected. A pass in
flight at the half-time whistle is not a contradicted reception.
Fix: when the window is truncated by the period boundary (or the anchor is at
or near the final frame) and no controlling evidence was observed, return
UNKNOWN with a new typed reason (suggest `reception_window_truncated`,
following the module's existing reason enum style). A genuine full-length
window with contradicting evidence stays FAIL.

### 2. T2 — sparse-tracking release → UNKNOWN (audit: `controlled_pass.py:351-357`)

Release control currently yields `FAIL/"release_not_confirmed"` if even one
non-missing frame lacks control — including 1-of-101-frames tracking. The
SPEC declares `release_control_status ∈ {PASS, UNKNOWN}` (no FAIL domain) and
its UNKNOWN semantics explicitly cover missing frames.
Fix: apply the module's existing `max_missing_frame_ratio` discipline to the
release window (it is currently reception-only); insufficient frame coverage
→ UNKNOWN. Restore the SPEC's declared status domain for
`release_control_status`. Where the executor/consumers read this field,
verify UNKNOWN propagates per doctrine.

### 3. G9 — event filter admits set pieces (audit: `controlled_pass.py:634-637`, also `one_touch.py:222`)

The filter `"Pass" in event_type` admits 76/639 (11.9%) set-piece events on
J03WOY (throw-ins evaluated with a ground-plane control radius while the ball
is in the thrower's hands). The SPEC default is `event_type_filter:
["Play_Pass"]`.
Fix: implement the SPEC's declared `event_type_filter` parameter (declared,
defaulting to `["Play_Pass"]`), in both modules. Candidates excluded by the
filter must be excluded from the candidate denominator (not silently counted
as FAIL/UNKNOWN).

### 4. D9 — alignment tolerance and reason vs SPEC (audit: `controlled_pass.py:592, 296-304`)

The 100 ms release-alignment tolerance is hardcoded (SPEC parameter
`max_release_alignment_ms`, default 250, range 0–1000), and misalignment is
reported as `"missing_tracking"` where the SPEC mandates
`"release_frame_alignment_failed"`. Fix both: declared parameter with SPEC
default, and the SPEC's reason string. Also reconcile
`reception_search_seconds` (code 6.0 vs SPEC default 4.0) — implement the
SPEC default as a declared parameter; if the observed results on J03WOY
change materially under 4.0, report the comparison rather than choosing
silently (include both distributions in your report).

## Required tests

House standard is `tests/test_m2a_bypass.py`: synthetic adversarial geometry,
mirrored orientations, exact boundaries, shuffle determinism,
missing→UNKNOWN, threshold-free assertions. Required minimum:

- T1: release at last frame of period; release 2 frames before period end;
  full window with genuine contradiction (stays FAIL).
- T2: passer tracked 1-of-N frames (UNKNOWN); passer fully tracked and
  clearly not in control at release (whatever the SPEC domain allows);
  coverage exactly at the `max_missing_frame_ratio` boundary.
- G9: throw-in/free-kick/goal-kick/kick-off candidates excluded under the
  default filter; widened filter re-admits them with correct provenance.
- D9: alignment at/inside/outside the declared tolerance; reason strings.

Existing pinned integration tests (`tests/test_m2a_controlled_pass.py`,
`tests/test_m2a_pass_bypass.py`, `tests/test_m2a_high_bypass_pass.py`) pin
snapshot counts/ids that WILL legitimately change. Update them, and for each
changed pin include a comment-free, commit-message-documented justification:
old value → new value → which fix moved it and why that direction is
correct (e.g. "84 release_not_confirmed FAILs → N FAILs + M UNKNOWNs under
T2: sparse windows reclassified").

## Expected legitimate ripples (do not "fix" these)

- The four AFL-09A gates (`afl-substrate-q4`, `afl-time-to-arrival`,
  `afl-relative-position`, `afl-line-break-support-response`) and
  `afl-09a-verify` will fail in check mode after your change if the
  controlled-pass contract or results move — that is expected drift,
  re-frozen by the director at acceptance. Report their status; do not
  re-freeze.
- If you add declared parameters (G9/D9), the catalog entry for
  `controlled_pass_episode` changes → `make scp-0-verify` will fail on
  parity drift. Report it; the director regenerates projections at
  acceptance. Do NOT edit `semantic-registry/` or run write modes.

## Deliverables

1. Branch `packet/f1-b` with focused commits (one per fix is ideal).
2. All new adversarial tests green; full suite green EXCEPT the expected
   ripples above (list exactly which tests/gates fail and why).
3. A report (as `delivery/packets/F1-B-REPORT.md` on your branch) containing:
   - per-fix summary with file:line;
   - **the headline table: old vs new PASS/FAIL/UNKNOWN distribution of
     `controlled_pass_episode` on match J03WOY** (old: 453/135/51 of 639),
     including the per-reason breakdown (how many of the 84
     `release_not_confirmed` FAILs became UNKNOWN, etc.), under BOTH
     reception_search_seconds values if D9 changes results;
   - the same distribution with the set-piece filter on vs off;
   - every pinned test value changed, with justification;
   - anything you found that this packet's analysis missed.

## Acceptance (director-run; for your information)

Adversarial re-review of each fix against the audit findings; verification
that no UNKNOWN-inflation shortcut was taken (UNKNOWN only where evidence is
genuinely insufficient); distribution review; then expectation re-freezes and
projection regeneration on the frontier after merge.
