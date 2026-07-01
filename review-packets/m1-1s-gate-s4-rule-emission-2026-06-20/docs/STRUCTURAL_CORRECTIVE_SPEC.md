# M1.1S Structural Corrective Specification - Plan-Driven Execution Handoff

## Decision

The external review of M1.1R Gate R5 rejected the implementation on 2026-06-20. M1.2 must remain blocked.

M1.1S is a structural corrective sub-milestone under M1.1. It preserves the M1.1R binder, catalog, invocation, corridor, and parity work, but replaces the remaining M1-specific execution handoff with a bounded plan-driven runtime core.

## Product Outcome

A bounded tactical query plan can produce real `QueryResult` rows through declared node outputs, typed anchors, predicate evaluation, classification rules, evidence requests, and trace propagation, without the generic executor depending on M1 candidate/result side channels.

## Boundary

M1.1S is still backend/runtime only.

It does not introduce Hermes, natural-language drafting, analyst feedback, saved detectors, polished UX, Priori integration, cloud deployment, or match video.

## Accepted External Finding

The controller accepts the following finding as blocking:

> R5 proves that the plan can name and parameterize pieces of the existing M1 pipeline. It does not prove that the plan is the tactical program.

The key unmet architecture test is:

> Can a plan using existing primitives and predicates produce a materially different set of real results without a Python terminal that understands that query's candidate shape?

M1.1S is complete only when the answer is yes.

## Non-Goals

M1.1S excludes:

- arbitrary DSL syntax or custom parser;
- arbitrary Python, SQL, or Polars expressions in plans;
- universal graph engine;
- runtime primitive invention by Hermes;
- automatic promotion of experimental plans;
- polished analyst workbench UI;
- broad tactical-family expansion beyond the minimal second result-producing plan required for proof.

## Required Architecture Changes

### 1. Declared Outputs Are The Only Inter-Node Channel

Node implementations should execute from an explicit input bundle:

```python
execute(
    inputs: Mapping[str, RuntimeValue],
    parameters: Mapping[str, TypedValue],
    context: MatchContext,
) -> NodeExecutionResult
```

`NodeExecutionResult` must contain:

- declared outputs;
- trace facts;
- warnings;
- cost/provenance metadata.

It must not contain undeclared `candidates`, `accepted`, `near_misses`, `source_results`, or `_runtime_result` fields used by downstream nodes.

### 2. General Anchor Model

Introduce a bounded anchor type with stable fields:

- `anchor_id`;
- `match_id`;
- `period`;
- `anchor_frame_id`;
- optional `start_frame_id`;
- optional `end_frame_id`;
- optional entity references;
- source node/output provenance;
- structured attributes.

Tactical primitives may enrich anchors with structured attributes, but relations and classification must consume anchors through this stable shape.

### 3. Rules Emit Results

For each anchor:

```text
predicate values -> classification-rule evaluation -> zero, one, or explicitly handled multiple labels -> QueryResult
```

Terminal primitives may calculate tactical facts or enum values, but classification rules must govern inclusion and final labels.

### 4. Generic Result Projection

Every result may contain a standard envelope:

- `result_id`;
- `match_id`;
- `period`;
- `anchor_frame_id`;
- `classification`;
- `provenance`.

Query-specific evidence must come from evidence requests resolved against declared node outputs.

Evidence requests must use stable aliases so public result keys do not change when node IDs are renamed:

```json
{
  "alias": "shift_metres",
  "source": {
    "source_node_id": "signed_shift",
    "output_name": "signed_shift"
  },
  "field": "value"
}
```

### 5. Generic Core Has No Query-Specific Result State

The generic executor must not depend on:

- `state.candidates`;
- `state.accepted`;
- `state.near_misses`;
- `block_shift_score`;
- `wide_entry_frame_id`;
- query-specific predicate IDs.

M1-specific evidence shaping may live in M1 primitive implementations or a legacy parity adapter after generic execution, but it must not control the generic execution engine.

### 6. Runtime Types Are Real

Frame signals need:

- frame IDs;
- values;
- validity/UNKNOWN mask;
- unit;
- entity scope.

Episode sets need a declared episode-record schema.

Relation episode sets need:

- relation ID;
- source anchor ID;
- source entity;
- target entity or region;
- open/close frames;
- typed attributes.

The runtime must fail when an implementation emits the wrong declared type. It must not drop missing values or silently convert M1 result dictionaries into scalars.

### 7. Plan-Generic Non-Match Evaluation

