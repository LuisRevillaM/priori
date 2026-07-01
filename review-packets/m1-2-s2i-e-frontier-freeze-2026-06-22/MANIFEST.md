# Manifest

| Packet Path | Source | Why Included | Class |
| --- | --- | --- | --- |
| `README.md` | generated for packet | Entry point and review map | inspection_summary |
| `scope.md` | generated for packet | Defines review boundaries | inspection_summary |
| `validation-output.md` | generated for packet | Summarizes local verification | command_output |
| `known-gaps.md` | generated for packet | Lists blockers and non-claims | inspection_summary |
| `next-steps.md` | generated for packet | Recommends review/evaluation flow | inspection_summary |
| `external-reviewer-prompt.md` | generated for packet | Relay-ready prompt for external agent | inspection_summary |
| `changed-files.md` | generated for packet | Lists files changed in the S2I-E commit | inspection_summary |
| `artifacts/frontier-runtime-freeze.json` | `delivery/m1.2/frontier-runtime-freeze.json` | Frozen route artifact | runtime_artifact |
| `artifacts/s2i-e-frontier-freeze-report.json` | `artifacts/m1.2/s2i-e-frontier-freeze-report.json` | S2I-E verifier report | generated_report |
| `artifacts/s2i-d-unseeded-hermes-report.json` | `artifacts/m1.2/s2i-d-unseeded-hermes-report.json` | Live Hermes authoring proof | generated_report |
| `artifacts/gate-s2i-verification-report.json` | `artifacts/m1.2/gate-s2i-verification-report.json` | Knowledge-pack verification | generated_report |
| `source-excerpts/m1_2_gate_s2ie.py` | `src/tqe/verification/m1_2_gate_s2ie.py` | Freeze verifier source | validator |
| `source-excerpts/m1_2_gate_s2id.py` | `src/tqe/verification/m1_2_gate_s2id.py` | Durable live-session verifier source | validator |
| `source-excerpts/Makefile` | `Makefile` | Make target definitions | source_file |
| `docs/CURRENT_STATE.md` | `CURRENT_STATE.md` | Current source-of-truth snapshot | documentation |
| `docs/status.yaml` | `delivery/m1.2/status.yaml` | Formal milestone state | documentation |
| `docs/local-review-2026-06-22-m1-2-s2i-e-frontier-freeze.md` | `docs/reviews/2026-06-22-m1-2-s2i-e-frontier-freeze.md` | Local controller review | documentation |
| `docs/learning-2026-06-22-m1-2-s2i-e-frontier-freeze.md` | `docs/learnings/2026-06-22-m1-2-s2i-e-frontier-freeze.md` | Learning note | documentation |
| `generated/capability-context.json` | `generated/capability-context.json` | Hermes-safe capability context | schema |
| `generated/tactical-knowledge-pack.md` | `generated/tactical-knowledge-pack.md` | Human-readable knowledge pack | documentation |
| `diffs/93ba710-freeze-frontier-hermes-configuration.patch` | `git format-patch -1 93ba710` | Exact S2I-E commit patch | diff |
| `commands/git-show-93ba710-stat.txt` | `git show --stat --oneline 93ba710` | Commit stat evidence | command_output |
| `commands/repo-state-at-packet-build.txt` | `git rev-parse HEAD`, branch, status | Build-time repo state | command_output |
