# M1.1 Specification - Composable Tactical Query Runtime

## Product Outcome

A developer can add a validated tactical detector plan, bind it against an approved primitive/relation catalog, execute it over the real IDSSE corpus through a generic deterministic runtime, inspect every predicate trace, and replay the resulting moments without adding query-specific backend code.

## Boundary Decision

M1.1 is an architectural runtime proof, not a Hermes or polished UI milestone.

M1.1 proves:

```text
RecipeDefinition
-> QueryInvocation
-> DraftQueryPlan
-> deterministic compiler / binder
-> BoundQueryPlan
-> generic executor
-> QueryExecution
-> predicate traces
-> evidence bundles
```

Hermes, natural-language drafting, analyst feedback, recipe revision, and visual workshop UX are deferred to M1.2. This prevents query-language design, generic execution, dynamic relations, LLM interpretation, persistence, and interface behavior from sharing one acceptance boundary.

## Required Precondition - M1 Baseline Freeze

M1.1 implementation must not begin until the accepted M1 state is made stable enough to act as an oracle.

Required before M1.1 implementation:

- valid Git baseline commit for the accepted M1 state;
- owner acceptance or explicit owner waiver for proceeding without final M1 acceptance;
- legacy detector source hash;
- frozen M1 query configuration hash;
- complete legacy result manifest;
- evidence-bundle manifest;
- reviewed M1 semantic gold set.

M1 parity preserves behavior, not correctness. Because M1 independent review was waived, the reviewed semantic gold set is required to reduce oracle laundering risk before the legacy detector becomes the M1.1 regression oracle.

The gold set must include:

- clear positives;
- borderline accepted moments;
- near misses;
- at least one example from each accepted outcome class;
- first-half and second-half examples.

Parity is measured against both the full machine output and the reviewed examples.

## Scope

M1.1 includes:

- a typed Tactical Query IR v1 using Pydantic as the authority;
- explicit separation of recipe definition, query invocation, bound plan, and query execution;
- a deterministic compiler/binder from draft plans to bound plans;
- a primitive and relation catalog with explicit input/output types, payload types, cardinality, units, limitations, missing-data semantics, and evidence fields;
- a generic executor that contains no query-ID branches;
- translation of the M1 Ball-Side Block Shift query into an approved plan;
- parity checks against the legacy M1 detector, which remains a read-only oracle through demo completion;
- tri-state predicate evaluation;
- formal forced-window/non-match evaluation;
- one dynamic relation primitive, `geometric_progressive_corridor`;
- one experimental relation-based composition authored as plan data, not query-specific Python;
- predicate traces for matching moments and supplied non-match windows;
- minimal developer-facing plan/result inspector artifacts;
- proof reports and version/hash manifests.

## Non-Goals

M1.1 excludes:

- Hermes or any other LLM runtime;
- natural-language query compilation;
- analyst feedback labels;
- recipe revision UX;
- user-authored detector saving;
- polished analyst workbench;
- arbitrary DSL syntax or custom parser;
- arbitrary Python, SQL, Polars expressions, or generated code execution;
- user-defined functions, loops, recursion, unrestricted joins, or custom expressions;
- automatic promotion of experimental plans to approved recipes;
- runtime primitive implementation or primitive mutation;
- semantic recipe search infrastructure or vector search;
- universal graph engine;
- pass-probability model;
- optimal pass, expected pass, best decision, player intent, causation, or missed-opportunity claims;
- production persistence, auth, cloud deployment, or match video.

## Architecture

```text
IDSSE tracking/events
        ↓
Canonical match store
        ↓
Primitive and relation catalog
        ↓
RecipeDefinition + QueryInvocation
        ↓
DraftQueryPlan
        ↓
Deterministic compiler / binder
        ↓
BoundQueryPlan
        ↓
Generic deterministic executor
        ↓
QueryExecution + predicate traces
        ↓
Evidence bundles + replay inspector
```

The compiler/binder is mandatory. Draft plans may reference names and parameters, but only bound plans can execute.

## Formal Objects

### `RecipeDefinition`

A reusable tactical program with parameter placeholders, defaults, claims, limitations, classification rules, ranking, and requested evidence.

It must not bake in one user's selected match scope, team perspective, or execution filters.

### `QueryInvocation`

Concrete matches, periods, perspective team, filters, parameter values, maximum returned moments, and execution mode.

### `DraftQueryPlan`

Human-authored, developer-authored, or future Hermes-authored representation before deterministic resolution.

### `BoundQueryPlan`

Execution-ready plan with primitive versions, relation versions, operator versions, units, value types, entity scope, parameter values, evidence fields, and complexity limits fully resolved.

### `QueryExecution`

Results, traces, provenance, timing, plan hashes, source hashes, and replay references for one run.

## Binder Responsibilities

The binder verifies:

- referenced primitives/relations exist;
- each referenced output type is known;
- payload type and cardinality are valid;
- operators are valid for each analytical and payload type;
- units and value types are correct;
- temporal references are resolvable;
- match scope and team perspective are explicit through `QueryInvocation`;
- requested evidence fields exist;
- classifications are exhaustive or intentionally partial;
- unknown-evidence policy is declared;
- complexity limits are respected;
- unsupported or ambiguous references fail visibly.