The runtime should:

1. derive compatible anchors for the target window;
2. evaluate every bound predicate over those anchors;
3. produce the same traces used during ordinary execution;
4. report `NO_COMPATIBLE_ANCHOR` explicitly.

No separate M1 candidate inspector should be required for generic plan evaluation.

## Required Gates

### Gate S0 - External Rejection Integration

Acceptance:

- external rejection is recorded in `docs/reviews/`;
- `delivery/m1.1/status.yaml`, `delivery/status.yaml`, and `delivery/m1.2/status.yaml` block M1.2;
- this structural corrective specification exists;
- ledger records the transition.

### Gate S1 - Runtime Value And Result Type Hardening

Acceptance:

- frame signals preserve frame alignment and UNKNOWN masks;
- runtime conformance rejects wrong temporal containers and payloads;
- episode and relation records are schema-validated;
- M1-shaped dictionaries cannot be normalized into `FrameSignal<Enum>` or `FrameSignal<Number>`;
- every runtime output carries provenance and declared output identity.

### Gate S2 - Node Execution Contract

Acceptance:

- nodes receive declared `RuntimeValue` inputs and parameters explicitly;
- downstream implementations cannot read undeclared node-output keys from a global signal dictionary;
- every declared required input is demonstrably consumed or explicitly declared as pass-through;
- substituting a compatible but measurably different input changes downstream output where semantics require it;
- generic operator implementations contain no query-specific candidate branches.

### Gate S3 - Anchor And Predicate Trace Core

Acceptance:

- a generic anchor set can be produced independently of M1 accepted results;
- predicates evaluate over anchors or frame/episode values and emit trace facts during execution;
- traces do not require M1 candidate dictionaries;
- actual missing data produces UNKNOWN end to end through ordinary execution;
- all three unknown policies are tested through actual node execution.

### Gate S3R - Explicit Anchor Contract And Generic Temporal Semantics

Acceptance:

- external S3 review is recorded and S4 remains blocked until this gate passes;
- the plan designates a single anchor source, and runtime anchor discovery does not scan arbitrary record sidecars;
- anchor records have a rigorous schema with semantic IDs derived from match, period, frame/window, and entities, not node IDs, output names, or list ordering;
- repeated representations of the same physical anchor deduplicate to one anchor;
- renaming plan nodes while preserving references leaves anchor IDs unchanged;
- a non-M1 anchor without `wide_entry_*`, `block_shift_*`, or `shift_gate_*` fields can be targeted and traced;
- clearing `state.candidates` and `state.accepted` does not change anchor discovery;
- runtime records are not hidden in provenance metadata;
- frame-signal frame-ID/value length mismatch is a hard error;
- `persists_for` consumes tri-state Boolean signals and emits episodes without shift-specific fields;
- generic anchor/target code contains no `wide_entry_*`, `block_shift_*`, or `shift_gate_*` assumptions;

### Gate S4 - Rule-Driven Result Emission

Acceptance:

- a generic plan produces at least one real `QueryResult` from canonical match data;
- classification rules control both result inclusion and labels;
- changing a required predicate changes inclusion while preserving labels for still-matching rules;
- PASS, FAIL, and UNKNOWN traces obey the plan's `unknown_evidence_policy`;
- requested evidence resolves from declared runtime outputs, not flat result sidecars;
- generic result envelopes do not require `block_shift_score`, `wide_entry_frame_id`, or `signed_shift_metres`;
- every generic execution proves `compatibility_profile = generic` and no legacy adapter use;
- result IDs and ordering are deterministic;
- `max_results`, `bind_only`, and `dry_run` are honored;
- frozen M1 parity remains exact only through explicit legacy helpers.

S4 is intentionally narrow. It must not add Hermes, UI work, new primitives, a second tactical family, a ranking language, or visualization grammar.
- node execution returns an explicit result containing resolved inputs, parameters, outputs, runtime values, warnings, and provenance.

External review rejected the first S3R packet as insufficient. The strengthened S3R acceptance additionally requires:

- runtime anchor discovery canonicalizes semantic identity and deduplicates by that semantic key;
- typed anchor outputs reject non-canonical producer-supplied IDs;
- list-backed frame signals require explicit frame IDs;
- predicate nodes execute from resolved input and parameter mappings;
- generic `persists_for` has one Boolean frame-signal path and does not inspect runtime records;
- legacy M1 persistence behavior is isolated behind named compatibility adapters;
- a non-M1 anchor produces engine-derived PASS and FAIL traces from declared runtime outputs.

