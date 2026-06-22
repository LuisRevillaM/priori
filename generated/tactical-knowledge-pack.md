# Tactical Knowledge Pack

Version: `m1.2-s2i-a.0`
SHA-256: `fa1e9f6987ae063500af95a31eaea506aa5c3a07e3ca5c4df18b639548399ded`
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

- `Makefile`: `e830f4424d13cfd97bc1281b467a1fe6526353dc978711b1a04d923ac4d3a876`
- `config/query-plans/ball_side_block_shift.ir.v1.json`: `877c185594e30442a745fe10e9b15fa3f5184ce28b1f8e5f2ca96d4a7439d945`
- `config/query-plans/opposite_corridor_after_shift.experimental.v1.json`: `9244603037c2db474bd766688a87ed7b72d5d8695953ec225a4a71f1b0206b74`
- `config/query-plans/possession_corridor_availability.experimental.v1.json`: `81ff93059b8b6bf5e0b5958610b2dc48a5814f0b7001f4bb4efc6956b2e94fde`
- `generated/capability-context.json`: `4816ffb893c34ddcd587192f5690f179d51ba46d09df6706a040b373f35950e8`
- `generated/tactical-query-plan.schema.json`: `2e012f1500b19c4159f69e937e604562b1374ff972780f2c7b0478c52d8c61db`
- `generated/tactical-query-plan.types.ts`: `58b25d3f41064565159dbcbcc52e8158217761cdb8b2c3ac142006d0fbf42d7f`
- `src/tqe/runtime/binder.py`: `a6d9ab90e0d7b6e7ffb0bb1e8b3ca355b59f528c2f444d6750c5ffec7a5f4459`
- `src/tqe/runtime/catalog.py`: `3ce519b65ecfa48c225c61897dfe9a921fba3892ac189326b77d902b4acc7d1b`
- `src/tqe/runtime/executor.py`: `39f581c9ba63f16dc081f9116a49dbb4acf606a1db6f7c153945bcb26aa62bf2`
- `src/tqe/runtime/ir.py`: `3fde1fe1e4fa61c596ab1579ecbd6c02df1fb63b503f13a6c146be206d642c3a`
- `src/tqe/runtime/relations.py`: `6408e3bb596ff3429091a0ab549bec8a73a1e999f6cfcc2aebd83cce26f862ee`
- `src/tqe/verification/m1_2_gate_s2i.py`: `00cf3e665ef2096c44a4d28ba37284bb9207ca5412e2e6c564ef0d8d3042c99f`
- `src/tqe/workshop/hermes_s2.py`: `ae2bb93b3444749d8fd131075e29404141e517820faf103fb58de2ebafcb1591`
- `src/tqe/workshop/knowledge_pack.py`: `d6329f79a5cc096616555c28baa205d97ec58702e78552460e1712e02dfb1143`
- `src/tqe/workshop/m1_2.py`: `481150ca1439006bc0c41b276aab62fa37960864e7d632cae660ff6f06c9c209`
