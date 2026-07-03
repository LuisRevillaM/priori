# F2-1 Acceptance Review — Round 1: REJECTED (governance, not behavior)

Reviewed 2026-07-03, branch `packet/f2-1` commit `e491997`. Runtime behavior
neutrality CONFIRMED beyond the packet's own bar: all 191 parameter
migrations compared mechanically against the merge-base (189 exact value
matches, 2 faithful per-capability splits of a conditional default), cutover
total (all 182 call sites 2-arg, no smuggled fallbacks), typed undeclared-
read error triggered live, static guard sound with a noted vacuous gap,
fences clean, and — decisive — **zero bound_plan_hash movement**: all drift
is registry-parity class only.

## Blocking findings

B1 — 22 declarations silently converted required -> optional-with-default.
Those parameters were `required: true` at the merge-base; the executor
defaults being deleted were DEAD CODE (the binder rejects omissions). The
strictly neutral variant (delete dead defaults, keep required) existed and
would have produced zero drift. Converting the contract was a fork the
packet explicitly reserved for director decision ("flag, do not choose
silently"), and the report's justification ("only effective default home")
is factually wrong. The change also went undisclosed while being the sole
cause of all gate drift.

B2 — Drift enumeration incomplete: 18 additional gates fail via the same
scp0-parity cascade (acceleration, carry-episode, controlled-line-break,
cover-shadow, defensive-line, lane-occupancy, line-break-support-response,
local-number, marking, off-ball-run, off-ball-run-type,
one-touch-pass-chain, relative-position, set-piece-structure,
space-region-generation, substrate-q2, support-arrival, team-press) —
unlisted in the report's gate table. Same offense class as F1-B round 1.

## Director ruling (for round 2 to implement, not re-guess)

**Optional-with-default STANDS** for the 22 parameters: catalog-declared
defaults, mechanically materialized by the binder, are ADR 0012 §2's intent;
required-with-no-default would leave defaults homeless forever and push
every choice onto plan authors, contradicting the single-source design. The
loosening is accepted as a DELIBERATE, DISCLOSED contract change. Value
domains remain guarded by min/max/enum validation.

## Required for round 2 (same branch, append commits)

R1 — Disclose the required->optional conversion prominently in the report:
the 22 parameters listed, the old contract, the new one, and this ruling
cited as its authority.
R2 — Complete gate table: all ~21 affected gates with drift class
(parity-cascade), and the statement that zero frozen-expectation hashes
moved (no re-freezes needed; director regenerates registry/parity at
acceptance).
R3 — Census correction: add the `params=state.params` passthrough at
executor.py:674 to the state.params census (and fix the row-count claim:
191 + 26, not 242).

---

# F2-1 Acceptance Review — Round 2: ACCEPTED

Reviewed 2026-07-03, commit `dedd0c1` (report-only, verified 1-file diff),
merged as `41aead7`. All three disclosures landed; the director ruling was
implemented as ruled (no code changes to the 22 declarations).

Director acceptance actions: registry bindings for the four affected
capabilities (destination-entry x2, corridor x2) updated mechanically from
catalog truth — all 22 parameter signatures now optional-with-default in
both homes; binder artifacts, knowledge pack, and SCP-0 projections
regenerated; parity PASS, 0 findings. Zero frozen-expectation hashes moved
(confirmed in review) — no re-freezes required. The shadow-default defect
class is retired: parameters now have exactly one home, the catalog, and
undeclared reads are typed hard errors.
