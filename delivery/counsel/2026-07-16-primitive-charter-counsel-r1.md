# Independent counsel position

My proposed exhaustive delta is **six new primitives across four families, plus three mandatory substrate amendments**. No new generic operators are needed: the existing `window`, `sequence_pattern`, `typed_join`, `project_onto_axis`, `aggregate_over`, `rate`, `persists_for`, and tri-state predicates already provide the required composition machinery.

Crucially, I would **not** build `long_ball`, `build_up_failure`, `wing_trap`, `counterpress`, `rest_defense`, or `adversary_weak` as primitives. Those are declared recipes over observable geometry and state.

## Demand-evidence ranking

| Rank | Missing primitive | Family | Demand unlocked | Cost |
|---:|---|---|---|---|
| 1 | `between_observed_lines` | Line/shape geometry | Receptions between lines; receiver; line spacing | S |
| 2 | `point_pair_metric` | Action geometry | “Long” passes; low-progress wide confinement | XS |
| 3 | `pitch_region_membership` | Pitch geometry | Left-side build-up; wings; opposing field; region entry | S–M |
| 4 | `team_distribution_relative_to_reference` | Team shape | Rest defense; players behind ball; block distribution | M |
| 5 | `ball_control_episode` | Game state | Who lost/received control; counterpress carrier; transition actors | L |
| 6 | `pass_attempt_episode` | Ball action | Attempted-but-failed switches; unsuccessful pass losses | M–L |

The ranking responds directly to:

- Receptions “between the back four and the midfield line,” frequency, and receiver identity: [demand evidence](/tmp/primitive-demand-evidence.md:2).
- Long balls that beat the opposing block: [demand evidence](/tmp/primitive-demand-evidence.md:5).
- Left build-up losses, failed switches, and wing traps: [demand evidence](/tmp/primitive-demand-evidence.md:7).
- Switches as a first-class concept: [demand evidence](/tmp/primitive-demand-evidence.md:10).
- Territorial progress, transitions, losses, and weakness/opportunity: [demand evidence](/tmp/primitive-demand-evidence.md:11).
- Team-shape primitives such as lines: [demand evidence](/tmp/primitive-demand-evidence.md:14).
- Prior demand for counterpress, rest defense, runner beyond the line, and compactness at regain: [demand evidence](/tmp/primitive-demand-evidence.md:17).

## Universal contract for all six

Every primitive must emit:

- A versioned declared definition and complete parameter echo.
- Witness records, coverage information, and provenance tokens.
- A public `PASS / FAIL / UNKNOWN` status and typed reason.
- Internal evidence intervals or competing hypotheses where appropriate.

`FAIL` means the negation is established under adequate observation—not merely that no positive witness was found. Missing evidence with a shared cause carries the same provenance token so downstream rates do not double-widen, as required by [ADR 0017](/Users/luisrevilla/code/priori/docs/adr/0017-counsel-synthesis.md:43).

Mathematical conventions, coordinate transforms, and versioned pitch geometry may be constants. Tactical thresholds—distance, duration, line rank, player count, dwell, “long,” “compact,” and “quick”—must be query or saved-definition parameters, never universal football truths.

## 1. `between_observed_lines`

**Questions unlocked.** “How often do they receive between the lines?”, “Who is the receiver?”, and “Show the situations between the back four and midfield line.” It also exposes inter-line spacing as one observable component of when an opponent may be weak.

**Declared definition.**

Inputs:

- Entity anchor, normally `controlled_pass_episode.anchors`.
- `multi_line_model` evidence at the same declared frame.
- Entity ID field, normally `receiver_id`.
- Entity frame field, normally `controlled_reception_frame_id`.

Geometry:

1. Select two declared observed line ranks, normally rank 1 and rank 2 goal-side of the ball.
2. Transform entity and line coordinates onto the attacking-direction-normalized longitudinal axis.
3. The entity is between them iff its signed position lies strictly inside both buffered boundaries.
4. Emit both signed distances, line IDs/player memberships, and `interline_gap_m`.

Parameters:

- `nearer_line_rank`, `farther_line_rank`.
- `entity_id_field`, `entity_frame_field`.
- `line_boundary_buffer_m`.
- Optional `minimum_interline_gap_m`.

Constants:

- Orientation transform from the observation manifest.
- Exact ordering and inequality convention.
- Rank semantics inherited from `multi_line_model`.

**Tri-state honesty.**

Return `UNKNOWN` when the receiver coordinate, orientation, either required line, line-frame alignment, or line-model coverage is uncertain; also when the receiver falls inside a declared boundary buffer. If tracking is adequately complete but two required line bands do not exist under the declared definition, return `FAIL`. A receiver clearly outside an adequately observed pair is also `FAIL`.

