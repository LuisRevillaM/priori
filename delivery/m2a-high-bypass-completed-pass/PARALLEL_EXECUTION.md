# M2A Parallel Execution Brief

Date: 2026-06-23

Status: controller-owned execution plan for parallel M2A implementation.

Primary spec: `delivery/m2a-high-bypass-completed-pass/SPEC.md`

## Core Rule

M2A can be parallelized, but S1 runtime semantics must not begin until the controller-owned S0C gate freezes the data truth and semantic contracts.

```text
A event/reception evidence
+ B active-player timeline
+ C pure bypass evaluator
→ S0C integrated data truth
→ s0-contract-freeze.json
→ S1 runtime implementation may begin
```

Worker A may report provisional observed-player distributions, but Worker A does not own the accepted bypass distribution or positive count at the declared thresholds. Those are only acceptance evidence after A, B, and C are integrated.

## Parallel Work That May Start Now

### Worker A - Event/Tracking And Controlled-Reception Preflight

Scope:

```text
event timestamp meaning
event-to-frame alignment
passer/receiver identity mapping
release-control feasibility
reception-control feasibility
PASS / FAIL / UNKNOWN candidate classification draft
visual samples for reception false-positive risk
```

Allowed files:

```text
scripts or modules under artifacts/m2a or src/tqe/verification for read-only preflight
delivery/m2a-high-bypass-completed-pass/M2A_S0A_EVENT_PREFLIGHT.md
artifacts/m2a/s0a-event-preflight.*
```

Do not edit:

```text
catalog.py
executor.py
knowledge_pack.py
m1_2.py
Makefile
recipe registry
generated catalogs
Workbench production UI
```

Required answers:

```text
Can event passer/receiver IDs map reliably to tracking entities?
What does events.timestamp physically represent?
How close is the named passer to the ball at the aligned event frame?
How often is the named receiver the first confirmed controller?
How many candidates are PASS, FAIL, and UNKNOWN under provisional rules?
Which visual cases show clear reception, wrong receiver, deflection, near-ball/no-control, possession break, and missing frames?
```

Stop if event timestamps, recipient IDs, or endpoint tracking cannot be reconciled on real data.

### Worker B - Active-Player Timeline

Scope:

```text
trusted active on-pitch player timeline
expected active opposition outfield denominator
substitution/dismissal/active-set transition policy
coverage proof at candidate pass windows
```

Allowed files:

```text
src/tqe/data or src/tqe/runtime helper only if isolated from executor wiring
tests for active-player timeline helper
delivery/m2a-high-bypass-completed-pass/M2A_S0B_ACTIVE_PLAYERS.md
artifacts/m2a/s0b-active-player-timeline.*
```

Do not edit shared runtime registries or generated catalogs.

Required answers:

```text
registered squad vs active on-pitch players vs observed tracked players
expected_active_outfield_ids at release and reception
missing_active_opponent_ids
frequency of active-player membership changes inside candidate windows
policy/hash/version for active-player timeline
```

M2A rule:

```text
If substitution, dismissal, or active-player membership changes inside a pass window,
the relevant controlled-pass/bypass coverage is UNKNOWN.
```

### Worker C - Pure Synthetic Bypass Measurement

Scope:

```text
direction-normalized endpoint comparison
goal-side and behind-ball buffers
expected/evaluated/missing active opponent sets
bypassed ids and count
coverage status
threshold-free measurement
```

Allowed files:

```text
src/tqe/runtime/bypass.py
tests/test_m2a_bypass.py
delivery/m2a-high-bypass-completed-pass/M2A_S0C_BYPASS_ENGINE.md
```

Strict boundary:

```text
Do not implement "five or more opponents" inside the capability.
Do not depend on real pass extraction.
Do not edit executor/catalog/knowledge-pack registries.
```

Worker C owns pure logic only:

```text
expected_active_ids
evaluated_ids
missing_ids
candidate_goal_side_ids
bypassed_ids
opponents_bypassed_count
coverage_status
```

The recipe/predicate layer later owns:

```text
opponents_bypassed_count >= 5
forward_progression_m >= 8
```

### Worker D - Cloud Event Dependency Contract

