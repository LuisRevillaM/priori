# M2A Spec - High-Bypass Completed Pass

Date: 2026-06-23

Status: implementation-ready handoff spec

Primary source of truth: `docs/TACTICAL_QUERY_ARCHITECTURE_AND_STANDARD_LIBRARY.md`

## Controller Goal

```text
/goal Build the High-Bypass Completed Pass tactical family so a user can find and replay completed passes where the receiving action leaves at least five opposition outfield players behind the ball. Done when the deterministic runtime can derive controlled pass episodes from synchronized event and tracking data, compute opponents bypassed with attacking-direction-normalized coordinates, emit evidence-backed QueryResult rows for the high-bypass recipe, render an exact replay overlay for human review, expose the safe capabilities in the generated knowledge pack, and pass the M2A verification suite plus a human-review packet. Scope excludes defensive-line modelling, support-arrival logic, lane occupancy, pass probability, optimality, intent, body orientation, and broad UI redesign; stop if event-to-tracking player/frame alignment cannot be proven on real canonical data or if implementation requires a broad IR redesign.
```

## Product Outcome

M2A adds the first concrete football-knowledge expansion after Beta 1C:

```text
synchronized event + tracking data
-> controlled_pass_episode
-> opponents_bypassed_by_action
-> high_bypass_completed_pass_v1
-> evidence and replay
```

The user-facing claim is:

```text
Show completed passes that bypass at least five opposition outfield players.
```

Do not call this a "line break" in the product or catalog yet. Bypassing opponents is related to line breaking, but it does not prove which defensive line was crossed until the defensive-line model exists.

## Current Data Contracts

Use the canonical data already in `data/canonical/v1`.

Required files:

```text
matches.parquet
players.parquet
active player timeline or trusted lineup/substitution source
orientation.parquet
frames/match_id=<match_id>/period=<period>.parquet
positions/match_id=<match_id>/period=<period>.parquet
events/match_id=<match_id>.parquet
```

Observed relevant columns:

```text
frames:
  match_id
  period
  frame_id
  timestamp_utc
  analysis_rate_hz

positions:
  match_id
  period
  frame_id
  timestamp_utc
  team_id
  team_role
  entity_id
  entity_type
  x_m
  y_m

orientation:
  match_id
  period
  team_id
  team_role
  attack_x_sign

players:
  match_id
  team_id
  team_role
  player_id
  playing_position
  is_goalkeeper

active player timeline:
  match_id
  period
  team_id
  team_role
  player_id
  active_from_frame_id
  active_to_frame_id
  active_from_timestamp_utc
  active_to_timestamp_utc

events:
  match_id
  period
  team_role
  row_index
  event_type
  gameclock_seconds
  timestamp
  team_id
  player_id
  at_x
  at_y
  to_x
  to_y
  qualifier_json
```

`events.qualifier_json` contains pass metadata such as `Evaluation`, `Recipient`, `Player`, and `Team`. Use events to identify candidate passes and named players. Use tracking data to prove physical release and controlled-reception endpoints. Do not treat event `to_x/to_y` as a controlled reception frame without tracking confirmation.

Use `events.timestamp` as the primary event-to-tracking alignment source. `gameclock_seconds` is retained for reporting and fallback only. Do not compute event time as `first_frame.timestamp_utc + gameclock_seconds` unless a preflight proves that convention is aligned for the match/period; first tracking frame is not guaranteed to be exact game-clock zero.

M2A must distinguish:

```text
registered squad
active on-pitch players
observed tracked players
```

Do not use the full `players.parquet` roster as the expected opposition denominator. Substitutes and off-pitch players must not become missing tracking evidence. The expected denominator is the trusted active on-pitch opposition outfield set at the release and reception frames. If an active-player timeline does not already exist, M2A-S0 must build and prove one from trusted lineup/substitution/event/tracking evidence before S1 implementation.

## Definitions

### Attacking-Direction-Normalized X

For a team in a match period:

```text
attack_x_m = x_m * attack_x_sign
```

where `attack_x_sign` comes from `orientation.parquet` for the event team. A larger `attack_x_m` means closer to the opposition goal for that team. If orientation is missing or contradictory, the affected action is `UNKNOWN`.

### Goal-Side Of The Ball

At a frame, an opponent is goal-side of the ball for the attacking team when:

```text
opponent_attack_x_m > ball_attack_x_m + goal_side_buffer_m
```

Default `goal_side_buffer_m = 1.0`.

### Behind The Ball

At a frame, an opponent is behind the ball for the attacking team when:

