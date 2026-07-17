My independent position: CAR v0 should be an exposure-sensitive, player-level sum of continuity residuals for uniquely attributed fragile-possession episodes. It must not be a team retention rate, a generic pressure-success statistic, or a per-90 leaderboard disguised as “above replacement.”

On the seven-match corpus, CAR v0 is a methodology demonstration only. The honest output will often be a broad interval or `UNKNOWN`; that is a successful computation, not a defect.

This follows the primitive/evidence laws in [ADR 0018](/Users/luisrevilla/code/priori/docs/adr/0018-primitive-charter.md), the aggregation constitution in [ADR 0014](/Users/luisrevilla/code/priori/docs/adr/0014-r2-aggregation-era.md), and the numeric-domain debt exposed in [R2-1-REVIEW](/Users/luisrevilla/code/priori/delivery/packets/R2-1-REVIEW.md). I agree with the north star’s core insight but tighten several definitions below.

## 1. CAR v0 definition

### 1.1 Unit of analysis

The atomic unit is a deduplicated `fragile_carrier_episode`, not a frame and not every passing detector firing.

An episode begins at the first eligible frame \(t_0\) at which:

1. a perspective team has a certified active possession segment;
2. one player has certified individual control of the ball;
3. the fragile-state predicate becomes `PASS` after previously being `FAIL`, `UNKNOWN`, or absent; and
4. the episode is not inside a cooldown from the same unresolved fragile spell.

A continuing pressure spell creates one episode, regardless of how many consecutive frames satisfy fragility. It cannot generate frame-count farming.

The episode ends at the first terminal event, horizon expiry, certified evidence loss, or possession discontinuity.

### 1.2 Involvement classes

Every episode must emit exactly one attribution class.

| Class | Meaning | CAR v0 treatment |
|---|---|---|
| `ONSET_CARRIER` | Player with certified control at fragility onset | Sole eligible credited player |
| `SUCCESSOR_RECEIVER` | Teammate who receives an escape pass during resolution | Evidence only; no v0 credit |
| `OFF_BALL_ENABLER` | Teammate whose run, support, occupation, or screen may assist | Evidence only; no v0 credit |
| `CONTESTED_OR_AMBIGUOUS_CARRIER` | No unique certified onset carrier | Player attribution `UNKNOWN`; no player point |
| `TEAM_ONLY_CONTROL` | Team possession is known but individual carrier is not | Never eligible for CAR |
| `REENTRY_CARRIER` | Same or another carrier controls later in the same unresolved fragile spell | No new episode until a declared reset/refractory condition |

This is deliberately austere. Split credit is not v0. The carrier owns the episode’s observed result, not a claim about causal responsibility or decision quality.

### 1.3 Fragility criterion

CAR v0 should use a typed conjunctive predicate, not a learned fragility score:

\[
F(e)=
\text{carrier control}
\land
\text{active possession}
\land
\text{pressure gate}
\land
\text{context eligibility}.
\]

I recommend the minimum viable pressure gate:

\[
\text{pressure gate}
=
(\text{qualifying pressure actors}\ge P_{\min})
\lor
(\text{touchline confinement}\land
 \text{qualifying pressure actors}\ge P_{\text{wide}})
\]

where a qualifying pressure actor satisfies declared distance, closing-speed, and approach-angle requirements. Missing required tracking yields `UNKNOWN`, not `FAIL`.

Do not make local numerical disadvantage, support arrival, or escape-route geometry mandatory for v0. Those should condition the replacement class. Requiring all of them in the eligibility predicate will collapse the seven-match sample and turn CAR into a detector-intersection coverage test.

### 1.4 Declared parameters

Every number below is a named parameter carried in the plan and evidence. These are proposed v0 defaults, not universal football truths:

