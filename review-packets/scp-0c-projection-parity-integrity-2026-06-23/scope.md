# Scope

## Target Commit

`6c6a5d81b4e21d21849befb92d3711526268145c`

Commit subject:

`Harden SCP-0 projection parity integrity`

## Prior External Decision Addressed

`APPROVE_WITH_REQUIRED_CHANGES_BEFORE_SCP_1`

The prior review approved the architectural direction but required proof that the registry layer was not decorative. SCP-0C addresses those required changes by making projection policy, parity reporting, plan integrity, and semantic graph traversal executable.

## Included Review Surface

- Semantic registry schema/model additions.
- Runtime manifest generation and plan artifact extraction.
- Registry generation and validation rules.
- Registry YAML policy/maturity/exposure/domain wording updates.
- Generated registry lock and projection artifacts.
- SCP delivery docs and verification report.
- Focused SCP-0 unit/adversarial tests.

## Out Of Scope

- Runtime query execution behavior.
- Workbench UI.
- Hermes prompts, MCP behavior, frontier model behavior, or deployed Render services.
- New tactical primitives or recipes.
- Research atlas productization.
- SCP-1 implementation.

## Main Acceptance Boundary

SCP-0C may be accepted if the reviewer agrees that:

1. Projection policies are actually enforced.
2. Product/AI projections no longer leak ungated or atlas-only entries.
3. Parity reports compute actual differences rather than hard-coded empty deltas.
4. Plan content affects the registry lock.
5. Recipe and composition plan artifacts are parsed and checked against registry declarations.
6. Pilot reports are produced through generic semantic graph traversal.
7. Runtime/operator signatures and transitive claim/evidence rules are checked by tests.

