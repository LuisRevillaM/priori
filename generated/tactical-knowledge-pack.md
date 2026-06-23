# Tactical Knowledge Pack

Version: `m1.2-s2i-a.0`
SHA-256: `0ede7a0a508a16dc18bb24ad08f6e1a74c5a419326e300b392e3aaece9a9eeb7`
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

- `Makefile`: `d64815a3ddfc621ee0e5c615245c5af8401fb4ef1d54d548e63b2831bc79bf52`
- `config/query-plans/ball_side_block_shift.ir.v1.json`: `877c185594e30442a745fe10e9b15fa3f5184ce28b1f8e5f2ca96d4a7439d945`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`: `9244603037c2db474bd766688a87ed7b72d5d8695953ec225a4a71f1b0206b74`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`: `81ff93059b8b6bf5e0b5958610b2dc48a5814f0b7001f4bb4efc6956b2e94fde`
- `generated/capability-context.json`: `54629bad914fd3fa44df0d7195ba2d0a78c29824919c2de569b5204431eb4172`
- `generated/tactical-query-plan.schema.json`: `0e45cff180c3738629e9c49b15a7191faa12c1517ae987a91d2f80424df68b0f`
- `generated/tactical-query-plan.types.ts`: `838bc7a1db332eb24f6fd80faa1530c6cc441aba7eb91eb3e806fa8d23d0bffc`
- `src/tqe/runtime/binder.py`: `1fef904ec403cda0ad9c01cad3e743f2ad2284c7334c606831c4cece3a8da210`
- `src/tqe/runtime/catalog.py`: `5537e58df2822b7268452cd948e0c5230c5eb76950b9cec15c1ca3e1dc36c677`
- `src/tqe/runtime/executor.py`: `ccb1562340d83ecb16faa13a73cace47b7d89e725fc2a755c4f8c22d0245a253`
- `src/tqe/runtime/ir.py`: `28e5fa2d221bc8f9ec66620d7a8f47a346a002dda9f2e264873492862c39dd3a`
- `src/tqe/runtime/relations.py`: `6408e3bb596ff3429091a0ab549bec8a73a1e999f6cfcc2aebd83cce26f862ee`
- `src/tqe/verification/m1_2_gate_s2i.py`: `00cf3e665ef2096c44a4d28ba37284bb9207ca5412e2e6c564ef0d8d3042c99f`
- `src/tqe/workshop/hermes_s2.py`: `ae2bb93b3444749d8fd131075e29404141e517820faf103fb58de2ebafcb1591`
- `src/tqe/workshop/knowledge_pack.py`: `80f6388833a35eaa8ffa1e9570e2c78137d0c2d84771f1e9ad51e723207679d5`
- `src/tqe/workshop/m1_2.py`: `8c6857259244cb3951b8e28a1e38dc6fc8557db5938df7e61c35e05743176ebd`
