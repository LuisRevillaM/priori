# Tactical Knowledge Pack

Version: `m1.2-s2i-a.0`
SHA-256: `c152e0d09df79f02805851f67c1f0a752e072c42492ae7d0fa61572b4a192192`
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

- `Makefile`: `b1a90bd11e5048f9aa37ab1a3668a850ab99374c059cdff94d98340c478bcb1e`
- `config/query-plans/ball_side_block_shift.ir.v1.json`: `877c185594e30442a745fe10e9b15fa3f5184ce28b1f8e5f2ca96d4a7439d945`
- `config/query-plans/first_time_relay_after_receiver_line_transition.experimental.v1.json`: `af52f539c8ef40c08f7300bf4af895e1d087be4c0c138c229be36e1780e5620d`
- `config/query-plans/high_bypass_completed_pass.experimental.v1.json`: `38cf4c31bd388df98284d80384cfba600ec6aa90312ff530427d03a19d8e6c83`
- `config/query-plans/line_break_support_response.experimental.v1.json`: `8f9d6da096c55c5bea3461750eeca77d19f08d6b363920021f07fcb7a02510a5`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`: `9244603037c2db474bd766688a87ed7b72d5d8695953ec225a4a71f1b0206b74`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`: `81ff93059b8b6bf5e0b5958610b2dc48a5814f0b7001f4bb4efc6956b2e94fde`
- `generated/capability-context.json`: `5020ae139fb1f92c237c4be167410a7486395ea580622f747fedb9f9a90f40de`
- `generated/tactical-query-plan.schema.json`: `0e45cff180c3738629e9c49b15a7191faa12c1517ae987a91d2f80424df68b0f`
- `generated/tactical-query-plan.types.ts`: `838bc7a1db332eb24f6fd80faa1530c6cc441aba7eb91eb3e806fa8d23d0bffc`
- `src/tqe/runtime/binder.py`: `1fef904ec403cda0ad9c01cad3e743f2ad2284c7334c606831c4cece3a8da210`
- `src/tqe/runtime/catalog.py`: `0a9b31e196990e605f0bcd9ca3ae1f5c936d0890e04f36604ee92c77f476d526`
- `src/tqe/runtime/executor.py`: `c28418f068dc8b34d110edd79a17a1a1a77b5bb4ab9e8d85ed8a650328f055d7`
- `src/tqe/runtime/ir.py`: `28e5fa2d221bc8f9ec66620d7a8f47a346a002dda9f2e264873492862c39dd3a`
- `src/tqe/runtime/relations.py`: `6408e3bb596ff3429091a0ab549bec8a73a1e999f6cfcc2aebd83cce26f862ee`
- `src/tqe/verification/m1_2_gate_s2i.py`: `00cf3e665ef2096c44a4d28ba37284bb9207ca5412e2e6c564ef0d8d3042c99f`
- `src/tqe/workshop/hermes_s2.py`: `ae2bb93b3444749d8fd131075e29404141e517820faf103fb58de2ebafcb1591`
- `src/tqe/workshop/knowledge_pack.py`: `2878869bc4ea757f3704740e3212c7556bffa84c95a72797c3e5a581956ef6aa`
- `src/tqe/workshop/m1_2.py`: `67d2654a63d719a19f398f608a3723a30ee2b3c9a97b0c6a0d545ed768637ccf`