S3R2 external review conditionally approved the direction but required S3R3 before S4. Additional acceptance:

- generic and legacy M1 parity execution are selected by host-only compatibility profile, not record shape;
- generic execution never invokes legacy adapters;
- generic target tracing never consumes `_runtime_result` or `_predicate_status`;
- `persists_for` has one shared generic temporal implementation used by runtime and tests;
- temporal output preserves UNKNOWN intervals;
- a non-M1 proof executes actual predicate nodes and produces PASS, FAIL, and UNKNOWN traces;
- perturbing candidates, accepted results, predicate traces, `_runtime_result`, and `_predicate_status` does not change generic target traces.

S3R3 external review conditionally approved the architecture but required S3R4 temporal correctness before S4. Additional acceptance:

- generic execution is the default compatibility profile;
- frozen M1 parity explicitly opts into legacy compatibility;
- typed persistence durations normalize `second`, `millisecond`, and `frame` units to equivalent frame counts;
- zero or negative persistence durations fail;
- `persists_for` distinguishes PASS, FAIL, and UNKNOWN intervals;
- anchors outside evaluated temporal coverage trace as UNKNOWN;
- `FrameSignal.unknown_mask` must agree with `None` values.

### Gate S4 - Rule-Driven Result Emission

Acceptance:

- classification rules, not terminal primitives, emit result inclusion and labels;
- changing a classification rule's predicate changes inclusion while keeping the same label set;
- a false required predicate prevents a result from being emitted;
- multiple-label behavior is explicit and deterministic;
- generic result ordering works without block-shift fields.

### Gate S5 - Alias-Based Evidence Projection

Acceptance:

- requested evidence uses stable aliases;
- node renaming preserves the entire public result, including requested evidence;
- evidence is resolved from declared runtime sources, not flat result dictionaries;
- rewiring an evidence request to another compatible source changes the value;
- query results do not include all hardcoded M1 evidence by default.

### Gate S6 - Second Real Plan And Relation Proof

Acceptance:

- a non-block-shift plan returns at least one real `QueryResult`;
- that plan uses generic classification rules;
- the plan produces results without `block_shift_score`, `wide_entry_frame_id`, or `signed_shift_metres`;
- a corridor relation executes from a non-M1 anchor set and produces relation episodes;
- every advertised capability has isolated positive, negative, and UNKNOWN fixtures.

### Gate S7 - Parity Adapter And Final Architecture Proof

Acceptance:

- M1 exact parity still passes, preferably through a dedicated M1 legacy-output adapter after generic execution;
- generic executor source contains no approved or experimental predicate IDs;
- generic executor source does not read undeclared node-output keys;
- deleting generated caches still reproduces results from canonical data;
- M1.1S external review packet is prepared and independently reviewed.

## Replacement Acceptance Tests

Before M1.2 begins, all of the following must pass:

1. A non-block-shift plan returns at least one real `QueryResult`.
2. The second plan uses generic classification rules. No terminal primitive writes `state.accepted`.
3. Changing a classification rule's predicate changes inclusion while keeping the same label.
4. A false required predicate prevents a result from being emitted.
5. Node renaming preserves the entire public result, including requested evidence.
6. Evidence is resolved from the declared source. Rewiring to another compatible source changes the value.
7. Every declared required input is actually consumed.
8. Runtime output mismatch fails.
9. An actual missing frame produces `UNKNOWN` end to end.
10. `persists_for` has one generic implementation.
11. A corridor relation executes from a non-M1 anchor set and produces relation episodes.
12. A simple plan can produce results without block-shift fields.
13. Generic result ordering works without block-shift fields.
14. The generic executor contains no approved or experimental predicate IDs.
15. The generic executor does not read undeclared node-output keys.
16. All advertised capabilities have isolated positive, negative, and UNKNOWN fixtures.
17. M1 exact parity still passes.

## Stop Conditions

Stop and request review if:

- preserving exact M1 parity requires keeping M1-specific side channels in the generic executor;
- the correction requires a universal DSL rather than bounded typed runtime contracts;
- a second result-producing plan cannot be created from existing primitives without new broad tactical scope;
- the implementation starts weakening M1.1S gates to preserve previous R5 claims.

## Reviewer Requirement

After M1.1S passes locally, package a new external review packet. M1.2 may begin only after the external decision is `APPROVE` or after required changes are integrated and independently re-reviewed.
