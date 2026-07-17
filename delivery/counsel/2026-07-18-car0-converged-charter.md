# CAR v0 — Final Converged Charter

## 1. Definition and unit of analysis

CAR v0 is an individual, exposure-sensitive measure of attributed possession continuity above a corpus replacement reference.

Its atomic unit is one deduplicated `fragile_carrier_episode`:

1. The episode begins when a uniquely identified player has certified control during an active possession and the reused certified pressure machinery first returns eligible pressure after the declared entry dwell.
2. One uninterrupted fragile spell produces exactly one episode and exactly one attributed player: the onset carrier.
3. Pressure flicker within the gap tolerance, later carriers, receivers, passers, and off-ball actors do not create additional attributed episodes.
4. The episode ends at the first certified terminal event, stable reset, horizon expiry, evidence loss, or possession discontinuity.
5. If no unique onset carrier can be certified, the episode remains in the complete ledger with player attribution `UNKNOWN` and contributes to no player CAR.

The attributed result is not a claim of causal responsibility, decision quality, or player ability.

Continuity is resolved by the first terminal event within the declared horizon:

- `PASS`: controlled same-team transfer or certified stable same-team reset after pressure release.
- `FAIL`: certified opponent possession, opponent-owned restart, or an action ending possession without a controlled same-team successor.
- `UNKNOWN`: uncertain control, continuity, ownership, coverage, identity, or unresolved horizon expiry.

Progression and stable reset are separate evidence labels, but both have episode value 1 in v0.

## 2. Formula and owner fork

For episode \(e\), attributed to onset carrier \(p\):

\[
Y_e =
\begin{cases}
1 & \text{continuity PASS}\\
0 & \text{continuity FAIL}\\
[0,1] & \text{continuity UNKNOWN}.
\end{cases}
\]

Let \(c(e)\) be the frozen onset situation class and \(B_{-p,c(e)}\) the eligible leave-player-out corpus-reference continuity rate. Then:

\[
R_e=Y_e-B_{-p,c(e)}
\]

and the recommended name-bearing metric is:

\[
\boxed{CAR^{v0}_p=\sum_{e:\operatorname{onset\_carrier}(e)=p}R_e}.
\]

The mandatory normalized companion is:

\[
CAR100_p=100\cdot\frac{CAR_p}{N_p},
\]

where \(N_p\) is the number of attributed eligible episodes.

**ADR 0019 owner fork:** The owner must rule whether “CAR” names the residual sum, which measures accumulated attributed contribution relative to the corpus reference, or the normalized residual rate, which measures efficiency per opportunity. Whichever quantity does not receive the CAR name remains a mandatory, separately labeled companion and may not silently replace the chosen headline quantity.

## 3. Parameters and pressure-machinery reuse

CAR must consume the registry’s certified pressure outputs and evidence; it must not recreate defender selection or introduce parallel geometric pressure thresholds.

| CAR round-1 name | Certified registry primitive or parameter |
|---|---|
| `pressure_actor_distance_m` | `pressure_on_carrier.maximum_pressure_distance_m`; for multi-actor classification, `team_press.maximum_press_distance_m` |
| `pressure_actor_closing_speed_mps` | `minimum_closing_speed_mps` |
| `pressure_actor_approach_angle_deg` | `maximum_approach_angle_degrees` |
| single qualifying pressure actor | `pressure_on_carrier.pressure_status` |
| qualifying actor count and bands | `team_press.pressure_actor_count`, derived under that primitive’s declared thresholds |
| pressure truth and uncertainty | `pressure_status`/`team_press_status` plus `coverage_status` |
| nearest-opponent proximity where required | `marking.marking_status`, `nearest_marker_distance_m`, and `maximum_marking_distance_m` |
| `fragility_entry_dwell_s` | `pressure_on_carrier.minimum_pressure_duration_seconds` |
| pressure kinematic window | existing `lookback_seconds` |

Accordingly, the proposed CAR-local distance, closing-speed, approach-angle, normal-count, and wide-count parameters are deleted. The plan identity instead carries the exact primitive versions and their bound parameters.

The existing primitives do **not** declare the following episode/resolution parameters, so these remain legitimately CAR-owned:

| Parameter | Proposed v0 default |
|---|---:|
| `same_episode_gap_tolerance_s` | 0.40 s |
| `refractory_after_resolution_s` | 1.00 s |
| `resolution_horizon_s` | 5.00 s |
| `stable_reset_dwell_s` | 1.00 s |
| `pressure_release_dwell_s` | 0.60 s |
| `progression_min_m` | 5.0 m, evidence label only |
| `baseline_min_known_episodes` | 30 |
| `baseline_min_distinct_players` | 8 |
| `baseline_min_distinct_matches` | 3 |
| `player_min_known_episodes_for_rate` | 10 |
| `class_coarsening_order` | frozen below |
| `replacement_exclusion` | leave-one-player-out |

