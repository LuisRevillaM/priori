# M1.1 Architecture Summary

## Boundary

M1.1 is a runtime milestone, not an AI or polished UI milestone.

It proves:

```text
RecipeDefinition
-> QueryInvocation
-> DraftQueryPlan
-> binder
-> BoundQueryPlan
-> executor
-> QueryExecution
-> predicate traces
-> evidence bundles
-> developer inspector
```

## Core Source Files

`src/tqe/runtime/ir.py`

- Defines strict Pydantic models for temporal containers, payload types, cardinality, units, entity scope, missing-data semantics, recipe definition, query invocation, draft plan, catalog entries, bound nodes, query results, predicate traces, and query execution.

`src/tqe/runtime/catalog.py`

- Defines default primitive, relation, and operator catalog entries.
- Includes typed outputs, limitations, missing-data semantics, evidence fields, and operator signatures.

`src/tqe/runtime/binder.py`

- Loads tactical query documents.
- Resolves draft plan references into bound catalog/predicate nodes.
- Rejects unknown references, invalid outputs, invalid operators, invalid units, cardinality mismatches, missing evidence fields, unsupported temporal references, unknown parameters, and complexity-limit violations.

`src/tqe/runtime/executor.py`

- Executes bound plans over the local canonical/raw corpus.
- Dispatches primitive, relation, and predicate implementations through catalogs of callables.
- Emits query execution objects, result rows, predicate traces, provenance, and replay references.
- Includes AST-gated checks that reject `if` branches on query/recipe/plan identity.

`src/tqe/runtime/relations.py`

- Implements `geometric_progressive_corridor`.
- Produces relation episodes, unknown/invalid controls, visual review cases, and SVG review artifacts.

`src/tqe/inspector/m1_1.py`

- Builds a direct-open static inspector under ignored local artifacts.
- Supports plan selection, validation summaries, result rows, coordinate replay, predicate traces, non-match inspection, replay-source links, and raw evidence.

## Plans Under Review

`config/query-plans/ball_side_block_shift.ir.v1.json`

- Approved M1 plan data.
- Used to prove parity with the frozen M1 baseline.

`config/query-plans/opposite_corridor_after_shift.experimental.v1.json`

- Experimental plan data.
- Composes M1 shift logic with `geometric_progressive_corridor` and `relation_destination_entry_classification`.
- Must remain experimental and must not claim causation, optimality, player intent, or missed opportunity.

## Main Architectural Claim

The implementation should let new tactical plans be represented as validated plan data over approved primitives and relations, without adding a new Python detector per query. The reviewer should inspect whether this claim is truly earned or only partly earned.
