# Atlas Strategic Review — 2026-07-01

Definition-level review of the 741-concept football atlas
(`semantic-registry/atlas/raw/five_year_capability_manifest.yaml`), performed
as the basis for the director's General Compiler v1 strategy. Method: full
family-by-family read of all 741 definitions, regex scans for 14
operator-shaped patterns cross-tabbed against the coverage map, manual
pruning. Operator-unlock counts are ranges (±30%); rank order is firmer than
individual counts. Companion decisions are recorded at the end.

## Headline calibration (extends foundation-audit finding V6)

Of 362 atlas rows marked "supported," **at least 125 justify themselves by
citing compositional machinery that does not exist as operators** — window
(37 rows), rank/ordering (34), component decomposition (20),
threshold-with-uncertainty (16), rate/slope (15), delta (8), joins/group_by
(5), sequence ops (2). The runtime has exactly 8 operators
(`gt,gte,lte,eq,neq,persists_for,exists,count_at_least`) and 7
compiler-reachable concepts. Honest support: **7 demonstrated floor, ~230
optimistic ceiling** out of 741. The gap is operators and composition
constraints, not detectors. Additionally, **68 atlas entries (9%) are
operators counted as concepts**, inflating the denominator.

## Taxonomy quality

- 26 families. Largest: temporal_logic_and_aggregation (68 — the operator
  wishlist), off_ball_attacking_movement (43), team_shape_units_and_lines
  (39), pressure_and_defending (37), shooting_and_goalkeeping (34).
- Definitional duplicates found (same measurement, different names):
  expected_goals≡shot_expected_goal; expected_pass_completion≡
  pass_completion_probability; ball_recovery_episode≡recovery_of_control;
  counterpress_candidate≡counterpress_phase_candidate; wall_pass≡give_and_go
  (+context); switch triplet; nearest-entity triplet; arrival-margin quartet;
  rest-defense concepts scattered across three families; restart semantics
  split across two families.
- Systematic compounds posing as atoms: 18 dual pairs (signal ×
  rising/falling edge ≈ 36 concepts), the `*_after` template (8 = delta ×
  window), the `*_within` template (6 = exists × window), the `expected_*`
  template (10), explicit compound tactics (press_trap, overload_to_isolate,
  up_back_through, …) that should be SequenceSet recipes.
- **Honest compression: 741 → ~430–480 atoms + ~25 operators + ~30 recipe
  templates**, no expressive loss.
- Permanent typed-gap territory ≈ 200 concepts (27%): learned value &
  counterfactuals (26), learned classifiers/embeddings (~30), pose/video
  proxies (8), intent-flavored run semantics (~7), officiating/external
  references (~13), MODELLED pitch-control stack (reachability family 22/25
  MODELLED).

## Operator-gap ranking (the key output)

