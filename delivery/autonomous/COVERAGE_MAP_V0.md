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

## Post-Set-Piece v0 Result

The audited v0 map covers Priori's authored 741-concept atlas, not all possible user language. These numbers are after Q5 landed `transition_anchor`, `structured_zone`, and `outcome_window`, and after the transition-anchor backlog was conservatively redistributed into supported rows or the next precise blocker.
They also include `time_to_arrival` v0.1, a static-point arrival primitive using straight-line travel at a declared max speed while carrying tracking coverage and point-mass limitation evidence, `carry_episode` v0.1, a conservative movement-under-control primitive with explicit control criteria and bias evidence, the Q2 pressure-reduction composition over carry start/end pressure, `acceleration` v0.1, a conservative two-window observed speed-change primitive, and `set_piece_structure` v0.1, an observed restart/set-piece event plus at-frame outfield-arrangement primitive.

| Classification | Concepts | Share |
| --- | ---: | ---: |
| `supported` | 355 | 47.9% |
| `partial_with_typed_gap` | 172 | 23.2% |
| `missing_primitive` | 149 | 20.1% |
| `missing_modality` | 43 | 5.8% |
| `role_or_reference_gap` | 13 | 1.8% |
| `ambiguous_or_needs_definition` | 9 | 1.2% |

Reachable now or with one named gap: 71.1%.

## Audit Posture

This is `v0 estimated` and internal-only. A 30-row stratified audit found roughly 26/30 rows solid and identified one systematic inflation pattern: aggregation and extremum concepts such as `argmax`, `argmin`, `local_maximum`, and `nearest_entity` had been treated as supported even though the catalog has no generic extremum operator.

That correction moved the affected rows from `supported` to `partial_with_typed_gap`, lowering supported coverage from 44.4% to 43.9%. After Q5, `time_to_arrival`, `carry_episode`, Q2's carry-pressure comparison, `acceleration`, and `set_piece_structure`, conservative redistribution raises the current internal steering estimate to 47.9% supported and 71.1% reachable now or with one typed gap.

Do not use this as an external coverage claim until additional audit passes and the held-out natural-language evaluation denominator exist.

## Current Roadmap Signal

The top missing primitives by atlas unlock count after `set_piece_structure` are:

1. `off_ball_run` — 11 concepts.
2. `space_region_generation` — 7 concepts.
3. `marking` / `cover_shadow` — 6 concepts each.
4. `team_press` — 5 concepts.
5. `structured_zones` for dynamic-region targets — 5 concepts.

Roadmap implication:

- Q5 has closed the generic transition-anchor blocker for the coverage map.
- `time_to_arrival` has closed Q4's lane-coverage typed gap only for static target-point reachability. It does not claim moving-ball interception, pass-line coverage, cover shadows, pitch-control fields, or reachability regions.
- `carry_episode` has closed the base carrying blocker. Remaining carry-family gaps are narrower: defender-bypass-by-carry, carry-path lane/profile aggregation, generated space regions, contact/touch evidence, body orientation, and learned value.
- Q2 closes the observed `carry_out_of_pressure` composition as carry start/end pressure-distance comparison. It does not claim pressure-breaking quality or defender bypass.
- `acceleration` has closed the first SCL-named missing-substrate gap. Speed-up, sustained acceleration, and deceleration are now supported as observed two-window speed-change evidence; turn rate, curvature, direction change, and jerk remain precise next blockers.
- `set_piece_structure` has closed only the observed restart-arrangement subset. Routine variants, delivery trajectory, setup windows, role/marking schemes, and planned-play claims remain precise next blockers.
- `off_ball_run` is now the leading missing primitive. The cheap reachability follow-ons remain `cover_shadow`, `marking`, and interception-margin compositions on top of `time_to_arrival`.
- Treat remaining transition-family partials as their next precise gap, not as generic transition-anchor debt.
- Regenerate the coverage map after every substrate package.

## Composition Constraint Backlog

The map also identifies 109 concepts blocked by missing declared composition constraints rather than missing runtime primitives. Examples include:

- same anchor identity;
- same team perspective;
- release vs reception frame alignment;
- line measured at release;
- pressure measured at reception;
- support measured after reception;
- entity identity preserved across nodes.

This is compiler work, not detector work. General compilation requires semantic composition validity, not only type-compatible node wiring.
