# R1-4 Acceptance Review — Round 1: REJECT (narrow) — operator sound, booked evidence true, composition subject and proof governance not

Reviewed 2026-07-04 at 756d724 (base a0a1709), detached worktree, all
executions reproduced independently. The operator core is the era's
cleanest yet: registry citizenship exact, executor/binder/kernel untouched,
all 13 frozen plans hash-invariant (probed base vs tip), T2 probed live
(unapplied window keys fail synthesis), T1 structural ratchet covers the
new rule, hint guard extended to constraint values, discovery space
honestly 1 and independently re-derived from the typed filter, q6/scp-0/s1
gates pass (q6 trace b9e24dab exact), s2/r3/s3/gate-a failures reproduce
identically at base (the ADR's flagged stale pins — zero gate drift).
Continuity law probed: break bounds trace-back at the break; missing/
non-covering evidence → UNKNOWN; booked rows 1, 2, 20 walked to raw
tracking XML — possession segments re-derived at the 5 Hz cadence match
booked continuity bounds EXACTLY, windows contained, boundary transitions
real. 10→11 on a ledger copy reproduces through the correspondence-gated
path; tracked tree untouched; real flip left undone. Downstream
composability verified beyond the packet's own demonstration: a
window→window chain binds through the real binder and executes (the
episode-set/anchor_ref output typing genuinely chains). Rejected on:

B1 — Both-teams at composition level (rule 13; a packet-REQUIRED test) is
missing and failed in substance: full-population audit of the certified
plan yields 4,189 window records — 1,266 PASS of which 1,265 are home;
away anchors are 1,674 UNKNOWN (continuity_evidence_not_covering_anchor)
because possession_segment is perspective-keyed
(possession_family.py:48) while controlled-pass anchors span both teams,
and the search invocation hardcodes perspective home
(compiler_search_reachability.py:3606). The booked 20 are 20/20 home
receptions from a single match-period (J03WOH firstHalf); the report's
audit table has no team column and discloses none of this. R1-2 B1 at
composition level, regressed after R1-2 round 2 and R1-3 had both-teams
booked evidence.

B2 — The continuity policies are team-blind, and the composition books a
semantically false PASS on real data: _continuity_decision selects on
temporal coverage of the anchor only (window.py:591-593); nothing ties the
continuity record's team to the anchor's team, and same_team_control is
behaviorally identical to same_possession (the enum is metadata). Live
counterexample from the certified plan: J03WN1 secondHalf anchor 167670 —
an AWAY controlled reception (receiver DFL-OBJ-J01G0J, away→away pass)
PASS-covered by a HOME possession segment [167670,167940] (raw-verified:
tracking attributes the window to home). "same_team_control_after" is
emitted with the controlling team being the opponent of the receiving
team. The declared correspondence ("requiring same-team possession
continuity" per r1-4-window-targets.v0.json:12-22) is not what the
composition enforces; the flip is gated on that correspondence.

B3 — Rule 16 partial breach (third packet running): published document
hash 7e7ccc, runtime trace 0862072f, row-ledger cbb140b7, and the 10→11
delta all reproduce exactly — but the row-ledger hash reproduces only with
TQE_SEARCH_OUT_DIR/TQE_SEARCH_REPORT overrides absent from the published
command (R1-4-REPORT.md:138-146), and the report hash b9b5186d and
ledger-copy hash a785227e do not reproduce on the committed tree under the
published or any reasonable invocation (path-field permutations
exhausted; my values 223adda9 / cc682807 — the flip embeds report_path,
an invocation-dependent field). The commit ledger cites clone-only hashes
(0a6a789/ad516f2) that do not exist on this branch.

## Fix-class findings (non-blocking, round 2 or R1-C)

F1 — fixed_duration consults continuity evidence through the
_period_bounds fallback (window.py:725-742): probed PASS↔UNKNOWN flip on
mere presence of continuity records when state.frame_ids is absent
(latent — the real executor always supplies frame_ids), and the fallback
hardcodes possession_start/end_frame_id provider field names
(window.py:736) — template rule 2 violation on a fallback path.
F2 — An anchor outside the data bounds emits a PASS 1-frame window beyond
the observed frames (window.py:450-451 reset) under emit_with_flag;
degenerate case undeclared and untested.
F3 — Evidence mislabeling: records short-circuited before continuity
evaluation carry continuity_status=PASS / continuity_reason=
fixed_duration_policy while declaring continuity_policy=same_possession
(window.py:454-455); trace-back windows bounded by continuity retain
truncated_start=True from the pre-bounding clip (probed).
F4 — Truncation is judged on the requested window before continuity
bounding (window.py:464-466): trace-back + truncation_policy=unknown
poisons windows whose continuity bound lies inside the period —
over-conservative false UNKNOWN.
F5 — Overlapping continuity candidates: deterministic latest-start
selection (window.py:597-601) is an undeclared ambiguity policy; a
could-change-the-answer disagreement never yields UNKNOWN.
F6 — A positively observed possession break mid-window (after-mode) yields
UNKNOWN, never FAIL: the negative class of the outcome-window row is
unreachable; break and coverage-gap are conflated (declared-conservative,
but tri-state asymmetry worth a named decision).
F7 — Report gaps: no full-population status distribution (the 20 booked
are the max_results cap over 1,266 PASS windows), no team distribution, no
disclosure that all booked rows are one match-period.
F8 — Ratchet erosion: "window" was removed from the shared-code
word-boundary ratchet due to name collision with pre-existing generic uses
in executor.py; the replacement literals would not catch
node.operator.name == "window" leakage, and the binder (zero occurrences)
could have kept the strict check (test_r1_0_operator_scaffolding.py:40-52).
F9 — Era notes: composition operator signatures have no generated declared
surface, so parity/drift guards are structurally blind to operator
additions (nothing needed regeneration in this packet — the guards passing
is consistent, not stale-green; catalog declarations were not needed
because both consumed outputs already declare the fields); rule-id
vocabulary still unregistered (per R1-3, R1-C); provider-name alphabetical
ordering decides candidate order in window_anchor_sources (inert at count
1); continuity evidence is sampled at 5 Hz behind a window declaring
frame_rate_hz=25 in its evidence.

## Required for round 2 (same branch)

1 (B1/B2): Declare the composition's subject and enforce it — either
constrain anchors to the perspective team's receptions as a declared plan
element, or bind anchor-team ↔ continuity-team identity through a declared
field constraint; add the named both-teams-at-composition-level test;
republish the audit table with a team column and the full population
distribution. The away counterexample must become UNKNOWN or FAIL — never
PASS. 2 (B2): narrow or enforce the target's declared correspondence to
what the plan actually guarantees, then re-measure the delta on a copy.
3 (B3): re-run both proof commands exactly as published from the committed
tree, publish the real invocation env, externalize or drop
invocation-dependent fields from hashed artifacts (finish R1-3 F4), and
reconcile the commit ledger to this branch's hashes. 4: fix the cheap
fix-class items (F1's field whitelist and F3's mislabeling at minimum);
defer the rest explicitly.

## The movement and the era

The 11 is NOT yet earned: the booked evidence is true and raw-verified,
but it certifies a correspondence the composition does not enforce, on a
single team from a single match-period, with the packet's own required
both-teams test absent. It becomes earned the moment the subject is
declared and enforced — the composition is otherwise real, novel, and
chain-composable. Prognosis for R1-5 (typed_join): R1-4 is the
demonstration of WHY typed_join's composition constraints
(same-team-perspective, entity-identity-preserved) are load-bearing —
window+continuity is a join in disguise and it leaked cross-team identity
exactly where those constraints would have caught it. R1-5 must land them
as bind-time-enforced plan elements, retrofit window's continuity binding
to consume them, and kill the search harness's hardcoded single
perspective (compiler_search_reachability.py:3606) before CAR-0 —
fragile_possession_state is possession-keyed and will hit every one of
these seams at once.

---

## Director rulings (round 2)

R-I: Continuity is TEAM-KEYED by declaration. The trace-back policies gain
a required team-binding parameter (the anchor's acting team keys which
possession/control evidence may cover the window); `same_team_control`
implements real team semantics or is deleted this round. The harness's
hardcoded home perspective dies; the acceptance run covers both teams and
the audit table gains a team column.
R-J: Publish only hashes that reproduce (rule 16): fix the path-embedding
in the report/ledger-copy artifacts or stop publishing those two hashes;
disclose env overrides needed for any published number.
R-K: Fix-class list (phantom out-of-bounds windows, fixed_duration's
continuity fallback with hardcoded field names, continuity_status
labeling, truncation-before-bounding order, overlap policy declaration,
break-vs-gap tri-state) — all in-round; none deferred, they are the
operator's own semantics.
R-L (era): R1-5's composition constraints (same-team-perspective,
entity-identity-preserved) are designed as bind-time-enforced elements
FIRST, and window's continuity binding retrofits onto them in R1-5 —
recorded now so the join packet inherits this as scope, not surprise.
CAR-0 is possession-keyed and waits on exactly these seams.
