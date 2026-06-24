# Priori — Next-Primitives Northstar

**Decisive steps toward a general football language.** Working draft (gitignored). Promote into
AFL-08 backlog entries via atlas-triage when chosen.

---

## 0. Thesis

We have proven the architecture composes: one vertical — *line-breaking against a block* — runs
end-to-end with typed evidence (anchor → spatial measurement → relation/episode → PASS/FAIL/UNKNOWN →
evidence-backed replay). Generality is now gated **not on more detectors** but on **two missing
foundation layers** that every team possession/defense pattern silently depends on:

- **Layer A — a geometric/kinematic substrate** (to *measure any moment*), and
- **Layer B — an action + possession-phase grammar** (to *chain moments into narratives*).

Build those two floors plus a few cheap event-backed anchors, and hundreds of atlas concepts stop
being one-off builds and become cheap compositions. That is the decisive investment.

---

## 1. Northstar test (what "general" means, concretely)

Generality = these queries compile to honest, evidence-backed programs (or a precise typed gap), with
**no bespoke detector per query**:

1. Goal kicks where we build short, attract pressure, then find the far-side fullback.
2. Carries that break pressure and lead to a third-player layoff.
3. Possessions where the receiver breaks the second line but has no underneath support.
4. Defensive possessions where our block is compact, then loses lane coverage after a switch.
5. Regains in our half that become a settled possession within N seconds (vs. immediate loss).
6. Throw-ins where the first action progresses past the first line under pressure.

These are the **triage forcing function**: every primitive below earns its place only by being
required to compile one of these. Decompose each query → the union of required primitives *is* the
build list, with dependencies made explicit.

---

## 2. The two foundation layers (the decisive investment)

### Layer A — Geometric / Kinematic substrate (measure any moment)
The continuous floor. Ranked by unlock value:

| ID | Primitive | Unlocks |
|----|-----------|---------|
| A1 | `pairwise_distance` (entity↔entity / ↔ball / ↔region, over time) | pressure, marking, compactness, support distance, duels — highest single-primitive leverage |
| A2 | `velocity` / `acceleration` / `speed` / `closing_speed` | press intensity, recovery runs, sprints, counterpress timing, carry speed — the physics layer |
| A3 | `time_to_arrival` / `time_to_intercept` (reachability) | pressing traps, interception margins, pass-window safety, pitch control |
| A4 | `structured_zones` (thirds, channels, half-spaces, zone14, box) | zonal pressing, half-space occupation, final-third entries — reusable pitch geography |
| A6 | `tracking_quality` / `derivation_confidence` | keeps the kinematic layer **honest** — velocity/pressure emit UNKNOWN when the track is thin or the derivative is unreliable, instead of fabricating |
| A5 | `reference_frames` (ball-relative, team-relative, actor-relative) | natural expression of pressing/compactness — **deferrable**: a cleanliness layer, not required to compile the first queries |

> A6 is not optional polish. Velocity, closing-speed, and pressure are *derived* quantities sensitive
> to frame rate, smoothing, and ball-track gaps. Without a derivation-confidence primitive the
> kinematic layer either fabricates numbers or fails closed too aggressively. Build it *with* A2.

### Layer B — Action + Phase grammar (chain moments into narratives)
The discrete floor. This is the leg that is *barely started* and matters most for "language feel."

| ID | Primitive | Unlocks |
|----|-----------|---------|
| B1 | typed **action vocabulary** (pass, carry, dribble, touch, reception, shot, clearance, interception, recovery, turnover, restart) | every sequence query — each a typed chain node |
| B2 | **possession-phase spine** (start / loss / regain; settled vs. transition) | the unit that chains live inside |
| B3 | **action-chain composition** (frame-ordered, same-phase, player-linked; never bridges a turnover) | "X then Y then Z" narratives |
| B4 | **transition anchors** (regain/loss instant + counterpress window) | the hinge of all team work patterns ("what happens after we win/lose it?") |
| B5 | **`change_across_anchor`** operator (measured state before vs. after an event) | "compact *then* loses coverage *after* a switch" — distinct from outcome-windows; generalizes the existing `signed_lateral_shift` baseline-vs-anchor pattern |

> **Do not build `pass_chain_episode` as a one-off.** Generalize the in-flight one-touch work into
> B1+B3 — the typed action-chain spine — so the grammar substrate falls out of work already funded.

---

## 3. Derived primitives (cheap once the floors exist)

These move from "foundational work" to "compositions over A + B":

