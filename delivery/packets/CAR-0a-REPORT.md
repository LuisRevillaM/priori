# CAR-0a — episode identity and attribution

Branch: `packet/car-0a`

Frontier: `174ac4fcaeee99ba79ce75932fc1fd11883ed8a4`

Executor clone: `/private/tmp/priori-car0a-executor.of6VJh` (outside the
repository tree)

Status: **DESIGN SEALED — IMPLEMENTATION PENDING**

## Design brief (authored before implementation)

### Packet boundary

CAR-0a introduces one deterministic primitive,
`fragile_carrier_episode@0.1.0`, whose only job is to turn a dense ordered
stream of already-qualified pressure observations into stable, deduplicated
episode identities and one frozen onset attribution per episode. It does not
decide the CAR-0b context-eligibility predicate, resolve CAR-0c continuity,
label success or failure, construct a situation class, calculate a baseline,
emit a residual, or aggregate by player or team.

The primitive's permitted claim is limited to: under one declared pressure
source, possession identity, gap law, and refractory law, these observations
belong to one fragile spell and this unique player was (or was not) certified
as its onset carrier. It never claims causal responsibility, ability, decision
quality, pressure quality, or possession value.

### Input contract and certified pressure reuse

The primitive consumes `pressure_evaluations`, an anchor-record collection
produced from a dense same-possession anchor stream by the certified
`pressure_on_carrier` relation. A composition may carry the certified
`team_press` record on the same anchor for pressure-actor IDs/counts, but CAR-0a
does not turn that evidence into a second pressure detector.

Every observation used to open or extend an episode must expose:

- `match_id`, `period`, `team_role`, frame ID, and match time;
- a certified active `possession_id` and `possession_status=PASS`;
- `pressure_status`, `pressure_reason`, `coverage_status`, and source anchor;
- the upstream `pressure_on_carrier` parameter echo, including
  `minimum_pressure_duration_seconds` and `pressure_duration_seconds`;
- individual-control status and the candidate carrier identity set; and
- optional identity-only boundary evidence and optional carried `team_press`
  witnesses.

Pressure qualification is reused, never recreated. `pressure_status=PASS` is
the truth gate. The primitive verifies that the same record's certified
`pressure_duration_seconds` meets that record's bound
`minimum_pressure_duration_seconds`; there is no CAR-local entry-dwell
parameter. It copies, hashes, and exposes the upstream pressure parameters and
primitive identity. It has no distance, closing-speed, approach-angle,
pressure-count, marking-distance, confinement, or lookback threshold. Thus the
deleted-parameters ruling is structural: no parallel knob exists to tune.

`team_press_status`, `pressure_actor_count`, actor IDs, and marking evidence are
pass-through witnesses only in CAR-0a. CAR-0b will own the declared fragility
composition and seven-match coverage gate.

### Stable episode identity

The identity preimage is versioned and carrier-independent:

```text
definition_version
pressure_source_signature_hash
match_id
period
perspective_team_role
possession_id
onset_frame_id
onset_match_time_ms
```

`pressure_source_signature_hash` is derived from the exact certified
`pressure_on_carrier` version and its parameter echo, not from CAR-local copies.
The emitted `fragile_carrier_episode_id` is a deterministic hash of that
preimage. It deliberately excludes carrier identity, outcome, later receiver,
team result, baseline, and aggregation state. Reordering identical input rows,
duplicating frames, or reconciling an ambiguous carrier later cannot mint a
second identity or rewrite the spell's identity.

Observations are canonicalized by match, period, team, possession, match time,
frame, and source-anchor identity. Exact duplicates collapse. Conflicting rows
at the same logical observation remain visible as ambiguity evidence; they are
never resolved by input order.

### Entry, gap, boundary, refractory, and re-arm laws

An episode opens on the first canonical observation for which active
possession is certified and reused pressure is eligible after the upstream
entry dwell. Every later pressure frame in that unresolved episode is evidence
for the same episode. It cannot create an episode per frame.

`same_episode_gap_tolerance_s=0.40` is CAR-owned. A run of explicit pressure
`FAIL` or `UNKNOWN` observations no longer than that tolerance between eligible
pressure observations is recorded as a bridged gap and remains in the same
spell. `UNKNOWN` never proves pressure release. A longer gap does not itself
score or resolve continuity; it only establishes a possible pressure release
for re-arming after an independently supplied identity boundary.

CAR-0a recognizes a boundary marker only as an identity boundary. It records
the first marker and its evidence, without mapping it to continuity PASS, FAIL,
or UNKNOWN. The continuity meaning of terminal event, stable reset, horizon,
evidence loss, restart, or possession discontinuity belongs to CAR-0c.

`refractory_after_resolution_s=1.00` is CAR-owned. After a boundary, no new
episode can open until both conditions hold:

