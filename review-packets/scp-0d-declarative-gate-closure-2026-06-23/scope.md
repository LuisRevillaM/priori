# Scope

## Review Target

SCP-0D closes the narrow set of declarative integrity gaps identified after SCP-0C and before SCP-1:

1. `ProjectionPolicy.requires` must alter projection behavior.
2. Semantic parity must compare canonical baseline forms, not wrapper hashes.
3. Required baselines must be present and hash-pinned.
4. Recipe and composition contracts must preserve concept/profile claim and evidence lineage.
5. AI-origin provenance must hash the complete origin artifact and the normalized selected document separately.
6. Runtime signature validation must be bidirectional for exact bindings and explicit for partial bindings.
7. Failed generation must not overwrite valid projections.

## Included Source Inputs Requested By Reviewer

Five typed plans:

- `repo-files/config/query-plans/ball_side_block_shift.ir.v1.json`
- `repo-files/config/query-plans/possession_corridor_availability.experimental.v1.json`
- `repo-files/config/query-plans/opposite_corridor_after_shift.experimental.v1.json`
- `repo-files/config/query-plans/high_bypass_completed_pass.experimental.v1.json`
- `extracted/n1f-selected-typed-plan-from-origin-bundle.json`

AI-origin evidence:

- `repo-files/delivery/n1d/n1f-origin-bundle.json`

Baseline artifacts:

- `repo-files/generated/capability-catalog.json`
- `repo-files/generated/tactical-knowledge-pack.json`

## Included Implementation Surface

- Semantic registry models and generator.
- Runtime manifest bridge.
- Semantic registry source YAML, lock, and generated schema.
- Generated projections, runtime manifest, plan artifact index, and parity report.
- SCP-0 verification report and delivery status docs.
- Focused SCP-0 unit tests and full command logs.

## Out Of Scope

- SCP-1 executable algebra design or implementation.
- Workbench UI behavior.
- Cloud deployment.
- M2A/high-bypass runtime work.
- Unrelated N1C/N1D artifact dirtiness and existing untracked review packets.
