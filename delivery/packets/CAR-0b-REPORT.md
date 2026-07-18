# CAR-0b — fragile-state predicate certification

Branch: `packet/car-0b`

Frontier: `4d46534bd3876e6ff3cf00b8be44d9881cb32148`

Executor clone: `/private/tmp/priori-car0b-executor`

Status: **DESIGN SEALED — IMPLEMENTATION IN PROGRESS**

## Design brief (authored before implementation)

### One-risk packet boundary

CAR-0b certifies one tri-state `fragile_state_eligibility@0.1.0`
predicate over the complete output of `fragile_carrier_episode@0.1.0`. It
answers only whether an episode onset is eligible for later CAR continuity
resolution. It does not resolve continuity, score an episode, construct a
replacement class, aggregate by player, or emit a player/team metric.

### Eligibility law

Eligibility is the conjunction of:

1. certified active perspective-team possession at onset;
2. certified unique individual carrier control and onset attribution;
3. `pressure_on_carrier@0.1.0` pressure PASS after its bound
   `minimum_pressure_duration_seconds`; and
4. certified observation coverage for the evidence required by those three
   clauses.

The pressure clause is consumed from the exact CAR-0a pressure-source
signature and parameter echo. CAR-0b introduces no distance, closing-speed,
approach-angle, count, or marking threshold. The plan identity binds the
certified pressure primitive version and its bound parameters. Entry dwell is
therefore `pressure_on_carrier.minimum_pressure_duration_seconds`, never a
CAR-local copy. The episode evidence carries CAR-0a's
`same_episode_gap_tolerance_s`; the predicate verifies and exposes it but does
not re-segment episodes.

Local numerical advantage/disadvantage, support arrival, touchline
confinement, escape-route geometry, lane occupancy, and reception-between-line
geometry are expressly **not** eligibility conjuncts. They are later
replacement-class conditioners. `team_press` actor counts and `marking`
evidence may be carried as witnesses where a composition already provides
them, but neither is mandatory and neither can turn pressure FAIL into PASS.

### Tri-state and coverage law

- PASS: every eligibility clause is certified PASS.
- FAIL: an eligibility clause is certified FAIL under its declared coverage.
- UNKNOWN: possession, carrier/control, pressure truth, required source
  signature, parameter echo, or observation coverage is absent, ambiguous, or
  uncertified.

GEO-0a governs negative evidence: pressure absence may testify as FAIL only
under certified player-track coverage. Uncertified absence is UNKNOWN. A
missing optional context witness never changes eligibility.

Reason codes are typed and deterministic, with coverage/ambiguity reasons
preceding certified negative reasons. The output preserves the episode ID,
onset carrier (or null), source pressure identity/hash, entry dwell, gap
tolerance, and evidence references.

### Runtime and composition model

The predicate is a small pure kernel plus a possession-family adapter. It
consumes episode records and emits a complete eligibility evaluation set plus
a tri-state signal. `fragile_carrier_episode@0.1.0` remains unchanged.

The certified composition uses existing controlled-carrier anchors, binds
`pressure_on_carrier@0.1.0`, feeds its complete evaluations to
`fragile_carrier_episode@0.1.0`, and then evaluates
`fragile_state_eligibility@0.1.0`. The producer executes both team
perspectives over all periods of all seven canonical matches and publishes one
row per match/team with eligible episodes, UNKNOWN share, and reason-code
counts. There is no outcome or player aggregation.

### Mutation standard

Named tests must kill at least these mutations:

- treating uncertified pressure absence as FAIL instead of UNKNOWN;
- making support/local-number/escape-route evidence mandatory;
- accepting a pressure PASS whose source entry-dwell echo is not satisfied;
- dropping ambiguous-attribution episodes instead of retaining UNKNOWN; and
- recomputing episode identity or gap grouping inside the predicate.

### STOP and census law

The new predicate is additive. Existing certified pressure implementations,
CAR-0a identity output, plans, tables, and frozen expectations are immutable.
Any existing certified value/status/evidence delta is a STOP. Generated
catalog/semantic artifacts and additive identities may move only with named
ratchet acknowledgment.

Expected census movements are declared before implementation:

- primitive vocabulary: 39 → 40 for `fragile_state_eligibility`;
- typed field references: add only the predicate's actually required frame,
  entity, provenance, and status references, acknowledged by kind;
- semantic registry concept/operationalization/implementation/binding/claim/
  evidence/exposure/maturity chains; and
- catalog/context, knowledge pack, registry lock, passport/projections,
  parity, and SCP-0 evidence.

