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

events:
  match_id
  period
  team_role
  row_index
  event_type
  gameclock_seconds
  team_id
  player_id
  at_x
  at_y
  to_x
  to_y
  qualifier_json
```

`events.qualifier_json` contains pass metadata such as `Evaluation`, `Recipient`, `Player`, and `Team`. Use events to identify candidate passes and named players. Use tracking data to prove physical release and controlled-reception endpoints. Do not treat event `to_x/to_y` as a controlled reception frame without tracking confirmation.

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

### High-Bypass Completed Pass

The initial tactical family is:

```text
controlled_pass_episode.status == PASS
AND forward_progression_m >= 8.0
AND opponents_bypassed_count >= 5
-> HIGH_BYPASS_COMPLETED_PASS
```

"More than four opponents" must be interpreted as `>= 5`. The Workbench interpretation should expose that conversion.

## Capability 1 - `controlled_pass_episode`

Visibility after proof: `AGENT_COMPOSABLE`

Recommended initial catalog kind: `primitive`

Recommended output shape:

```text
controlled_pass_episode.episodes
  temporal_type: episode_set
  payload_type: boolean
  cardinality: collection
  entity_scope: possession
  missing_data_semantics: unknown
```

Do not add a new IR temporal type for M2A unless the existing `episode_set` cannot carry required records. Each episode record must contain an explicit `pass_episode_id` so downstream predicates and evidence can correlate by action identity, not by frame only.

### Inputs

This primitive has no plan-node inputs in M2A. It reads host-owned canonical event/tracking state from the runtime `PeriodState`, scoped by the bound invocation.

### Parameters

```text
event_type_filter: enum list by implementation contract
  default: ["Play_Pass"]
  allowed initially: open-play completed passes only

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

minimum_forward_progression_m: number metre
  default: 0.0
  minimum: -30.0
  maximum: 80.0
```

If the current catalog parameter model does not support enum lists, use an enum parameter for `pass_family` with allowed value `open_play_completed_pass` and keep the exact event-type set host-owned.

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

Set pieces can be added later. M2A must stay narrow and prove open-play completed passes first.

### Release Frame Alignment

Find the canonical tracking frame nearest the event's `gameclock_seconds` in the same match/period.

Preferred implementation:

```text
period_start_timestamp = first frames.timestamp_utc for period
event_timestamp = period_start_timestamp + gameclock_seconds
release_frame = nearest frame timestamp_utc to event_timestamp
```

If existing runtime utilities already define match time or frame alignment, reuse those. Do not add a second incompatible timing convention.

If absolute time delta is greater than `max_release_alignment_ms`, emit a controlled pass record with:

```text
controlled_pass_status = UNKNOWN
unknown_reason = "release_frame_alignment_failed"
```

and do not use it as a positive result.

### Controlled Reception Frame

The event timestamp alone is not the controlled reception. Search forward from the release frame for at most `max_reception_search_seconds`.

The controlled reception frame is the first frame where all are true:

```text
receiver position exists
ball position exists
distance(ball, receiver) <= max_reception_ball_distance_m
receiver is the nearest teammate to the ball, or tied within receiver_nearest_margin_m
same-team possession continuity has not broken
```

Possession continuity can initially use the runtime's existing ball possession/team role state if available. If reliable possession continuity is unavailable for a frame window, the action is `UNKNOWN`.

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

Visibility after proof: `AGENT_COMPOSABLE`

Recommended initial catalog kind: `primitive` unless relation plumbing fits better.

Recommended output shape:

```text
opponents_bypassed_by_action.evaluations
  temporal_type: episode_set
  payload_type: boolean
  cardinality: collection
  entity_scope: possession
  missing_data_semantics: unknown
```

Each record is keyed by `pass_episode_id`. The boolean payload indicates whether the evaluation meets a declared threshold when used directly by a recipe; the record must also carry the count and player IDs as evidence.

### Inputs

```text
controlled_passes:
  source: controlled_pass_episode.episodes
  required: true
```

### Parameters

```text
minimum_bypassed_opponents: number count
  default: 5
  minimum: 1
  maximum: 10

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

1. If `controlled_pass_status != PASS`, emit `evaluation_status = UNKNOWN` or `FAIL` according to the pass status:
   - `UNKNOWN` stays `UNKNOWN`.
   - known failed continuity/reception stays `FAIL`.
2. Load all opposition outfield player positions at `release_frame_id` and `reception_frame_id`.
3. Load ball positions at `release_frame_id` and `reception_frame_id`.
4. Normalize x coordinates with the attacking team's `attack_x_sign`.
5. Build `candidate_goal_side_ids`:
   ```text
   opponent_release_attack_x > release_ball_attack_x + goal_side_buffer_m
   ```
6. Build `bypassed_player_ids` from those candidates:
   ```text
   opponent_reception_attack_x < reception_ball_attack_x - bypassed_buffer_m
   ```
