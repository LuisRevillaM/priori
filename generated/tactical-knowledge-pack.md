# Tactical Knowledge Pack

Version: `m1.2-s2i-a.0`
SHA-256: `b8d8425d92a46573d0a4779552af99f6da9dfcb5154c89c83006e90211f31f7a`
Generated: `reproducible_from_source_hashes`

## Architecture

Hermes/frontier model authors or selects typed tactical plans; deterministic host validates, confirms, executes, and serves replay.

MCP role: Thin Hermes adapter over the host-owned application service; not a runtime, database, or permission layer.
Initial MCP transport: `local stdio`

## S2I Hermes MCP Tool Allowlist

- `list_capabilities`
- `search_recipes`
- `describe_capability`
- `submit_query_plan`
- `validate_query_plan`
- `inspect_result`
- `inspect_non_match`
- `retrieve_replay_window`

Host-only tools:

- `host_confirm_bound_plan`
- `execute_query_plan`
- `record_feedback`
- `compare_query_versions`
- `save_experimental_recipe`

## Recipes

### Ball-Side Block Shift (`ball_side_block_shift_v1`)

State: `APPROVED`

Find possessions where the ball enters a wide channel and the defending outfield block shifts toward that side under the frozen M1 semantics.

Allowed claims:

- The ball entered a configured wide area.
- The defending outfield centroid shifted toward the ball side by the configured threshold.
- The subsequent outcome was SWITCHED, RETAINED_NO_SWITCH, LOST_BEFORE_SWITCH, or excluded STOPPAGE under the frozen predicates.
- The replay coordinates come from canonical 25 Hz source frames.

Disallowed claims:

- The attack intentionally caused the shift.
- A switch was always available.
- Not switching was a mistake.
- The moment proves an optimal decision or missed opportunity.
- The result is backed by licensed match video.

### Possession Corridor Availability (`possession_corridor_availability_v1`)

State: `EXPERIMENTAL`

Experimental composition that starts from ordinary possession anchors and detects whether a geometric progressive corridor appears without using the M1 wide-entry block-shift spine.

Allowed claims:

- The team had an active-ball possession anchor.
- A geometric progressive corridor appeared under the configured relation thresholds.
- The replay coordinates come from canonical 25 Hz source frames.

Disallowed claims:

- The attack intentionally created the corridor.
- A pass should have been played.
- The corridor is optimal.
- The result is a pass probability, decision-quality, causation, player-intent, or missed-opportunity claim.
- The result is backed by licensed match video.

### Opposite Corridor After Shift (`opposite_corridor_after_shift_v1`)

State: `EXPERIMENTAL`

Experimental composition that finds wide-entry block shifts, evaluates opposite-side geometric progressive corridors, and classifies whether the ball enters the corridor destination region.

Allowed claims:

- The ball entered a configured wide area.
- The defending outfield centroid shifted toward the ball side by the configured threshold.
- A geometric progressive corridor appeared on the opposite side under the configured relation thresholds.
- The ball either entered or did not enter the selected corridor destination region within the configured horizon.
- The replay coordinates come from canonical 25 Hz source frames.

Disallowed claims:

- The attack intentionally created the corridor.
- A pass should have been played.
- The corridor is optimal.
- The result is a pass probability, decision-quality, causation, player-intent, or missed-opportunity claim.
- The result is backed by licensed match video.

### High-Bypass Completed Pass (`high_bypass_completed_pass_v1`)

State: `EXPERIMENTAL`

Experimental composition that finds completed controlled passes where the ball progresses forward and at least a declared number of opposition outfield players move from goal-side of the ball at release to behind the ball at controlled reception.

Allowed claims:

- The event data identified a completed pass candidate.
- Tracking data confirmed physical release and controlled reception.
- The measured action bypassed the declared number of opposition outfield players.
- The replay coordinates come from canonical source frames.

Disallowed claims:

- The pass was optimal.
- The pass probability was high.
- The passer intended to break a defensive line.
- The pass alone caused every opponent to be bypassed.
- The result proves which defensive line was broken.
- The result is backed by licensed match video.

### Line-Break Support Response (`line_break_support_response_v1`)

State: `EXPERIMENTAL`

Experimental capstone composition that finds observed controlled-pass crossings of a supplied geometric defensive line and evaluates the declared support-arrival, lane-occupancy, and local-number context around the controlled reception.

Allowed claims:

- A controlled pass crossed a supplied observed geometric defensive line under declared thresholds.
- Observed teammates satisfied the declared support-arrival relation around the controlled reception.
- Observed attacking players occupied at least the declared number of lateral lanes.
- Observed local player counts satisfied the declared numeric relation.
- The replay coordinates come from canonical tracking frames.

Disallowed claims:

- The system identified a first, second, midfield, or back defensive line.
- The pass caused the line break or support response.
- The pass, support run, or resulting decision was optimal.
- The measured support was the right tactical option.
- The system inferred player intent, communication, scanning, or pressure.
- The result is a pass probability or video-backed claim.

### First-Time Relay After Receiver Line Transition (`first_time_relay_after_receiver_line_transition_v1`)

State: `EXPERIMENTAL`

Experimental composition that finds event-linked first-time relays where the receiver/relay player moves beyond a supplied observed line during the input pass leg and the onward pass has a terminal controlled reception.

Allowed claims:

- The relay was event-linked and tracking-bounded under declared thresholds.
- The receiver/relay player transitioned from not beyond to beyond a supplied observed line.
- The onward pass reached a terminal controlled reception.
- Replay/evidence comes from canonical event and tracking records.

Disallowed claims:

- The pass or ball itself crossed the line.
- The system identified a tactical defensive-line role or definitive line break.
- The sequence was a planned third-man combination.
- The players intended the measured outcome.
- The decision was optimal or has an inferred completion probability.

## Ambiguity Dimensions

- `SUPPORT_DEFINITION`: Clarify what support means: corridor, nearby teammate, receiving option, lane occupation, or another definition.
- `TIME_WINDOW`: Clarify when support must arrive relative to possession, carry, pass, or line break.
- `DISTANCE_THRESHOLD`: Clarify proximity language with an explicit distance threshold.

## Capability Gap Codes

- `PRIMITIVE_MUTATION`: Request would alter primitive or relation definitions.
- `CONFIRMATION_BYPASS`: Request bypasses host-owned confirmation.
- `DIRECT_EXECUTION`: Request asks the agent to execute directly.
- `PLAYER_INTENT`: Tracking data cannot prove player intent.
- `BODY_ORIENTATION`: No body-orientation primitive is available.
- `SCANNING`: No head-check or scanning primitive is available.
- `PASS_PROBABILITY`: Pass-probability modelling is not available.
- `OPTIMALITY`: Optimal decision claims are out of scope.
- `COMMUNICATION`: Communication is not represented in tracking data.
- `VIDEO`: Video is outside the current data boundary.
- `BODY_SHAPE`: No body-shape primitive is available.
- `DECEPTION`: Deception is not observable in current deterministic vocabulary.
- `COACH_INSTRUCTIONS`: Coach instruction evidence is unavailable.
- `FACIAL_CUES`: Facial cues are unavailable without video/perception.

## Composition Grammar

Composition operators: `8`
- `project_onto_axis@0.1.0`: Project a source point-pair vector onto a declared axis, producing witnessed signed scalar and angle channels.
- `delta_across_anchor@0.1.0`: Compare declared before/after scalar values for the same anchor, emitting witnessed signed delta and rising/falling edge statuses.
- `extremum_over_set@0.1.0`: Select witnessed argmin/argmax/top-k elements from declared per-anchor candidate records under explicit coverage and tie-break rules.
- `window@0.1.0`: Emit witnessed bounded temporal windows around anchors, including trace-back windows bounded by declared continuity evidence.
- `typed_join@0.1.0`: Join two declared evidence channels on explicit identity keys under bind-time composition constraints.
- `aggregate_over@0.1.0`: Aggregate a declared anchor-level evidence population into interval-typed group results with UNKNOWN rows carried into bounds.
- `rate@0.1.0`: Compute interval-typed count rates from a joint numerator/denominator tri-state partition under a declared subset law.
- `sequence_pattern@0.1.0`: Build tri-state ordered anchor chains across declared stage outputs, preserving UNKNOWN when successor windows are unobserved or only UNKNOWN candidates match.

Composition constraint kinds:

- `aggregate_over`
- `before_after_same_anchor`
- `delta_across_anchor`
- `distinct_entity_fields`
- `extremum_over_set`
- `frame_alignment`
- `rate`
- `relation_on_anchor`
- `same_anchor_identity`
- `same_player_return`
- `sequence_pattern`
- `temporal_order`
- `typed_join`
- `vector_projection`
- `window`

## Source Hashes

