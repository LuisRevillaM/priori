# Tactical Query Architecture And Standard Library

Date: 2026-06-23

Status: source-of-truth architecture brief for the current Workbench/Hermes demo path and the next football-knowledge expansion.

Current generated Tactical Knowledge Pack: `generated/tactical-knowledge-pack.json`

Current pack SHA-256 recorded in the pack: `2fc0ed6e97fd8e23d08b050e45e915ed327d38648cc1c15a56544291bb961115`

## Purpose

This document explains the architecture of the tactical query system in terms of the layers that sit above tracking data, the concepts Hermes can compile to, the deterministic runtime contracts that execute those concepts, and the next standard-library capabilities required to make the product feel like a football tactical language rather than a narrow set of demos.

The central principle is:

```text
We are not adding more canned queries first.
We are expanding the typed football vocabulary from which Hermes can construct queries.
```

Hermes should compile natural language into bounded typed plans. The deterministic host should measure those plans over canonical tracking data, emit evidence-backed moments, and provide replay for human inspection.

## Claim Boundary

The system can truthfully claim:

```text
It measures explicit spatial-temporal football definitions over real tracking data.
It can execute reviewed recipes.
It can execute one verified Hermes-authored experimental composition with deterministic provenance.
It can replay evidence-backed moments for human inspection.
```

The system must not claim:

```text
player intent
optimal decisions
pass probability
coaching causation
body orientation
scanning
video understanding
offside correctness
complete football ontology coverage
```

Those claims require data or models not currently in the system.

## Layer Model

The clean architecture is:

```text
L0  Raw source data
L1  Canonical match state
L2  Typed value model
L3  Measurements and compiler-lowering geometry
L4  Football relations and episodes
L5  Predicates, operators, and temporal logic
L6  Classification and result emission
L7  Evidence, trace, and replay
L8  Hermes and Workbench product surface
```

Hermes authors plans in the middle of the stack. It should normally work with reusable football concepts such as possession anchors, progressive corridors, destination entry, defensive lines, support arrival, and lane occupancy. It should not normally author raw coordinate math such as point-to-segment distance, vector projections, or pitch-normalization kernels. Those remain deterministic lowering details.

### L0 - Raw Source Data

Raw source data is the bottom of the stack:

```text
match tracking frames
player positions
ball positions
frame IDs
period IDs
match metadata
team metadata
player metadata
event/source annotations where available
```

Hermes does not receive raw match dumps. It receives bounded capability descriptions, schemas, recipes, and safe tools.

### L1 - Canonical Match State

Canonical match state normalizes raw data into host-owned runtime facts:

```text
canonical pitch coordinates
canonical frame timing
period-aware frame order
player and ball entity records
team role / perspective role
attacking direction
possession/source team state
deployed match manifest
```

This layer is deterministic infrastructure. It is not tactical interpretation yet.

### L2 - Typed Value Model

The runtime works with explicit tactical value types. These types are the contract between catalog nodes, predicates, result emission, inspection, and replay.

Important value types:

| Type | Meaning | Example |
| --- | --- | --- |
| `frame_signal` | A value indexed by frame. | ball lateral fraction, defensive centroid y |
| `episode_set` | A collection of time intervals. | possession segment, persistence interval |
| `anchor_set` | Tactical moments/windows around which later evaluation happens. | possession-start anchors |
| `relation_episode_set` | A collection of entity-to-entity relationships over time. | progressive ball-to-teammate corridor episodes |
| `anchor_evaluations` | Anchor-relative PASS/FAIL/UNKNOWN relation coverage. | whether an anchor has a qualifying corridor |
| `enum` | A closed set of named values. | `PASS`, `FAIL`, `UNKNOWN`, `PRESENT_AT_OPEN` |
| `number` | A numeric measurement with unit. | metres, seconds, count, fraction |
| `boolean` | A truth value, usually lifted into tri-state runtime semantics. | condition met |
| `entity_ref` | A player, team, ball, or relation reference. | target player ID, relation ID |

The most important semantic rule is:

```text
UNKNOWN is not FALSE.
```

Missing data, insufficient coverage, impossible frame alignment, or invalid evidence must produce explicit unknown/invalid state rather than silently becoming a non-match.

