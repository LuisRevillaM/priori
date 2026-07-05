# Work Packet R2-1: aggregate_over — the aggregation keystone

**Era**: R2 (ADR 0014 governs; read it before anything else)
**Branch**: `packet/r2-1` off the frontier
**Executor ground rules**: commit locally in stages, never push; report
`delivery/packets/R2-1-REPORT.md` created WITH the first item commit;
full-suite table (`make test`) on the committed tree in the final
report, every failure enumerated and attributed.

**Fences**: `generated/coverage-map.json`/`.csv` (director's alone);
`semantic-registry/atlas/`; `artifacts/autonomous/` except the sweep
tool's canonical report path; all sealed packet evidence; no freezes,
no re-pins.

## Headline risk (the one argument this packet must win)

Principle 20 made the dishonest aggregate unrepresentable ON PAPER.
This packet must make it unrepresentable IN THE TYPE SYSTEM: an
aggregate result whose population contains UNKNOWN rows and which
lacks bounds must be unconstructible, and the bounds must be COMPUTED
from the tri-state row statuses, not asserted by the caller.

## Scope

### 1. The operator
`src/tqe/runtime/operators/aggregate_over.py`, a registry citizen
behind the binder like the five R1 operators (ADR 0013 nine-rule
template applies in full — read the template addendum and the R1-5
operator as the house reference). Semantics:

- Input: a bound evidence relation of anchor-level rows (the R1
  grammar's output), a declared population expression (principle 21:
  typed, carried in the plan, echoed in evidence), a declared group-by
  key set (team perspective, match, player where the relation carries
  it), and an aggregation kind from exactly {count, sum, mean} over a
  declared numeric field (sum/mean) or row existence (count).
- Tri-state law (principle 20): rows partition into PASS / FAIL /
  UNKNOWN by the relation's status field(s), declared at bind time.
  The result type carries: observed (UNKNOWN excluded), lower_bound
  (every UNKNOWN resolves against), upper_bound (every UNKNOWN
  resolves for), unknown_count, population_count, and the population
  expression. Bounds are computed inside the operator; the result
  constructor REFUSES bounds supplied from outside (the same
  discipline as R1-C's guard: forged honesty raises).
- When unknown_count == 0 the interval collapses (observed ==
  lower == upper) — still emitted as the full shape; presentation
  layers may collapse it, the data layer never does.
- Composition: aggregate_over binds R1 operator outputs (including
  typed_join products). Composition constraints (same_team_perspective,
  frame_alignment, entity_identity_preserved) are inherited bind-time
  law — an aggregate over a join that violates them must fail at bind,
  not produce a number.

### 2. Flagship question (era acceptance pattern)
"How many fragile possession situations does each team face per
match?" — count over fragile_possession_state rows, grouped by team
perspective and match, all seven IDSSE matches, both perspectives.
This is CAR-0's denominator. Deliverable: the computed table in the
report (14 team-matches, interval-typed, unknown counts shown) plus
the certified plan committed as packet evidence under
`delivery/packets/r2-1-flagship/`. Numbers must reconcile with the
sealed R1-5 population audit's 145 PASS rows — state the
reconciliation arithmetic explicitly in the report (which statuses the
audit counted vs which the aggregate partitions).

### 3. Tests (mutation standard throughout)
The house suite standard plus, at minimum: bounds computed correctly
for a fixture with known PASS/FAIL/UNKNOWN mix (hand-computable);
constructor refuses external bounds (raises); UNKNOWN dropped
silently is caught (mutate the operator to drop UNKNOWN in a scratch
copy → the named bounds test fails); group-by keys respect team
perspective (both-teams test per R1-5 case law, with the
continuity/anchor role assertion pattern); bind-time failure on a
constraint-violating composition.

## Explicitly OUT of scope
rate_and_share (R2-2 — no ratio machinery, no subset law yet);
any dossier/presentation surface; ledger targets or flips (no new
coverage rows this packet — the operator earns rows in R2-2+ when
question-bank rows become reachable; the flagship table is packet
evidence, not a ledger claim).

## Deliverables
Operator + binder registration; flagship table + certified plan under
delivery/packets/r2-1-flagship/; tests; stage-committed report with
full-suite table. Nothing pushed.
