# Tactical Knowledge Pack

Version: `m1.2-s2i-a.0`
SHA-256: `536fbe4f0649eaa1557ae7638581e3fbb7eaa6d49710e3e31521df8d99c06d7a`
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

## Source Hashes

- `Makefile`: `4c251caaf2a4fa73fc002a9ed949b388e00ee61da978adee8577bd07d405b3aa`
- `config/query-plans/ball_side_block_shift.ir.v1.json`: `877c185594e30442a745fe10e9b15fa3f5184ce28b1f8e5f2ca96d4a7439d945`
- `config/query-plans/first_time_relay_after_receiver_line_transition.experimental.v1.json`: `af52f539c8ef40c08f7300bf4af895e1d087be4c0c138c229be36e1780e5620d`
- `config/query-plans/high_bypass_completed_pass.experimental.v1.json`: `38cf4c31bd388df98284d80384cfba600ec6aa90312ff530427d03a19d8e6c83`
- `config/query-plans/line_break_support_response.experimental.v1.json`: `8f9d6da096c55c5bea3461750eeca77d19f08d6b363920021f07fcb7a02510a5`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`: `9244603037c2db474bd766688a87ed7b72d5d8695953ec225a4a71f1b0206b74`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`: `81ff93059b8b6bf5e0b5958610b2dc48a5814f0b7001f4bb4efc6956b2e94fde`
- `generated/capability-context.json`: `b17ea9761a5a5d93655787a28a5a0351358778268417d1c5ffc5738078c28f08`
- `generated/tactical-query-plan.schema.json`: `7904105efeba7b8297ee3d3dbd183b92c6b8d67f5f034e34da8c52f42b0b54ae`
- `generated/tactical-query-plan.types.ts`: `5c027189c9b5f314bc62fd765656e30aeaebe163add038320f74cca932627ceb`
- `src/tqe/runtime/binder.py`: `19e85bbae959644dcb4295a420361d06f92355987ba7af62a2cc14ea51b5c8f6`
- `src/tqe/runtime/catalog.py`: `0f58e55acdd789f1f101b969a0255b864bdc333d6c4a8f596160c57e8b00590f`
- `src/tqe/runtime/executor.py`: `7a2cd8a4641f7d179111064dbafa17f83e1d8b44bcc330f1237a1a1e33b0814d`
- `src/tqe/runtime/ir.py`: `33e4885a6ad75afa7b4e9df96b72eba43c49b92b24ac67c8d2979d0bde13eedd`
- `src/tqe/runtime/relations.py`: `eb305cd2ff4c9c5f886342eeb8c35253500e6dd777bdf7b4dc403469b771d8e0`
- `src/tqe/verification/m1_2_gate_s2i.py`: `9397f1a8a6b11e28d1f0bb48105a44dfae9a2c49ca61ff44413108f1d85ce125`
- `src/tqe/workshop/hermes_s2.py`: `ae2bb93b3444749d8fd131075e29404141e517820faf103fb58de2ebafcb1591`
- `src/tqe/workshop/knowledge_pack.py`: `2878869bc4ea757f3704740e3212c7556bffa84c95a72797c3e5a581956ef6aa`
- `src/tqe/workshop/m1_2.py`: `481097c94dfe922a2e8e6322263e7124841c028601ae78d0608145acca65266c`