| Parameter | Proposed default | Purpose |
|---|---:|---|
| `pressure_actor_distance_m` | 3.0 m | Maximum defender–carrier distance |
| `pressure_actor_closing_speed_mps` | 0.5 m/s | Minimum certified closing speed |
| `pressure_actor_approach_angle_deg` | 60° | Maximum approach-vector deviation |
| `pressure_actor_min_count` | 1 | Normal pressure gate |
| `wide_confinement_pressure_min_count` | 1 | Pressure count when geometrically confined |
| `fragility_entry_dwell_s` | 0.20 s | Reject one-frame detector flicker |
| `same_episode_gap_tolerance_s` | 0.40 s | Bridge brief pressure-gate flicker |
| `refractory_after_resolution_s` | 1.00 s | Prevent repeated credit from one spell |
| `resolution_horizon_s` | 5.00 s | Maximum continuity horizon |
| `stable_reset_dwell_s` | 1.00 s | Required clean-control stability |
| `pressure_release_dwell_s` | 0.60 s | Pressure must remain released for reset |
| `progression_min_m` | 5.0 m | v0 evidence label only, not extra score |
| `baseline_min_known_episodes` | 30 | Minimum known baseline outcomes per class |
| `baseline_min_distinct_players` | 8 | Avoid one/few-player “replacement” classes |
| `baseline_min_distinct_matches` | 3 | Avoid match-specific baselines |
| `player_min_known_episodes_for_rate` | 10 | Display threshold for companion rate |
| `class_coarsening_order` | declared | Deterministic sparse-cell fallback |
| `replacement_exclusion` | leave-one-player-out | Prevent self-comparison |

The final ratified defaults should be sensitivity-tested. Changing any of them creates a new metric version.

### 1.5 Continuity criterion

Let the episode begin at \(t_0\). Inspect only the first terminal event within the horizon.

`CONTINUED` (`PASS`) means that before a certified loss, the team reaches either:

1. `CONTROLLED_TRANSFER`: a controlled pass/reception or controlled carry transition with same-possession continuity; or
2. `STABLE_RESET`: certified same-team control persists for `stable_reset_dwell_s`, while the pressure gate remains `FAIL` for `pressure_release_dwell_s`.

`BROKEN` (`FAIL`) means the first terminal event is:

1. certified possession loss to the opponent;
2. uncontrolled ball exit that awards the opponent the restart; or
3. a player action ending the possession without a same-team controlled successor.

`UNKNOWN` means:

- possession continuity is uncertain;
- individual control or terminal ownership is uncertain;
- tracking coverage disappears before a terminal result;
- restart ownership cannot be certified;
- the horizon expires without either a certified continuation or break; or
- required manifestations are not coverage-certified.

A horizon timeout is therefore `UNKNOWN`, not automatic failure. “We did not observe resolution by five seconds” is not “the player failed.”

Progression and reset are separate evidence labels but both have v0 value 1. Progression weighting would make CAR partly a possession-value metric and belongs to v1.

### 1.6 Exact episode value and formula

For episode \(e\):

\[
Y_e =
\begin{cases}
1 & \text{if continuity is PASS}\\
0 & \text{if continuity is FAIL}\\
[0,1] & \text{if continuity is UNKNOWN}.
\end{cases}
\]

Let \(c(e)\) be its declared spatial/situational replacement class, and let \(B_{-p,c(e)}\) be the leave-player-\(p\)-out replacement continuity rate for that class.

The episode residual is:

\[
R_e = Y_e-B_{-p,c(e)}.
\]

The headline metric is:

\[
\boxed{
CAR^{v0}_p=\sum_{e:\operatorname{onset\_carrier}(e)=p} R_e
}
\]

This is the number called CAR. It is exposure-sensitive: keeping ten more fragile possessions alive than replacement is more contribution than keeping one more alive.

Also publish, but do not rename as CAR:

\[
CAR100_p=100\cdot\frac{CAR_p}{N_p}
\]

where \(N_p\) is the number of eligible episodes. This companion describes efficiency; it must never replace the contribution total silently.

### 1.7 Interval computation

If a known episode outcome is compared with a baseline interval \([B_L,B_U]\):

- continuity `PASS`: residual \([1-B_U,\;1-B_L]\);
- continuity `FAIL`: residual \([-B_U,\;-B_L]\);
- continuity `UNKNOWN`: residual \([-B_U,\;1-B_L]\).

CAR bounds are the sum of episode residual bounds. Baseline and player intervals must remain visible beside:

- known PASS/FAIL/UNKNOWN episode counts;
- class counts;
- baseline population counts;
- matches and minutes represented;
- class-coarsening events.