- **Pressure:** `pressure_on_carrier`, `time_under_pressure`, `unpressured_receiver` = A1 + A2
- **Carry/progression:** `carry_episode`, `progressive_carry`, `carry_into_zone`, `carry_past_opponent` = B1 + A4
- **Team shape:** `compactness`, `block_height`, `line_spacing`, `team_width/depth`, `rest_defense_shape` = A1 across units
- **Multi-line model:** first/midfield/back line, `between_lines_pocket`, `beyond_second_line` = current `defensive_line` generalized + A1
- **Coverage (defensive mirror of `lane_occupancy`):** `cover_shadow`, `lane_denial`, `marking_tightness` = A1 + A3
- **Support geometry:** `support_angle/depth`, `underneath/wide_support`, `third_player_option` = A1 + B-chain
- **`switch_of_play`** (near-free bridge from the old vertical): a fast ball transfer to the opposite
  side/channel = `ball_lateral_fraction` + `signed_lateral_shift` (both **already executable**) + B1
  action. The first new action primitive that reuses the existing block-shift machinery — and it's
  required by two northstar queries (#1 "switch out", #4 "after a switch").

---

## 4. Cheap parallel wins (don't wait on the floors)

Event-backed, no substrate dependency, distinctive query unlock:

- **Restart anchors** — goal kick, throw-in, corner, free kick, kickoff as **first-class tactical
  anchors** (not just events). Precisely marked in event data → cheap to build, high distinctiveness.
- **Outcome windows** — `next_action`, `shot_within_N`, `final_third_entry_within`, `turnover_after`,
  `progression_retained`. Generalizes the existing `relation_destination_entry` ("ball enters region
  within post-open window"). Makes every detector **consequential** — did breaking the line lead to
  anything?

---

## 5. Sequencing (decisive path, not all-at-once)

The trap is "implement the 741-atlas." The discipline is **two thin parallel slices + a quick win**,
each verified end-to-end through the AFL-09A factory.

1. **Slice 1 — geometric:** A1 `pairwise_distance` + A2 `velocity` → `pressure_on_carrier` +
   `carry_episode`. (Largest measurement surface; carry + pressure appear in nearly every northstar
   query.)
2. **Slice 2 — grammar:** generalize `pass_chain` → typed action-chain spine (B1 + B3) + transition
   anchor (B4).
3. **Parallel quick win:** restart anchors + outcome windows.
4. **Then:** shape / multi-line / coverage / support as **compositions** = the first real-row
   consumers of AFL-09A (closing "proof-carrying on real rows" + the dedup dividend).

Each primitive runs the standard rail: registry object → generated passport → runtime binding →
verifier → frozen snapshot → factory gate. **No agent/product exposure without a passing verifier.**

### Package framing & definition-of-done
Bundle Slices 1–3 as one AFL-08 package — call it **"Substrate Package 1: Action Grammar + Basic
Kinematics."** Definition-of-done (the acceptance bar):

> A user can ask about **a restart**, **a pass/carry chain**, **pressure around the ball**, and
> **what happened next**, and the system either compiles it to an evidence-backed program **or returns
> a precise typed gap** — with kinematic outputs carrying tracking-quality confidence (A6).

The "or a precise typed gap" half is non-negotiable: it is what makes broadening *safe* rather than
overclaiming. A query that needs a primitive we haven't built must fail as a named `SemanticGap`, not
a fabricated result.

> **Governance:** this is an **AFL-08 package name, not a new milestone.** Do not mint a
> "Substrate Package 1" milestone ID or a parallel ladder — that re-triggers the SCP-2A/AFL-D0 trap
> already corrected in `ONBOARDING_RECONCILE_WITH_REALITY.md`. It runs as slices under AFL-08
> (Standard Library Expansion); promotion authority stays with the protected gate.

### Sequencing risk: do not gate the substrate on One-Touch's stop condition
One-Touch has a **STOP gate** (deflection separability at S0). If the substrate is serialized *behind*
One-Touch and One-Touch stalls there, the whole substrate stalls. **Decouple them:** extract the
generalizable **action-chain spine (B1+B3)** from the One-Touch work early, then let A1+A2 proceed
*in parallel*. One-Touch-the-tactical-capability may stop at S0; the action grammar it seeds must not.

---

## 6. What this is NOT (guardrails)

- **Not "implement the atlas."** The 741 atlas is a flat, undifferentiated wishlist; this is the
  dependency *floor under it*. The missing AFL-08 artifact is a substrate-tiered dependency ordering,
  not 741 dispositions.
- **No new claim semantics.** PASS/FAIL/UNKNOWN, evidence/replay obligations, and the prohibition on
  intent/optimality/decision-quality/causation are unchanged.
- **Substrate must measure honestly.** Velocity/pressure/reachability carry tracking-quality gaps —
  UNKNOWN when tracking is thin or ball track is poor. No fabricated kinematics.
- **Exposure stays earned.** Each primitive remains DENIED to agent/product until its verifier passes
  on real rows.

---

## 7. If you invest in one thing

**The action + phase grammar (Layer B), paired with A1 (distance) + A2 (velocity).**

Layer B is the leg that is barely started (only `pass_chain`, narrowly), it is what turns isolated
measurements into the *sequences* that make a football language feel general, and it is already
half-funded by the one-touch work. With B + A1 + A2 in place, the majority of the northstar queries
compile. That is the most decisive single step toward generality.
