# Changed Files

## Commit Delta

The SCP-0C commit changes 19 tracked files:

- `delivery/ledger.jsonl`
- `delivery/scp-0/SPEC.md`
- `delivery/scp-0/progress.md`
- `delivery/scp-0/status.yaml`
- `docs/learnings/2026-06-23-scp-0-semantic-registry.md`
- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/plan-artifact-index.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/runtime-manifest.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `semantic-registry/registry.lock.json`
- `semantic-registry/registry.yaml`
- `src/tqe/semantic_registry/generate.py`
- `src/tqe/semantic_registry/models.py`
- `src/tqe/semantic_registry/runtime_manifest.py`
- `tests/test_scp0_semantic_registry.py`

See `commands/git-show-head-name-status.txt` and `diffs/head-commit-scp0c.diff`.

## Implementation Files To Inspect First

- `repo-files/src/tqe/semantic_registry/generate.py`
  - projection policy execution;
  - plan artifact parsing;
  - plan/recipe/composition integrity checks;
  - generic pilot graph traversal;
  - parity baseline comparison.

- `repo-files/src/tqe/semantic_registry/runtime_manifest.py`
  - runtime manifest extension;
  - plan manifest payload extraction;
  - parameter/default/operator dependency capture.

- `repo-files/src/tqe/semantic_registry/models.py`
  - `RegistryLock.plan_artifact_revision`.

- `repo-files/tests/test_scp0_semantic_registry.py`
  - focused adversarial tests for the previously identified gaps.

## Registry/Artifact Files To Inspect

- `repo-files/semantic-registry/registry.yaml`
- `repo-files/semantic-registry/registry.lock.json`
- `repo-files/generated/semantic-registry/plan-artifact-index.json`
- `repo-files/generated/semantic-registry/semantic-parity-report.json`
- `repo-files/generated/semantic-registry/product-projection.json`
- `repo-files/generated/semantic-registry/ai-projection.json`
- `repo-files/artifacts/scp-0/verification-report.json`

## Delivery Files To Inspect

- `repo-files/delivery/scp-0/SPEC.md`
- `repo-files/delivery/scp-0/status.yaml`
- `repo-files/delivery/scp-0/progress.md`
- `repo-files/docs/learnings/2026-06-23-scp-0-semantic-registry.md`