| # | Operator | Atlas co-unlock | Serves |
|---|----------|-----------------|--------|
| OP1 | `typed_join` + declared composition constraints | ~109 rows (map's own backlog; ≈70 with landed primitives) | nearly every dossier question; ALL CAR layers |
| OP2 | `extremum_over_set` (argmin/argmax/rank/top-k/nearest, witness + tie policy + UNKNOWN on incomplete membership) | 30–40 | progression hubs, nearest recoverers; CAR-0/3 |
| OP3 | `project_onto_axis` (vector→signed scalar; angle-between) | 35–45 | support geometry, movement components; CAR-0 |
| OP4 | `window` bidirectional + `trace_back_from_outcome` | 25–35 | chance genealogy (QB A3, D2); CAR-1/3 |
| OP5 | `aggregate_over` with typed UNKNOWN-aware coverage | 35–50 | the tendency layer (QB D1); CAR-2/3 |
| OP6 | `delta_across_anchor` generalized + rising/falling edge | 35–45 | the 18 dual pairs; block-shift speed; CAR-0/1 |
| OP7 | `rate_and_share` (honest denominators) | 10–15 atlas, highest question-bank density | taxonomy shares, loss-rate maps, press decay; CAR-2/3 |
| OP8 | `entity_set_algebra` (filter/group_by/set ops with expected-membership honesty) | 25–35 | rest defense, flank asymmetry; CAR-0/2/3 |
| OP9 | `sequence_pattern` (followed_by/until + interval algebra) | 30–40 | third-man, press triggers; CAR-1 next-useful-action |
| OP10 | `spatial_join` (dynamic regions, grids, dwell) | 25–30 | zone maps; CAR-2 classing |
| OP11 | `arrival_margin` (composes time_to_arrival + OP2) | 12–18 | interception/receiver margins; CAR-0 |
| OP12 | `compare_to_baseline` / normalize (sample-size gated) | 8–12 | **the CAR number itself** (CAR-2/3 core) |
| OP13 | threshold-with-uncertainty | ~10 | claim discipline everywhere |
| OP14 | coordination/synchrony | 10–15 | keep as recipe over OP3+OP5 |

**OP1–OP7 (~8 operators of work) conservatively unlocks 180–250 distinct
concepts with already-landed primitives.** Ship as coherent releases, not one
at a time: R1 = OP1, OP2, OP3, OP4-window, OP6 (post-F2, pure typed-IR work);
R2 = OP5, OP7, OP8, OP9, OP10.

## Primitive ranking refresh (operator lens applied)

Operators dissolve several coverage-map "missing primitives" into
compositions (marking, team_press typing, rest_defense, run typing). What
remains genuinely primitive, ranked: (1) **contact/touch_candidate** —
gateway to duels, miscontrol, first contact, second balls; promoted to #1,
absent from the old ranking; (2) moving_target_interception / time_to_arrival
v2; (3) shot_anchor + shot geometry (worst family: 1/34 supported); (4)
structured_zones v2 (dynamic/standard regions); (5)
**fragile_possession_state** — CAR-0, low atlas count but highest product
value; schedule as OP1's acceptance test; (6) off_ball_run onset/end
anchoring; (7) duel/contest_episode; (8) pressure_release/escape typing +
stable_possession_reset (CAR-1); (9) set_piece_routine typing; (10)
reachability/space regions (heaviest model risk, last).
`generated/audits/next-primitive-recommendations.json` is stale — all five of
its recommendations have landed; regenerate with this ranking.

## The 25 redesign proposals (decision digest)

1. Move the 68 temporal_logic_and_aggregation entries from the concept
   denominator to the operator registry.
2. Add `required_missing_operators[]` to every coverage-map row; downgrade
   the ~125 phantom-machinery rows to partial_with_typed_gap; make
   aggregate.py validate rather than normalize.
3. Merge support_angle/width/depth/distance → one support_geometry vector +
   OP3 projections.
4. Collapse the 18 dual pairs into signals + edge operator (~36→18).
5. Collapse `*_after` (8) into delta×window and `*_within` (6) into
   exists×window templates.
6. Merge movement-component concepts into vector primitives + OP3 (~12→4).
7. Delete the four literal duplicate pairs.
8. Reclassify shot_distance/shot_angle as distance/angle_to_goal at
   shot_anchor.
9. Consolidate the six rest-defense concepts into one record + projections.
10. Merge the arrival-margin quartet into one arrival_margin template.
11. Merge the switch-of-play triplet.
12. Merge wall_pass into give_and_go; fold actor-view variants in.
13. Delete nearest-entity triplet as atoms; re-express via OP2.
14. Reclassify compound tactics (press_trap, overload_to_isolate,
    attract_then_release, counterattack) as reviewed SequenceSet recipes.
15. Reclassify learned_value family + learned classifiers (~56) as
    MODELLED_EPOCH, excluded from the GC-v1 denominator.
16. Rename intent-promising run concepts (decoy_run_candidate →
    unused_disruptive_run_candidate; dragging_run/marker_attraction →
    defender_displacement_correlated_run).
17. Strip/gate body-axis clauses; mark the 8 pose proxies permanent
    missing_modality.
18. Unify lane/channel geometry into one declared partition (the atlas
    currently encodes audit bug G4 as three concepts).
19. Merge team-spread statistics septet → team_extent(axis, statistic) +
    covariance_ellipse.
20. Unify restart semantics into one family with a single anchor chain.
21. Rename or demote qualitative_superiority_proxy and
    support_quality_score ("quality" in a name violates claim doctrine).
22. Promote fragile_possession_state and next_useful_action into the working
    taxonomy as first-class typed concepts.
23. Split record-bundle atoms (receiving_location_relation,
    line_break_receiver_state) into measurements + OP1 joins.
24. Add the tendency layer as explicit concepts (tendency_share,
    zone_rate_map, per_player_baseline_rate) with UNKNOWN-denominator
    contracts.
25. Regenerate next-primitive-recommendations.json with the operator-lens
    ranking.

## General Compiler v1 — the honest claim

> Any question expressible as (a) anchors/episodes drawn from the bound
> capability registry, composed with (b) the operator set {comparison,
> persists_for, exists/count_at_least, window (both directions),
> delta_across_anchor, rising/falling edge, project_onto_axis,
> extremum_over_set, aggregate_over with typed coverage,
> rate_with_honest_denominator, entity filter/group_by, typed joins with
> declared composition constraints, followed_by} — either compiles to an
> executable typed plan or returns a typed gap naming the exact missing
> capability, operator, modality, or composition constraint. **No third
> outcome exists.**

Sizing: ~420–480 of 741 concepts compile-and-execute; ~260–320 return typed
gaps — both auditable per row. ~70% of the scouting question bank executable,
100% compile-or-typed-gap. CAR-0..2 covered structurally; CAR-3 in v1.1.
Preconditions: F1 complete, F2 executor extraction, proposal #2 (measured
denominator). **KPI: `compiler_reachable` (currently 7), never "supported."**

## Director rulings attached to this review

- Adopted: operator-first build order (F1 → F2 → R1 → R2 → GC-v1 freeze →
  sealed evaluation).
- Adopted: KPI change to `compiler_reachable`.
- Constraint: the raw 741 manifest is Priori's authored document and is never
  mutated; all redesign lives in the registry/coverage layers as an explicit
  mapping.
- The owner's sealed set (`afl-hidden-suite-v1`, hash-pinned 2026-07-02) is
  reserved for the GC-v1 evaluation.