A point CAR is legal only when every constituent outcome and baseline collapses to a point. That is unlikely on seven matches.

## 2. Field-domain mechanism

The R2-1 amputation was correct. A row’s truth status and a numeric field’s observability are separate dimensions; conflating `FAIL` with numeric zero fabricated measurements.

### 2.1 Domain declaration

Every aggregatable numeric field must bind to a versioned `FieldDomain`:

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

`domain_basis` must distinguish:

- `ONTOLOGICAL`: inherently bounded, such as probability `[0,1]`;
- `RULE_BOUND`: bounded by detector/episode construction, such as horizon duration `[0,H]`;
- `OBSERVATION_BOUND`: bounded only by certified producer limits;
- `DATASET_EXTREMA`: prohibited for inferential bounds because observed extrema do not bound unseen values.

Bounds must be declared before aggregation. They cannot be learned from the rows currently being aggregated.

Each row then has two independent states:

1. membership status: `PASS`, `FAIL`, `UNKNOWN`;
2. field observation: exact value, interval value, or `UNKNOWN`.

### 2.2 FAIL-row contribution

A membership-`FAIL` row contributes exactly zero to `sum` and zero to the included count, but it does not contribute a numeric field value.

That distinction is essential:

- correct: “this row is outside the aggregate population”;
- forbidden: “the field value on this row was observed to be 0.”

Evidence should record `excluded_by_membership`, not manufacture `field=0`.

If the intended question is “mean field value over every denominator row, treating non-occurrence as zero,” that is a different derived field—e.g. `occurrence_weighted_value`—whose zero semantics must be explicitly defined. It cannot be smuggled into generic `mean`.

### 2.3 Sum bounds

For row \(i\), let field interval be \([l_i,u_i]\). An exact observed value is the collapsed interval \([v_i,v_i]\); an unknown field uses its declared domain \([L,U]\).

Contribution intervals are:

\[
C_i =
\begin{cases}
[l_i,u_i] & M_i=PASS\\
[0,0] & M_i=FAIL\\
[\min(0,l_i),\max(0,u_i)] & M_i=UNKNOWN.
\end{cases}
\]

Then:

\[
SUM_L=\sum_i C_{i,L},
\qquad
SUM_U=\sum_i C_{i,U}.
\]

The `min(0,l)`/`max(0,u)` rule is necessary because an UNKNOWN-membership row may ultimately be excluded. It also handles negative domains without inverted intervals.

`observed_sum` is defined only when every membership-`PASS` row has an exact observed field. It sums exact PASS values and excludes membership-UNKNOWN rows. Otherwise `observed_sum=UNKNOWN`.

### 2.4 Mean bounds

Mean requires joint numerator/count reasoning, just as R2-2 rates require a joint partition.

Rows divide into:

- mandatory members: membership `PASS`;
- excluded members: membership `FAIL`;
- optional members: membership `UNKNOWN`.

If there are no mandatory or possible members, mean is typed `UNKNOWN`.

For the lower bound:

1. assign every mandatory row its field lower bound;
2. for each optional row, use its field lower bound;
3. choose the subset of optional rows whose inclusion minimizes the mean.

For the upper bound:

1. assign mandatory rows their upper bounds;
2. use optional upper bounds;
3. choose the subset whose inclusion maximizes the mean.

The exact deterministic implementation is:

- lower: sort optional lower endpoints ascending and evaluate every prefix average with the mandatory lower sum/count;
- upper: sort optional upper endpoints descending and evaluate every prefix average with the mandatory upper sum/count;
- include the empty optional prefix;
- take the minimum/maximum valid candidate.

This is exact because, for a fixed optional cardinality, the smallest lower endpoints minimize the mean and the largest upper endpoints maximize it.

`observed_mean` is defined only when:

- at least one membership-`PASS` row exists; and
- every PASS row has an exact field value.

It is the mean of exact PASS values. Membership-UNKNOWN rows are excluded from the observed value. If a mandatory member’s field is unknown, observed mean is `UNKNOWN`; this avoids the R2-1 error where a partial observed mean can sit outside the actual full-population bounds.

### 2.5 Required invariants