Touchline confinement is a situation-class field, not an alternative pressure detector. Any pressure qualification inside or outside that class uses the same certified primitives.

All defaults require preregistered sensitivity testing. A change to any primitive version, bound primitive parameter, CAR parameter, class schema, field domain, or coverage manifestation creates a new metric version.

## 4. Situation class, including GEO-1

The frozen onset-only situation class is:

\[
c(e)=(
\text{pitch region},
\text{pressure-count band},
\text{touchline confinement},
\text{support-arrival band},
\text{reception-between-observed-lines}
).
\]

The fifth field joins v0 once `between_observed_lines` is certified. Deferring it would force an immediate semantic version change and discard a certified contextual distinction already identified independently by both positions.

On seven matches, its cost is cell multiplication and a likely high `UNKNOWN` rate. That cost is controlled by:

- values `yes`, `no`, and `UNKNOWN`, never inferred;
- baseline population thresholds;
- deterministic coarsening; and
- acceptance that many player/class results remain `UNKNOWN`.

The frozen coarsening ladder is:

1. remove `reception-between-observed-lines`;
2. remove support-arrival band;
3. merge pressure bands `2` and `3+`;
4. remove touchline confinement;
5. fall back to pitch region alone;
6. otherwise baseline `UNKNOWN`.

This makes GEO-1 available where supported without allowing it to destroy baseline coverage. No alternative ladder may be selected after viewing player results.

## 5. CAR-1 episode ledger as an independent product

CAR-1 is a Film Room product before any baseline or CAR aggregate exists. It must directly support queries such as “show every certified episode in which player X came under pressure and what happened.”

Every row must contain at least:

- stable episode ID and metric/primitive version hashes;
- match, period, timestamps, frame range, and replay/clip reference;
- perspective team and unique onset-carrier ID, or attribution `UNKNOWN`;
- possession-segment and source-anchor IDs;
- episode onset, gap-bridge, reset, and terminal timestamps;
- reused `pressure_status`, `pressure_actor_count`, actor IDs where licensed, marking fields where consumed, and their evidence references;
- frozen raw situation-class fields, including GEO-1 status;
- continuity status, reason, first terminal event, restart ownership, and resolution path;
- `progression` versus `stable_reset` label and progression metres where known;
- coverage status and all `UNKNOWN` reasons;
- successor receiver and other involvement identities as evidence-only fields;
- audit disposition and provenance hashes.

The Film Room surface must filter by player, match, outcome, pressure-count band, region, confinement, GEO-1, resolution type, and coverage state. It must expose complete successes, failures, and unknowns—not curated highlights. Baseline and residual columns may be joined later but are not prerequisites for ledger usefulness.

## 6. Field-domain law

Every aggregatable numeric field binds before aggregation to a versioned `FieldDomain` containing:

```text
field_ref
unit
lower_bound
upper_bound
lower_closed
upper_closed
finite_required
domain_basis
coverage_manifest_ref
version
```

`domain_basis` is one of:

- `ONTOLOGICAL`;
- `RULE_BOUND`;
- `OBSERVATION_BOUND`; or
- `DATASET_EXTREMA`, which is prohibited for inferential bounds.

Membership status and numeric observation are independent. A membership-`FAIL` row is excluded; it is not an observed numeric zero.

For field interval \([l_i,u_i]\) and declared domain \([L,U]\):

\[
C_i =
\begin{cases}
[l_i,u_i] & M_i=PASS\\
[0,0] & M_i=FAIL\\
[\min(0,l_i),\max(0,u_i)] & M_i=UNKNOWN.
\end{cases}
\]

Sum bounds are the exact sums of contribution endpoints.

Mean bounds use joint numerator/count reasoning:

1. mandatory members are membership `PASS`;
2. optional members are membership `UNKNOWN`;
3. the lower bound evaluates every prefix average after sorting optional lower endpoints ascending;
4. the upper bound evaluates every prefix average after sorting optional upper endpoints descending;
5. the empty optional prefix is included.

This prefix-average construction gives exact bounds. An observed mean exists only when at least one mandatory member exists and every mandatory field value is exact.

CAR residual has ontological domain `[-1,1]`. Units, finiteness, containment, ordering, evidence partitions, and domain versions are invariant; callers may not supply convenient aggregate bounds.

## 7. Baseline law

“Replacement” in v0 means the observed pooled continuity performance of other eligible onset carriers in the seven-match corpus under the same situation class. It is a corpus reference, not a labor-market replacement player.

For focal player \(p\), the baseline includes:

- all qualifying episodes across all seven matches and both perspectives;
- onset carriers other than \(p\);
- identical metric, primitive, parameter, coverage, and evidence versions;
- no duplicate or overlapping episodes; and
- no team aggregate substituted for player episodes.

