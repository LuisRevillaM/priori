# Manifest

| Packet path | Source | Why included | Class |
|---|---|---|---|
| `README.md` | generated | packet orientation | inspection_summary |
| `scope.md` | generated | review scope | inspection_summary |
| `changed-files.md` | generated | changed-file inventory | inspection_summary |
| `validation-output.md` | generated | command and sealed score summary | command_output |
| `known-gaps.md` | generated | explicit blockers | inspection_summary |
| `next-steps.md` | generated | reviewer decision options | inspection_summary |
| `config/m1_2_s2d_sealed_prompt_set.json` | `config/evaluation/m1_2_s2d_sealed_prompt_set.json` | sealed prompt set | fixture |
| `artifacts/agent-sealed-evaluation-report.json` | `artifacts/m1.2/agent-sealed-evaluation-report.json` | sealed run rows/scores | generated_report |
| `artifacts/gate-s2-verification-report.json` | `artifacts/m1.2/gate-s2-verification-report.json` | focused gate report | generated_report |
| `artifacts/hermes-s2-trace-report.json` | `artifacts/m1.2/hermes-s2-trace-report.json` | trace/sealed-run index | generated_report |
| `artifacts/agent-evaluation-report.json` | `artifacts/m1.2/agent-evaluation-report.json` | visible regression comparison | generated_report |
| `artifacts/agent-heldout-evaluation-report.json` | `artifacts/m1.2/agent-blind-evaluation-report.json` | held-out regression comparison | generated_report |
| `docs/2026-06-21-m1-2-s2d-sealed-run.md` | `docs/reviews/2026-06-21-m1-2-s2d-sealed-run.md` | controller sealed-run assessment | documentation |
| `docs/delivery-m1.2-status.yaml` | `delivery/m1.2/status.yaml` | current milestone state | documentation |
| `docs/delivery-m1.2-SPEC.md` | `delivery/m1.2/SPEC.md` | source-of-truth spec | documentation |
| `docs/delivery-ledger.jsonl` | `delivery/ledger.jsonl` | progress ledger | documentation |
| `source-files/src-tqe-workshop-hermes_s2.py` | `src/tqe/workshop/hermes_s2.py` | compiler source | source_file |
| `source-files/src-tqe-verification-m1_2_gate_s2.py` | `src/tqe/verification/m1_2_gate_s2.py` | verifier source | validator |
| `diffs/s2d-provenance-commit.patch` | `git show 8a87380` | provenance implementation patch | diff |
| `diffs/sealed-run-commit.patch` | `git show 9077249` | sealed evidence patch | diff |
| `commands/report-summary.txt` | generated from JSON reports | compact failure summary | command_output |
| `commands/git-head.txt` | `git rev-parse HEAD` | current commit | command_output |
| `commands/git-status-short.txt` | `git status --short` | worktree context | command_output |