- domain unit equals field unit;
- every exact or interval value lies inside the declared domain;
- finite-only domains reject NaN and infinity;
- `lower ≤ upper`;
- whenever observed is defined, `lower ≤ observed ≤ upper`;
- no external caller supplies aggregate bounds;
- row-level partitions and domain versions are carried in evidence;
- empty and malformed populations fail closed;
- changing a field domain changes the plan identity and result identity.

CAR residual has an ontological field domain of `[-1,1]`, making it a clean first customer of reinstated `sum`.

## 3. Replacement baseline

### 3.1 What “replacement” means in v0

For v0, replacement means:

> The observed pooled continuity performance of other eligible onset carriers in the corpus when facing the same declared situation class.

It does not mean:

- an available free agent;
- a bench player;
- an academy player;
- the league’s Nth percentile;
- minimum professional competence;
- expected performance after transfer;
- a causal estimate of how a literal substitute would perform.

“Replacement” is therefore a metric convention, not a labor-market claim. I would surface the full name once: `corpus replacement reference`.

### 3.2 Baseline population

For player \(p\) and class \(c\), construct the baseline from:

- all qualifying fragile-carrier episodes in class \(c\);
- all seven matches;
- both team perspectives;
- onset carriers other than \(p\);
- the same exact metric version, thresholds, continuity definition, and evidence tier;
- no duplicate frames or overlapping episodes;
- no team aggregate substituted for player episodes.

Use leave-one-player-out, not the global mean including the focal player. Otherwise a high-volume player drags their own baseline toward themselves.

If practical identifiers permit, publish an additional leave-one-match-out sensitivity result. The headline remains leave-player-out; the sensitivity reveals whether one match controls the result.

### 3.3 Situation class

Use a small, predeclared categorical tuple:

\[
c(e)=(
\text{pitch region},
\text{pressure-count band},
\text{touchline-confinement},
\text{support-arrival band}
).
\]

Recommended initial bands:

- pitch region: declared typed regions, not raw coordinate bins invented inside CAR;
- pressure count: `1`, `2`, `3+`;
- touchline confinement: `yes/no`;
- nearest support arrival: `≤1s`, `(1,2]s`, `>2s`, `UNKNOWN`.

Do not include player, team, score state, match identity, or observed outcome in the class. Those invite self-referential or sparse baselines.

Class coarsening must be deterministic and declared before seeing player rankings:

1. remove support-arrival band;
2. merge pressure `2` and `3+`;
3. remove touchline confinement;
4. fall back to pitch region alone;
5. otherwise baseline `UNKNOWN`.

Never hunt across alternative coarsenings for the one most favorable to a player.

### 3.4 Baseline eligibility

A baseline class is eligible only if it reaches all three thresholds:

- `baseline_min_known_episodes`;
- `baseline_min_distinct_players`;
- `baseline_min_distinct_matches`.

UNKNOWN baseline outcomes still appear in bounds and unknown counts; “known episodes” controls whether the observed baseline rate exists.

No Bayesian smoothing, learned embedding, hierarchical shrinkage, or cross-class imputation in v0. Those may be valuable later, but they create modeled evidence and must wear a different tier.

### 3.5 Evidence tier

CAR v0 should be labeled:

```text
DETERMINISTIC_DERIVED
METHODOLOGY_DEMONSTRATION
SEVEN_MATCH_CORPUS
NOT_PLAYER_EVALUATION
```

The replacement rate is a deterministic aggregate of observed/unknown typed episodes. It is not an external benchmark and not a validated player-quality model.

It may claim:

> In this seven-match corpus, under declared fragile-state and continuity definitions, this player accumulated X continuity outcomes above/below the leave-player-out corpus reference in comparable observed situations.

It must never claim ability, talent, value, decision quality, causal contribution, future performance, transferability, league rank, or literal replaceability.

## 4. Goodhart attack surface