### L3 - Measurements And Compiler-Lowering Geometry

Measurements are deterministic computations over canonical match state. Some are football-aware enough for Hermes to compose directly. Others are lower-level geometry that should remain beneath the agent-visible vocabulary.

Current measurement-style catalog entries:

| Capability | Current role | Recommended visibility |
| --- | --- | --- |
| `possession_segment` | Builds possession episodes and possession anchors. | `AGENT_COMPOSABLE` |
| `ball_lateral_fraction` | Normalizes ball y position toward touchline. | `COMPILER_LOWERING` |
| `defensive_outfield_centroid` | Computes defending outfield centroid. | `COMPILER_LOWERING` |
| `signed_lateral_shift` | Measures/constructs ball-side block-shift detector stage. | `TRUSTED_RECIPE_ONLY` until dependencies are fully formalized |
| `outcome_classification` | M1-specific outcome classifier. | `TRUSTED_RECIPE_ONLY` |
| `relation_destination_entry` | Generic relation-destination ball-entry measurement. | `AGENT_COMPOSABLE` |
| `relation_destination_entry_classification` | Trusted wrapper around relation destination entry. | `TRUSTED_RECIPE_ONLY` |

The current system historically uses the word "primitive" for both small measurements and larger football-aware operations. That is acceptable for runtime naming, but the architecture should distinguish the layers:

```text
small measurement
football relation
temporal operator
trusted recipe wrapper
reviewed recipe
```

### L4 - Football Relations And Episodes

Relations describe relationships between entities over time. They are more tactically meaningful than scalar measurements.

Current relation capabilities:

| Capability | Purpose | Recommended visibility |
| --- | --- | --- |
| `geometric_progressive_corridor` | Finds a clear forward ball-to-teammate geometric corridor. | `AGENT_COMPOSABLE` |
| `geometric_progressive_corridor_from_anchor_set` | Same relation, but driven by explicit anchor sets. | `AGENT_COMPOSABLE` |

The corridor relation emits evidence such as:

```text
relation_id
open_frame_id
open_confirm_frame_id
close_frame_id
duration_seconds
target_player_id
destination_side
destination_lane
destination_region
destination_region_bounds
minimum_clearance_m
limiting_defender_id
source_open_point
target_open_point
source_close_point
target_close_point
```

This is already a real football relation, but its claim is deliberately narrow:

```text
It is a geometric progressive corridor.
It is not pass probability.
It is not the optimal pass.
It does not prove player intent.
It does not use receiver body orientation or offside.
```

### L5 - Predicates, Operators, And Temporal Logic

Operators turn measurements and relations into tactical truth conditions.

Current operators:

| Operator | Role |
| --- | --- |
| `gt` | numeric greater-than |
| `gte` | numeric greater-than-or-equal |
| `lte` | numeric less-than-or-equal |
| `eq` | typed equality |
| `neq` | typed inequality |
| `persists_for` | boolean frame signal must remain true for a minimum duration |
| `exists` | anchor has at least one qualifying anchor-relative episode/evaluation |
| `count_at_least` | anchor-relative collection count reaches a threshold |

Current safety rule:

```text
exists and count_at_least are safe for agent-visible use only where the input has anchor-relative semantics, such as anchor_evaluations.
```

`persists_for` must preserve tri-state semantics:

```text
TRUE TRUE UNKNOWN  -> UNKNOWN / indeterminate
TRUE TRUE FALSE    -> FAIL
no evaluated coverage -> UNKNOWN
```

This is what prevents missing tracking evidence from being treated as a tactical non-event.

### L6 - Classification And Result Emission

Classification rules decide which anchor moments become result rows.

A generic pattern looks like:

```text
anchor exists
predicate A == PASS
predicate B == PASS
unknown policy permits inclusion
→ emit QueryResult with label, rank, evidence, provenance, and trace
```

Example:

```text
possession anchor
→ progressive corridor relation exists
→ relation destination entry status == PASS
→ classify as DESTINATION_ENTERED
→ request evidence aliases
→ emit result
```

The result row must be deterministic:

```text
same plan
same scope
same runtime/data versions
same max_results
→ same result IDs and ordering
```

### L7 - Evidence, Trace, And Replay

Every accepted result should answer:

