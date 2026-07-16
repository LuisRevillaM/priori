Convergence is complete: six primitives, three substrate amendments, no seventh primitive. Two residuals require contract clarification, not new capabilities: evidence-source agnosticism for `ball_control_episode`, and a `deepest_observed_line` selector for `between_observed_lines`.

## Residual rulings

1. **Overloads — no seventh primitive and no amendment.**

At anchor frame \(F\), for arbitrary versioned region \(R\):

- Run `team_distribution_relative_to_reference` once per team with `player_scope=outfield` to establish eligible player IDs and coverage.
- `typed_join` every eligible player to `pitch_region_membership(subject=player_id, frame=F, region=R)`.
- Aggregate membership by `team_id`.
- For team \(t\), define:
  - \(C^-_t=\#PASS\): definitely inside.
  - \(C^+_t=\#PASS+\#UNKNOWN\): possibly inside.
  - Missing eligible tracks are `UNKNOWN`, never omitted.
- For perspective team \(A\), opponent \(B\), and declared advantage \(\Delta\):
  - `PASS` iff \(C^-_A-C^+_B\ge\Delta\).
  - `FAIL` iff \(C^+_A-C^-_B<\Delta\).
  - Otherwise `UNKNOWN`.
- A literal `3v2` is `PASS` only when the intervals collapse to \([3,3]\) and \([2,2]\). “At least a 3v2 superiority” instead declares `minimum_A=3`, `maximum_B=2`, and `minimum_delta=1`.
- `lane_occupancy` is a shortcut or consistency witness when \(R\) is exactly a registered lane; it cannot define arbitrary polygons.

Counts belong in `aggregate_over`, not inside the membership primitive. Folding aggregation into `pitch_region_membership` would weaken orthogonality.

2. **Free man — closed by existing `marking`.**

Recipe name: `receiver_separation_at_controlled_reception.v1`.

```text
controlled_pass_episode(PASS)
→ marking(
    frame_field=controlled_reception_frame_id,
    target_player_id_field=receiver_id,
    candidate_scope=opposition_outfield_to_anchor_team,
    maximum_marking_distance_m=D
  )
```

It emits `nearest_marker_distance_m`, `nearest_marker_id`, and `unmarked_status`. Under the existing convention, `unmarked_status=PASS` means nearest observed opposition distance is strictly greater than declared \(D\). Missing opposition tracks that could alter the result force `UNKNOWN` under observation-manifest enforcement.

The certified claim is “receiver separation at controlled reception under threshold \(D\),” not marking assignment, defensive responsibility, scanning, or tactical freedom.

3. **`ball_control_episode` — confirmed evidence-source-agnostic.**

Its semantic contract consumes canonical possession, ball-state/trajectory, player-candidate, and coverage evidence—not a particular tracker implementation. Every input carries producer/model version, observation tier, confidence or calibration where applicable, validity interval, provenance token, and competing hypotheses.

Clean tracking can supply observed evidence today; D-3 can later supply learned ball/possession/possessor evidence through the same port. Outputs retain and never strengthen the input evidence tier. Competing D-3 hypotheses remain competing controllers or `UNKNOWN`.

Therefore Gate 2 changes the producer binding and evidence quality, not the primitive’s definition or version.

4. **Beyond-last-line — signed geometry suffices, but line selection needs amendment.**

Define signed distance to line \(\ell\) in attacking-direction-normalized coordinates:

\[
s_\ell=x'_{\text{entity}}-x'_\ell
\]

For nearer and farther lines:

- Between: \(s_{\text{near}}>b\) and \(s_{\text{far}}<-b\).
- Beyond the farther line: \(s_{\text{far}}>b\).
- Inside either boundary buffer: `UNKNOWN`.

A fixed rank cannot always be called the last line because the observed line count varies. Amend `between_observed_lines` with `line_selector=deepest_observed_line`, meaning the identifiable observed band with maximum normalized longitudinal coordinate, and emit its identity plus signed distance.

Run composition is then: start \(s\le b\), end \(s>b\), sufficient forward progression, and adequate line coverage. Existing `off_ball_run_type.run_in_behind_status` remains the normal shortcut.

I disagree with calling this an “offside line.” The certified phrase is **deepest observed geometric line**. Legal offside requires a separate laws-aware relation involving the ball, second-last opponent, half, timing, and participation.

# Final converged charter

1. **Scope.** Build exactly six new primitives. Add no overload, free-man, last-line, long-ball, build-up-failure, wing-trap, counterpress, rest-defense, or adversary-weak primitive. Those are declared recipes over observable evidence.

2. **Universal contract.** Every primitive emits a versioned definition, complete parameter echo, witnesses, coverage, provenance tokens, `PASS / FAIL / UNKNOWN`, and typed reasons. `FAIL` requires adequate evidence of negation. Shared missing causes retain shared provenance. Tactical thresholds are declared parameters, never universal football truths.

3. **Mandatory substrate amendments.**

   1. Observation-manifest enforcement: absence becomes negative evidence only when relevant event, ball, possession, player, and window coverage is certified.
   2. Typed field references: frame, entity, point, status, and provenance fields compose through typed references rather than expanding hard-coded literal enums.
   3. `multi_line_model` coverage correction: distinguish adequately observed absence of a declared line/pair (`FAIL`) from insufficient or ambiguous defender observation (`UNKNOWN`).

4. **Primitive set.**

   1. `between_observed_lines`: signed entity distances to declared observed lines, line identities/memberships, and inter-line gap. Support `deepest_observed_line`; never infer tactical line roles or legal offside.
   2. `pitch_region_membership`: full-frame and anchor-relative membership of balls, entities, or points in versioned orientation-aware rectangles, polygons, lanes, halves, thirds, or compound regions.
   3. `point_pair_metric`: planar endpoint displacement, elapsed time, and optional average chord speed. It does not claim 3D path length, height, or loft.
   4. `team_distribution_relative_to_reference`: player IDs, signed longitudinal distances, own-goal-side/level/opponent-goal-side partitions, and coverage-bounded counts relative to a declared ball, entity, point, or observed line.
   5. `ball_control_episode`: conservative controller episodes over canonical, evidence-source-agnostic ball/possession/player evidence, preserving observation tier, provenance, and competing hypotheses.
   6. `pass_attempt_episode`: provider-declared pass attempt plus witnessed release and evidence-resolved terminal state, depending on `ball_control_episode`; it does not infer intent from ball direction alone.

5. **Build order.**

   1. Observation-manifest enforcement.
   2. Typed field references.
   3. `multi_line_model` coverage correction.
   4. `between_observed_lines`.
   5. `pitch_region_membership`.
   6. `point_pair_metric`.
   7. `team_distribution_relative_to_reference`.
   8. `ball_control_episode`.
   9. `pass_attempt_episode`.

   No primitive implementation begins before all three substrate amendments pass their gates. `pass_attempt_episode` cannot precede `ball_control_episode`.

6. **Ratified recipe catalog.**

| Recipe | Declared composition |
|---|---|
| Reception between observed lines | `controlled_pass_episode → between_observed_lines`; aggregate by `receiver_id`; rate over controlled receptions with unknown bounds. |
| Receiver separation at reception | Controlled reception → `marking` at `controlled_reception_frame_id`, target `receiver_id`; expose nearest-opponent distance and declared `unmarked_status`. |
| Regional numerical superiority | Team player scopes → `pitch_region_membership(R)` per player → team count intervals → declared advantage comparison. |
| Progressive pass | Controlled pass or attempt → `project_onto_axis(longitudinal)` ≥ declared progression threshold. |
| Long planar pass beating the block | Pass → `point_pair_metric ≥ L` → declared line break and/or `opponents_bypassed_by_action ≥ N`. |
| Region entry | Subject changes from outside/unknown to inside a declared region, or action endpoint is inside; censored boundaries remain `UNKNOWN`. |
| Left-side build-up loss | Declared build-up origin → attacking-left compound region → loss before declared destination entry. |
| Failed switch | A: no completed `switch_of_play` before loss in a fully observed window. B: explicit opposite-side `pass_attempt_episode` whose completion is observed to fail. |
| Wide confinement | Wide membership persists ≥ \(T\); progress < \(P\); no observed switch/exit; optional pressure/local-number condition; ends in loss. Certified as confinement, not causal trap. |
| Counterpress response | Loss → opponent control confirmation → former possessor’s `team_press`/carrier pressure → optional regain within \(R\). Report immediate pressure separately from counterpress regain. |
| Observed rest-defense shape | At high-possession or loss anchor: own-goal-side distribution + `team_compactness` + `lane_occupancy`. No quality judgment. |
| Run beyond deepest observed line | `off_ball_run` plus signed start/end distance to `deepest_observed_line`; normally use existing `off_ball_run_type.run_in_behind_status`. |
| Compactness at regain | `transition_anchor(regain) → team_compactness → aggregate_over`; evidence gaps remain visible. |
| Observed block shape | `multi_line_model` line heights/gaps + `team_compactness`; no formation, role, or low/high-quality label without declared thresholds. |

7. **Anti-goals.** Do not infer tactical line roles, formation, legal offside, aerial trajectory, intent, causation, quality, optimality, marking assignment, body orientation, scanning, or missed opportunity from these deterministic primitives. Do not treat learned D-3 evidence as observation. Do not turn censored windows or absent event rows into false negatives. Do not add primitives to conceal SHADOW-1 evidence vacuity.