```text
opponent_attack_x_m < ball_attack_x_m - bypassed_buffer_m
```

Default `bypassed_buffer_m = 1.0`.

The buffer prevents frame noise from turning level players into bypassed players.

### Opponent Bypassed By Action

An opponent is bypassed by a controlled pass if:

```text
opponent is goal-side of the ball at release
AND
opponent is behind the ball at controlled reception
```

Exclude goalkeepers in M2A. If goalkeeper identity is missing for either team, the action is `UNKNOWN`, not a reduced count.

## Architecture Principle

Capabilities measure reusable football facts. Recipes apply tactical thresholds and labels.

M2A must therefore keep this separation:

```text
controlled_pass_episode measures:
  controlled_pass_status
  release_control_status
  controlled_reception_status
  possession_continuity_status
  forward_progression_m
  coverage_status

opponents_bypassed_by_action measures:
  opponents_bypassed_count
  bypassed_player_ids
  evaluation_coverage_status

high_bypass_completed_pass_v1 applies:
  controlled_pass_status == PASS
  forward_progression_m >= 8m
  opponents_bypassed_count >= 5
```

Implementation may use host-owned pruning limits for performance, but returned measurements must not be defined by recipe thresholds.

### High-Bypass Completed Pass

The initial tactical family is:

```text
controlled_pass_episode.anchor_evaluations.controlled_pass_status == PASS
AND forward_progression_m >= 8.0
AND opponents_bypassed_count >= 5
-> HIGH_BYPASS_COMPLETED_PASS
```

"More than four opponents" must be interpreted as `>= 5`. The Workbench interpretation should expose that conversion.

## Capability 1 - `controlled_pass_episode`

Visibility after accepted M2A proof: `AGENT_COMPOSABLE`

Recommended initial catalog kind: `primitive`

Recommended output shape:

```text
controlled_pass_episode.episodes
  temporal_type: episode_set
  payload_schema: ControlledPassEpisode
  cardinality: collection
  entity_scope: possession
  missing_data_semantics: unknown

controlled_pass_episode.anchors
  temporal_type: anchor_set or episode_set with anchor_ref payload
  payload_schema: AnchorRef
  cardinality: collection
  entity_scope: anchor
  missing_data_semantics: unknown

controlled_pass_episode.anchor_evaluations
  temporal_type: anchor_evaluations or episode_set with anchor-relative semantics
  payload_schema: ControlledPassEvaluation
  cardinality: collection
  entity_scope: anchor
  missing_data_semantics: unknown
```

Do not add a new IR temporal container for M2A unless the existing typed containers cannot honestly represent the required records. It is acceptable to implement named payload schemas on top of the current containers, but the catalog must not declare a boolean payload while hiding rich records in sidecars. Each episode record must contain an explicit `pass_episode_id` so downstream predicates and evidence can correlate by action identity, not by frame only.

Generic predicates and result emission must use the `anchors`/anchor-relative outputs, not raw pass episode records. Raw episode records may exist as runtime payload for inspection/evidence, but they must not be the direct source of `exists` or `count_at_least`.

`ControlledPassEpisode` is the rich evidence/replay record. `ControlledPassEvaluation` is the predicate-facing anchor-relative record. Generic predicates must consume declared fields from `controlled_pass_episode.anchor_evaluations`, not fields hidden inside episode sidecars.

`ControlledPassEvaluation` must declare:

```text
anchor_id
pass_episode_id
controlled_pass_status        # PASS | FAIL | UNKNOWN
release_control_status        # PASS | UNKNOWN
controlled_reception_status   # PASS | UNKNOWN
possession_continuity_status  # PASS | FAIL | UNKNOWN
forward_progression_m
coverage_status               # PASS | UNKNOWN
unknown_reason
```

### Inputs

This primitive has no plan-node inputs in M2A. It reads host-owned canonical event/tracking state from the runtime `PeriodState`, scoped by the bound invocation.

Every host-context dependency must be declared in the catalog/binder contract so validation knows what execution will need:

```text
events parquet
frame timestamp index
player identity mapping
active-player timeline
positions
orientation
possession state
analysis cadence
maximum frame-gap policy
event/tracking alignment policy version
reception-search stop policy version
```

If the binder accepts `controlled_pass_episode`, execution must not later fail because any of those host resources are unavailable.

### Parameters

