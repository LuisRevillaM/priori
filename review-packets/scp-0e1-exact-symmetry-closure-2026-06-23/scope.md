# Scope

## Included

- Commit: `bb3195b3c0538ba97d2a43f2241bb2735df0d295`
- Milestone: `SCP-0E.1 — Exact Symmetry Closure`
- Validator change: exact metadata comparison is symmetric for:
  - cardinality;
  - entity scope;
  - coordinate frame.
- Validator change: exact semantic optional inputs and outputs must be bound.
- Runtime-manifest change: generated runtime contexts are deep-copied before
  being returned.
- Registry change: original `geometric_progressive_corridor` anchors are
  declared possession-scoped.
- Verification updates:
  - metadata deletion tests;
  - runtime-context metadata deletion test;
  - optional semantic input/output omission test.
- Generated SCP-0 artifacts and delivery ledgers updated after verification.

## Excluded

- Runtime behavior changes.
- Hermes behavior changes.
- Workbench/UI behavior changes.
- Tactical capability additions.
- SCP-1 implementation.
- Broad SCP-0 redesign.

## Review Question

Does this patch close the specific blocker that exact conformance could still
pass after deleting runtime metadata or omitting semantic metadata/optional
semantic ports?
