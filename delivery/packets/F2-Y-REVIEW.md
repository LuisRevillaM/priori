# F2-Y Acceptance Review — Round 1: REJECTED

Reviewed 2026-07-04, branch packet/f2-y at 467a5b3, full adversarial pass
with every item verified empirically on detached worktrees.

## What is genuinely excellent (keep untouched in round 2)

T5: fail-open fallbacks deleted; binder rejects exists/count_at_least over
non-anchor sources with typed issues; zero checked-in plans bound the
forbidden pattern (verified across all 13). T6: CoverageDeclaration on
CatalogOutput, all 36 anchor-evaluation outputs declared, catalog build
RAISES for undeclared future kernels, operator logic reads declarations
only — the audit's PASS-for-every-record bug proven fixed live at base vs
tip. V8: witness chain declared end-to-end, frame-id fallback gone,
same-frame cross-bind dead, both boundary allowlists at ZERO, fabricated-
trace helper untouched per ruling R-A. V9(a-c): horizon bypass closed,
anchor-evaluation complexity limits, manifest-hashed cache key — all
empirically green.

## Why it rejects

B1 — **T7 implemented a different truth contract than authorized.** The
packet: uncovered -> UNKNOWN, observed non-satisfaction -> FAIL. The code:
every plain-episode non-match -> UNKNOWN unconditionally, stamped with a
fabricated "episode_trace_anchor_uncovered" reason; the FAIL leg is
unreachable. This inverts the audit's truth class (fabricating coverage
diagnoses instead of fabricating certainty) and is the mechanism behind
the legacy 180->0 and opposite-corridor 9->0 wipeouts and five M1.1 test
failures. Silent fork, aggravated by tests codifying the wrong contract.
B2 — **The disclosure apparatus is entirely missing.** No committed report:
six pinned gates red and one unit test red on the committed tree,
undisclosed. (Attribution split for the record: the executor WROTE the
report but never committed it — the run ended at "ready to commit" — and
the director's worktree cleanup then destroyed the uncommitted copy. Both
sides own a law below.)
B3 — V9(d) `_predicate_status` silently skipped; the `arrival_candidates`
rename unpacketed and unexplained (sound motive, zero words).

## New standing laws (both sides)

L1 — **Reports are stage-committed like code**: the report file is created
WITH the first item commit and updated per item — never a trailing
uncommitted artifact.
L2 — **The director never force-removes an executor worktree without
checking for uncommitted content.**

## Required for round 2 (same branch, append commits)

R1 — Author and COMMIT F2-Y-REPORT.md meeting every packet bar: gate color
table (the review's drift table is the crib), catalog-edit enumeration,
corpus deltas, full-suite table, V9(d) disposition.
R2 — T7 redo: thread the packet's own CoverageDeclaration machinery into
the trace path so observed non-satisfaction stays FAIL and UNKNOWN fires
only with evidenced absence-of-coverage; if the plain-episode path is
genuinely indistinguishable, STOP and escalate with the honest option set —
in no case emit an uncovered reason that is not evidenced. Quantify the
resulting trace/row deltas (legacy 180 and corridor 9 must be explained or
restored by evidence, not by fiat).
R3 — `_predicate_status`: retire with proof or record the consumption
proof.
R4 — Hygiene: dead output_name param; ""-vs-None manifest-hash guard;
note the count-field/multiplicity conflation for a future limits review.

---

# F2-Y Round-2 Diagnosis (director-commissioned) and Round-3 Ruling

The round-2 suite failures were diagnosed surgically: the regressor is
commit 14e23bb (V8 witness hardening), NOT the T7 redo. Deleting the
frame-identity fallback from record_matches_anchor was correct for witness
selection (records declare anchor_id) but killed the predicate-trace record
path outright: legacy and generic trace records carry NO anchor_id key
(identity is minted later and never stamped back), so strict matching
misses 100%, falls to a FrameSignal branch keyed by a DIFFERENT frame
column (outcome frames vs anchor frames), emits UNKNOWN
anchor_frame_missing_from_predicate_signal, and exclude_candidate wipes the
corpus (180->0 legacy, 9->0 generic). Monkeypatch simulation restores the
frozen baseline byte-exactly and resolves all five test failures. The T7
redo itself (be9f43f) is byte-neutral and its contract verified correct on
real examples (covered->PASS, uncovered->UNKNOWN).

## Director ruling for round 3

Implement the SCOPED MATCHER variant: record_matches_anchor stays strict
(the witness chain keeps its teeth); predicate_trace_from_runtime_record
gains its own explicitly-named fallback for records that declare no
anchor_id key — matching on result_id equality against the anchor's
result_id attribute, else the (match_id, period, anchor_frame_id) triple.
Name it for what it is (legacy-record identity bridging), comment WHY those
records lack anchor_id, and add the diagnostician's two probes as tests:
covered anchor -> PASS via record path; genuinely-uncovered frame ->
UNKNOWN with the reason. Quantify the restoration in the report (180/900
against the frozen manifest; generic 9 rows with both classifications).
Record the latent FrameSignal-fallback trap (sparse record-backed signals
keyed by other frame columns) as a named R1-era backlog item — do not fix
it here.
