# ADR 0014: The R2 Aggregation Era

Status: ACCEPTED (era-opening constitution)
Date: 2026-07-05
Author: the director
Governs: operator packets R2-1 onward, until superseded

## Context

The R1 era built the composition grammar: five operators, composition
constraints as bind-time law, a ledger where every reachable row
declares its meaning and nothing flips undeclared (ADR 0013, twelve
rows, closed at 2efb550). R1 answers "find the moments and measure
them." It cannot yet answer the questions scouts actually ask, which
are almost all aggregates: how OFTEN, what SHARE, compared to WHOM.
CAR itself is a rate — continuity per fragile situation, against a
replacement baseline. The R2 era builds the aggregation layer.

## The signature design problem: UNKNOWN in the denominator

Tri-state truth (PASS/FAIL/UNKNOWN, UNKNOWN ≠ FALSE) collides with
aggregation. A rate is numerator/denominator; UNKNOWN rows belong to
neither and to both. Every dishonest analytics product on earth
resolves this by silently dropping UNKNOWN — which inflates
confidence and is exactly the failure mode this project exists to
refuse.

### Ruling: aggregates are intervals, not points

(20) Every aggregate over a population containing UNKNOWN rows
reports THREE numbers: the observed value (UNKNOWN excluded), and the
bounds — the value if every UNKNOWN resolved against, and if every
UNKNOWN resolved for. `rate = 0.62 [0.55, 0.71], unknown = 9/145`.
When the population has no UNKNOWN rows the interval collapses and
MAY be presented as a point with the population stated. Product
language follows the interval: a claim is only as strong as its worse
bound, and dossier prose may never quote the observed value without
its unknown count. No operator, surface, or export may emit a
point-estimate field for a population whose unknown count is nonzero
without the bounds beside it — the schema makes the dishonest shape
unrepresentable.

(21) Denominators are DECLARED, never inferred. An aggregate's
population is a typed expression over evidence relations (the same
grammar the R1 operators bind), carried in the plan and echoed in the
evidence, so "62% of WHAT" always has a machine answer. Changing the
denominator is changing the question; two aggregates with different
denominators are different rows, never the same number "filtered."

(22) Aggregation never manufactures observation. An aggregate's
inputs are anchor-level evidence rows produced by the R1 grammar;
aggregation may count, bound, rank, and normalize them but may not
impute, interpolate, or weight by any model not itself a declared
evidence source. (The own-footage law "imputation is never presented
as observation" is the same principle upstream.)

## The operator roster (build order)

- **R2-1 `aggregate_over`** — count/sum/mean over a declared
  population, grouped by declared keys (team, player, match, phase),
  emitting interval-typed results per principle 20. The keystone; every
  later operator composes through it.
- **R2-2 `rate_and_share`** — ratios of two declared populations with
  compatibility law: numerator population must be a declared subset of
  denominator population, enforced at bind time (the aggregation
  analogue of R1's composition constraints).
- **R2-3 `entity_set_algebra`** — declared set operations over entity
  populations (starters vs finishers, pressing unit vs rest-defense)
  so populations are constructible without new detectors.
- **R2-4 `sequence_pattern`** — ordered anchor patterns within a
  possession/window (regain → progression → entry), the bridge from
  moments to tendencies.
- **R2-5 `spatial_join`** — aggregate keyed by declared spatial
  partitions (zones v2), the "where" dimension.
- **R2-C** — checkpoint: unified sweep, CAR-0 rate computed
  end-to-end as the era's acceptance (fragile situations per team per
  match, interval-typed, both perspectives, all seven matches).

## Inherited law

All of ADR 0013 stands: the nine-rule operator template, teeth T1-T5,
principles 15-19 (semantics never hidden under pinned surfaces; proofs
reproduce on the committed tree; authority does not transfer with
correctness — the ledger flips by the director's hand; output
declarations derive from bound inputs; declarations are not verdicts).
Era case law: the R1-1..R1-5 and R1-C review files. The standing bar:
no full-suite table on the committed tree, no review.

## Acceptance pattern for R2 packets

Each operator packet names one flagship question from
docs/SCOUTING_QUESTION_BANK.md that its operator makes answerable,
and its acceptance includes that question computed over all seven
matches with the interval and unknown count in the report. The era
closes when CAR-0's rate is one of them.