- `Makefile`: `7f5eaa0883aba521eab5d07afb8d4b8136b8ccf5e6e10c04afe79913977eb010`
- `config/query-plans/ball_side_block_shift.ir.v1.json`: `877c185594e30442a745fe10e9b15fa3f5184ce28b1f8e5f2ca96d4a7439d945`
- `config/query-plans/first_time_relay_after_receiver_line_transition.experimental.v1.json`: `af52f539c8ef40c08f7300bf4af895e1d087be4c0c138c229be36e1780e5620d`
- `config/query-plans/high_bypass_completed_pass.experimental.v1.json`: `38cf4c31bd388df98284d80384cfba600ec6aa90312ff530427d03a19d8e6c83`
- `config/query-plans/line_break_support_response.experimental.v1.json`: `8f9d6da096c55c5bea3461750eeca77d19f08d6b363920021f07fcb7a02510a5`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`: `9244603037c2db474bd766688a87ed7b72d5d8695953ec225a4a71f1b0206b74`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`: `81ff93059b8b6bf5e0b5958610b2dc48a5814f0b7001f4bb4efc6956b2e94fde`
- `generated/capability-context.json`: `4dec071034bf8a3db63ace5b627e7157eed0b9ac3a6cad43e195167b65651026`
- `generated/tactical-query-plan.schema.json`: `73289de85bf8cb486ea27c166c8039f0cb002c6bd5a234f77631370e97941c5d`
- `generated/tactical-query-plan.types.ts`: `b674c5091ce001e04f393defba6bed2f9ec9b93ec660bc679b7aa73b6d955223`
- `src/tqe/runtime/binder.py`: `74326af6f81bc72028da0a3fd829891a6a2bc7d393804f71ef08e29cb289f1e9`
- `src/tqe/runtime/catalog.py`: `b79a84bf09fbe4ebde10ef6f3ffb3de837b3e33ed96387eb6d0ebd7aca202ea9`
- `src/tqe/runtime/executor.py`: `2299bd238aaef5889a8a330a3a81b7b7e58877b3063f6ac1eb100421bfc3bbad`
- `src/tqe/runtime/ir.py`: `43507b1929ec3bee528b5dfff851d73ed73aad12e1a4e2dfe8223f50b1ca1c55`
- `src/tqe/runtime/operators/__init__.py`: `20c6e5cfe7f575d3846a1511cbc610192881a8bc2845d4c5a85b79789a6e4fd3`
- `src/tqe/runtime/operators/aggregate_over.py`: `1f883d7035795e97ad4ff12a78ce13deda417c857fc18244758e095608aa1b64`
- `src/tqe/runtime/operators/delta_across_anchor.py`: `acd81710c06856c71aac2ac41e68a7e07d17262a69f597a92696a0721f77b806`
- `src/tqe/runtime/operators/extremum_over_set.py`: `e9bf407db795f44600ffe65f6c0333a3cdaae3b8b234206e1157eed533eb15e3`
- `src/tqe/runtime/operators/project_onto_axis.py`: `65159a823e7573cc19fd3728f425680a8cc80349e1bc8e790db890b589ecd9d0`
- `src/tqe/runtime/operators/rate.py`: `b91e0475374e7b7295cdc511e545f7e21bbad28e9c5e08efff6470a6c8027d7c`
- `src/tqe/runtime/operators/sequence_pattern.py`: `34e9df3a816ab4b8949f4eaba3da5cd8d76505cf0782daea04f11f9445ad1246`
- `src/tqe/runtime/operators/typed_join.py`: `a8fcd01ce6d39273da4e2bff4c3d6c206619a7c1da669c78d08bf88850209174`
- `src/tqe/runtime/operators/window.py`: `c7247d0fb72c8c0c1705b75d71ced179d7c814c3c2aee93a2dbd9948c773188e`
- `src/tqe/runtime/relations.py`: `eb305cd2ff4c9c5f886342eeb8c35253500e6dd777bdf7b4dc403469b771d8e0`
- `src/tqe/verification/m1_2_gate_s2i.py`: `9397f1a8a6b11e28d1f0bb48105a44dfae9a2c49ca61ff44413108f1d85ce125`
- `src/tqe/workshop/hermes_s2.py`: `ae2bb93b3444749d8fd131075e29404141e517820faf103fb58de2ebafcb1591`
- `src/tqe/workshop/knowledge_pack.py`: `ff3ee2e2780e4535e40bad327fce72d98a6c0b25194de8287337e52b3d8d919a`
- `src/tqe/workshop/m1_2.py`: `223dffe0621a14b666c6396b0f5db5ace9b7048e0019112236bc3913cd5aafe9`