The binder must reject errors such as:

```text
persists_for applied directly to a scalar number
distance compared to seconds
team-level signal used as a player relation
count applied to a non-collection
destination requested from a frame signal
```

## Type Model

M1.1 keeps three temporal containers but makes payload type, cardinality, units, entity scope, and missing-data semantics explicit.

### Temporal Containers

#### `FrameSignal<T>`

A value at each analysis frame.

Examples:

- `ball_lateral_fraction`
- `defensive_centroid_y`
- `nearest_defender_distance`
- `progressive_corridor_count`

#### `EpisodeSet`

Intervals.

Examples:

- possession;
- wide entry;
- block shift;
- pressure increase;
- forward run.

#### `RelationEpisodeSet`

Relationships that exist over intervals.

Examples:

- attacking player has a geometric corridor to another attacking player;
- defender tracks attacker;
- player occupies lane;
- player supports ball carrier.

### Payload Types

Supported payload types:

```text
Boolean
Number<Unit>
Enum
EntityRef
TeamRef
RegionRef
Point
EntitySet
RelationRef
```

### Cardinality

Supported cardinalities:

```text
single value
per-player value
per-team value
collection
```

Operators must be type-aware and cardinality-aware. Invalid combinations fail at bind time rather than returning no results.

## Tri-State Predicate Logic

Every predicate resolves to exactly one of:

```text
TRUE
FALSE
UNKNOWN
```

`UNKNOWN` covers:

- missing ball state;
- unavailable entities;
- invalid geometry;
- insufficient prior frames;
- insufficient future horizon;
- quality failures;
- relation state that cannot be evaluated.

`UNKNOWN` must never silently become `FALSE`.

Predicate traces expose:

```text
PASS
FAIL
UNKNOWN - insufficient prior frames
UNKNOWN - target player unavailable
UNKNOWN - invalid relation geometry
```

Every recipe or invocation declares the unknown-evidence policy:

```text
exclude_candidate
include_with_warning
invalidate_execution
```

## EvaluationTarget for Non-Matches

Non-match inspection uses a formal `EvaluationTarget`.

Example:

```json
{
  "matchId": "J03WOY",
  "period": 2,
  "approximateTimeMs": 3674000,
  "searchRadiusMs": 3000
}
```

The engine must:

1. search for compatible anchors within the window;
2. evaluate each candidate anchor against the same bound plan;
3. report the closest compatible candidate and failed/unknown predicates;
4. report `NO_COMPATIBLE_ANCHOR` when no anchor exists.

Hermes must not fabricate a non-match explanation when the engine returns `NO_COMPATIBLE_ANCHOR`.

## Required Dynamic Relation

M1.1 implements `geometric_progressive_corridor`.

Version 1 means:

> A geometrically clear, forward connection from the current ball location to an attacking teammate that persists for a minimum interval.

Initial inputs:

- source is the ball position;
- target is an attacking teammate;
- forward progression;
- segment length;
- minimum defender-to-segment clearance;
- destination region/lane;
- open and closed frames;
- persistence;
- limiting defender.

Explicitly excluded from V1 acceptance:

- best-pass probability;
- expected completion;
- receiver body orientation;
- player intention;
- optimality;
- offside unless already reliable;
- defensive lines crossed unless the line model is already verified.

Use hysteresis so an edge does not appear and disappear every analysis frame:

```text
open after N consecutive passing frames
close after M consecutive failing frames
```

Compute corridors at the analysis rate or on scoped candidate windows. Do not build a huge full-corpus graph unless profiling proves it is needed.

## Internal Implementation Order and Gates

### Gate 0 - M1 Baseline and Gold Set

Hard acceptance:

- valid committed M1 baseline exists;
- owner acceptance or explicit owner waiver exists;
- legacy detector source hash is recorded;
- frozen query configuration hash is recorded;
- complete legacy result manifest exists;
- evidence-bundle manifest exists;
- reviewed semantic gold set exists.

### Gate A - Minimal IR, Type System, and Binder

Hard acceptance:

- `RecipeDefinition`, `QueryInvocation`, `DraftQueryPlan`, `BoundQueryPlan`, and `QueryExecution` schemas exist;
- generated JSON Schema and TypeScript types are produced from Pydantic;
- primitive and relation catalog entries declare temporal type, payload type, cardinality, units, limitations, missing-data semantics, and evidence fields;
- operator signatures are versioned;
- invalid primitive names, units, cardinality, operators, temporal references, and unsupported evidence fields fail at bind time;
- complexity limits are enforced before execution;
- plan hash and bound-plan hash are deterministic and stable across processes.

### Gate B - M1 Runtime Execution and Complete Parity

Translate the completed M1 Ball-Side Block Shift detector into the Tactical Query IR.

Run:

```text
legacy M1 detector
vs.
query-runtime implementation
```

Hard acceptance:

- accepted result IDs are identical;
- classifications are identical;
- baseline, anchor, and outcome frames are identical;
- evidence values match within declared tolerance;
- result ordering is identical or explicitly justified;
- repeated execution produces identical moment IDs and traces;
- replay source frame windows remain traceable to the same canonical source frames;
- legacy implementation remains read-only as an oracle regression path.

Stop if parity requires query-specific branches in the generic executor.

### Gate C - Predicate Trace and Non-Match Evaluation

Hard acceptance:

- every result has a full predicate trace with pass/fail/unknown, value, threshold, unit, frame/window, and source evidence;
- missing data never silently evaluates as false;
- a supplied `EvaluationTarget` can be evaluated against the same bound plan;
- failed predicates are returned by the engine, not inferred by Hermes;
- a forced non-match window can produce `NO_COMPATIBLE_ANCHOR`;
- replay coordinates match canonical source data;
- unsupported or invalid plans fail visibly.

### Gate D - Dynamic Relation Proof

Hard acceptance:

- `geometric_progressive_corridor` relation intervals are derived from real canonical coordinates;
- opened/closed frames, duration, clearance, target, destination side/lane, limiting defender, and evidence fields are reproducible;
- at least several relation episodes exist across multiple Fortuna evaluation matches;
- every displayed corridor can be reconstructed from evidence fields;
- corridor intervals pass visual review for positives, negatives, and flicker boundaries;
- unknown and invalid relation states are represented explicitly;
- no optimality or missed-opportunity language is emitted.

### Gate E - No-Code Composition Proof

Author one experimental plan using only the query representation:

```text
ball enters wide area
-> defending block shifts toward ball side
-> opposite-side geometric progressive corridor appears
-> corridor persists for a minimum period
-> classify whether the ball enters the destination region
```

Hard acceptance:

- adding the plan document is sufficient to validate and execute it;
- runtime loads the external plan file without query-specific code changes;
- no new Python detector is added for this plan;
- no query-ID branch exists in the executor;
- architecture test confirms the executor does not import recipe modules;
- verification executes from canonical data after deleting caches or ignoring precomputed results;
- result evidence and replay bundles are generated;
- experimental status is explicit in every report and inspector surface.

### Gate F - Developer Inspector and Reports

Hard acceptance:

- minimal developer-facing plan selector exists;
- validation results are visible;
- result list, coordinate replay, predicate trace, non-match tester, and raw evidence values are inspectable;
- inspector reuses existing M1 replay implementation where possible;
- inspector does not depend on hardcoded M1 result shapes.

## Complexity Limits

M1.1 starts with conservative explicit limits:

- maximum plan nodes;
- maximum nesting depth;
- maximum temporal horizon;
- maximum returned moments;
- maximum relations evaluated per anchor;
- maximum execution cost.

Plans that exceed limits fail visibly.

## Required Artifacts

```text
delivery/m1.1/SPEC.md
delivery/m1.1/status.yaml
config/query-plans/ball_side_block_shift.ir.v1.json
config/query-plans/opposite_corridor_after_shift.experimental.v1.json
generated/tactical-query-plan.schema.json
generated/tactical-query-plan.types.ts
generated/capability-catalog.json
artifacts/m1.1/m1-baseline-manifest.json
artifacts/m1.1/legacy-result-manifest.json
artifacts/m1.1/evidence-bundle-manifest.json
artifacts/m1.1/parity-report.json
artifacts/m1.1/binder-validation-report.json
artifacts/m1.1/predicate-trace-report.json
artifacts/m1.1/non-match-inspection-report.json
artifacts/m1.1/relation-validation-report.json
artifacts/m1.1/experimental-query-results.json
artifacts/m1.1/verification-report.json
```

## Required Commands

```bash
make m1-verify
make m1-1-build
make m1-1-verify
```

`make m1-1-verify` must fail if M1 baseline freeze, binder validation, M1 parity, predicate tracing, non-match inspection, relation proof, no-code composition, replay correspondence, or architecture branch checks fail.

## Anti-Reward-Hacking Rules

- M1 parity is measured against the complete frozen M1 result set and reviewed gold set, not selected examples.
- The legacy M1 detector remains available as a read-only oracle.
- The generic executor may not check query IDs or plan names.
- No agent-generated code executes.
- No custom expression, opaque plugin, or hidden handler may be embedded in a plan.
- Missing data must not silently evaluate as false.
- Experimental plans are clearly labeled.
- Sparse results may not trigger automatic threshold relaxation.
- Geometric corridors must remain distinct from actionable options, selected actions, and optimal actions.
- No precomputed result set may be accepted as a no-code composition proof.

## Stop Conditions

Stop and reassess if:

- no valid M1 baseline commit exists;
- M1 parity requires special cases in the generic executor;
- the IR starts becoming a general programming language;
- plans require primitive-specific code embedded in the AST;
- the relation layer cannot be displayed and verified visually;
- non-match explanations cannot be produced deterministically;
- execution becomes opaque enough that predicate traces are incomplete;
- the inspector depends on hardcoded M1 result shapes.