**Composition.**

- `controlled_pass_episode` supplies the reception and `receiver_id`.
- `multi_line_model` supplies observed bands.
- Existing `aggregate_over(group_by=receiver_id)` answers “who/how many.”
- Existing `rate` answers share of controlled receptions, with interval bounds for unknown rows.
- `interline_gap_m` can combine with marking, pressure, corridor, and local-number evidence.

A dedicated `reception_between_lines` primitive would be redundant; that should be a recipe over this geometry.

**Must not claim.**

It must not call rank 1 “the midfield line” or rank 2 “the back four.” Those are observed geometric bands, not tactical-role identification. It must not infer formation, defensive assignment, receiver intent, pass quality, or whether receiving there was optimal.

## 2. `point_pair_metric`

**Questions unlocked.** The measurable part of “long ball,” and the low-progression part of “trapped on the wing.”

**Declared definition.**

Given two witnessed point fields:

\[
d_{xy}=\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}
\]

Emit:

- `planar_endpoint_displacement_m`.
- `elapsed_seconds`, if witnessed frame/time fields are supplied.
- Optionally `average_planar_chord_speed_mps`.

Parameters:

- Start/end point and frame fields.
- Optional required upstream status field/value.

There is deliberately **no built-in “long” threshold**. A saved coach definition applies existing `gte`, such as endpoint displacement ≥ a declared number of metres. Goalward and lateral components remain the job of the existing `project_onto_axis` operator.

Constants are only Euclidean geometry, unit conversion, and manifest frame cadence.

**Tri-state honesty.**

Missing or untrusted endpoint coordinates, unresolved source status, invalid frame ordering, or unregistered coordinate units produce `UNKNOWN`. Zero distance is a valid observed value, not missing evidence.

**Composition.**

- Controlled pass endpoints → declared long planar completed pass.
- Pass-attempt endpoints → declared long planar attempt.
- Region-window start/end points plus `project_onto_axis` → forward escape or confinement.
- Existing `opponents_bypassed_by_action` or `controlled_line_break_episode` supplies “beat the block.”

**Must not claim.**

Planar endpoint displacement is not ball path length. It says nothing about ball height, loft, aerial trajectory, ground contact, spin, whether the ball travelled “over” a line, or 3D speed. Therefore the certified phrase must initially be **“long planar completed pass”**, not “aerial long ball.”

## 3. `pitch_region_membership`

**Questions unlocked.** Left-side build-up, wing confinement, entry into the opposing half/third, and region-specific transitions.

**Declared definition.**

Evaluate a witnessed ball/entity/point against a shared versioned pitch-region registry. It must support compound regions:

- Longitudinal: defensive third, middle third, final third, own/opposing half.
- Lateral: left wide, left half-space, central, right half-space, right wide.
- Compound examples: `defensive_third × attacking_left_wide`.

It should expose both:

- A full-frame signal for tracked ball membership, allowing `persists_for`.
- Anchor-relative evaluations for ball, entity ID, or point field.

Parameters:

- Subject mode and field references.
- Team role and `side_basis`: attacking-team-relative or pitch-fixed.
- Named region or explicit versioned rectangle/polygon.
- `boundary_buffer_m`.

Constants:

- Match-specific pitch dimensions and orientation.
- The existing five-lane boundaries and tie-toward-centre rule.
- Versioned thirds/halves definitions.

This must reuse the current `structured_zone` and lane geometry kernels, not create competing definitions.

**Tri-state honesty.**

Return `UNKNOWN` for missing coordinates, missing calibration/orientation, invalid pitch registration, or any point inside the boundary uncertainty buffer. A fully observed point clearly outside the selected region is `FAIL`. Off-pitch coordinates caused by an invalid projection are `UNKNOWN`, not automatically a meaningful tactical location.

**Composition.**

- `persists_for` supplies wide dwell; no separate residency primitive is required.
- `window` and `sequence_pattern` relate region entry/dwell to loss, switch, or destination entry.
- `structured_zone` remains valid for existing longitudinal-only queries.
- `point_pair_metric` plus `project_onto_axis` measures progress while resident.
- `transition_anchor(loss)` identifies region-specific losses.

**Must not claim.**

Membership in a region does not itself mean build-up, isolation, overload, a trap, opportunity, or tactical role. “Left” must always state whether it is attacking-team-relative or pitch-fixed.

## 4. `team_distribution_relative_to_reference`

**Questions unlocked.** The observable substrate of rest defense; number of players behind the ball; the distribution a pass bypasses; and richer team-shape descriptions.

**Declared definition.**

For a declared player scope and reference point/line:

1. Project every observed player onto the team’s goalward axis.
2. Compute signed distance relative to the ball, another entity, a point, or a supplied observed line.
3. Partition players into own-goal-side, level, and opponent-goal-side sets.
4. Emit player IDs, signed distances, and count intervals using known roster/coverage information.

Parameters:

- Player/team scope.
- Reference mode and fields.
- Acting-team orientation basis.
- `level_buffer_m`.
- `minimum_observed_players`.

Constants:

- Axis projection formula and orientation convention.
- Stable player identity and outfielder/GK taxonomy from the fact store.

Thresholds such as “at least three players behind the ball” remain downstream predicates.

**Tri-state honesty.**

If missing players could change a threshold result, the public result is `UNKNOWN`. Internally the count is bounded by observed and potentially missing eligible players. Adequately observed counts below a threshold are `FAIL`; counts whose lower bound already satisfies it may be `PASS`.

Unknown identities or team assignments must not be silently omitted.

**Composition.**

- At a loss or attacking-possession anchor, combine with existing `team_compactness` and `lane_occupancy` for an observed rest-defense-shape recipe.
- Combine with line bands and inter-line gaps for shape descriptions.
- Existing `opponents_bypassed_by_action` remains the stronger action-specific bypass relation.

**Must not claim.**

It must not label a formation, infer centre-backs/full-backs, certify “good rest defense,” predict counterattack prevention, or infer role/intent. It measures relative distribution only.

## 5. `ball_control_episode`

**Questions unlocked.** Who controlled the ball before and after a loss, the carrier against whom a counterpress begins, and actor-bearing transition analysis.

**Declared definition.**

Create conservative player-control episodes from the joint ball, player, and team-possession evidence. Control requires more than nearest-player proximity:

- Ball-player planar distance under a parameter.
- Minimum dwell.
- Player-ball co-motion or sufficiently low relative velocity.
- Uniqueness margin over competing players.
- Compatibility with team-possession evidence.
- Acceptable missing-frame ratio.

Emit:

- Controller ID/team.
- Episode start, confirmation, and end frames.
- Competing controller candidates.
- Control evidence components and termination reason.

Parameters:

- `maximum_control_distance_m`.
- `minimum_control_dwell_seconds`.
- `nearest_candidate_margin_m`.
- `maximum_relative_velocity_mps`.
- `maximum_missing_frame_ratio`.
- Search/confirmation window and candidate scope.

Constants:

- Deterministic episode construction and interval convention.
- No arbitrary tie-break assigning control when candidates remain materially indistinguishable.

**Tri-state honesty.**

Return `UNKNOWN` for competing candidates, ball/player gaps, incompatible possession evidence, or a high-speed ball whose 2D projection passes near a player without sufficient dwell/co-motion. A fully observed loose ball may produce an observed `NO_CONTROLLER` state; missing evidence may not.

Shared ball/possession uncertainty must retain the same provenance cause identified by the tracker.

**Composition.**

- `transition_anchor(loss)` + new opponent controller anchor + existing `team_press` + later regain gives a counterpress recipe.
- Control before/after a loss supplies losing and gaining actors.
- `pressure_on_carrier`, marking, local-number, and support relations gain a generic carrier source.
- `pass_attempt_episode` uses control episodes to determine terminal outcome.

**Must not claim.**

It must not infer last touch, deliberate possession, technical mastery, shielding, foul responsibility, or an airborne touch. Without ball height, control must be conservative; proximity alone is insufficient.

## 6. `pass_attempt_episode`

**Questions unlocked.** The strict reading of “failed to switch it”: an actual switch attempt that did not reach same-team control. It also supports pass-caused build-up losses.

**Declared definition.**

Start from a provider-declared pass event of any outcome, not only `successfullyCompleted`, and require evidence of physical release by the declared actor. Resolve the terminal state through `ball_control_episode`, stoppage/out-of-play evidence, and tracking.

Emit:

- Passer and provider-declared recipient/target, when present.
- Release frame/point.
- Provider target point or recipient provenance.
- Terminal frame/point.
- `attempt_status`.
- `completion_status`.
- Terminal class: same-team control, opponent control, out of play, observed loose ball, or `UNKNOWN`.

Parameters:

- Event-to-tracking alignment tolerance.
- Release search window.
- Terminal search horizon.
- Terminal control dwell.
- Accepted provider event types.

Constants:

- Provider lineage and event identity.
- Ordered terminal-state precedence.

**Tri-state honesty.**

No event row is not evidence of “no attempt” unless the observation manifest certifies event coverage for that interval. A physical release with no defensible terminal state yields completion `UNKNOWN`. Missing provider target/recipient means the pass attempt may be observed but “attempted switch” is `UNKNOWN`.

`FAIL` for completion requires positively observed opponent control, out-of-play termination, or another declared failure outcome.

