# Director's sealed position — CAR v0 and the machinery to compute it
Sealed before counsel. Owner law: CAR is INDIVIDUAL; nothing
team-level ships under the CAR name.

## The definition (position, to be debated)
CAR v0 measures: given possession-involvements where the player is
the CONTINUITY DECISION-MAKER (receives under declared conditions,
or carries, or passes under pressure), the rate at which the team's
possession CONTINUES (declared horizon; observed continuity stream)
— versus the replacement baseline for the same situation class.
- Involvement classes v0 (few, declared): reception-under-pressure,
  carry-out-of-pressure, pass-under-pressure, reception between
  observed lines (GEO-1 when certified).
- Continuity: team retains controlled possession N seconds after the
  involvement resolves (N declared, default 5.0), tri-state from the
  observed possession stream; truncation (half-end) is UNKNOWN.
- CAR_v0(player) = weighted sum over situation classes of
  (player_rate - baseline_rate), weights = player's own involvement
  mix (so CAR answers "vs a replacement doing THIS player's job").
  All arithmetic interval-propagated; UNKNOWN never resolves.

## Replacement baseline (position)
Position-pooled (GK excluded; outfield pooled v0 — role clustering
is NOT observation and is deferred): for each situation class, the
pooled rate of all OTHER players' involvements, trimmed to the
interquartile band ("replacement" = median-adjacent, not average —
declared choice). Baseline wears its own tier: BASELINE(v0,
definition-hash) on every artifact; never blends into observed.

## Field-domain mechanism (position)
A field declares [min, max] (and unit) in the registry; an UNKNOWN
row contributes its declared domain to sum/mean bounds; FAIL rows
contribute NOTHING (they are not observations of the field — the
R2-1 principle-22 lesson). Rates of counts stay the joint-partition
law; mean-of-field gains: observed mean over A-rows, bounds widened
by UNKNOWN rows at domain edges. Ordering invariant inherited.
Difference-of-rates (CAR's core op) propagates intervals exactly:
[pl_lo - base_hi, pl_hi - base_lo].

## Goodhart pre-attack (position)
- Backward-pass farming: continuity alone rewards safe recycling →
  v0 REPORTS but does not blend a progression covariate (carry/pass
  forward metres alongside, never merged into one number silently).
- Small-n: minimum involvement count per class (declared, default
  10) below which the class row is UNKNOWN for that player.
- Selection: involvement classes are certified compositions —
  a player cannot opt out of pressure situations being counted.

## Sequencing position
1a field-domains+sum/mean; 1b share+difference-of-rates; 1c player
populations + cross-match aggregation; then components; baseline;
table+card; gauntlet. GEO continues interleaved; GEO-1 feeds class 4.

## Anti-goals
No role/position inference v0; no cross-season claims on 7 matches;
no single-number CAR without its interval and involvement mix on the
same surface; no team CAR, ever, per owner law.
