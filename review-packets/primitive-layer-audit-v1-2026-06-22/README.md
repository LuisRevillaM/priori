# Primitive Layer Audit v1 External Review Packet

packet_type: inspection_packet_only
created: 2026-06-22
source_repo: /Users/luisrevilla/Documents/priori
source_commit: 464b9a80eaef584d1ffd6a23c5bd48987cc23f3a
source_branch: codex/m1-1-s1-ir-binder
scope: Primitive/lowering architecture audit artifacts and supporting evidence

## Executive Summary

This packet packages the Primitive & Lowering Audit v1 for review by an external agent without repository access. It includes the Markdown audit, the four generated JSON audit artifacts, relevant source-of-truth docs, runtime/catalog/source excerpts, schemas, query plans, tests, validators, and command evidence.

The audit verdict is `SUFFICIENT_WITH_TARGETED_ADDITIONS`: the deterministic primitive/IR foundation is sound enough to continue S2I and Workbench Alpha, but the second tactical family needs targeted additions such as defensive-line-relative position, lane occupancy, local numerical difference, support arrival, and pressure change.

This is not a standalone reproducible package. It does not include canonical tracking data, raw IDSSE files, runtime artifacts, virtual environments, dependency caches, or the full repository. Re-running runtime verification requires the full repo and local data.

## Review Map

| Area | Packet Path | Why It Matters |
| --- | --- | --- |
| Scope | `scope.md` | Defines what is included and excluded |
| Manifest | `MANIFEST.md` | Lists every packaged file and why it is included |
| Audit Report | `artifacts/audits/PRIMITIVE_LAYER_AUDIT_V1.md` | Main human-readable audit |
| Inventory | `artifacts/audits/primitive-inventory.json` | Capability inventory and layer classification |
| Dependency Graph | `artifacts/audits/primitive-dependency-graph.json` | Lowering/dependency graph |
| Coverage Matrix | `artifacts/audits/tactical-query-coverage-matrix.json` | 15-question tactical coverage assessment |
| Recommendations | `artifacts/audits/next-primitive-recommendations.json` | At-most-five next capabilities |
| Validation | `validation-output.md` | Commands run for this packet |
| Known Gaps | `known-gaps.md` | What this packet does not prove |

## What Is Real

- The audit artifacts were created in the source repo and copied into this packet. Proof: `artifacts/audits/`.
- The runtime catalog currently defines 6 primitives, 2 relations, and 8 operators. Proof: `source-excerpts/catalog.py`, `schemas/capability-context.json`, `commands/inventory-summary.txt`.
- The query IR includes typed nodes, predicates, anchors, requested evidence, complexity limits, classification rules, and unknown-evidence policies. Proof: `source-excerpts/ir.py`, `schemas/tactical-query-plan.schema.json`.
- The safe tool boundary and model/host split are implemented in source excerpts. Proof: `source-excerpts/m1_2.py`, `schemas/capability-context.json`.

## What Is Fixture, Generated, Or Local

- `schemas/tactical-knowledge-pack.json` and `.md` are generated knowledge-pack artifacts from the source repo.
- `artifacts/audits/*.json` are generated audit artifacts, not runtime verification outputs.
- `commands/*.txt` are local command outputs captured during packet assembly.
- Source files in `source-excerpts/`, `validators/`, and `tests/` are copied excerpts/full files, not a complete source tree. They reflect the working tree state at packet assembly time.

## What Was Validated

| Command | Result | Evidence |
| --- | --- | --- |
| `jq empty generated/audits/*.json` | pass | `commands/jq-audit-json-validation.txt` |
| `git rev-parse HEAD` | pass | `commands/git-rev-parse-head.txt` |
| `git branch --show-current` | pass | `commands/git-branch-current.txt` |
| `git status --short` | pass | `commands/git-status-short.txt` |
| packet secret scan | pass after scan | `commands/packet-secret-scan.txt` |

## What This Packet Does Not Prove

- It does not prove that the deterministic runtime can execute without the full repo and data.
- It does not include raw tracking data or replay artifacts.
- It does not prove future primitive implementations.
- It does not prove S2I/Hermes provisioning or Workbench Alpha UI readiness.
- It does not include every repository file that informed historical milestones.

## Reviewer Instructions

Start with:

1. `scope.md`
2. `artifacts/audits/PRIMITIVE_LAYER_AUDIT_V1.md`
3. `artifacts/audits/primitive-inventory.json`
4. `artifacts/audits/primitive-dependency-graph.json`
5. `validation-output.md`
6. `known-gaps.md`

Then inspect `source-excerpts/catalog.py`, `source-excerpts/executor.py`, `source-excerpts/relations.py`, `source-excerpts/ir.py`, `source-excerpts/m1_2.py`, and the three query plans under `config/query-plans/`.

## Workspace Note

The source worktree contained dirty/untracked files outside the audit deliverables, including `pyproject.toml`, `src/tqe/workshop/knowledge_pack.py`, `src/tqe/workshop/m1_2.py`, `src/tqe/workshop/mcp_server.py`, and many pre-existing untracked review packets. They were left untouched. Relevant workshop files copied into `source-excerpts/` reflect the working tree state; unrelated files are represented only through status evidence in `commands/git-status-short.txt`.
