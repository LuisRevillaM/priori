# Work Packet F1-C — Progressive-Corridor Episode Honesty

Issued: 2026-07-02 by the project director. Self-contained brief for an
external executor. Read fully before writing code.

## Ground rules (same regime as F1-B; that packet's two-round history is
instructive — round 1 failed at an unwired executor boundary)

- Dedicated branch `packet/f1-c` off `codex/afl08-passport-loop` (tip
  `3d7e648` or later). Acceptance review gates the merge.
- Read first: `docs/audits/FOUNDATION_AUDIT_2026-07-01.md` (findings T3, T4;
  also the spatial-kernel audit items on `relations.py` reproduced there),
  `delivery/packets/F1-B-REVIEW.md` (what acceptance rejects),
  `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md` (claim
  boundaries for the corridor relation).
- Tri-state doctrine: UNKNOWN = insufficient/contradictory evidence; FAIL =
  positively observed contradiction. Missing evidence never silently becomes
  PASS, FAIL, or fabricated continuity.
- All `make <gate>-verify` targets are read-only checks. Never run
  `TQE_WRITE=1`; never touch `delivery/autonomous/afl09a/frozen-expectations/`,
  `delivery/n1d/`, `artifacts/`, `semantic-registry/`, `generated/`.
  Re-freezes and regeneration happen at director acceptance.
- **N1 fence (the big one for this packet):** the N1 hero question is
  corridor-based. All N1 evidence is pinned history
  (`delivery/n1d/*`, `artifacts/n1c/*`, N1 reports) and must not be
  regenerated or edited. Your report must include a full gate-status table:
  `make n1c-verify`, `n1d-verify`, `n1d1-verify`, `n1i-verify`, plus every
  `afl-*-verify` gate that consumes corridor outputs (survey which do).
  F1-B's round-1 rejection was partly for an unreported gate — do not repeat
  it. Also run `make m1-1-verify` and `make m1-2-verify` if runnable locally
  and report status.
- Env: `.venv/bin/python`, `PYTHONPATH=src`; full suite
  `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` (~8 min,
  needs `data/canonical/v1`). `tests/test_afl_validation_factory` fails on
  uncommitted `src/tqe/runtime` edits by design — green after commit.

## Scope — `src/tqe/runtime/relations.py` (progressive corridor machinery)

Lane geometry (`destination_lane`), GK-blind clearance semantics, and
anchor-set evidence stamping are OUT of scope (later packets F1-D and F2).

### 1. T3a — missing frames must not be bridged into episode continuity
(audit: `relations.py:152-156` + `episodes_from_states:331-449`)

A frame absent from tracking only bumps a global counter and never enters
`states_by_states`; PASS states on either side of a dropout become adjacent,
fabricating corridor continuity (reproduced: states at frames 100,105,
[110 missing],115,120 → single episode 100→120). Fix: emit explicit
per-target UNKNOWN states for missing frames inside the analysis window, so
an episode cannot span a gap silently. An episode interrupted by missing
frames closes with a distinct close reason (suggest
`closed_on_missing_evidence`), and whether a new episode may reopen after
the gap is a declared semantic, not an accident.

### 2. T3b — UNKNOWN frames must not count as failures for hysteresis
(audit: `relations.py:431-441`)

Any non-PASS status (including UNKNOWN) increments `fail_count`, so two
UNKNOWN frames close an open episode as `closed_after_failures` — missing
evidence converted into a definite boundary with a mislabeled reason. Fix:
UNKNOWN and FAIL are separate hysteresis channels; UNKNOWN-driven closes use
the distinct close reason from fix 1; only observed FAILs may close as
`closed_after_failures`.

### 3. T3c — anchor evaluation must reflect unknown coverage
(audit: `relations.py:210-217`)

The anchor evaluation returns PASS whenever any episode exists, regardless
of how much of the window was UNKNOWN. Fix: carry the per-anchor
unknown-frame coverage into the anchor evaluation record (a typed field, not
a name convention), and where coverage could change the answer — e.g. the
episode exists only because a gap was bridged, which fix 1 eliminates — the
evaluation must be UNKNOWN. Declare the rule; do not invent a threshold
silently (a declared parameter with a conservative default is acceptable).

### 4. T4 — `duration_seconds` off-by-one and flicker-inflation
(audit: `relations.py:378`)

`duration_seconds = pass_frame_count / analysis_rate` counts PASS states,
not elapsed span: two adjacent PASS frames at 5 Hz report 0.4 s instead of
0.2 s, and flickering episodes report neither wall-clock span nor
in-corridor time. Fix: `duration_seconds = (close_frame - open_frame) /
analysis_rate_hz` (elapsed span), and expose the PASS-state count as its own
typed output if consumers need it. KNOWN RIPPLE: a frozen-baseline
integration test bakes the wrong duration in
(`tests/test_m1_1_runtime.py` expects 0.4 where the honest span differs) —
update it with justification. Duration-threshold semantics (`persists_for`,
the hero question's ≥0.8 s) consume this value: quantify in your report how
many corridor episodes on the M1.1 corpus cross the 0.8 s threshold before
vs after (both directions).

### 5. Small hardening in the same module

- `load_attack_x_sign` raises instead of yielding UNKNOWN on unknown
  orientation (audit spatial item 17): return UNKNOWN with a typed reason
  through the callers.
- Add unit tests for `episodes_from_states` directly — the audit found zero
  unit coverage for the hysteresis core.

## Required tests

House standard `tests/test_m2a_bypass.py`. Minimum: dropout-inside-episode
(no bridging; distinct close reason); dropout at open/close boundaries; two
UNKNOWN frames do not close as failures; genuine two-FAIL close still works;
duration = elapsed span at multiple analysis rates (5 Hz and 25 Hz);
flickering PASS/FAIL/PASS episode durations; anchor-evaluation UNKNOWN when
coverage could change the answer; orientation-unknown → UNKNOWN. Plus
executor-path tests (through the real binder → executor, as F1-B round 2
did) for at least one corridor plan exercising the new close reasons.

## Expected legitimate ripples (report, don't fix)

- `tests/test_m1_1_runtime.py` corridor pins (durations, possibly episode
  counts) — update with per-pin justification.
- `make n1a`-class verifiers and any corridor-consuming AFL gates may fail
  check mode on hash or content drift — REPORT with counts (content changes
  need the before/after result counts and which fix moved them).
- SCP-0 parity if you add declared parameters/outputs — report only.

## Deliverables

1. Branch `packet/f1-c`, focused commits.
2. New tests green; full suite green except enumerated expected ripples.
3. `delivery/packets/F1-C-REPORT.md`: per-fix summary with file:line; the
   corridor-episode delta on the M1.1 corpus (episode count, duration
   distribution before/after, 0.8 s-threshold crossings both directions);
   the complete gate-status table (see N1 fence); every changed pin with
   justification; anything this packet's analysis missed.
