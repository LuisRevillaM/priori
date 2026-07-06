# EXAM-1 Findings — interim report (E1 sweeps, first session)

Examiner: the director. Evidence: delivery/packets/exam-1-evidence/
runs/ (R-AZ layout; every exhibit reproducible by the committed
scripts/exam/threshold_sweep.py with the command in each file).

## F-D (HIGH) — the certified and runtime paths answer DIFFERENT QUESTIONS under one ask

Same expression, same document hash (d8179a5a…): the certified-table
path reports the interval over the REGAIN-SEED population
(C=2261, population 2811, lower 0.000356, unknown 2810), while the
runtime path reports it over the CHAIN-RECORD population (C=90,
population 115, lower 0.008696, unknown 114) — a 24× difference in
the honest bounds, decided by CACHE STATE (whether the plan hash
matches a committed table). The two paths also carry different labels.
ADR 0014 principle 21: a different denominator is a different
question. The ratified R2-4 question is per-REGAIN; the runtime
interval extraction appears to compute per-SEEDED-CHAIN — if so, the
runtime bounds are optimistically narrow (denominator undercount).
Exhibit: runs/2026-07-06T215432Z…/sweep-stage_2_minimum_numeric_value
.json (compare point 3.0 vs neighbors).
Disposition: fix packet — one denominator convention, declared in the
plan, identical on both serving paths; the label derives from it.

## F-A (MEDIUM-HIGH) — expression clause/parameter coherence is unchecked

An expression whose meaning_clauses say "carry ≥ 8.0m" while its
operator parameter says 3.0 passes the vocabulary gate, synthesizes,
and executes the 3.0 plan — five clause-mutated variants produced
byte-identical documents (runs/…T215317Z…). Because rendered meanings
derive from typed clauses (R-AI), a declaration can DESCRIBE a plan
the contract does not execute. Hermes emits both halves; nothing
checks their agreement.
Disposition: fix packet — synthesis validates that every numeric
meaning_clause value matches the parameter it describes (or clauses
are derived FROM parameters, one source of truth), mismatch raises.

## F-C (MEDIUM) — the execution API's result rows carry empty evidence

ExecuteQueryPlanResponse.results rows arrive with evidence {} (and
the home role emits zero rows on this plan family); the interval
numbers travel only via the requested-evidence side channel that the
Film Room reads separately. Any API-only consumer sees results with
no measurements and no failure flag (requested_evidence_failure_count
= 0). Exhibit: runs/…T215151Z… raw_results.
Disposition: fix packet or documented contract — either the response
carries evidence or its absence is a declared, discoverable shape.

## F-E (MEDIUM, data truth) — the counterattack flagship is single-witness

A = 1 completed chain in the entire seven-match corpus at EVERY carry
threshold from 1.0m to 8.0m (observed = 1.0 throughout; the threshold
is immaterial because only one chain ever completes under the
5s/4s windows). The honest interval is near-vacuous and the sweep
proves no elected constant can rescue it: the discriminative levers
are the WINDOW parameters and more film, not the carry threshold.
Window sweeps are the exam's next exhibit.
Disposition: demo guidance — the counterattack rate should not be a
headline exhibit on this corpus; fragile-retention (A=145) should.

## F-F (LOW) — ergonomics debt

The execution payload shape is undocumented (three call sites read to
learn it — this exam's harness broke twice on it); moment_total_count
semantics differ from the rate population (205 moments vs 115 chains
at threshold 1.0) without a stated definition.
Disposition: one documentation packet item; a named definition for
moment counts.

## Verified sound along the way

Synthesis is threshold-faithful on operator parameters (distinct
documents per value, distinct plans certified and executed); the node
cache made a five-point sweep affordable (~6 min/point cold, 0.2s on
certified hit); vocabulary gating, certification, and execution held
through every mutated variant with zero crashes — every outcome was a
typed result. The engine took its exam without breaking; what the
exam found is seams between SUBSYSTEMS' truths, not wrong arithmetic.

## Remaining exam scope (next session of E1-E3)

Window-parameter sweeps (stage_2/stage_3 seconds; fragile retention
4s/8s); adversarial compositions (E2); honesty edge probes (E3,
including stale-cache-under-mutated-data). Findings F-D and F-A are
already sufficient to commission the fix packet.