```text
why did this match?
what exact fields were measured?
which frames/entities/relations ground it?
what was unknown?
what can the user inspect visually?
```

Evidence aliases are the bridge between runtime records and Workbench display.

Examples:

```text
possession_start_frame_id
anchor_frame_id
relation_id
target_player_id
minimum_clearance_m
entry_status
entry_mode
time_to_entry_seconds
destination_region_bounds
```

Predicate traces expose:

```text
predicate ID
operator
input value
threshold
unit
status: PASS | FAIL | UNKNOWN
reason / why text
```

Replay is the human inspection surface. It must render only what evidence supports. If exact geometry is absent, the UI must hide the overlay or label it as witness-only rather than infer a stronger visual.

### L8 - Hermes And Workbench Product Surface

Hermes is a bounded tactical compiler client. It receives:

```text
safe capability catalog
tool schemas
approved and experimental recipes
authoring contracts
claim boundaries
complexity limits
```

Hermes does not receive:

```text
raw tracking dumps
arbitrary Python
SQL
filesystem access
terminal access
host confirmation authority
execution authority without user confirmation
primitive mutation authority
```

The Workbench provides:

```text
Ask Hermes
Browse recipes
interpreted plan display
host confirmation
deterministic execution
result rail
trace inspection
coordinate replay
developer details
```

The product must distinguish provenance explicitly:

```text
REVIEWED_RECIPE
MANUAL_PRESET
HERMES_RECIPE_SELECTION
HERMES_NOVEL_COMPOSITION
DETERMINISTIC_REPAIR
CAPABILITY_GAP
MODEL_UNAVAILABLE
```

No plan should appear AI-authored if it was a preset, reviewed recipe, deterministic fallback, or manually selected plan.

## What Hermes Actually Compiles To

Hermes compiles natural language into a typed query plan graph. It does not compile to Python, SQL, or runtime code.

The normal flow is:

```text
user natural-language request
→ Hermes inspects safe capability context
→ Hermes either:
    selects a reviewed recipe
    drafts an experimental typed plan
    asks for clarification
    reports a capability gap
→ host validates and binds the plan
→ user confirms execution
→ deterministic runtime executes
→ Workbench displays results, evidence, trace, and replay
```

The plan graph can contain:

```text
scope
parameters
primitive nodes
relation nodes
input mappings
predicate nodes
operators
classification rules
requested evidence aliases
unknown-evidence policy
max result limits
```

Hermes can compose from registered capabilities only. If the concept cannot be represented using the visible catalog and safe operators, Hermes should say capability gap rather than inventing a hidden primitive.

## Recipes / Detectors

A recipe or detector is a saved plan graph. It is not the primitive layer.

Current tracked recipes:

| Recipe | Status | Meaning |
| --- | --- | --- |
| `ball_side_block_shift_v1` | approved/reviewed | Defending block shifts toward ball side under frozen M1 semantics. |
| `possession_corridor_availability_v1` | experimental | Possession anchors with a progressive geometric corridor. |
| `opposite_corridor_after_shift_v1` | experimental | Block shift plus opposite-side corridor and destination-entry analysis. |

The architecture goal is not to keep adding one-off recipes. The goal is to add reusable football vocabulary so Hermes can author new recipes safely.

## Visibility Tiers

Every capability should be assigned one of these tiers:

| Tier | Meaning | Example |
| --- | --- | --- |
| `COMPILER_LOWERING` | Deterministic geometry/math or source facts. Normally not user-facing. | point-to-segment distance, raw lateral fraction |
| `AGENT_COMPOSABLE` | Reusable football measurement or relation Hermes may compose. | possession anchors, progressive corridor, destination entry |
| `TRUSTED_RECIPE_ONLY` | Bundled logic with recipe-specific assumptions. | M1 outcome classification |
| `USER_TACTICAL` | Reviewed named tactical recipe/concept. | Ball-Side Block Shift |

The tiering prevents Hermes from treating an opaque recipe macro as a universal primitive.

## Current Capability Posture

### Strong Foundation

The system already has:

```text
canonical tracking pipeline
typed query plans
deterministic binder
generic executor
anchors
relations
predicate traces
PASS / FAIL / UNKNOWN
evidence aliases
non-match inspection
replay windows
safe Hermes/MCP boundary
host confirmation
cloud Workbench
verified Hermes novel-composition proof
```

