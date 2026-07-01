# Changed Files

## Source

- `src/tqe/semantic_registry/models.py`
  - Adds `ParameterSpec`.
  - Adds `TypeRef.cardinality`.
  - Enforces `RuntimeInputBinding` source/target exclusivity.
- `src/tqe/semantic_registry/runtime_manifest.py`
  - Adds generated typed `runtime_contexts`.
- `src/tqe/semantic_registry/generate.py`
  - Resolves runtime-context refs.
  - Tightens exact field and parameter compatibility.
  - Validates uncovered declarations.
  - Rejects duplicate waivers.
  - Labels product recipe comparison as current-runtime alignment.

## Registry and Generated Artifacts

- `semantic-registry/registry.yaml`
- `semantic-registry/registry.lock.json`
- `semantic-registry/schemas/semantic-registry.schema.json`
- `generated/semantic-registry/runtime-manifest.json`
- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `artifacts/scp-0/verification-report.json`

## Tests

- `tests/test_scp0_semantic_registry.py`
  - Adds tests for every requested closure-patch mutation.

## Delivery State

- `delivery/scp-0/SPEC.md`
- `delivery/scp-0/progress.md`
- `delivery/scp-0/status.yaml`
- `delivery/ledger.jsonl`
- `docs/learnings/2026-06-23-scp-0-semantic-registry.md`

## Excluded Dirty Files

The repository still contains unrelated dirty/untracked files from prior work. See `commands/git-status-after-commit.txt`. They were intentionally not staged or committed.

