# Scope

## Review Target

SCP-0E - Waiver and Conformance Closure.

Source commit:

```text
beea7dfe9e2af10473f613f30687d7454aed1b34
```

## Required Corrections Addressed

1. Real bidirectional runtime binding conformance.
2. Hash- and field-pinned parity waivers.
3. Dependency-derived recipe and composition contract closure.
4. Projection-policy application to AI operators and unsupported output.

## In Scope

- Semantic registry model/schema changes.
- Registry declaration migration to explicit input/output/parameter bindings.
- Runtime-context binding support.
- Exact, partial, and legacy runtime signature validation.
- Parity waiver schema and validation.
- Plan dependency contract derivation for recipes and compositions.
- Projection policy enforcement for AI operators and unsupported projection.
- Generated registry lock, projections, parity report, schema, and SCP-0 verification report.
- Focused adversarial tests for every external acceptance bullet.
- Delivery status/progress/learning/ledger updates.

## Out Of Scope

- SCP-1 algebra compiler implementation.
- Runtime tactical semantics.
- New football capabilities.
- Hermes prompt/config/runtime changes.
- Workbench UI changes.
- Deployment.
- Transactional hardening of generated artifact publication beyond the existing temporary-directory publish safety.

## Stop Condition

Stop after SCP-0E verifies locally and an inspection packet is ready for external review. Do not claim SCP-1 accepted until external review approves.