### Current Narrowness

The current football vocabulary is still concentrated around:

```text
possession anchors
ball-side block movement
geometric progressive corridors
relation destination entry
```

That is enough to prove the architecture. It is not enough to feel like a broad tactical language.

## Standard Library Expansion

The next work should add the Line-Break Support package:

```text
defensive_line_model
relative_position_to_defensive_line
controlled_line_break_episode
lane_occupancy
support_arrival_relation
local_number_relation
```

These capabilities are deliberately orthogonal. Together, they support a second tactical family:

```text
Line-Break Support Response

controlled line break
→ attackers beyond line
→ support arrives within N seconds
→ distinct lanes occupied
→ local numerical context
→ evidence-backed result and replay
```

This is the right next proof because it moves beyond the current corridor/block-shift center of gravity.

## Capability Contract Template

Every new capability must define:

```yaml
id:
version:
visibility_tier:
layer:
purpose:
inputs:
parameters:
outputs:
units:
entity_scope:
temporal_semantics:
unknown_behavior:
evidence_fields:
visual_evidence_contract:
complexity_limits:
limitations:
prohibited_claims:
positive_tests:
negative_tests:
unknown_tests:
real_data_fixture:
first_consumer:
```

Acceptance rule:

```text
If deterministic validation accepts a plan as executable,
execution must not later fail because of missing runtime globals,
undeclared parameters, unsupported output domains, or hidden node assumptions.
```

## Proposed Capability: defensive_line_model

```yaml
id: defensive_line_model
version: 0.1.0
visibility_tier: COMPILER_LOWERING
layer: L2
purpose: Build a deterministic defensive-line reference from defending outfield players.
```

### Why It Exists

Line-break concepts need a reference line. Without a deterministic defensive line, "break the line" becomes subjective.

### Inputs

```text
canonical player coordinates
team role / defending team
attacking direction
outfield-player selector
line-selection policy
frame or anchor window
```

### Parameters

```text
line_type: back_line | second_line
minimum_defenders: count
maximum_line_depth_spread_m: metre
lookback_window_seconds: second
lookahead_window_seconds: second
```

### Outputs

```text
line_x_m
line_type
defender_ids_used
line_quality_status: PASS | FAIL | UNKNOWN
line_depth_spread_m
source_frame_id
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
attacking direction is unavailable
defending team is unavailable
too few eligible outfield defenders exist
defender positions are missing
line spread exceeds declared quality policy
```

### Visual Evidence

```text
line overlay
source defender markers
line quality/status
```

### Limitations

```text
Does not infer tactical intent.
Does not know coaching line designation.
Does not prove offside line correctness.
```

## Proposed Capability: relative_position_to_defensive_line

```yaml
id: relative_position_to_defensive_line
version: 0.1.0
visibility_tier: AGENT_COMPOSABLE
layer: L2
purpose: Measure whether an entity is in front of, on, or beyond a defensive line.
```

### Inputs

```text
defensive_line_model.line_x_m
entity position: player | ball | relation target
attacking direction
frame or anchor window
```

### Parameters

```text
line_buffer_m: metre
entity_selector: ball | player | receiver | relation_target
```

### Outputs

```text
relative_x_m
side_of_line: IN_FRONT | ON_LINE | BEYOND | UNKNOWN
line_x_m
entity_id
frame_id
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
line model is UNKNOWN
entity position is missing
attacking direction is missing
frame alignment fails
```

### Visual Evidence

```text
defensive line overlay
entity marker
relative distance label
```

### Limitations

```text
Does not establish whether the player should receive.
Does not establish offside.
Does not establish tactical intent.
```

## Proposed Capability: controlled_line_break_episode

```yaml
id: controlled_line_break_episode
version: 0.1.0
visibility_tier: AGENT_COMPOSABLE
layer: L3
purpose: Create anchor episodes where the ball or active attacking entity crosses from in front of a defensive line to beyond it under measurable control conditions.
```

### Inputs

```text
possession_segment.episodes
defensive_line_model
relative_position_to_defensive_line
canonical ball/player coordinates
team role / possession team
```

### Parameters