| Attack | How CAR is gamed | Definitional counter |
|---|---|---|
| Frame farming | Count every pressure frame as an opportunity | One onset episode per continuous fragile spell |
| Detector flicker | Tiny pressure interruptions create new episodes | Entry dwell, gap tolerance, refractory period |
| Holding indefinitely | Player delays until horizon and avoids a loss | Timeout is UNKNOWN, not success |
| Safe backward-pass farming | Every immediate bailout earns success | v0 intentionally counts continuity, but baseline conditions on situation; publish reset vs progression labels separately |
| Hospital-pass externalization | Carrier gives a teammate an impossible ball yet receives success | Controlled successor required; uncontrolled transfer is not continuity |
| Receiver theft | Receiver saves a poor pass but onset carrier gets full causal credit | CAR claims attributed episode outcome, not causal merit; receiver credit prohibited in v0 and replay remains inspectable |
| Drawing pressure deliberately | Player seeks pressure to accumulate opportunities | CAR total plus CAR100 and exposure counts; no claim that opportunity creation is skill |
| Avoiding involvement | Player hides from difficult receptions, preserving efficiency | Headline CAR is a sum; efficiency never shown without opportunity count |
| Minutes farming | More minutes mechanically increase CAR | Intentional for contribution total; always accompany with episodes, minutes, and CAR100 |
| Garbage-time farming | Analyst includes low-stakes phases selectively | Corpus/phase eligibility fixed before computation; phase exclusions declared |
| Threshold shopping | Tune distance/horizon until a favored player rises | Versioned parameters; preregistered sensitivity grid; rankings never choose defaults |
| Class shopping | Add/remove conditioning dimensions for favorable baseline | Frozen class schema and deterministic coarsening order |
| Sparse-cell exploitation | Compare player against three weak observations | Minimum episodes, players, and matches; otherwise UNKNOWN |
| Self-baseline dilution | High-volume player enters their own comparator | Leave-player-out baseline |
| Team-quality leakage | Strong team raises/lowers player baseline | Do not call causal skill; publish team/match composition and leave-match-out sensitivity |
| Weak-opponent harvesting | Favorable schedule produces high CAR | Seven-match demonstration label; no generalization |
| Role mismatch | Centre-back and winger compared in unlike contexts | Situation conditioning, but no role inference; publish unresolved role/context limitation |
| UNKNOWN laundering | Drop uncertain failures | Full outcome bounds; unknown counts; no naked point estimate |
| Coverage targeting | Prefer players/matches with better tracking | Coverage manifest and per-player UNKNOWN share; minimum coverage gate |
| FAIL-as-zero | Missing field on excluded row depresses mean | FAIL excludes membership; never fabricates numeric zero |
| Negative-domain inversion | Analyst supplies convenient sum bounds | Typed field domains; internal exact bounds only |
| Outcome reordering | Ignore an early loss because a later regain occurs | First-terminal-event law |
| Restart laundering | Treat any stoppage as retention | Restart ownership must be certified |
| Opponent touch ambiguity | Call a deflection retained or lost opportunistically | Typed control/possession semantics; ambiguity is UNKNOWN |
| Double attribution | Credit passer and receiver for one episode | One onset carrier only in v0 |
| Team-to-player leakage | Allocate a team retention rate across players | Every CAR residual requires a unique onset-carrier episode |
| Off-ball narrative inflation | Credit support/run intent without proof | Off-ball actors evidence-only in v0 |
| Progression-value creep | Give more points to flashy progression | Binary retained/lost v0; progression merely labeled |
| Outcome leakage in classes | Baseline class uses post-outcome features | Class fields frozen at fragility onset |
| Identity leakage | Class includes player/team, making bespoke baselines | Player/team forbidden from situation-class keys |
| Survivorship bias | Only players with enough known results appear | Publish excluded-player ledger and reasons |
| Ranking without uncertainty | Sort by observed CAR alone | Rank only on declared rule, preferably lower bound; show interval overlap and prohibit ordinal claims where unresolved |
| Rounding manipulation | Close values appear decisively ordered | Compute full precision; display intervals and sample sizes |
| Retroactive exclusion | Remove “bad data” after seeing results | Exclusion reasons coverage-based and committed before player computation |
| Analyst multiplicity | Publish the best of many CAR variants | One ratified v0; sensitivity outputs labeled, never mixed |
| Primitive drift | Upstream detector changes without metric version change | Hash primitive versions, parameters, manifests, and plan into CAR version |
| Re-identification errors | Same person split/merged across IDs | Identity reconciliation gate; uncertain identity emits UNKNOWN/excluded |
| Cherry-picked clips | Show only successful moments | Every number decomposes to the complete eligible episode ledger |
| Causal language | “Player created +3 possessions” | Required wording: attributed observed residual, not causation |
| Replacement rhetoric | “Better than a real replacement player” | Always disclose corpus-reference construction and evidence tier |