```text
event_type_filter: enum list by implementation contract
  default: ["Play_Pass"]
  allowed initially: successfully completed Play_Pass events only

completed_evaluation_value: enum
  default: "successfullyCompleted"

max_release_alignment_ms: number millisecond
  default: 250
  minimum: 0
  maximum: 1000

max_reception_search_seconds: number second
  default: 4.0
  minimum: 0.2
  maximum: 10.0

max_reception_ball_distance_m: number metre
  default: 2.5
  minimum: 0.1
  maximum: 8.0

receiver_nearest_margin_m: number metre
  default: 1.0
  minimum: 0.0
  maximum: 5.0

max_release_ball_distance_m: number metre
  default: 2.5
  minimum: 0.1
  maximum: 8.0

passer_nearest_margin_m: number metre
  default: 1.0
  minimum: 0.0
  maximum: 5.0

minimum_control_dwell_seconds: number second
  default: 0.24
  minimum: 0.04
  maximum: 1.0
```

If the current catalog parameter model does not support enum lists, use an enum parameter for `pass_family` with allowed value `completed_play_pass` and keep the exact event-type set host-owned.

### Candidate Event Selection

For each selected match/period/perspective team:

1. Read events for the match.
2. Keep rows where `event_type == "Play_Pass"`.
3. Keep rows where `team_id` matches the attacking/perspective team for the current invocation.
4. Parse `qualifier_json`.
5. Keep rows where `Evaluation == "successfullyCompleted"`.
6. Resolve `passer_id = events.player_id`.
7. Resolve `receiver_id = qualifier_json["Recipient"]`.
8. Reject or mark `UNKNOWN` when passer or receiver cannot be mapped to a tracked player in `players.parquet`.

M2A's initial pass family is successfully completed `Play_Pass` events. Do not describe this as "open play" unless M2A-S0 proves that `Play_Pass` plus the source qualifiers reliably excludes restarts/set pieces. Set pieces can be added later through a formal host-owned pass-family mapping.

### Controlled Pass Status Semantics

Use `PASS`, `FAIL`, and `UNKNOWN` distinctly:

```text
PASS
  Release and controlled reception are positively established for the named passer/receiver inside the same possession.

FAIL
  Sufficient evidence contradicts the candidate:
  wrong receiver controls first,
  another attacking player clearly controls the ball first,
  an opponent clearly controls the ball first,
  possession definitively breaks,
  ball out/stoppage occurs before controlled reception,
  or event completion conflicts with tracking.

UNKNOWN
  Missing frames, unresolved player identity, excessive frame gaps,
  unbounded event/tracking alignment, incomplete possession evidence,
  or incomplete active-player evidence prevents a definitive decision.
```

Non-match inspection should preserve these distinctions; do not collapse all non-PASS paths into UNKNOWN.

### Release Frame Alignment

Find the canonical tracking frame nearest the event's `timestamp` in the same match/period.

Preferred implementation:

```text
event_timestamp = events.timestamp converted to UTC
release_frame = nearest frame timestamp_utc to event_timestamp
```

If existing runtime utilities already define event timestamp to frame alignment, reuse those. Do not add a second incompatible timing convention.

Fallback implementation, allowed only when `events.timestamp` is missing:

```text
period_start_timestamp = first frames.timestamp_utc for period
event_timestamp = period_start_timestamp + gameclock_seconds
release_frame = nearest frame timestamp_utc to event_timestamp
```

The fallback must be reported in M2A-S0 with measured alignment error. It must not silently become the default.

If absolute time delta is greater than `max_release_alignment_ms`, emit a controlled pass record with:

```text
controlled_pass_status = UNKNOWN
unknown_reason = "release_frame_alignment_failed"
```

and do not use it as a positive result.

### Pass Release Confirmation

Release must be physically confirmed from tracking, parallel to controlled reception. At the aligned release frame, all are required:

```text
passer position exists
ball position exists
distance(ball, passer) <= max_release_ball_distance_m
passer is the nearest attacking player to the ball, or tied within passer_nearest_margin_m
event-to-frame offset is within max_release_alignment_ms
```

If release confirmation fails, emit:

```text
controlled_pass_status = UNKNOWN
release_control_status = UNKNOWN
unknown_reason = "release_control_not_confirmed"
```

M2A-S0 should compare event `at_x/at_y` and `to_x/to_y` to tracking endpoints as QA evidence where a coordinate conversion is available. Event coordinates are not authoritative geometry for result/replay.

### Controlled Reception Frame

The event timestamp alone is not the controlled reception. Search forward from the release frame for at most `max_reception_search_seconds`.

The controlled reception frame is the first frame where all are true:

```text
receiver position exists
ball position exists
distance(ball, receiver) <= max_reception_ball_distance_m
receiver is the nearest teammate to the ball, or tied within receiver_nearest_margin_m
receiver remains nearest/within-threshold for at least minimum_control_dwell_seconds
same-team possession continuity has not broken
the next compatible event, where available, does not contradict the same receiver
```