```text
line_type: back_line | second_line
crossing_entity: ball | ball_carrier | receiver
minimum_before_seconds: second
minimum_after_seconds: second
control_policy: active_ball_team | possession_state
maximum_break_window_seconds: second
```

### Outputs

```text
line_break_episodes: episode_set<anchor_ref>
break_frame_id
breaking_entity_id
crossed_line_type
pre_relative_x_m
post_relative_x_m
control_status
line_x_m
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
possession/control cannot be established
line model is UNKNOWN
before/after windows are incomplete
entity tracking is missing
crossing cannot be temporally ordered
```

### Visual Evidence

```text
before/after defensive line
breaking entity trail
break frame marker
control status
```

### Limitations

```text
Controlled means measurable possession/active-ball state, not subjective quality.
Does not infer intent.
Does not classify pass quality.
Does not prove offside legality.
```

## Proposed Capability: lane_occupancy

```yaml
id: lane_occupancy
version: 0.1.0
visibility_tier: AGENT_COMPOSABLE
layer: L2
purpose: Measure which pitch lanes are occupied by selected entities during an anchor-relative window.
```

### Inputs

```text
canonical player coordinates
team role
anchor_set or episode_set
pitch orientation
```

### Parameters

```text
lane_model: five_vertical_lanes | thirds | custom_bands
team_role: attacking | defending
entity_filter: outfield | attackers_beyond_line | support_candidates
window_start_offset_seconds: second
window_end_offset_seconds: second
minimum_presence_seconds: second
```

### Outputs

```text
occupied_lanes: entity_set or enum collection
lane_count
lane_ids
player_ids_by_lane
occupancy_status: PASS | FAIL | UNKNOWN
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
orientation is unavailable
player positions are missing in the required window
lane model cannot be projected
window coverage is incomplete
```

### Visual Evidence

```text
lane bands overlay
occupied lanes highlighted
players contributing to occupancy
time window label
```

### Limitations

```text
Lane occupation does not establish availability to receive.
Lane occupation does not establish optimal spacing.
```

## Proposed Capability: support_arrival_relation

```yaml
id: support_arrival_relation
version: 0.1.0
visibility_tier: AGENT_COMPOSABLE
layer: L3
purpose: Detect teammates arriving into a support region within a declared time window after an anchor.
```

### Inputs

```text
anchor_set: line break anchors or possession anchors
canonical player coordinates
attacking team entity set
reference entity: ball carrier | receiver | relation target
optional lane_occupancy
```

### Parameters

```text
maximum_arrival_seconds: second
support_radius_m: metre
minimum_support_duration_seconds: second
support_region: radius | lane | behind_line_zone | relation_destination_region
minimum_arrivals: count
exclude_anchor_entity: boolean
```

### Outputs

```text
support_relation_episodes: relation_episode_set
arrival_status: PASS | FAIL | UNKNOWN
arriving_player_ids
arrival_frame_id
arrival_delay_seconds
support_distance_m
support_lane
duration_seconds
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
anchor coverage is incomplete
reference entity is missing
candidate teammate positions are missing
arrival window is partially unevaluated and could change the answer
```

### Visual Evidence

```text
anchor frame
reference entity marker
support region overlay
arriving player trail
arrival frame marker
arrival delay label
```

### Limitations

```text
Does not prove the player intended to support.
Does not prove the support was useful or optimal.
Does not infer passing availability unless combined with corridor or lane capabilities.
```

## Proposed Capability: local_number_relation

```yaml
id: local_number_relation
version: 0.1.0
visibility_tier: AGENT_COMPOSABLE
layer: L3
purpose: Count attackers and defenders inside a declared local region around an anchor or entity.
```

### Inputs

```text
anchor_set
canonical player coordinates
team role
region selector
optional reference entity
```

### Parameters

```text
region_type: radius | lane_band | rectangle | relation_destination_region
radius_m: metre
window_start_offset_seconds: second
window_end_offset_seconds: second
minimum_presence_seconds: second
minimum_attacker_advantage: count
```

### Outputs

```text
attacker_count
defender_count
local_difference
attacker_ids
defender_ids
local_number_status: PASS | FAIL | UNKNOWN
region_bounds
```

### Unknown Behavior

Return `UNKNOWN` when:

