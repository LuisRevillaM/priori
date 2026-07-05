# Work Packet R2-2: rate_and_share — rates under the subset law

**Era**: R2 (ADR 0014 governs)
**Branch**: `packet/r2-2` off the frontier
**Executor ground rules**: unchanged (stage-committed report at
`delivery/packets/R2-2-REPORT.md`, full-suite table on the committed
tree, commit locally, never push; clone route with prominent
provenance if the sandbox blocks commits).

**Fences**: unchanged (ledger director's-only; atlas; sealed evidence;
autonomous artifacts; no freezes/re-pins).

## Headline risk

A rate couples its numerator and denominator through SHARED rows. The
naive move — compute two independent count intervals and divide — is
wrong: an UNKNOWN row cannot simultaneously resolve into the
numerator and out of the denominator. The bounds law below is exact;
implementing anything else, or implementing it without the joint
partition, is this packet's failure mode.

## The bounds law (implement exactly; the spec is the math)

Bind-time subset law: the numerator population must be a DECLARED
subset of the denominator population — same source relation, with the
numerator adding predicates only (the aggregation analogue of R1's
composition constraints). Two unrelated populations divided is not a
rate; it fails to bind.

Each row therefore carries a JOINT tri-state (num_status, den_status),
with num PASS ⇒ den PASS enforced as a runtime invariant (violation
raises — it means the subset law was broken by the evidence itself).
Partition the population:

- A: num PASS (hence den PASS)
- B: num FAIL, den PASS
- C: num UNKNOWN, den PASS
- D1: num FAIL, den UNKNOWN
- D2: num UNKNOWN, den UNKNOWN
- E: den FAIL — excluded from everything (with num PASS impossible;
  num PASS with den FAIL raises)

Result fields (all six partition counts carried in evidence, plus):
- observed = A / (A + B), defined only when A + B > 0 — rows with any
  UNKNOWN component are excluded from the observed value entirely.
- lower_bound = A / (A + B + C + D1 + D2) — every UNKNOWN resolves
  against the numerator and into the denominator.
- upper_bound = (A + C + D2) / (A + B + C + D2) — numerator-UNKNOWNs
  resolve in (raising both counts), D1 rows fall out of the
  denominator entirely.
- Ordering invariant: lower <= observed <= upper whenever observed is
  defined; violation raises in the constructor (inherited tooth).
- Degenerate denominators: if A+B+C+D1+D2 == 0 the rate is UNKNOWN
  as a typed status, never 0, never NaN, never omitted.

Bounds are computed inside the operator from the joint partition;
external bounds raise (R2-1 constructor discipline; reuse, don't
reimplement). rate_and_share emits both the rate interval and the
underlying count intervals (numerator, denominator) so no consumer
ever needs to re-derive them.

`share` is the special case where the numerator partitions the
denominator by a declared key (shares must sum: the observed shares
over known rows sum to 1, and the operator asserts it — a share table
that doesn't sum is a bug surfaced, not normalized away silently).

## What this packet does NOT include

No numeric (sum/mean) rates — the field-domain mechanism remains
declared debt from R2-1; count rates only. No new coverage rows or
ledger targets. No dossier surface.

## Flagship (era acceptance pattern): CAR-0 becomes a rate

"When a team's possession turns fragile, how often do they keep the
ball anyway?" — numerator: fragile_possession_state rows whose
same-team control-retention window (the R1-4/R1-5 composition,
same_possession continuity) is PASS; denominator: all
fragile_possession_state rows. Per team per match, all seven matches,
both perspectives, computed through the bound plan and emitted with
the full partition (A, B, C, D1, D2, E per row group), the rate
interval, and both count intervals. Committed under
`delivery/packets/r2-2-flagship/` with a generator that
byte-reproduces the table on the committed tree (R2-1's R-Y is
standing law now). Reconcile the denominator against R2-1's flagship
table explicitly (the denominators must be the SAME 14 rows — state
the comparison in the report).

This is CAR-0 v0: the retention rate in fragile situations, honest
intervals, per team. The report's flagship section should present the
14-row table exactly as a scout would read it, interval and unknown
count beside every rate.

## Tests (mutation standard)

At minimum: hand-computable joint fixture covering all six partition
classes with exact expected bounds; num-PASS-with-den-FAIL raises;
num-PASS-with-den-UNKNOWN raises (subset invariant); external bounds
raise; ordering invariant; degenerate denominator yields typed
UNKNOWN; bind rejects non-subset populations (different source
relations; numerator with removed predicates); share-sum assertion
fires on a corrupted fixture; both-teams grouping per the R1-5
case-law pattern (roles from operator output vs independently
sourced fixture truth). Mutations: flip C into the observed
denominator → named test fails; drop D1 from lower_bound's
denominator → named test fails.

## Deliverables

Operator + binder registration (structural dispatch; ratchet
extended); flagship table + generator + plan under
delivery/packets/r2-2-flagship/; tests; stage-committed report with
full-suite table. Nothing pushed.