`minimum_control_dwell_seconds` must be evaluated using canonical frame timestamps and interrupted by excessive frame gaps. Do not assume `sample_count / nominal_hz` when observed gaps exist.

The controlled pass episode should record:

```text
control_window_start_frame_id
control_window_end_frame_id
control_window_start_timestamp_utc
control_window_end_timestamp_utc
observed_control_duration_seconds
maximum_observed_gap_ms
```

Possession continuity can initially use the runtime's existing ball possession/team role state if available. If reliable possession continuity is unavailable for a frame window, the action is `UNKNOWN`.

M2A-S0 must report false-positive risk for this controlled-reception heuristic. If visual spot checks show that ball-near-receiver does not reliably indicate controlled reception, stop and tighten the reception definition before implementing S1.

The reception search must stop at the earliest of:

```text
max_reception_search_seconds
possession loss
ball out or stoppage
next incompatible on-ball event
another attacking player clearly controlling the ball first
opposition player clearly controlling the ball first
active-player membership change inside the pass window
```

If another player controls the ball before the named recipient, emit:

```text
controlled_pass_status = FAIL
unknown_reason = "receiver_not_first_controller"
```

If active-player membership changes between release and reception because of substitution, dismissal, or an unresolved active-player timeline transition, emit:

```text
controlled_pass_status = UNKNOWN
coverage_status = UNKNOWN
unknown_reason = "active_player_set_changed_during_pass"
```

If no reception frame is found, emit:

```text
controlled_pass_status = UNKNOWN
unknown_reason = "controlled_reception_not_found"
```

Do not convert missing reception evidence into `FAIL`.

### Forward Progression

Compute:

```text
forward_progression_m =
  reception_ball_attack_x_m - release_ball_attack_x_m
```

If ball coordinates are missing at either endpoint, status is `UNKNOWN`.

### Output Record Fields

Each controlled pass episode must include:

```text
pass_episode_id
match_id
period
team_id
team_role
event_row_index
event_type
event_gameclock_seconds
passer_id
receiver_id
release_frame_id
reception_frame_id
release_match_time_ms
reception_match_time_ms
anchor_id
anchor_frame_id
coverage_status               # PASS | UNKNOWN
release_control_status       # PASS | UNKNOWN
controlled_reception_status  # PASS | UNKNOWN
control_window_start_frame_id
control_window_end_frame_id
control_window_start_timestamp_utc
control_window_end_timestamp_utc
observed_control_duration_seconds
maximum_observed_gap_ms
release_ball_point
reception_ball_point
release_passer_point
reception_receiver_point
forward_progression_m
controlled_pass_status        # PASS | FAIL | UNKNOWN
possession_continuity_status  # PASS | FAIL | UNKNOWN
unknown_reason
```

M2A may omit `FAIL` controlled passes from positive result candidates, but must retain enough non-match inspection data to explain known timestamps and near misses.

## Capability 2 - `opponents_bypassed_by_action`

Visibility after accepted M2A proof: `AGENT_COMPOSABLE`

Recommended initial catalog kind: `primitive` unless relation plumbing fits better.

Recommended output shape:

```text
opponents_bypassed_by_action.anchor_evaluations
  temporal_type: anchor_evaluations or episode_set with anchor-relative semantics
  payload_schema: BypassedOpponentsEvaluation
  cardinality: collection
  entity_scope: anchor
  missing_data_semantics: unknown
```

Each record is keyed by both `anchor_id` and `pass_episode_id`. The payload measures count and coverage. It must not mean "five or more opponents bypassed"; the recipe owns that threshold.

Do not expose a raw `episode_set` fallback to Hermes for `exists` or `count_at_least`. M2A must stay anchor-relative to preserve the safety discipline established in M1.2/S7R2.

### Inputs

```text
controlled_passes:
  source: controlled_pass_episode.episodes
  required: true

anchors:
  source: controlled_pass_episode.anchors
  required: true
```

### Parameters

```text
goal_side_buffer_m: number metre
  default: 1.0
  minimum: 0.0
  maximum: 5.0

bypassed_buffer_m: number metre
  default: 1.0
  minimum: 0.0
  maximum: 5.0

exclude_goalkeepers: enum
  default: "true"
  allowed_values: ["true"]
```

Keep `exclude_goalkeepers` fixed to `true` for M2A. Do not expose a public toggle until goalkeeper handling has separate tests.