```text
region cannot be constructed
team role is unavailable
player positions are missing
window coverage is incomplete and could change the count
```

### Visual Evidence

```text
region overlay
included attackers and defenders
count labels
time-window label
```

### Limitations

```text
Numerical advantage does not prove tactical superiority.
Does not measure pressure unless combined with a pressure capability.
```

## First New Tactical Family: Line-Break Support Response

After the standard-library capabilities exist, the first consumer should be a tactical family:

```text
Line-Break Support Response
```

Definition sketch:

```text
controlled_line_break_episode == PASS
AND receiver/ball is beyond selected defensive line
AND support_arrival_relation within N seconds
AND lane_occupancy satisfies lane-diversity rule
OPTIONALLY local_number_relation reaches threshold
→ emit support-response moment
```

Example user questions this family should support:

```text
Show controlled line breaks where support arrived within three seconds.
Find line breaks where the receiver was isolated afterward.
Show second-line breaks followed by two support arrivals in different lanes.
Find moments where we broke the line but had no nearby supporting runner.
Show line breaks that created a local attacking overload.
```

Workbench explanation target:

```text
USER ASKED
"Show line breaks where the receiver was left unsupported."

INTERPRETED TACTICALLY
Controlled second-line break
+ receiver beyond the line
+ fewer than two support arrivals within three seconds
+ limited lane occupation nearby

MEASURED AS
Line broken at 42:18
Receiver beyond line: 4.6m
Support arrivals within 3s: 1
Occupied support lanes: 1
Local numbers: 2 attackers vs 4 defenders
```

## Standard-Library Acceptance Gates

Each new capability must pass:

```text
contract completeness
positive tests
negative tests
UNKNOWN tests
real canonical-data proof
determinism proof
Hermes visibility proof
Workbench evidence/replay proof
no forbidden claim proof
```

For each capability, acceptance requires:

```text
1. The catalog declares every required input, parameter, output, unit, allowed enum value, and evidence field.
2. The binder rejects impossible input/output combinations before execution.
3. The executor consumes only declared inputs and host-owned globals.
4. PASS, FAIL, and UNKNOWN behavior is explicitly tested.
5. Missing evidence cannot silently become FAIL.
6. Result evidence aliases resolve to the same source relation/anchor used for classification.
7. Replay overlays render only exact evidence geometry.
8. Hermes can describe the capability through the safe tool surface.
9. Hermes can use AGENT_COMPOSABLE capabilities without raw data or code access.
10. The Workbench explains limitations and does not overclaim.
```

## Recommended Implementation Order

Do not start with a polished recipe. Build the vocabulary bottom-up:

```text
1. defensive_line_model
   - compiler-lowering only
   - visual debug overlays
   - positive/negative/UNKNOWN tests

2. relative_position_to_defensive_line
   - agent-composable
   - proves line-relative entity measurement

3. controlled_line_break_episode
   - anchor-producing tactical capability
   - first line-break event surface

4. lane_occupancy
   - reusable spatial context
   - needed for support/spacing questions

5. support_arrival_relation
   - anchor-relative relation after line break
   - supports "left unsupported" and "runner arrived" questions

6. local_number_relation
   - optional but high-value
   - supports overload/rest-defence framing

7. Line-Break Support Response
   - first reviewed/experimental consumer of the new package

8. Hermes novel composition rerun
   - ask Hermes to compose a new question from the expanded library
   - no prompt/code tuning after question freeze
```

## What Not To Do

Do not:

```text
add a broad football ontology before the second tactical family
add more one-off recipes without reusable capabilities
expose trusted wrappers as generic Hermes primitives
let Hermes mutate primitive definitions
claim intent, optimality, or probability
infer overlays from missing evidence
turn UNKNOWN into FAIL
use UI labels to hide provenance
```

## Practical Mental Model

The tactical system should feel like this:

```text
Data gives us coordinates over time.
The runtime turns coordinates into typed football facts.
Hermes combines visible football facts into a typed plan.
The host validates and executes the plan deterministically.
The Workbench shows the exact measured moment and why it matched.
The replay lets a human decide whether the measured concept is tactically useful.
```

That is the architecture. The next frontier is not a new runtime. It is a richer, carefully tiered tactical standard library.
