# Northstar Query Decomposition → First AFL-08 Package

**Method (per constraint):** decompose ONLY the six northstar queries; do not build a taxonomy. Let
shared dependencies reveal the build order. Companion to `next-primitives-northstar.md`.

Legend: **EXISTS** = executable today · **[A#/B#]** = substrate id from the northstar · *derived* =
a composition of foundationals (not separately built) · **GAP** = typed `SemanticGap` to return
honestly if asked before built.

---

## Per-query decomposition

### Q1 — Goal kicks: build short, attract pressure, find far-side fullback
- **Grammar:** `restart_anchor.goal_kick` · `action_event_anchor` [B1] · `action_chain` [B3] · build-up phase [B2]
- **Geometry:** *pressure_on_carrier* (= [A1]+[A2]+[A6]) · *switch_of_play* (= EXISTS `ball_lateral_fraction`+`signed_lateral_shift` + [B1]) · side/channel via `ball_lateral_fraction`
- **Outcome:** `outcome_window.retained_possession`
- **EXISTS:** `ball_lateral_fraction`, `signed_lateral_shift`, `possession_segment`, `controlled_pass_episode`
- **Missing (foundational):** restart_anchor, [B1], [B3], [A1], [A2], [A6], outcome_window
- **GAP:** "fullback" = player-role identity (no role taxonomy) → reduce to *opposite-side wide receiver*. "attract" = intent → reduce to *pressure rose near the ball during the short phase* (no intent claim).

### Q2 — Carries that break pressure and lead to a third-player layoff
- **Grammar:** `action_event_anchor` [B1] · `action_chain` [B3] (length-3, player-linked) · *carry_episode* · *relay/layoff* (one-touch, in-flight)
- **Geometry:** *pressure_on_carrier* (= [A1]+[A2]+[A6]) · "break pressure" = pressure **delta** across the carry = `change_across_anchor` [B5]
- **Outcome:** `outcome_window` (layoff = terminal action)
- **EXISTS:** `possession_segment`, `controlled_pass_episode`; one-touch relay (draft pipeline)
- **Missing (foundational):** [B1], [B3], [A1], [A2], [A6], [B5]
- *derived:* carry_episode (= [B1]+[A2]), pressure_on_carrier

### Q3 — Receiver breaks the second line but has no underneath support
- **Grammar:** `action_event_anchor` (the reception) [B1]
- **Geometry:** *multi_line_model* (2nd line — generalizes EXISTS `defensive_line`) · `controlled_line_break` EXISTS · `relative_position_to_line` EXISTS · *support_geometry* directional ("underneath" = support behind ball — extends EXISTS `support_arrival` via [A1] direction)
- **EXISTS:** `controlled_line_break`, `relative_position_to_line`, `support_arrival`, `local_number_relation`, `defensive_line`, `controlled_pass_episode`
- **Missing (foundational):** multi_line_model, [A1] (for support direction), [B1]
- **NOTE:** *nearest-to-today.* Compiles almost entirely on the existing line family; gap is only multi-line + support **direction**. Candidate early standalone win, independent of the kinematic substrate.

### Q4 — Defensive block compact, then loses lane coverage after a switch
- **Grammar:** `action_event_anchor` (the switch) [B1] · `change_across_anchor` [B5] (compact→loses, before/after the switch)
- **Geometry:** *compactness/team_shape* (= [A1] across the unit) · *lane_denial/cover_shadow* (defensive mirror of EXISTS `lane_occupancy`; = [A1]+[A3]) · *switch_of_play* (EXISTS machinery) · `lane_occupancy` EXISTS
- **EXISTS:** `lane_occupancy`, `ball_lateral_fraction`, `signed_lateral_shift`, `defensive_outfield_centroid`
- **Implemented substrate:** [A1], [B5], [B1], and `time_to_arrival` [A3] now compile the Q4 lane-coverage clause as static target-point reachability.
- **Remaining precision boundary:** this is not full lane denial, cover shadow, pass-line interception, pitch control, or moving-target interception. The v0.1 claim is fixed-point arrival under a declared max-speed, point-mass model.

### Q5 — Regains in our half → settled possession within N sec (vs immediate loss)
- **Grammar:** `transition_anchor` [B4] (the regain instant) · possession-phase spine [B2] (settled vs transition) · `outcome_window` (within N)
- **Geometry:** `structured_zones` [A4] ("our half") · minimal kinematics
- **EXISTS:** `possession_segment` (regain = the boundary between opp and own possession — [B4] is cheap to derive from it)
- **Missing (foundational):** [B4], [B2], outcome_window, [A4]
- **NOTE:** *purest Layer-B test* — heavy grammar, almost no kinematics. The one query that argues for pulling transition/phase into Package 1 (cheap, because `possession_segment` already exists). "settled" needs a **frozen threshold** (N retained actions / duration-without-loss) — define-and-freeze, deflection-audit style.
- **AUTHORING RULE:** Q5 must annotate temporal/entity alignments in the typed plan as they are authored. Name the transition anchor frame, the possession segment it opens, the same-team possession continuity constraint, the outcome-window start/end frames, and the entity identities that must remain correlated across regain → settled phase → outcome. Do not leave these as implicit wiring in node order; future coverage-map mining should read them directly from plan metadata rather than reconstruct them from graph archaeology.

### Q6 — Throw-ins: first action progresses past first line under pressure
- **Grammar:** `restart_anchor.throw_in` · `action_event_anchor` (first action) [B1] · `action_chain` head [B3]
- **Geometry:** *multi_line_model* (1st line) · `controlled_line_break` EXISTS · `relative_position_to_line` EXISTS · *pressure_on_carrier* (= [A1]+[A2]+[A6])
- **EXISTS:** `controlled_line_break`, `relative_position_to_line`, `defensive_line`, `controlled_pass_episode`, `opponents_bypassed_by_action`
- **Missing (foundational):** restart_anchor, [B1], [A1], [A2], [A6], multi_line_model

---

## Aggregate — foundational primitives ranked by unlock count (this is the proof)

| Rank | Foundational primitive | Queries | Count | Verdict |
|------|------------------------|---------|-------|---------|
| 1 | **`action_event_anchor` + action vocab [B1]** | Q1–Q6 | **6/6** | Package 1 — universal |
| 2 | **`pairwise_distance` [A1]** | Q1,Q2,Q3,Q4,Q6 | **5/6** | Package 1 — geometric floor |
| 3 | **`action_chain` spine [B3]** | Q1,Q2,Q5,Q6 (+Q4) | **4–5/6** | Package 1 — grammar spine |
| 4 | **`velocity`/`closing_speed` [A2]** | Q1,Q2,Q4,Q6 | **4/6** | Package 1 (pairs w/ A6) |
| 4 | **`tracking_quality` [A6]** | Q1,Q2,Q4,Q6 | **4/6** | Package 1 (rides A2 — honesty) |
| 6 | **`outcome_window`** | Q1,Q2,Q5 | **3/6** | Package 1 — cheap, reusable |
| 7 | `structured_zones` [A4] | Q1*,Q5,Q6* | 2–3/6 | Package 1 *thin* (sides already via `ball_lateral_fraction`) |
| 8 | `restart_anchor` | Q1,Q6 | 2/6 | Package 1 — cheap, high-distinctiveness |
| 9 | `change_across_anchor` [B5] | Q2,Q4 | 2/6 | Package 1 — only way to say "X then Y after Z" |
| 10 | `multi_line_model` | Q3,Q6 | 2/6 | Package 1 — generalizes EXISTS `defensive_line` |
| 11 | `transition_anchor`[B4]+`phase_spine`[B2] | Q5 (+context) | 1–2/6 | **Decision point** — cheap via `possession_segment`; include to win Q5 |
| 12 | `time_to_arrival` [A3] | Q4 | **1/6** | **Implemented after Q5 due atlas-scale unlock value**; v0.1 static-point reachability |
| 13 | `reference_frames` [A5] | — | **0/6** | **Defer** (proven) |

---

## What the data proves (not assumes)

1. **The two-layer thesis is confirmed by frequency, not assertion:** the top-4 are `[B1]` action anchor (grammar) + `[A1]` distance (geometric) + `[B3]` chain (grammar) + `[A2/A6]` velocity (geometric). Grammar and geometry are *co-equal* in the build floor — neither dominates.
2. **Package 1 spine (4–6/6 tier):** `action_event_anchor [B1]` · `pairwise_distance [A1]` · `action_chain [B3]` · `velocity+closing_speed [A2]` · `tracking_quality [A6]`. These five make the *measurement inputs* for *pressure_on_carrier* and *carry_episode* cheap — but **the concepts are not free**: each is still a first-class capability needing its own DefinitionProfile + ClaimContract + thresholds + real-data verifier + frozen snapshot. *pressure_on_carrier* = nearest-defender + distance/closing-speed thresholds + approach angle + duration + track-quality policy; *carry_episode* = ball-carrier continuity + start/end frames + same-player control + minimum displacement + interruption/turnover logic. Much cheaper, not automatic.
3. **Add the cheap high-leverage tier (2–3/6):** `outcome_window`, `restart_anchor`, `switch_of_play` (free — reuses existing block-shift), `change_across_anchor [B5]`, `multi_line_model` (generalizes existing line family).
4. **One deferral remains proven by the six-query slice:** `reference_frames [A5]` = 0/6. `time_to_arrival [A3]` looked deferrable inside the six-query sample, but the 741-concept coverage map later promoted it because it unlocked far more atlas rows than the sample revealed. It has now landed as v0.1 static-point reachability.
5. **One decision point:** `transition_anchor [B4]` + settled-`phase_spine [B2]` are only strictly needed by Q5 — but they're *cheap* (derivable from existing `possession_segment`) and Q5 is the purest "team work pattern" ("what happens after we win it?"). Recommend **include**; the marginal cost is low and it covers the whole transition family beyond these six queries.

## Coverage after Package 1 (spine + cheap tier + B2/B4)

| Query | Status | Residual gap |
|-------|--------|--------------|
| Q1 goal-kick switch | **Compiles** | "fullback" → opposite-side wide receiver; "attract" → pressure-rose (no intent) |
| Q2 carry breaks pressure → layoff | **Compiles** | — |
| Q3 2nd line, no underneath support | **Compiles** (mostly already) | support **direction** extension only |
| Q4 compact → loses coverage after switch | **Compiles** | v0.1 reachability only; no cover-shadow/pass-line/pitch-control claim |
| Q5 regain → settled within N | **Compiles** (with B2/B4) | freeze "settled" threshold |
| Q6 throw-in past 1st line under pressure | **Compiles** | — |

**Result after the post-Q5 reachability slice: Q3, Q4, Q5, and Q6 have all been exercised across the honest outcomes: observed results, honest zero, and precise typed gap.** Q4's former [A3] gap now compiles as static-point reachability, with the remaining cover-shadow/pass-line/pitch-control scope kept explicit.

## Claim-boundary flags (carry into the passports)
- **"attract pressure" (Q1):** observable = pressure rose near the ball; **never** claim intent/causation.
- **"settled possession" (Q5):** a frozen, reviewable threshold — not a judgement of control quality.
- **player roles ("fullback", Q1):** no role taxonomy → typed `GAP` or reduce to position/side. Do not infer role.
- **all kinematics:** emit UNKNOWN under poor track/ball quality via [A6]; no fabricated velocity.