The baseline is leave-player-out and pooled. There is no IQR trimming, percentile selection, role inference, shrinkage, imputation, or outcome-dependent class selection.

A class is eligible only after satisfying the minimum known-episode, distinct-player, and distinct-match thresholds. Unknown outcomes remain present in interval bounds and counts. If a class fails, the frozen coarsening ladder is applied exactly; if every level fails, its baseline is `UNKNOWN`.

Leave-one-match-out is a required sensitivity result, not the headline baseline.

Episode residual bounds are:

- episode `PASS`: \([1-B_U,1-B_L]\);
- episode `FAIL`: \([-B_U,-B_L]\);
- episode `UNKNOWN`: \([-B_U,1-B_L]\).

CAR bounds are summed exactly. A point CAR is legal only when every episode outcome and baseline collapses to a point.

## 8. Evidence tier and publication law

Every CAR artifact carries:

```text
DETERMINISTIC_DERIVED
METHODOLOGY_DEMONSTRATION
SEVEN_MATCH_CORPUS
NOT_PLAYER_EVALUATION
BASELINE(v0, definition_hash)
```

Every player surface must show:

- CAR interval;
- CAR100 interval;
- attributed episode count;
- PASS/FAIL/UNKNOWN counts;
- minutes represented;
- class composition;
- baseline populations;
- class-coarsening events;
- coverage and exclusion reasons; and
- links to the complete episode ledger.

The permitted claim is limited to attributed observed continuity residuals against the declared leave-player-out corpus reference. CAR v0 may not claim ability, talent, value, causation, decision quality, future performance, literal replaceability, or league rank.

## 9. Goodhart counters

The full round-1 Goodhart table is incorporated by reference as normative acceptance material. In particular, ratification requires tests for:

- one onset episode per continuous fragile spell;
- dwell, gap tolerance, and refractory protection against flicker;
- first-terminal-event resolution;
- timeout as `UNKNOWN`;
- controlled-successor and certified-restart ownership;
- no receiver, passer, off-ball, or team double attribution;
- frozen primitive parameters and class schema;
- deterministic coarsening;
- leave-player-out comparison;
- complete uncertainty bounds and coverage disclosure;
- no `FAIL`-as-zero field fabrication;
- no outcome, identity, team, or match leakage into classes;
- full episode-ledger decomposition;
- CAR plus CAR100 plus exposure;
- no ranking claims beyond interval evidence; and
- mandatory non-causal, corpus-reference language.

Safe backward continuity is deliberately counted in v0, but progression versus stable reset is always reported separately and never silently blended into the score.

## 10. Packet sequence

1. **CAR-0a — Episode identity and attribution:** deduplicated episode IDs, unique onset carrier, gap/refractory law, ambiguity propagation.
2. **CAR-0b — Fragile-state composition:** reuse and certify existing pressure/marking primitives, bound parameters, context eligibility, and seven-match coverage.
3. **CAR-0c — Continuity resolver:** first terminal event, controlled transfer, stable reset, losses, restart ownership, timeout, and `UNKNOWN`.
4. **R2-1b — Numeric field domains and sum:** exact interval sum, negative domains, and unknown membership.
5. **R2-1c — Exact bounded mean:** mandatory/optional prefix optimization and observed-mean law.
6. **CAR-1 — Seven-match episode ledger and Film Room surface:** complete player-attributed ledger, replay links, provenance, coverage, and film audit; no baseline required.
7. **CAR-2a — Situation classifier:** freeze all five onset-only fields and the coarsening ladder; publish population tables.
8. **CAR-2b — Replacement baseline:** pooled leave-player-out class rates, minimum thresholds, and baseline evidence tier.
9. **CAR-3 — Residual and player aggregation:** CAR, CAR100, exposure, coverage, class composition, and excluded-player ledger.
10. **CAR-C — Adversarial corpus computation:** byte reproduction, sensitivity grids, leave-match-out analysis, manual replay audit, and round-1 Goodhart tests.
11. **CAR-4 — Integrated inspectable product:** every player aggregate linked to every eligible success, failure, and unknown episode.

## 11. Anti-goals

CAR v0 is not:

- a team metric or team-level artifact;
- a generic pressure-success or fragile-retention rate;
- a causal credit allocation;
- split credit across carriers, passers, receivers, or off-ball actors;
- a possession-value, progression, threat, or xG model;
- a role-, formation-, or position-inference system;
- a learned fragility or similarity model;
- a market definition of a replacement player;
- a league norm or cross-season player rating;
- a per-90 statistic presented as accumulated contribution;
- a naked point estimate, uncertainty-free leaderboard, or scout-opinion fit;
- an imputation presented as observation;
- a mechanism for dropping `UNKNOWN`, weakening coverage, or fabricating numeric zero;
- a license to infer intent, tactical responsibility, or unobserved structure; or
- a substitute for the complete replayable episode ledger.