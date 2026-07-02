# Known Issues

Updated: 2026-07-01. Ordered by severity. See `CURRENT_STATE.md` for the
overall snapshot and `docs/audits/` for full audit reports. (The previous
version of this file was the day-0 planning checklist and had never been
updated; it described a project with "no implementation," which has been false
since June 19.)

## Correctness (from the 2026-07-01 foundation audit)

- Tri-state fail-open paths exist in the executor and several kernels:
  specific code paths where missing evidence can surface as FAIL (or PASS)
  instead of UNKNOWN — e.g. reception windows truncated by period end,
  sparse-tracking release checks, corridor episodes silently bridging missing
  frames, `exists`/`count_at_least` fallbacks on empty episode sets. Full
  list with file:line and reproductions in the foundation audit report.
  PARTIALLY FIXED (F1-A, 2026-07-01) — the sharp low-ripple findings are
  closed with adversarial tests: T9 (non-numeric coordinate no longer raises
  from `relative_position_to_line`; yields UNKNOWN `entity_position_invalid`),
  G8 (live gt/gte/lte `truth_series` now honors the actual operator instead
  of always `>=`), G5 (goalkeeper handling in `defensive_line` is fail-closed
  — `goalkeeper_id=None` + `goalkeeper_id_known=True` yields UNKNOWN
  `goalkeeper_identity_missing` unless the caller declares
  `goalkeeper_excluded_from_positions=True`; mapping `y_m` is no longer
  fabricated as 0.0), G3 temporal-order half (`controlled_line_break` returns
  UNKNOWN `reception_before_release` for temporally impossible evidence), and
  G7 overlap half (`local_number_relation` returns UNKNOWN
  `player_present_on_both_sides` instead of double-counting). Still open from
  the audit: T1–T8, G1–G2, G4, G6, G9–G10, the G3 buffer-provenance half, and
  the G7 roster-known flag.
- Two incompatible lane geometries coexist (`lane_occupancy` five-lane model
  vs `relations.destination_lane` fractional model); composed queries mixing
  them will disagree with themselves.
- `executor.py` is an ~11k-line accretion module; capability-specific names
  have leaked into shared trace/evidence code paths. Remediation plan in the
  audit report; structural extraction should precede the next vocabulary
  expansion wave.
- Controlled-reception "control" is proximity-based and opponent-blind; the
  case study's clean-control gate fences this at the product layer, but the
  substrate field names still say more than they measure.

## Process / gates

- FIXED (F0-2, 2026-07-01): verifiers no longer mutate tracked files when
  run. Every `make <gate>-verify` target is a read-only check (run reports go
  to gitignored `artifacts/check-runs/`; tracked generated artifacts are
  regenerated in memory and diffed, failing on drift). Regenerating tracked
  evidence/projection files requires the explicit `TQE_WRITE=1` opt-in via
  `make <gate>-write`, and a FAIL in write mode still writes the FAIL report
  (no stale-green). Historical note kept for the record: before this fix,
  running `make n1i-verify`/`n1d-verify` locally regenerated
  `delivery/n1d/N1I_REPORT.md` and the knowledge packs in place — this once
  overwrote the historical VERIFIED N1I report with a weaker "not run" record
  on a superseded branch — and parity/passport artifacts were written on PASS
  only, so a FAIL could leave stale PASS evidence checked in.
- `make n1d-verify` fails 2/15 checks by design since the AFL expansion moved
  executor/binder/catalog past the N1D freeze-manifest pins. Expected drift;
  re-pinning requires a fresh live rerun.
- RESOLVED (2026-07-02): the four drifted AFL-09A frozen expectations
  (time-to-arrival, relative-position, substrate-q4,
  line-break-support-response) were re-frozen after a byte-level attribution
  investigation traced all four to one mechanism — commit 8cbb1f4's
  unannounced widening of the controlled_pass_episode catalog contract —
  with zero behavioral change proven. The duplicated evidence field that
  commit introduced was fixed first so the pins moved exactly once. All five
  gates (incl. afl-09a) pass in check mode. Lesson recorded: catalog
  contract changes must be announced in their commit and trigger expectation
  review.

## Standing blockers (external authority)

- S2I-F final independent sealed evaluation: the owner has authored and
  hash-pinned a private sealed set (`afl-hidden-suite-v1`), deliberately
  reserved for the General Compiler v1 evaluation (a sealed run burns the
  questions, so it is spent once, when it counts).
- SCP-0E.1 semantic registry external review not yet performed.
- RESOLVED (2026-07-02): AFL protected promotion authority now exists. The
  `afl-protected-gate` GitHub environment carries the owner-held signing key
  and pinned hidden-suite id/hash; run 28563273941 produced the first signed
  certificate — SCP-0E.1 `PROMOTED, SIGNED_HMAC_SHA256`. Local gate runs
  remain honestly BLOCKED (self-verified mode).

## Scope / data

- The public corpus is 7 matches; any player-level or rate statistic is a
  methodology demonstration, not a stable rating (see
  `docs/CAR_NORTH_STAR.md` honesty constraints).
- Most primitive verification scopes are single-match (J03WOY); all-corpus
  verification is pending per capability.

## Repository

- `origin/main` is behind the canonical frontier
  (`codex/afl08-passport-loop`) and holds a rebased duplicate of the SCP/AFL
  history; needs a fast-forward/reset decision at the next release point.
- Four pre-policy review-packet zips remain tracked (grandfathered by
  `docs/EVIDENCE_RETENTION_POLICY.md`).

## Standing scope clarifications (unchanged)

- The public IDSSE/DFL dataset has no match video; replay means
  coordinate-based pitch replay, not footage.
- This project ends at an independent pre-meeting demo. Priori
  SDK/API/private-data access is not part of the plan.
