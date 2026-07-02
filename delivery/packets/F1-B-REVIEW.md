# F1-B Acceptance Review — Round 1: REJECTED

Reviewed: 2026-07-02, branch `packet/f1-b` (commits `ee4ab83`, `a0787a9`),
by the project director with an independent adversarial review pass. Every
blocking finding below was empirically confirmed, not inferred.

## What passed (keep exactly as-is)

The four module-level fixes are honest and verified: no UNKNOWN inflation
(contradictions still FAIL from inside the reception loop, before any
truncation/ratio check); the release FAIL→UNKNOWN change is SPEC-mandated,
not a shortcut; the missing-frame-ratio boundary is on the correct side;
denominator arithmetic reproduced exactly on independent re-execution
(default 563 = 408/84/71; widened 639 = 453/102/84; 76 restarts = 41
ThrowIn + 17 FreeKick + 12 GoalKick + 6 KickOff); excluded candidates vanish
from the denominator; changed pins are arithmetically consistent and
documented; scope fences fully respected; UNKNOWN propagates correctly in
all three downstream consumers checked.

## Blocking findings (all one root cause: the executor boundary)

**B1 — `event_type_filter` is declared but not wired into the module
config.** `src/tqe/runtime/executor.py` (`primitive_controlled_pass_episode`)
reads the parameter but constructs `ControlledPassConfig` without it, so the
module pre-filters to its new `("Play_Pass",)` default regardless of the
bound plan, and the executor's exact-match post-filter can only narrow
further:
- a plan declaring the allowed value `"any"` silently returns Play_Pass-only
  results through the executor path (the path parameter declarations exist
  for);
- a plan declaring `"ThrowIn_Play_Pass"` gets the empty intersection —
  confirmed on J03WOY: 0 throw-in anchors via the executor vs 41 with the
  filter passed to config.

**B2 — this silently vacates the live `afl-substrate-q6` gate, unreported.**
`src/tqe/verification/afl_substrate_q6.py` binds `controlled_pass_episode`
with `event_type_filter="ThrowIn_Play_Pass"`; its frozen expectation pins an
honest-zero result over a probe substrate of 17 first-half throw-in anchors.
Post-change the probe substrate collapses to 0 anchors — the honest zero
becomes a vacuous zero that can never again turn non-zero. The packet's
deliverable 2 required listing exactly which gates fail and why;
`afl-substrate-q6-verify` was neither run nor mentioned.

**B3 — `max_release_alignment_ms` is declared but never read by the
executor** (both the controlled-pass and one-touch node functions; one-touch
also never reads its new `event_type_filter`). Plan-level overrides of a
declared, range-validated parameter are silently ignored; behavior matches
today only because module default equals catalog default. This reintroduces,
for the new parameters, the exact declared-vs-runtime dishonesty pattern
(audit finding V4) this remediation program exists to eliminate.

## Required for round 2 (minimal path to acceptance)

1. Wire `event_type_filter` and `max_release_alignment_ms` from the bound
   node into BOTH config constructions in `executor.py` (controlled pass and
   one-touch). Reconcile or remove the exact-match post-filter so declared
   values (`"any"`, `"ThrowIn_Play_Pass"`, `"Play_Pass"`) behave identically
   through the executor path and the direct-module path.
2. Add executor-path parameter tests: at minimum `"any"` (restores widened
   distribution 639 = 453/102/84 on J03WOY) and `"ThrowIn_Play_Pass"`
   (restores 41 throw-in candidates / 17 first-half probe anchors).
3. Run and report `afl-substrate-q6-verify`: the probe substrate must be
   restored (17 first-half throw-in anchors) and the honest-zero result
   preserved. List it in the report's gate table.
4. Align the executor shadow default `reception_search_seconds=6.0` to the
   catalog's 4.0 (or better, read it with no fallback disagreement).
5. Optional but preferred (from the non-blocking list): release-side
   missing-ratio check should not precede transition detection — a
   positively observed release transition inside a sparse window should not
   degrade to UNKNOWN (match the reception side's ordering); add the
   contradiction-inside-truncated-window-stays-FAIL test and an
   inside-tolerance alignment test.

Ratified without change: the one_touch alignment-tolerance change (forced by
the shared helper's signature, disclosed in the report).

Resubmit on the same `packet/f1-b` branch (append commits; do not rewrite
history). Same fences as the original packet apply.
