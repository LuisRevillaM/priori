# Manifest

| Packet path | Source | Why included | Class |
|---|---|---|---|
| `README.md` | generated | packet orientation | inspection_summary |
| `scope.md` | generated | review scope and non-goals | inspection_summary |
| `changed-files.md` | generated | changed-file inventory | inspection_summary |
| `validation-output.md` | generated | command evidence summary | command_output |
| `known-gaps.md` | generated | explicit limits | inspection_summary |
| `next-steps.md` | generated | requested review outcome | inspection_summary |
| `diffs/commit-stat.txt` | `git show --stat --oneline 6636dc4` | commit summary | diff |
| `diffs/commit.patch` | `git show --format=fuller --stat --patch 6636dc4` | full reviewed patch | diff |
| `commands/git-status-short.txt` | `git status --short` | worktree context | command_output |
| `commands/git-diff-check.txt` | `git diff --check` | whitespace check output | command_output |
| `source-files/src-tqe-workshop-hermes_s2.py` | `src/tqe/workshop/hermes_s2.py` | compiler implementation | source_file |
| `source-files/src-tqe-verification-m1_2_gate_s2.py` | `src/tqe/verification/m1_2_gate_s2.py` | S2 verifier | validator |
| `config/m1_2_s2c_blind_corpus.json` | `config/evaluation/m1_2_s2c_blind_corpus.json` | blind corpus source | fixture |
| `docs/delivery-m1.2-SPEC.md` | `delivery/m1.2/SPEC.md` | source-of-truth spec | documentation |
| `docs/delivery-m1.2-status.yaml` | `delivery/m1.2/status.yaml` | milestone state | documentation |
| `docs/delivery-ledger.jsonl` | `delivery/ledger.jsonl` | progress ledger | documentation |
| `docs/2026-06-21-m1-2-s2c-external-review.md` | `docs/reviews/...` | review integration note | documentation |
| `docs/2026-06-21-m1-2-s2c-agent-identity-strict-eval.md` | `docs/learnings/...` | durable learning | documentation |
| `artifacts/gate-s2-verification-report.json` | `artifacts/m1.2/gate-s2-verification-report.json` | focused gate proof | generated_report |
| `artifacts/agent-evaluation-corpus.json` | `artifacts/m1.2/agent-evaluation-corpus.json` | visible corpus artifact | runtime_artifact |
| `artifacts/agent-evaluation-report.json` | `artifacts/m1.2/agent-evaluation-report.json` | visible scoring report | generated_report |
| `artifacts/agent-blind-evaluation-corpus.json` | `artifacts/m1.2/agent-blind-evaluation-corpus.json` | copied blind corpus artifact | runtime_artifact |
| `artifacts/agent-blind-evaluation-report.json` | `artifacts/m1.2/agent-blind-evaluation-report.json` | blind scoring report | generated_report |
| `artifacts/hermes-s2-trace-report.json` | `artifacts/m1.2/hermes-s2-trace-report.json` | trace index | generated_report |
| `artifacts/hermes-traces/*.json` | `artifacts/m1.2/workshop/hermes-traces/*.json` | referenced compile/execution traces | runtime_artifact |
| `artifacts/m1.2-verification-report.json` | `artifacts/m1.2/verification-report.json` | aggregate proof | generated_report |
| `artifacts/m1.1-gate-s7r-verification-report.json` | `artifacts/m1.1/gate-s7r-verification-report.json` | M1.1 regression proof | generated_report |
