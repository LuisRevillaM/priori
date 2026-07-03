# F2-X Acceptance Review — Round 1: ACCEPT-WITH-FIXES

Reviewed 2026-07-04, branch packet/f2-x at 171d15a. All five kill-list items
verified on detached worktrees with gates rerun: noop registrations gone
(debt ledger now asserts empty); dead predicate family deleted with the
decisive proof that the dead copies CRASHED when invoked (base Gate R3
RuntimeError); fabricated-traces keep verified correct against the real
consumer chain; legacy M1 quarantine functionally equivalent (mechanical
rewrite deltas enumerated and parity-covered — "byte-identical" softened to
"semantically equivalent, gate-proven"); allowlist shrank by exactly the
deleted needles; suite 356 green; fences held. Executor 3,715 -> 3,227
lines; legacy_m1.py 395 lines.

## Director rulings recorded

R-A: The fabricated-trace helper ("live by gate fiat" — fenced from all
product paths, asserted only by M1-era gates E/S7 and the frozen
opposite-corridor recipe) is scheduled for deletion COUPLED to the
retirement of that experimental plan and its gates, in the R1-era cleanup
— not deleted on a technicality while gates pin it.
R-B: The stale approved-plan pins surfaced by the review (Gate R3 2/10,
Gate S2 1/4, identical 119/747 numbers at base and final — pre-existing
reds, never regressions) get the established treatment: attribution
investigation, then a deliberate re-pin batch. Queued after F2-Y alongside
the optional hygiene items (orphaned candidate_key, duplicated profile
constant, stale noop names in the authoring blocklist).

## Required for round 2 (report amendment only, no code)

R1 — Amend F2-X-REPORT.md to disclose Gate R3 and Gate S2 status on the
committed tree with the base-state evidence establishing pre-existence
(base R3/S3 crash via the dead copy; base S2 identical fail). An
adversarial-deletion packet that edits gates must table their color — the
undisclosed-red pattern is what this whole program exists to kill.