**Composition.**

- Explicit opposite-side provider target/recipient position + `pitch_region_membership` defines a switch attempt.
- Completion `FAIL` defines an observed failed attempt.
- `point_pair_metric` supplies planar length.
- `transition_anchor(loss)` links the attempt to a possession loss.
- Existing `switch_of_play` remains the completed-switch primitive.

**Must not claim.**

Ball direction alone must not be used to infer intended recipient or switch intent. It must not label a pass a mistake, blame the passer, infer decision quality, or claim that another option was better.

## Recipe closure over every demand

| Owner question | Declared recipe |
|---|---|
| Receive between lines; who/how often? | `controlled_pass_episode` → `multi_line_model` → `between_observed_lines`; aggregate by `receiver_id`; rate over controlled receptions. |
| Long ball beat block | Controlled pass → `point_pair_metric >= L` → existing line break of declared rank and/or opponents bypassed ≥ N. |
| Lost building up on the left | Possession starts in declared build-up origin → left compound region → loss before declared destination entry. |
| Failed to switch | Reading A: no completed `switch_of_play` before loss, using a fully observed sequence window. Reading B: `pass_attempt_episode` with explicit opposite-side target and completion failure. |
| Trapped on the wing | Wide membership persists ≥ T; forward escape/progress < P; optional observed pressure/local-number condition; no completed switch/region exit; ends in loss. Certified label: “wide confinement under declared conditions,” not causal trap. |
| Counterpress | Loss → opponent control confirmation → existing team press by former possessor → optional regain within R seconds. Separate `IMMEDIATE_PRESSURE` from `COUNTERPRESS_REGAIN`. |
| Rest defense | At a high-possession or loss anchor: own-goal-side player distribution + current compactness + lane occupancy. Output observed shape, not quality. |
| Runner beyond line | Already present: `off_ball_run` + `off_ball_run_type.run_in_behind_status`. No addition. |
| Switched play | Already present: `switch_of_play`. No addition. |
| Compactness at regain | Already expressible: `transition_anchor(regain)` + `team_compactness` + aggregation. SHADOW-1 shows an upstream evidence problem, not a missing primitive. |

“How often?” must return interval counts/rates, and “who?” must group by receiver while retaining unknown bounds. The existing aggregation machinery already supports that.

## Mandatory amendments before these primitives are trustworthy

These are not additional primitives, but they are part of my convergence condition:

1. **Line-model coverage correction.** `multi_line_model` must distinguish “adequate observation, no declared pair exists” from “insufficient/ambiguous defender observation.” The former can support `FAIL`; the latter must be `UNKNOWN`.

2. **Typed field references.** Existing relations enumerate a narrow set of frame/entity field names. New controller and region anchors must compose through typed fields, not require adding every new literal to multiple hard-coded enums. This follows the canonical typed-relational direction of ADR 0017.

3. **Observation-manifest enforcement.** Event absence, ball absence, or missing player tracks may count as negative evidence only when the relevant manifest certifies coverage. SHADOW-1’s vacuity—especially possession/ball UNKNOWN and the 91.73% position veto rate—must remain visible rather than be “fixed” by catalog expansion: [SHADOW-1 review](/Users/luisrevilla/code/priori/delivery/packets/SHADOW-1-REVIEW.md:17).

## Explicit anti-goals

Refuse or defer the following:

- **No tactical-role inference from geometric lines.** Do not rename observed ranks “back four,” “midfield line,” or “second line” without independently supplied role evidence.
- **No monolithic tactical-label primitives.** `build_up_failure`, `wing_trap`, `counterpress`, `rest_defense`, `opportunity`, and `adversary_weak` must be saved declared recipes.
- **No universal thresholds.** There is no system truth for how many metres make a long ball, how many seconds make a trap, or how many players make adequate rest defense.
- **No aerial/over-the-block claim from XY tracking.** Ball height, loft, trajectory arc, and whether a ball passed over rather than through defenders require ball-Z or video perception.
- **No intent from movement.** A lateral pass is not automatically an intended switch; a run is not automatically a decoy; a loss is not automatically caused by pressure.
- **No optimality, pass probability, xT, or “missed opportunity” claim in the deterministic tier.** These belong to a calibrated model tier with its own empirical-validity certificate.
- **No formation or role recognition from one snapshot.**
- **No body orientation, scanning, communication, or coach-instruction inference from current tracking.**
- **No false negatives from absent event rows or censored windows.**
- **No new primitive to mask SHADOW-1 vacuity.** Team compactness at regain is already expressible; the bottleneck is ball/possession/calibration evidence.

My convergence position is therefore: **build exactly these six primitives, harden the three substrate laws, and express every requested tactical concept as a declared recipe over them and the existing catalog.**