### Evaluation Algorithm

For each `controlled_pass_episode`:

1. If `controlled_pass_status != PASS`, emit `evaluation_coverage_status = UNKNOWN` and preserve the controlled-pass status in trace:
   - `UNKNOWN` stays `UNKNOWN`.
   - known failed continuity/reception does not produce a bypass count.
2. Load all opposition outfield player positions at `release_frame_id` and `reception_frame_id`.
3. Load ball positions at `release_frame_id` and `reception_frame_id`.
4. Normalize x coordinates with the attacking team's `attack_x_sign`.
5. Build `expected_active_opposition_outfield_ids` from the trusted active-player timeline at both release and reception, excluding goalkeepers.
6. Build `evaluated_opponent_ids` from players with valid positions at both release and reception.
7. Build `candidate_goal_side_ids`:
   ```text
   opponent_release_attack_x > release_ball_attack_x + goal_side_buffer_m
   ```
8. Build `bypassed_player_ids` from those candidates:
   ```text
   opponent_reception_attack_x < reception_ball_attack_x - bypassed_buffer_m
   ```
9. Exclude goalkeepers using `players.is_goalkeeper`.
10. Set:
   ```text
   opponents_bypassed_count = len(bypassed_player_ids)
   evaluation_coverage_status = PASS if the active opposition endpoint set is complete, otherwise UNKNOWN
   ```

If substitution, dismissal, or active-player membership changes inside the pass episode window, set `evaluation_coverage_status = UNKNOWN` for M2A. Do not choose release set, reception set, union, or intersection silently.

Missing evidence rule:

```text
If any expected active opposition outfield player is missing at release or reception, coverage is `UNKNOWN`. Threshold predicates may still prove PASS when the measured bypassed count already satisfies the recipe threshold, but non-passing threshold results with incomplete coverage must remain UNKNOWN rather than FAIL.
```

That means:

```text
measured count >= recipe threshold -> threshold predicate PASS
measured count < threshold and coverage UNKNOWN -> threshold predicate UNKNOWN
measured count < threshold and coverage PASS -> threshold predicate FAIL
```

Semantic limitation:

```text
The metric counts opponents whose ball-relative position changed across the completed action.
It does not attribute each change solely to the pass; opponents also move during the action.
```

The product label "High-Bypass Completed Pass" remains valid. Do not claim "the pass alone bypassed every highlighted opponent" or "the pass caused each opponent to be bypassed."

### Output Record Fields

Each evaluation record must include:

```text
pass_episode_id
anchor_id
anchor_frame_id
match_id
period
team_id
team_role
release_frame_id
reception_frame_id
passer_id
receiver_id
release_ball_point
reception_ball_point
forward_progression_m
goal_side_buffer_m
bypassed_buffer_m
expected_active_opposition_outfield_ids
evaluated_opponent_ids
missing_active_opponent_ids
candidate_goal_side_player_ids
bypassed_player_ids
opponents_bypassed_count
excluded_goalkeeper_ids
evaluation_coverage_status    # PASS | UNKNOWN
unknown_reason
```

Ordering must be deterministic:

```text
match_id, period, release_frame_id, reception_frame_id, pass_episode_id
```

Player ID lists must be sorted.

## Recipe - `high_bypass_completed_pass_v1`

State during implementation: `EXPERIMENTAL`

Recommended recipe document path:

```text
config/query-plans/high_bypass_completed_pass.experimental.v1.json
```

Add this path to every existing recipe registry used by the Workbench and knowledge-pack generation, including `RECIPE_PLAN_PATHS` in `src/tqe/workshop/knowledge_pack.py` and `src/tqe/workshop/m1_2.py`.

### Recipe Parameters

```text
minimum_forward_progression_m:
  default: 8.0
  unit: metre

minimum_bypassed_opponents:
  default: 5
  unit: count

goal_side_buffer_m:
  default: 1.0
  unit: metre

bypassed_buffer_m:
  default: 1.0
  unit: metre

max_reception_search_seconds:
  default: 4.0
  unit: second
```

### Plan Graph

The recipe graph should compile to:

```text
node: controlled_pass_episode
  parameters:
    pass_family = completed_play_pass
    max_reception_search_seconds = $max_reception_search_seconds

node: opponents_bypassed_by_action
  input:
    controlled_passes = controlled_pass_episode.episodes
    anchors = controlled_pass_episode.anchors
  parameters:
    goal_side_buffer_m = $goal_side_buffer_m
    bypassed_buffer_m = $bypassed_buffer_m

predicates:
  - source = controlled_pass_episode.anchor_evaluations.controlled_pass_status
    operator = eq PASS over anchor-relative evaluation status
  - source = controlled_pass_episode.anchor_evaluations.forward_progression_m
    operator = gte $minimum_forward_progression_m
  - source = opponents_bypassed_by_action.opponents_bypassed_count
    operator = gte $minimum_bypassed_opponents
    unknown_source = opponents_bypassed_by_action.evaluation_coverage_status

classification:
  label = HIGH_BYPASS_COMPLETED_PASS
  include_when = all predicates PASS
  unknown_policy = exclude candidate, preserve trace
```

Create deterministic action anchors from `pass_episode_id`:

```text
anchor_id = stable_hash(match_id, period, pass_episode_id, release_frame_id, reception_frame_id)
anchor_frame_id = reception_frame_id
start_frame_id = release_frame_id
end_frame_id = reception_frame_id
```

Do not generate IDs from node names, output list indexes, or result ordering.

The accepted implementation must prove that clearing raw pass episodes from sidecar/provenance does not change anchor discovery or result identity. Anchors are first-class runtime outputs, not inferred side effects.

### Required Evidence Aliases

Results must request and resolve:

```text
pass_episode_id
anchor_id
event_row_index
passer_id
receiver_id
release_frame_id
reception_frame_id
release_match_time_ms
reception_match_time_ms
controlled_pass_status
release_control_status
controlled_reception_status
possession_continuity_status
coverage_status
release_ball_point
reception_ball_point
release_passer_point
reception_receiver_point
forward_progression_m
opponents_bypassed_count
bypassed_player_ids
candidate_goal_side_player_ids
expected_active_opposition_outfield_ids
evaluated_opponent_ids
missing_active_opponent_ids
goal_side_buffer_m
bypassed_buffer_m
evaluation_coverage_status
unknown_reason
```

`requested_evidence_failure_count` must be zero for accepted positive results.

## Knowledge Pack And Hermes Contract

Expose these to the generated knowledge pack in phases:

```text
controlled_pass_episode
opponents_bypassed_by_action
high_bypass_completed_pass_v1
```

Visibility:

```text
controlled_pass_episode              AGENT_COMPOSABLE
opponents_bypassed_by_action         AGENT_COMPOSABLE
high_bypass_completed_pass_v1        USER_TACTICAL / EXPERIMENTAL
```

During M2A-S1 through M2A-S3, the new capabilities may appear in internal generated catalogs but must remain hidden or marked non-authorable in Hermes-facing context. Promote them to Hermes-visible `AGENT_COMPOSABLE` only after M2A-S4 human visual verification passes and the human-review packet is accepted.

Hermes must see:

```text
inputs
outputs
parameters
units
allowed enum values
limitations
examples of safe wording
unsupported claims
```

Hermes must not see:

```text
raw event dumps
raw coordinate payloads
filesystem paths
host-only runtime globals
private runner endpoints
implementation labels as tactical truth
```

Do not add a canned hero template that maps one exact prompt to the recipe. Recipe selection is allowed; novel composition is not the M2A acceptance target.

## Cloud And Deployment Contract

M2A adds a first-class event-data dependency. The deployed runtime bundle must include synchronized event parquet files and must expose those dependencies in readiness and cache identity.

Add these fields to the demo-data manifest, `/readyz`, execution provenance, execution/cache identity, and cloud smoke verification:

```text
event_data_files
event_data_sha256
event_schema_version
event_tracking_alignment_version
active_player_timeline_version
active_player_timeline_sha256
```

If those fields are missing or stale, the cloud runtime must not advertise M2A readiness.

## Runtime Implementation Guidance

Prefer small helpers over adding more logic directly to the already-large executor:

```text
src/tqe/runtime/action_episodes.py
  controlled pass extraction
  event qualifier parsing
  frame alignment
  reception search

src/tqe/runtime/bypass.py
  attacking-direction normalization
  opponent candidate selection
  bypass count evaluation
  missing-evidence semantics
```

Then wire those helpers from `src/tqe/runtime/executor.py` through catalog-node implementations.

Expected touchpoints:

```text
src/tqe/runtime/catalog.py
src/tqe/runtime/executor.py
src/tqe/runtime/action_episodes.py       # new
src/tqe/runtime/bypass.py                # new
src/tqe/workshop/knowledge_pack.py
src/tqe/workshop/m1_2.py                 # only if tool/schema exposure requires it
config/query-plans/high_bypass_completed_pass.experimental.v1.json
generated/capability-catalog.json
generated/capability-context.json
generated/tactical-knowledge-pack.json
tests/...
apps/workbench-alpha/src/...             # replay and product copy only after backend proof
```

