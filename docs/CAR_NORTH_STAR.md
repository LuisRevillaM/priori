# CAR — Continuity Above Replacement (North-Star Metric Spec)

Status: `NORTH_STAR_SPEC_V0` — direction-setting, not an implementation
contract. No milestone may claim "CAR" until every layer below it is verified
under the same evidence discipline as the rest of the system.

## Why this metric

Existing possession-value models ask: *how much did this action increase the
probability of a goal?* That framing systematically undervalues players whose
contribution is keeping fragile possessions alive — players who make bad teams
better without consistently moving them measurably closer to scoring.

CAR asks a different question:

> How much better is this player than a replacement-level player at keeping a
> fragile possession alive through a difficult moment, so that the team reaches
> the next useful action — sometimes progressing the ball, sometimes just
> preventing the attack from dying — **compared in the same spatial situation**?

CAR is the flagship proof-of-power target for this engine because its three
ingredients are exactly what a typed spatio-temporal language provides and
event-data models cannot: situation identification from geometry, outcome
definition from typed possession semantics, and replacement baselines
conditioned on spatial situation rather than on event labels.

## Decomposition

CAR requires four layers, each an independently verifiable claim. Per the
system invariant, no layer's product wording may exceed its evidence.

### 1. Fragile possession states (situation layer)

A frame-window where the possessing player/team is under measurable threat of
losing the ball. Candidate composition from the existing catalog:

- pressure on the carrier (distance / closing / angle-spread gates — exists)
- local numerical disadvantage or parity around the ball (exists:
  local number relation)
- support availability: teammates' time-to-arrival and lane occupancy
  (exists: support arrival, time to arrival, lane occupancy)
- escape-route geometry: open corridors / cover shadows denying lanes
  (exists: progressive corridor, cover shadow)
- field context: zone, distance to own goal, touchline confinement
  (exists: structured zones)

A "fragility score" is NOT required for v0. A typed, thresholded
`fragile_possession_state` primitive with PASS/FAIL/UNKNOWN and an explicit
claim boundary is sufficient and preferred: fragility as observed geometry,
not inferred danger.

### 2. Continuity outcomes (resolution layer)

For each fragile state, what happened next, within a bounded horizon:

- `POSSESSION_RETAINED_PROGRESSED` — team keeps the ball and it progresses
  (forward progression / line break / switch — all exist)
- `POSSESSION_RETAINED_RESET` — team keeps the ball without progression
  (the "prevented the attack from dying" outcome; needs a typed
  next-useful-action definition)
- `POSSESSION_LOST` — typed loss (exists in possession-segment semantics)
- `UNKNOWN` — evidence insufficient; never coerced to a definite outcome

The key definitional work: **next useful action**. Proposal: the earliest of
(a) a completed action that changes the tactical picture (progression, switch,
line break, restart won), or (b) a stable-possession reset (clean control,
pressure gates released). This must be a typed definition reviewed like any
catalog primitive.

### 3. Player attribution (actor layer)

Which player carried the possession through the fragile window: the carrier at
fragility onset, plus (v1+) the receiver of an escape pass. v0 should attribute
only to the on-ball player — off-ball credit is a later, separately-verified
claim.

### 4. Replacement baseline (comparison layer)

The rate at which possession survives fragile states of the *same spatial
class*, pooled across all players in the corpus. Spatial classing comes from
the situation layer's typed evidence (pressure count, support arrival time
bands, zone) — NOT from learned embeddings, so the baseline stays inspectable.

`CAR(player) = Σ over player's fragile windows [ outcome_value − baseline(spatial class) ]`

with `outcome_value` a declared mapping (e.g. retained=1, lost=0; progression
weighting deferred to v1) and UNKNOWN windows excluded from both sides, never
imputed.

## Honesty constraints (non-negotiable)

- The 7-match public corpus is far too small for stable player-level ratings.
  Any surfaced number is a **methodology demonstration**, labeled as such —
  "CAR computed over 7 matches" is a claim about the pipeline, not the player.
- UNKNOWN discipline applies end-to-end: missing tracking evidence in any layer
  propagates; no silent imputation.
- CAR does not claim intent, skill, decision quality, or transferability.
  It claims: in geometrically similar observed situations, this player's
  possessions survived at a rate X above/below the pooled baseline.
- Replacement baseline classes must publish their sample sizes; classes below a
  declared minimum emit UNKNOWN, not a noisy number.

## What CAR unlocks for prioritization

Primitive roadmap items should carry a CAR-unlock score alongside atlas
coverage-unlock. Known dependencies already on the coverage map's
top-missing list that CAR needs:

- `transition_anchor` (fragility often begins at transitions)
- `time_to_arrival` (support availability — landed in the AFL expansion)
- `carry_episode` (escape-by-carry outcomes — landed in the AFL expansion)
- pressure-release / escape-pass typing (new)
- stable-possession reset detection (new; relates to
  `clean_control_retention_sequence`, currently a generation-layer gate the
  case study already proposes promoting into the catalog)

## Staging

```text
CAR-0  typed fragile_possession_state primitive + verifier (single match)
CAR-1  typed continuity outcome resolution + next-useful-action definition
CAR-2  corpus-wide window extraction + spatial classing + baseline table
CAR-3  per-player CAR over the 7-match corpus, methodology-labeled,
       with per-class sample sizes and UNKNOWN accounting surfaced
CAR-4  workbench surface: browse a player's fragile windows with replay —
       every CAR number decomposes to inspectable moments
```

CAR-4 is the product payoff: a scouting-report claim ("keeps difficult balls
alive under pressure") that decomposes, moment by moment, into replayable
evidence. That is the difference between this system and a stats table.