One consequential limitation has no definitional cure: onset-carrier attribution can penalize players asked to receive structurally bad balls and reward those protected by team structure. Situation classing reduces that distortion but cannot erase it in seven matches. CAR v0 must expose rather than deny this.

## 5. Packet sequencing

One headline risk per packet:

1. **CAR-0a — Episode identity and attribution**  
   Build deduplicated fragile-carrier episode IDs, onset-carrier assignment, gap/refractory law, and ambiguity propagation. No continuity scoring.

2. **CAR-0b — Fragile-state predicate**  
   Certify the pressure/context eligibility predicate and its coverage behavior on all seven matches. No outcome or player aggregation.

3. **CAR-0c — Continuity resolver**  
   Implement first-terminal-event resolution, controlled transfer, stable reset, loss, restart ownership, horizon timeout, and UNKNOWN. No baseline.

4. **R2-1b — Numeric field domains**  
   Reinstate `sum` only, with negative-domain and UNKNOWN-membership fixtures. No mean.

5. **R2-1c — Exact bounded mean**  
   Add mandatory/optional-member optimization and undefined observed-mean behavior. CAR does not need this to proceed, so it must not share the sum packet.

6. **CAR-1 — Episode ledger over seven matches**  
   Produce the complete reproducible player-attributed episode ledger with outcome partitions, provenance hashes, and manual film audit sample. No replacement comparison.

7. **CAR-2a — Situation classifier**  
   Freeze onset-only class fields, bands, and deterministic coarsening. Publish population tables. No baseline rates.

8. **CAR-2b — Replacement baseline**  
   Construct leave-player-out class rates using R2-2’s joint-partition law. Enforce minimum population thresholds. No CAR sum.

9. **CAR-3 — CAR residual and player aggregation**  
   Derive interval-valued episode residuals and sum them with the field-domain operator. Emit CAR, CAR100, exposure, coverage, class composition, and excluded-player ledger.

10. **CAR-C — Adversarial corpus computation**  
    Byte-reproduce all seven matches; threshold sensitivity; leave-match-out sensitivity; manual replay audit; Goodhart tests; verify no team-level CAR artifact exists.

11. **CAR-4 — Inspectable product surface**  
    Only after methodology acceptance: every player number links to every eligible episode, including failures and UNKNOWNs.

The field-domain mechanism should not be folded into CAR-3. Doing so would repeat the exact one-packet/two-risks error that caused the R2-1 amputation.

## 6. Anti-goals

CAR v0 is not:

- a team metric, team table, or team strength estimate;
- a renamed fragile-retention rate;
- a possession-value, xG, threat, or progression model;
- a causal allocation of why possession survived;
- a measure of intent, bravery, technique, decision quality, or tactical obedience;
- split credit between carrier, passer, receiver, runner, and supporter;
- a role-adjusted or formation-adjusted model;
- a learned fragility score;
- an embedding-based similarity model;
- an imputed estimate presented as observation;
- a market definition of a replacement footballer;
- a league norm or population prior;
- a stable player rating from seven matches;
- a per-90 statistic masquerading as contribution;
- a leaderboard whose ordering exceeds interval evidence;
- a metric tuned to match scout opinions;
- a mechanism for silently excluding UNKNOWN;
- a reason to weaken coverage manifests or primitive claim boundaries;
- a reason to infer offside, intent, aerial control, or tactical role from insufficient evidence;
- a universal set of football thresholds;
- a substitute for replayable episode evidence.

The strongest discarded alternative is a player continuity-rate difference:

\[
\text{player rate}-\text{replacement rate}.
\]

It is simpler and more comparable across minutes, but it mistakes efficiency for accumulated contribution and invites low-involvement players to lead. It should survive only as the `CAR100` companion.

The principal owner fork for ADR 0019 is therefore crisp: whether the name CAR denotes the residual sum or the normalized residual rate. My recommendation is unambiguously the residual sum. The rate is valuable context; the sum is the faithful meaning of “Continuity Above Replacement.”