# R2-1 Review — Round 1: REVISE

Reviewed 2026-07-05 on packet/r2-1 (2948880..3c2e8de, base a658247).
Director's full suite green on the committed tree. Adversarial review
with execution-verified findings; the director independently confirmed
the constructor takes bounds as parameters and relies on internal
validation (which the reviewer then attacked directly).

## What survived attack (independently verified)

- The COUNT path is the era's promise kept: dishonest shape
  unconstructible, forged bounds raise (lower-only, upper-only, both;
  dataclasses.replace blocked; no bypass constructor), None status is
  UNKNOWN never PASS/FAIL, fourth status values raise.
- The flagship reconciliation is EXACT: all 14 team-match rows
  recomputed from the sealed audit's 8,414 raw rows — 145 PASS
  (73 home / 72 away), 2,615 FAIL, 5,654 UNKNOWN, interval math
  correct row by row, all three provenance hashes verify.
- The plan is real: binds clean through the actual binder on this
  tree, aggregate node appended to the certified R1-5 lineage.
- Fences clean; report stage-committed; the recovery clone's tested
  tree is byte-identical to the branch commit (clone-route provenance
  verified).

## Findings (blocking: F1-F4; design: F5-F9; noted: F10-F12)

F1: mean bounds unsound — observed can fall outside its own interval
(pass=[10], unknown=[1] → observed 10, interval [5, 5.5]).
F2: mean fabricates values — FAIL rows contribute 0.0 to a mean of a
field nobody observed on them (principle 22 breach).
F3: sum interval inverts on negative UNKNOWN values (no field-bounds
mechanism, no ordering guard).
F4: zero tests exercise sum/mean bounds — ADR 0013 rule 7 violated on
the operator's own enum; the spec's hand-computable fixture exists
for count only.
F5: operator name hardcoded 7× in binder.py against the typed_join
structural-dispatch precedent; scaffolding ratchet list not extended,
so the "ratchet green" claim is letter-true, spirit-false.
F6: ambient injection of {match_id, period, perspective_team_role}
into declared fields for ALL operators — weakens bind-time
declaration law globally (principle 18).
F7: perspective_team_role group key is a state stamp; the packet's own
test proves a home-role row counts under an away group key. Safe in
the flagship only because the upstream join is perspective-pure — and
nothing at bind time requires that.
F8: the committed flagship table (14 per-match rows merged from 28
per-period records) was produced by NO code on the committed tree —
rule 16 violated; the merge arithmetic happened outside the guarded
constructor (verified honest by hand, but honesty by hand is not the
standard this repo keeps).
F9: constraint inheritance is opt-in (defaults False; missing upstream
returns silently) — the spec said law, the code says suggestion.
F10: type guarantee lives one function call (results flatten to dicts;
artifacts are attested by provenance hashes, not runtime types).
F11: malformed populations yield empty aggregates (fail-open).
F12: the both-teams role assertion is a tautology over fixture inputs,
not the R1-5 case-law pattern.

## Director's rulings

**R-U (on F1-F4): amputate sum and mean.** R2-1 ships COUNT ONLY.
AGGREGATION_KINDS = {count}; the sum/mean parameters, code paths, and
bind surface are removed, with a declared limitation naming why:
bounding numeric aggregates over UNKNOWN rows requires a declared
field-domain mechanism (a field states its [min, max] before an
unobserved contribution can be bounded; FAIL rows never contribute
values). That mechanism is its own headline risk and belongs to a
future packet (R2-1b or folded into R2-2) with its own spec. One
packet, one risk — this is that law enforced in hindsight, not a
punishment. Additionally: the constructor gains a permanent ordering
invariant (lower <= observed <= upper whenever observed is defined;
violation raises) — a tooth that outlives count.

**R-V (on F5):** restructure binder dispatch to the structural
pattern (typed_join precedent) and extend the scaffolding ratchet's
name list with aggregate_over so the literal it should forbid is
visible to it.

**R-W (on F6):** remove the ambient field injection entirely. Group-by
keys validate against fields the bound input relation actually
declares. If upstream relations genuinely do not declare match_id /
period / perspective_team_role, STOP and report — the fix is
declaring them at the source, and if that is large, it escalates to
the director rather than weakening the law for every operator.

**R-X (on F7):** grouping by perspective_team_role is bindable ONLY
when the population's node chain enforces same_team_perspective — the
validator checks the chain, it does not trust the author. Otherwise
bind fails with a typed reason. The state-stamp mechanics may remain
behind that gate.

**R-Y (on F8):** commit the flagship generator. The per-match merge
goes THROUGH the guarded constructor (a merge of count aggregates is
a count aggregate over the union population — construct it as one),
and the committed tool must byte-reproduce the committed table on the
committed tree. Rule 16 is not optional for packet evidence.

**R-Z (on F9):** for aggregate_over the three *_required constraints
default TRUE; opting out requires a declared reason string that lands
in the evidence. Upstream-node-not-found is a bind ERROR. (F11 rides
along: malformed population raises, fail-closed.)

**Noted, not fixed this round:** F10 — accepted Python reality;
document in the signature's limitations that the guarantee is at
construction and artifacts are attested by provenance hashes. F12 —
rewrite the both-teams test to the R1-5 pattern (roles read from
operator output, compared against independently-sourced fixture
truth, not one variable).

## Fix list

1. Amputation per R-U + ordering invariant + count-enum test coverage
   (mutation standard: break the invariant, watch the named test fail).
2. Binder dispatch + ratchet per R-V.
3. Ambient injection removal per R-W (or STOP-and-report).
4. Bind-time perspective gate per R-X, with a test that an
   unconstrained population grouped by perspective FAILS to bind.
5. Flagship generator per R-Y, byte-reproducing the committed table.
6. Defaults flip + fail-closed per R-Z, with tests.
7. F12 test rewrite; F10 limitations line.
8. Full-suite table on the new committed tree.

Round 2 appends to packet/r2-1. The clone-route provenance discipline
(report the clone path + SHAs prominently) worked well this round —
keep it.
