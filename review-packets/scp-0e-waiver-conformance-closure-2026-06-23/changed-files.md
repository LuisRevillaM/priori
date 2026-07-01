# Changed Files

## Implementation

- `src/tqe/semantic_registry/models.py`
  - Adds typed runtime input/output bindings and pinned parity waiver model.
- `src/tqe/semantic_registry/generate.py`
  - Enforces bidirectional binding conformance, pinned waiver integrity, dependency-derived contract closure, and projection policy application.

## Registry and Generated Contracts

- `semantic-registry/registry.yaml`
  - Migrates runtime bindings to explicit bindings and declares pinned waivers and dependency-closed contracts.
- `semantic-registry/registry.lock.json`
  - Regenerated lock with SCP-0E registry state.
- `semantic-registry/schemas/semantic-registry.schema.json`
  - Regenerated schema reflecting new binding and waiver models.
- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `artifacts/scp-0/verification-report.json`

## Tests

- `tests/test_scp0_semantic_registry.py`
  - Adds/updates adversarial tests for the SCP-0E acceptance bullets.

## Delivery State

- `delivery/scp-0/SPEC.md`
- `delivery/scp-0/progress.md`
- `delivery/scp-0/status.yaml`
- `delivery/ledger.jsonl`
- `docs/learnings/2026-06-23-scp-0-semantic-registry.md`

## Excluded Dirty Files

The repository contains unrelated dirty/untracked files from prior work, visible in `commands/git-status-after-commit.txt`. They were intentionally not staged or committed for SCP-0E.