Keep M1 parity, N1C/N1D/N1I gates, destination-entry semantics, and existing Workbench recipe flows unchanged.

## Replay Contract

Add one exact overlay type:

```text
actual_completed_pass_bypass
```

Overlay data must come only from resolved evidence. If release/reception points or bypassed player IDs are missing, hide the overlay and show an evidence-unavailable message in developer details. Do not infer from event coordinates alone.

Replay rendering:

```text
observed ball trail: tracked ball positions from release to reception
optional straight vector: release_ball_point -> reception_ball_point, labelled "pass vector"
highlight: passer at release
highlight: receiver at reception
highlight: bypassed opponents at reception
ghost markers: bypassed opponents at release
badge: "<N> opponents bypassed"
label: forward progression in metres
markers: release frame and controlled-reception frame
```

Temporal behavior:

```text
before release:
  no pass line

release -> reception:
  animate observed ball trail
  optionally show a straight pass vector as a separate labelled guide

at reception:
  highlight receiver
  highlight bypassed opponents
  show ghost release positions
  show bypass count badge
```

Do not display the bypass count before controlled reception has been established.
Do not call a straight release-to-reception chord the actual ball path.

Copy:

```text
High-bypass completed pass
Completed pass where the controlled reception left N opposition outfield players behind the ball.
This does not claim optimality, pass probability, player intent, or a formally broken defensive line.
```

The result card should include:

```text
match title
period
canonical reception match time
passer -> receiver
opponents bypassed count
forward progression
```

## Human Verification Packet

Because final tactical correctness is visual/human for M2A, the implementing agent must produce:

```text
delivery/m2a-high-bypass-completed-pass/M2A_REPORT.md
artifacts/m2a/high-bypass-results.json
artifacts/m2a/high-bypass-human-review/
```

The human-review folder must contain at least:

```text
5 positive examples, or all positives if fewer than 5
3 near misses where available
2 UNKNOWN examples where available
one screenshot or frame export at release for each example
one screenshot or frame export at reception for each example
one replay screenshot with overlay for each positive example
one evidence JSON excerpt for each example
```

Where the corpus permits, the sample must span:

```text
at least two matches
first and second halves
both attacking orientations
```

For each positive example, the reviewer should be able to answer:

```text
Is the pass actually completed?
Are passer and receiver correct?
Are the highlighted opponents goal-side of the ball at release?
Are those same opponents behind the ball at controlled reception?
Does the count badge match highlighted player IDs?
Does the visual avoid claiming "line break" or "optimal pass"?
```

## Verification Gates

Add:

```text
make m2a-verify
```

The gate must exit nonzero on failure.

Required automated checks:

1. Catalog entries validate and generated internal capability packs include the new capabilities with explicit named payload schemas, not false boolean payload declarations.
2. Hermes-facing capability context hides or marks the new capabilities non-authorable until M2A-S4 acceptance.
3. `controlled_pass_episode` emits deterministic IDs independent of event row iteration order.
4. Event timestamp alignment uses `events.timestamp` by default; a synthetic fallback-only case is separately reported.
5. Release-frame alignment beyond tolerance produces `UNKNOWN`.
6. Physical pass-release confirmation failure produces `UNKNOWN`.
7. Missing controlled reception produces `UNKNOWN`.
8. Controlled-reception dwell/nearest-player checks use canonical timestamps and reject at least one synthetic near-ball-but-not-controlled case.
9. Receiver-not-first-controller produces `FAIL`, not delayed PASS.
10. Active-player membership changes inside the pass window produce `UNKNOWN`.
11. Excessive frame gaps interrupt dwell and produce `UNKNOWN`.
12. Broken possession continuity does not count as a completed controlled pass.
13. Attacking-direction mirroring produces identical bypass counts.
14. Player record ordering does not change bypass counts or result IDs.
15. A player inside either positional buffer is not spuriously bypassed.
16. Expected active/evaluated/missing opposition outfield denominators are recorded for every evaluation.
17. Missing active opponent positions do not silently reduce the count when coverage could affect a threshold predicate.
18. Measured count above recipe threshold can pass while coverage remains explicitly recorded.
19. Measured count below recipe threshold with incomplete coverage yields UNKNOWN, not FAIL.
20. Goalkeepers are excluded and listed in `excluded_goalkeeper_ids`.
21. Generic predicates consume `anchor_evaluations`, not raw episode sidecars.
22. Every highlighted opponent in replay evidence appears in `bypassed_player_ids`.
23. Every positive result resolves all required evidence aliases.
24. Repeated execution is deterministic for the same match scope.
25. Demo-data manifest, `/readyz`, execution/cache identity, and cloud smoke include event-data and alignment hashes.
26. M1.2 Workbench, N1C, N1D.1/N1I, and existing unit suites remain green or are explicitly explained if a known generated-artifact footgun dirties tracked files.