7. Exclude goalkeepers using `players.is_goalkeeper`.
8. Set:
   ```text
   opponents_bypassed_count = len(bypassed_player_ids)
   evaluation_status = PASS if count >= minimum_bypassed_opponents else FAIL
   ```

Missing evidence rule:

```text
If any opponent who could affect the threshold is missing at release or reception,
the evaluation is UNKNOWN unless the count is already proven above threshold
without that player.
```

That means:

```text
proven count >= threshold -> PASS even with unrelated missing opponent evidence
proven count < threshold and missing candidate evidence could reach threshold -> UNKNOWN
fully evaluated count < threshold -> FAIL
```

### Output Record Fields

Each evaluation record must include:

```text
pass_episode_id
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
minimum_bypassed_opponents
goal_side_buffer_m
bypassed_buffer_m
candidate_goal_side_player_ids
bypassed_player_ids
opponents_bypassed_count
missing_opponent_ids
excluded_goalkeeper_ids
evaluation_status             # PASS | FAIL | UNKNOWN
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
plans/high_bypass_completed_pass_v1.json
```

If recipe plan files currently live elsewhere, use the existing recipe-plan convention and add this alongside the other experimental recipe documents.

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
    pass_family = open_play_completed_pass
    max_reception_search_seconds = $max_reception_search_seconds
    minimum_forward_progression_m = $minimum_forward_progression_m

node: opponents_bypassed_by_action
  input:
    controlled_passes = controlled_pass_episode.episodes
  parameters:
    minimum_bypassed_opponents = $minimum_bypassed_opponents
    goal_side_buffer_m = $goal_side_buffer_m
    bypassed_buffer_m = $bypassed_buffer_m

predicate:
  source = opponents_bypassed_by_action.evaluations
  operator = exists or eq PASS over anchor/action evaluation

classification:
  label = HIGH_BYPASS_COMPLETED_PASS
  include_when = predicate PASS
  unknown_policy = exclude candidate, preserve trace
```

If current generic result emission needs anchor-like records, create deterministic action anchors from `pass_episode_id`:

```text
anchor_id = stable_hash(match_id, period, pass_episode_id, release_frame_id, reception_frame_id)
anchor_frame_id = reception_frame_id
start_frame_id = release_frame_id
end_frame_id = reception_frame_id
```

Do not generate IDs from node names, output list indexes, or result ordering.

### Required Evidence Aliases

Results must request and resolve:

```text
pass_episode_id
event_row_index
passer_id
receiver_id
release_frame_id
reception_frame_id
release_match_time_ms
reception_match_time_ms
release_ball_point
reception_ball_point
release_passer_point
reception_receiver_point
forward_progression_m
opponents_bypassed_count
bypassed_player_ids
candidate_goal_side_player_ids
goal_side_buffer_m
bypassed_buffer_m
evaluation_status
unknown_reason
```

`requested_evidence_failure_count` must be zero for accepted positive results.

## Knowledge Pack And Hermes Contract

Expose these after local deterministic proof:

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
plans/...                                # new experimental recipe
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
solid line: release_ball_point -> reception_ball_point
highlight: passer at release
highlight: receiver at reception
highlight: bypassed opponents at reception
ghost markers: bypassed opponents at release
badge: "<N> opponents bypassed"
label: forward progression in metres
markers: release frame and controlled-reception frame
```

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

1. Catalog entries validate and generated capability/knowledge packs include the new safe capabilities.
2. `controlled_pass_episode` emits deterministic IDs independent of event row iteration order.
3. Release-frame alignment beyond tolerance produces `UNKNOWN`.
4. Missing controlled reception produces `UNKNOWN`.
5. Broken possession continuity does not count as a completed controlled pass.
6. Attacking-direction mirroring produces identical bypass counts.
7. Player record ordering does not change bypass counts or result IDs.
8. A player inside either positional buffer is not spuriously bypassed.
9. Missing opponent positions do not silently reduce the count when the missing player could affect threshold.
10. A proven count above threshold remains `PASS` despite unrelated missing non-candidate evidence.
11. Goalkeepers are excluded and listed in `excluded_goalkeeper_ids`.
12. Every highlighted opponent in replay evidence appears in `bypassed_player_ids`.
13. Every positive result resolves all required evidence aliases.
14. Repeated execution is deterministic for the same match scope.
15. M1.2 Workbench, N1C, N1D.1/N1I, and existing unit suites remain green or are explicitly explained if a known generated-artifact footgun dirties tracked files.

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

Before building Workbench UI exposure, run a real-data distribution preflight across the deployed match manifest:

```text
completed open-play passes
controlled receptions found
UNKNOWN controlled receptions
forward progression distribution
opponents bypassed distribution
positive count at threshold >= 5 and progression >= 8m
```

If there are zero positives across deployed matches, stop and report. Do not silently lower the threshold. The user may decide whether to use the broader seven-match corpus or adjust the product claim.

## Implementation Slices

### M2A-S0 - Data Alignment Preflight

Deliver:

```text
event recipient parsing proof
event-to-frame alignment proof
release/reception search feasibility
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
threshold/missing-data semantics
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
