# M1.1R Corrective Specification - Explicit Graph Runtime

## Decision

The external implementation review rejected the first M1.1 implementation on 2026-06-19. M1.2 must not begin until M1.1R passes.

M1.1R is a corrective sub-milestone under M1.1. It preserves the useful M1.1 scaffolding but replaces the false architectural claim with proof of an explicit, typed execution graph.

## Product Outcome

A developer can author a tactical query plan whose node dependencies, parameter contracts, runtime values, classification rules, evidence projection, unknown handling, and invocation behavior are all enforced by the binder and executor, with M1 parity preserved and no M1-specific orchestration in the generic runtime.

## Boundary

M1.1R is still backend/runtime only.

It does not introduce Hermes, natural-language drafting, analyst feedback, saved detectors, polished UX, Priori integration, cloud deployment, or match video.

## External Review Findings Accepted As Blocking

The controller accepts the following external findings as blocking:

- plan nodes lack explicit typed inputs;
- catalog input metadata is not used to wire runtime dependencies;
- runtime outputs do not conform to declared catalog output types;
- query orchestration is encoded in mutable `PeriodState` fields, node IDs, and M1-specific result fields;
- several catalog capabilities are advertised as executable but map to no-op primitives;
- classification rules, requested evidence, unknown policy, `max_results`, and `execution_mode` are present in IR but not honored;
- tri-state values exist in traces but not in the execution graph;
- relation execution is coupled to M1 accepted results rather than explicit anchors;
- proof gates can pass while the central composability claim remains false.

## Corrective Scope

M1.1R includes:

- explicit node input maps in `DraftCatalogNode` and `BoundCatalogNode`;
- catalog input signatures for every executable primitive and relation;
- parameter schemas on catalog entries with allowed names, required/default state, type, unit, numeric bounds, and enum values;
- binder validation for node inputs, parameter names/ranges, recipe/plan classification agreement, executable implementation availability, and invocation semantics;
- `BoundQueryPlan` carrying `execution_mode`, `max_results`, and filters required for execution;
- first-class runtime value wrappers for scalar, frame-signal, episode-set, and relation-episode-set outputs;
- runtime output conformance checks against declared catalog outputs;
- generic node-output store instead of global `state.candidates`, `state.accepted`, and `state.near_misses`;
- generic predicate execution over typed runtime values with automatic trace generation;
- operational unknown policy;
- plan-driven classification and result evidence projection;
- relation execution over explicit anchor/scope inputs, not implicit M1 accepted results;
- corrected destination-entry semantics or honest renaming;
- metamorphic architecture gates that prove node-ID opacity and plan-driven behavior;
- full M1 parity after the correction.

## Non-Goals

M1.1R excludes:

- arbitrary DSL syntax or custom parser;
- arbitrary Python/SQL/Polars expressions in plans;
- runtime primitive invention by Hermes;
- universal graph engine;
- automatic promotion of experimental plans;
- second tactical family;
- analyst workbench UX.

## Required Gates

### Gate R0 - State Correction And Review Integration

Acceptance:

- external rejection is recorded in `docs/reviews/`;
- `delivery/m1.1/status.yaml` and `delivery/status.yaml` block M1.2;
- this corrective specification exists;
- ledger records the state transition.

### Gate R1 - Explicit Plan Graph And Binder Contracts

Acceptance:

- `DraftCatalogNode` requires or supports typed `inputs`;
- every executable primitive/relation declares catalog inputs or explicitly declares no inputs;
- `BoundCatalogNode` includes resolved input references and resolved parameter values;
- unknown node parameters fail binding;
- invalid parameter values fail binding;
- missing required inputs fail binding;
- temporal type, payload type, cardinality, unit, and entity scope mismatches fail binding;
- recipe output classifications must agree with plan classification labels;
- non-executable/no-op capabilities are removed from the exposed catalog.

### Gate R2 - Typed Runtime Values And Invocation Semantics

Acceptance:

- runtime values exist for scalar, frame-signal, episode-set, and relation-episode-set outputs;
- every node output is checked against the bound catalog contract;
- `bind_only` never executes match data;
- `dry_run` validates/estimates without producing match results;
- `execute` runs the match executor;
- `max_results` is honored;
- repeated execution is deterministic.

### Gate R3 - Generic Predicate, Classification, Evidence, And Unknown Semantics

Acceptance:

- predicates consume typed runtime values and never branch on node IDs;
- `persists_for` consumes a tri-state boolean frame signal and emits episode-set output;
- traces are generated as predicates execute, not hand-authored per query;
- classification rules are evaluated from predicate outputs;
- requested evidence determines query-specific result evidence;
- unknown policy changes execution behavior;
- forced-window/non-match traces use the same generic predicate mechanism.

### Gate R4 - Relation Anchor Decoupling And Experimental Plan Repair

Acceptance:

- `geometric_progressive_corridor` consumes explicit anchor/scope input;
- it can run from a non-M1 anchor set in a minimal valid plan;
- destination evaluation is either renamed to its actual lane semantics or changed to use a real spatial region;
- multiple relation episodes have explicit selection semantics;
- the opposite-corridor experimental plan executes without hidden M1 accepted-result coupling.

### Gate R5 - Architecture Proof And Parity

Acceptance:

- renaming all node IDs while preserving references leaves results unchanged;
- removing a required dependency fails binding;
- every advertised capability executes successfully in a minimal valid plan;
- changing classification rules changes classification behavior;
- changing requested evidence changes result projection;
- unknown policy changes behavior;
- generic executor source contains none of the approved recipe's predicate IDs;
- a second simple plan with no block-shift fields executes successfully;
- deleting generated caches still reproduces results from canonical data;
- corrected runtime still reproduces M1 exactly.

## Stop Conditions

Stop and request review if:

- preserving exact M1 parity requires retaining M1-specific global runtime state;
- the correction requires a universal tactical DSL rather than bounded graph contracts;
- relation decoupling cannot be proven on the current corpus;
- M1.1R gates pass only by weakening the original M1.1 product outcome.

## Reviewer Requirement

After M1.1R passes locally, package a new external review packet. M1.2 may begin only after the external decision is `APPROVE` or after required changes are integrated and independently re-reviewed.