Scope:

```text
manifest schema
event-data hash fields
active-player timeline hash fields
negative readiness tests
cache identity structure
cloud smoke expectations
```

Allowed files:

```text
config/deploy/demo-data-manifest schema or verifier files
scripts/cloud-smoke.py
readiness contract tests
delivery/m2a-high-bypass-completed-pass/M2A_S0D_CLOUD_CONTRACT.md
```

Fail-closed rule:

```text
/readyz must remain false for M2A until genuine event and active-player artifacts exist and hashes match.
No placeholder hash may satisfy readiness.
```

### Worker E - Fixture-Only Replay Contract

Scope:

```text
typed overlay DTO
fixture renderer
visual tests
temporal display rules
observed ball trail vs labelled pass vector
release ghosts and reception highlights
count reveal only after controlled reception
```

Allowed files:

```text
apps/workbench-alpha fixture-only DTO/tests
frontend visual test fixtures
delivery/m2a-high-bypass-completed-pass/M2A_S0E_REPLAY_CONTRACT.md
```

Do not wire into normal Workbench result flow until S3 supplies exact release/reception points and bypassed-player IDs.

## Controller-Owned S0C Gate

The controller integrates A, B, and C into:

```text
M2A-S0C - Integrated Data Truth
```

Required artifact:

```text
artifacts/m2a/s0-contract-freeze.json
```

It must pin:

```text
pass-family definition
event timestamp alignment policy/version
release-control definition
reception-control definition
reception search stop conditions
PASS / FAIL / UNKNOWN decision table
active-player timeline policy/version/hash
goalkeeper policy
ControlledPassEpisode schema
ControlledPassEvaluation schema
BypassedOpponentsEvaluation schema
pure bypass evaluator version/hash
```

S0C must run combined real-data distributions:

```text
controlled pass PASS / FAIL / UNKNOWN counts
release-control failure counts
receiver-first-controller rate
active-player membership change counts
opponents_bypassed_count distribution
forward_progression_m distribution
positive count at opponents_bypassed_count >= 5 and forward_progression_m >= 8
```

S0C must visually inspect at least:

```text
clear completed reception
wrong player controlling first
deflection
receiver near ball without control
possession break
missing-frame case
substitution/active-set edge case, if present
```

S0C decides:

```text
PROCEED_TO_S1
or
STOP_AND_REPORT_DATA_GAP
```

## Blocked Until S0C

Do not start these until S0C produces `PROCEED_TO_S1`.

### Worker F - Controlled Pass Runtime

Owns:

```text
src/tqe/runtime/action_episodes.py
controlled_pass_episode implementation
ControlledPassEpisode tests
ControlledPassEvaluation tests
```

### Worker C2 - Real-Data Bypass Wiring

Owns adapting Worker C's pure evaluator to frozen pass anchors/evaluations.

### Controller/Integrator - Shared Runtime And Registries

Controller/integrator only:

```text
src/tqe/runtime/catalog.py
src/tqe/runtime/executor.py
src/tqe/workshop/knowledge_pack.py
src/tqe/workshop/m1_2.py
Makefile
recipe registry
generated catalogs
config/query-plans/high_bypass_completed_pass.experimental.v1.json
```

## Execution Graph

```text
PARALLEL NOW

A — event/tracking and controlled-reception preflight
B — trusted active-player timeline
C — pure synthetic bypass measurement
D — cloud schema and fail-closed readiness contract
E — fixture-only replay contract

        ↓

CONTROLLER S0C GATE

freeze semantics and schemas
run combined real-data distribution
visually inspect alignment/reception samples
prove at least one real positive at declared thresholds
or stop honestly

        ↓

PARALLEL AFTER S0C

F — controlled_pass_episode runtime
C2 — adapt bypass evaluator to frozen pass contracts

        ↓

CONTROLLER INTEGRATION

catalog + executor wiring
anchor-relative outputs
generic predicates
recipe/result emission

        ↓

G — high_bypass_completed_pass_v1
complete evidence
non-match inspection
m2a-verify

        ↓

D activation
real cloud hashes and readiness

        ↓

E production wiring
exact replay overlay

        ↓

S4 human review packet
```
