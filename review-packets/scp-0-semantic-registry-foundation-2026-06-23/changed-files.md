# Changed Files

## SCP-0 Files Included For Review

- `delivery/scp-0/SPEC.md`
- `delivery/scp-0/status.yaml`
- `delivery/scp-0/progress.md`
- `docs/learnings/2026-06-23-scp-0-semantic-registry.md`
- `semantic-registry/registry.yaml`
- `semantic-registry/registry.lock.json`
- `semantic-registry/schemas/semantic-registry.schema.json`
- `semantic-registry/atlas/raw/five_year_capability_manifest.yaml`
- `generated/semantic-registry/runtime-manifest.json`
- `generated/semantic-registry/product-projection.json`
- `generated/semantic-registry/ai-projection.json`
- `generated/semantic-registry/recipe-library-projection.json`
- `generated/semantic-registry/unsupported-capability-projection.json`
- `generated/semantic-registry/research-atlas-projection.json`
- `generated/semantic-registry/semantic-parity-report.json`
- `artifacts/scp-0/verification-report.json`
- `src/tqe/semantic_registry/__init__.py`
- `src/tqe/semantic_registry/models.py`
- `src/tqe/semantic_registry/runtime_manifest.py`
- `src/tqe/semantic_registry/generate.py`
- `src/tqe/verification/scp0.py`
- `tests/test_scp0_semantic_registry.py`

## Existing Project Files Touched For SCP-0

- `Makefile`: adds `scp-0-verify`.
- `delivery/ledger.jsonl`: records SCP-0 start, implementation, and verification closeout.
- `generated/capability-catalog.json`: refreshed through `make m1-1-build` after the broader suite detected stale generated contract drift.

## Unrelated Dirty Files Present In The Working Tree

These were present from other work and are not part of SCP-0 review:

- `artifacts/n1c/n1c-canonical-freeze-manifest.json`
- `artifacts/n1c/n1c-verification-report.json`
- `delivery/n1d/N1I_REPORT.md`
- pre-existing audit, review-packet, scratch, and test-result files listed in `commands/git-status-short.txt`.

The packet includes `commands/git-status-short.txt` so the reviewer can see the full worktree context.
