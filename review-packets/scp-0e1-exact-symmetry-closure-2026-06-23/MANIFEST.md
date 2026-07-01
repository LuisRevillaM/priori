# Manifest

| Packet Path | Source | Class | Why Included |
| --- | --- | --- | --- |
| `README.md` | generated for packet | inspection_summary | Packet overview and review map |
| `scope.md` | generated for packet | inspection_summary | Defines included and excluded work |
| `changed-files.txt` | `git show --name-only HEAD` | command_output | Lists committed file surface |
| `validation-output.md` | generated for packet | command_output | Summarizes validation commands and results |
| `known-gaps.md` | generated for packet | inspection_summary | Records non-proofs and boundaries |
| `next-steps.md` | generated for packet | inspection_summary | Recommended path after review |
| `external-reference/decision-summary.md` | summarized from external decision | external_reference | Captures the blocker this patch addresses |
| `diffs/commit-stat.txt` | `git show --stat HEAD` | diff | Commit summary |
| `diffs/commit-full.patch` | `git show HEAD` | diff | Full patch |
| `commands/make-scp-0-verify.txt` | `make scp-0-verify` | command_output | Focused verifier output |
| `source/generate.py` | `src/tqe/semantic_registry/generate.py` | source_file | Exact conformance validator |
| `source/runtime_manifest.py` | `src/tqe/semantic_registry/runtime_manifest.py` | source_file | Runtime-context manifest generation |
| `source/test_scp0_semantic_registry.py` | `tests/test_scp0_semantic_registry.py` | test | Adversarial SCP-0 tests |
| `source/registry.yaml` | `semantic-registry/registry.yaml` | source_file | Semantic declarations and corridor scope |
| `generated/registry.lock.json` | `semantic-registry/registry.lock.json` | generated_report | Updated registry lock |
| `generated/semantic-parity-report.json` | `generated/semantic-registry/semantic-parity-report.json` | generated_report | Generated parity report |
| `generated/product-projection.json` | `generated/semantic-registry/product-projection.json` | generated_report | Product projection after patch |
| `generated/ai-projection.json` | `generated/semantic-registry/ai-projection.json` | generated_report | AI projection after patch |
| `artifacts/verification-report.json` | `artifacts/scp-0/verification-report.json` | runtime_artifact | SCP-0 verification report |
| `docs/SPEC.md` | `delivery/scp-0/SPEC.md` | documentation | Formal SCP-0 spec with SCP-0E.1 |
| `docs/status.yaml` | `delivery/scp-0/status.yaml` | documentation | Current milestone status |
| `docs/progress.md` | `delivery/scp-0/progress.md` | documentation | Progress ledger |
| `docs/learnings.md` | `docs/learnings/2026-06-23-scp-0-semantic-registry.md` | documentation | Durable learnings |