1. the full refractory time has elapsed; and
2. a certified pressure-`FAIL` release longer than the gap tolerance has been
   observed, or a new certified possession identity begins.

Pressure that remains continuously PASS across a boundary never re-arms merely
because the clock advanced. A PASS inside refractory is recorded as suppressed
re-entry evidence. These two conditions jointly block frame farming, brief
detector flicker, and one-spell repeated-credit attacks.

### Onset attribution and ambiguity propagation

Attribution is frozen from the complete logical onset observation, not from a
later carrier. `onset_carrier_id` is emitted only when individual-control
status is certified and the canonical candidate set contains exactly one ID.
Missing, conflicting, or multiple candidates produce:

```text
onset_carrier_id = null
attribution_status = UNKNOWN
attribution_reason = <typed reason>
```

The episode remains in `episodes` with its stable ID, onset evidence, and full
candidate set. It is not silently dropped. Later carriers and repeated pressure
records are emitted as `reentry_carrier_ids` or evidence-only identities and
cannot replace the onset attribution. No receiver, passer, off-ball actor, or
team receives a second attribution.

### Output contract

Each episode record will include at least:

- stable episode ID, definition hash/version, and pressure-source signature;
- match, period, team role, possession ID, onset frame/time, current identity
  end frame/time, and boundary/open state;
- `onset_carrier_id`, attribution status/reason, onset candidate IDs, control
  status, and re-entry carrier IDs;
- pressure status/reason/coverage, upstream parameter echo, source anchor IDs,
  pressure actor evidence where carried, and evidence hashes;
- bridged-gap intervals, refractory-suppressed frames, deduplicated source-row
  counts, and ambiguity witnesses; and
- explicit `continuity_status=NOT_EVALUATED` to prevent consumers from treating
  identity completion as a continuity result.

The runtime output is an episode set plus an attribution-status frame signal.
There is no score, baseline, residual, rate, sum, mean, ranking, or player/team
aggregate output.

### Runtime and semantic integration inventory

Implementation will be isolated in a new pure kernel and a possession-family
adapter. Existing pressure geometry in
`src/tqe/runtime/capabilities/teamshape_family.py` remains byte-untouched.
Catalog dispatch gains only the new primitive. GEO-0b typed references will be
used for the onset frame, carrier ID, possession provenance, pressure status,
control status, and boundary status fields rather than adding literal enums.

The semantic registry will add the full concept → operationalization →
implementation → runtime binding → claim → evidence → exposure → maturity
chain. Its dependencies name `pressure_on_carrier@0.1.0` and
`team_press@0.1.0`; claim and evidence contracts explicitly prohibit parallel
pressure geometry and continuity/metric claims. Generated catalog, context,
knowledge-pack, SCP-0, passport, parity, and registry-lock artifacts will be
producer-generated, never hand-edited.

### Mutation standard and Goodhart attacks

Named tests will cover:

- one episode for hundreds of repeated PASS frames (frame-farming attack);
- one episode across a sub-tolerance FAIL/UNKNOWN flicker;
- no re-arm from UNKNOWN absence;
- no re-arm before refractory expiry;
- no re-arm while pressure remains continuously PASS;
- a second episode only after certified release plus refractory;
- upstream entry-dwell enforcement without a CAR-local dwell parameter;
- duplicate-row/order invariance of episode IDs;
- ambiguous/multiple onset carriers retained with attribution UNKNOWN;
- later carrier and receiver non-attribution;
- possession separation and first identity-boundary selection; and
- catalog/registry absence of the five deleted CAR pressure knobs.

At least two live mutations are mandatory. Removing deduplication must make the
frame-farming oracle fail. Weakening the gap/refractory re-arm conjunction must
make the flicker/refractory oracle fail. Each mutation is restored, the named
oracle passes, and a source diff proves no mutation remains.

### Certified-result STOP law

CAR-0a is additive and does not modify certified pressure implementations or
existing plans. Nevertheless, its catalog and semantic additions can move
global identity hashes. An untouched `174ac4fc` control and the implementation
tree will freshly execute the certified surfaces that bind pressure machinery:

- Q6 throw-in first action under pressure (`pressure_on_carrier`);
- Q2 carry breaks pressure and layoff (`pressure_on_carrier`);
- R1-5 fragile-possession state and its certified R2-1/R2-2 descendants; and
- the standalone certified `team_press` verifier.

Values, status populations, classifications, evidence rows, and committed
certified table bytes are the STOP domain. Identity-only movement caused by the
additive catalog/registry contract will be disclosed. If any existing certified
tactical value changes, implementation stops and reports the exact delta; no
oracle, frozen expectation, dev set, plan, or certified table is rewritten to
make the delta disappear.