Suggested command bundle:

```text
make m2a-verify
make m1-2-gate-s2i-verify
make n1c-verify
make n1d1-verify
make n1i-verify
make workbench-alpha-verify
python -m unittest discover -s tests
```

If `n1c-verify` dirties tracked artifacts, restore only those generated artifacts after recording the known footgun in the report. Do not mix generated-artifact churn into the M2A implementation commit.

## Preflight Requirement

M2A-S0 must answer:

```text
Can event passer/receiver IDs map reliably to tracking entities?
What does events.timestamp physically represent?
How close is the named passer to the ball at the aligned event frame?
How often is the named receiver the first confirmed controller?
How often does active-player membership change inside candidate windows?
How many candidates are PASS, FAIL, and UNKNOWN?
What are the progression and bypass-count distributions?
How many real positives satisfy progression >= 8m and count >= 5?
```

M2A-S0 visual inspection must include:

```text
clear successful receptions
wrong-recipient or deflection cases
near-ball but not controlled cases
incomplete tracking cases
```

Before building Workbench UI exposure, run a real-data distribution preflight across the deployed match manifest:

```text
completed Play_Pass events
controlled receptions found
UNKNOWN controlled receptions
release-control confirmation failures
forward progression distribution
opponents bypassed distribution
positive count at threshold >= 5 and progression >= 8m
active-player timeline coverage
event/tracking alignment error distribution
```

If there are zero positives across deployed matches, stop and report. Do not silently lower the threshold. The user may decide whether to use the broader seven-match corpus or adjust the product claim.

## Implementation Slices

### M2A-S0 - Data Alignment Preflight

Deliver:

```text
event recipient parsing proof
event-to-frame alignment proof
release/reception search feasibility
active-player timeline proof
event/tracking alignment error report
distribution report
```

Stop if player IDs, event timing, or tracking positions cannot be joined reliably.

### M2A-S1 - Controlled Pass Episode

Deliver:

```text
controlled_pass_episode catalog entry
runtime implementation
unit tests for PASS/UNKNOWN/continuity/timing
inspection records for known timestamps
```

No Workbench UI yet.

### M2A-S2 - Opponents Bypassed Evaluation

Deliver:

```text
opponents_bypassed_by_action catalog entry
attacking-direction-normalized evaluator
coverage/missing-data semantics
unit tests for mirror/order/buffer/missing evidence
```

No Workbench UI yet.

### M2A-S3 - Recipe And Generic Results

Deliver:

```text
high_bypass_completed_pass_v1 experimental recipe
QueryResult emission
complete requested evidence
non-match inspection
knowledge-pack regeneration
cloud manifest/readiness/cache identity event-data fields
make m2a-verify
```

### M2A-S4 - Replay And Human Review

Deliver:

```text
Workbench result card support
actual_completed_pass_bypass replay overlay
human-review packet
screenshots
M2A_REPORT.md
```

## Non-Goals

Do not implement in M2A:

```text
defensive_line_model
relative_position_to_defensive_line
controlled_line_break_episode
lane_occupancy
support_arrival_relation
local_number_relation
Hermes novel-composition proof
pass probability
optimal pass
player intent
body orientation
scanning
offside model
video integration
large visual redesign
automatic feedback/revision loop
```

## Stop Conditions

Stop and report instead of forcing a pass if:

```text
event Recipient cannot be mapped to tracking player IDs
event-to-frame alignment cannot be bounded
controlled reception cannot be inferred from tracking with acceptable evidence
attacking direction is unavailable or inconsistent for selected matches
goalkeeper exclusion cannot be trusted
there are zero qualifying real examples at the declared threshold
the implementation would require a broad IR/type-system redesign
the replay overlay would need inferred geometry rather than exact evidence
```

## Acceptance Statement

M2A is accepted when the product can truthfully say:

```text
The Workbench can find and replay real completed passes where the controlled reception left at least five opposition outfield players behind the ball, with exact passer, receiver, bypassed-player, progression, timing, trace, and replay evidence.
```

It must not say:

```text
This proves a defensive line was broken.
This was the optimal pass.
The player intended the action.
The model inferred football intelligence from video/body shape/scanning.
```
