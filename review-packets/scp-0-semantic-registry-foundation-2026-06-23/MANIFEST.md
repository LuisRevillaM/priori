# Manifest

| Packet Path | Source | Class | Why Included |
| --- | --- | --- | --- |
| `README.md` | generated for packet | inspection_summary | Packet overview and review question. |
| `scope.md` | generated for packet | inspection_summary | Defines in-scope and out-of-scope work. |
| `changed-files.md` | generated for packet | inspection_summary | Explains SCP files, touched existing files, and unrelated worktree noise. |
| `validation-output.md` | generated for packet | command_output | Summarizes validation commands and results. |
| `known-gaps.md` | generated for packet | inspection_summary | Records limitations and boundaries. |
| `next-steps.md` | generated for packet | inspection_summary | Gives post-review paths. |
| `commands/git-branch-current.txt` | `git branch --show-current` | command_output | Branch context. |
| `commands/git-diff-stat.txt` | `git diff --stat` | command_output | Tracked diff context. |
| `commands/git-rev-parse-head.txt` | `git rev-parse HEAD` | command_output | Base HEAD context. |
| `commands/git-show-head-stat.txt` | `git show --stat --oneline HEAD` | command_output | SCP-0 commit summary. |
| `commands/git-status-short.txt` | `git status --short` | command_output | Full dirty worktree context. |
| `commands/make-scp-0-verify.txt` | `make scp-0-verify` | command_output | Focused SCP verification transcript. |
| `diffs/head-commit-scp0.diff` | `git show HEAD -- <SCP paths>` | diff | SCP-0 committed implementation patch. |
| `diffs/scp0-untracked-file-list.txt` | `git ls-files --others ...` | diff | SCP-0 untracked file inventory. |
| `diffs/tracked-scp0-and-generated-catalog.diff` | pre-commit scoped `git diff` | diff | Historical pre-commit tracked SCP and generated-catalog diff retained for inspection. |
| `repo-files/Makefile` | `Makefile` | source_file | Shows `scp-0-verify` target. |
| `repo-files/delivery/ledger.jsonl` | `delivery/ledger.jsonl` | documentation | Durable delivery ledger entries. |
| `repo-files/delivery/scp-0/SPEC.md` | `delivery/scp-0/SPEC.md` | documentation | SCP-0 source-of-truth spec. |
| `repo-files/delivery/scp-0/progress.md` | `delivery/scp-0/progress.md` | documentation | Slice progress ledger. |
| `repo-files/delivery/scp-0/status.yaml` | `delivery/scp-0/status.yaml` | documentation | Current milestone state and evidence. |
| `repo-files/docs/learnings/2026-06-23-scp-0-semantic-registry.md` | `docs/learnings/2026-06-23-scp-0-semantic-registry.md` | documentation | Implementation learnings and follow-ups. |
| `repo-files/generated/capability-catalog.json` | `generated/capability-catalog.json` | runtime_artifact | Existing generated catalog refreshed for full-suite green. |
| `repo-files/src/tqe/semantic_registry/__init__.py` | `src/tqe/semantic_registry/__init__.py` | source_file | Package marker. |
| `repo-files/src/tqe/semantic_registry/models.py` | `src/tqe/semantic_registry/models.py` | source_file | Semantic registry schema models. |
| `repo-files/src/tqe/semantic_registry/runtime_manifest.py` | `src/tqe/semantic_registry/runtime_manifest.py` | source_file | Runtime manifest generation. |
| `repo-files/src/tqe/semantic_registry/generate.py` | `src/tqe/semantic_registry/generate.py` | source_file | Registry validation, projection, lock, and report generation. |
| `repo-files/src/tqe/verification/scp0.py` | `src/tqe/verification/scp0.py` | validator | SCP-0 verification entrypoint. |
| `repo-files/tests/test_scp0_semantic_registry.py` | `tests/test_scp0_semantic_registry.py` | test | Focused adversarial tests. |
| `repo-files/semantic-registry/registry.yaml` | `semantic-registry/registry.yaml` | source_file | Current semantic registry source. |
| `repo-files/semantic-registry/registry.lock.json` | `semantic-registry/registry.lock.json` | generated_report | Registry/runtime/projection lock. |
| `repo-files/semantic-registry/schemas/semantic-registry.schema.json` | `semantic-registry/schemas/semantic-registry.schema.json` | schema | Generated JSON schema. |
| `repo-files/semantic-registry/atlas/raw/five_year_capability_manifest.yaml` | `semantic-registry/atlas/raw/five_year_capability_manifest.yaml` | external_reference | Raw proposed atlas input. |
| `repo-files/generated/semantic-registry/runtime-manifest.json` | `generated/semantic-registry/runtime-manifest.json` | generated_report | Executable runtime truth manifest. |
| `repo-files/generated/semantic-registry/product-projection.json` | `generated/semantic-registry/product-projection.json` | generated_report | Product-supported projection. |
| `repo-files/generated/semantic-registry/ai-projection.json` | `generated/semantic-registry/ai-projection.json` | generated_report | AI-authorable/reviewed-plan-only projection. |
| `repo-files/generated/semantic-registry/recipe-library-projection.json` | `generated/semantic-registry/recipe-library-projection.json` | generated_report | Registered recipe projection. |
| `repo-files/generated/semantic-registry/unsupported-capability-projection.json` | `generated/semantic-registry/unsupported-capability-projection.json` | generated_report | Denied/unsupported capability projection. |
| `repo-files/generated/semantic-registry/research-atlas-projection.json` | `generated/semantic-registry/research-atlas-projection.json` | generated_report | Proposed atlas research projection. |
| `repo-files/generated/semantic-registry/semantic-parity-report.json` | `generated/semantic-registry/semantic-parity-report.json` | generated_report | Main parity report. |
| `repo-files/artifacts/scp-0/verification-report.json` | `artifacts/scp-0/verification-report.json` | generated_report | Verification report produced by `make scp-0-verify`. |
