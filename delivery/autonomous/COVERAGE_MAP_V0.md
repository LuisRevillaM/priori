# Coverage Map v0

## Purpose

The coverage map is an internal steering artifact for General Compiler v1. It asks:

> For each authored football-atlas concept, can the current Priori capability catalog express it, express it with one typed gap, or not express it honestly yet?

It is static analysis. It does not change runtime behavior, the Workbench UI, Hermes prompts, or tactical semantics.

## Regeneration

Run:

```bash
make coverage-map
```

Authoritative generated artifacts:

- `generated/coverage-map.json` — row-level classification ledger.
- `generated/coverage-map.csv` — spreadsheet-friendly projection.
- `artifacts/autonomous/coverage-map-report.json` — aggregate dashboard.
- `scripts/coverage_map/aggregate.py` — deterministic report generator.

## Classification Meanings

- `supported`: the row names an existing primitive, composition, or runtime path that can express the concept.
- `partial_with_typed_gap`: the row names the exact missing primitive, modality, role/reference gap, or composition constraint.
- `missing_primitive`: a new runtime capability is required.
- `missing_modality`: the current data cannot support the concept, such as gaze, body orientation, video, or learned expected-value models.
- `role_or_reference_gap`: the concept depends on a role taxonomy or ambiguous football reference not yet modeled.
- `ambiguous_or_needs_definition`: the atlas entry is too underspecified to operationalize safely.

## v0 Result

The audited v0 map covers Priori's authored 741-concept atlas, not all possible user language.

| Classification | Concepts | Share |
| --- | ---: | ---: |
| `supported` | 325 | 43.9% |
| `partial_with_typed_gap` | 155 | 20.9% |
| `missing_primitive` | 197 | 26.6% |
| `missing_modality` | 42 | 5.7% |
| `role_or_reference_gap` | 13 | 1.8% |
| `ambiguous_or_needs_definition` | 9 | 1.2% |

Reachable now or with one named gap: 64.8%.

## Audit Posture

This is `v0 estimated` and internal-only. A 30-row stratified audit found roughly 26/30 rows solid and identified one systematic inflation pattern: aggregation and extremum concepts such as `argmax`, `argmin`, `local_maximum`, and `nearest_entity` had been treated as supported even though the catalog has no generic extremum operator.

That correction moved the affected rows from `supported` to `partial_with_typed_gap`, lowering supported coverage from 44.4% to 43.9%. The more important steering number, reachable now or with one typed gap, remained 64.8%.

Do not use this as an external coverage claim until additional audit passes and the held-out natural-language evaluation denominator exist.

## Current Roadmap Signal

The top missing primitives by atlas unlock count are:

1. `transition_anchor` — 31 concepts.
2. `time_to_arrival` — 30 concepts.
3. `carry_episode` — 17 concepts.
4. `set_piece_structure` — 12 concepts.
5. `off_ball_run` — 10 concepts.

Roadmap implication:

- Q5 should continue as the transition/phase/outcome-window substrate milestone.
- After Q5, prioritize `time_to_arrival` rather than treating it as deferrable.
- Regenerate the coverage map after every substrate package.

## Composition Constraint Backlog

The map also identifies 89 concepts blocked by missing declared composition constraints rather than missing runtime primitives. Examples include:

- same anchor identity;
- same team perspective;
- release vs reception frame alignment;
- line measured at release;
- pressure measured at reception;
- support measured after reception;
- entity identity preserved across nodes.

This is compiler work, not detector work. General compilation requires semantic composition validity, not only type-compatible node wiring.
