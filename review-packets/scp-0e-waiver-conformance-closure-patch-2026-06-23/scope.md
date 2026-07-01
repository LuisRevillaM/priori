# Scope

## Review Target

Small SCP-0E closure patch after the reviewer found remaining exactness and waiver-uniqueness gaps.

Source commit:

```text
fb8193a553939870fcda315b8399f31c6352f6b7
```

## In Scope

- Typed runtime-context manifest definitions.
- Runtime-context binding resolution and type compatibility.
- `RuntimeInputBinding` source/target exclusivity.
- Exact field conformance for unit, cardinality, entity scope, coordinate frame where declared, and runtime input requiredness.
- Exact parameter conformance for payload, unit, requiredness, minimum, maximum, default, and allowed values.
- Uncovered runtime/semantic declaration validation.
- Duplicate parity waiver validation.
- Product recipe parity wording/metadata.
- Focused adversarial tests for all requested mutations.
- Regenerated registry lock, schema, projections, parity report, and SCP-0 verification report.
- Delivery status/progress/ledger/learnings updates.

## Out Of Scope

- SCP-1 compiler implementation.
- New runtime capabilities.
- Runtime tactical behavior.
- Hermes behavior.
- Workbench UI.
- Deployment.
- Creating a new pinned product recipe baseline artifact.

## Stop Condition

Stop after local verification and an inspection packet are ready for external review. Do not claim SCP-1 unblocked until external review accepts.

