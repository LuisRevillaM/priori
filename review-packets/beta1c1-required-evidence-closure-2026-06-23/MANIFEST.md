# Manifest

| Packet Path | Source | Why Included | Class |
|---|---|---|---|
| `README.md` | generated packet summary | reviewer entry point | inspection_summary |
| `scope.md` | generated packet summary | review scope and assumptions | inspection_summary |
| `changed-files.md` | generated packet summary | changed-file inventory | inspection_summary |
| `validation-output.md` | generated packet summary | verification commands and results | command_output |
| `known-gaps.md` | generated packet summary | limitations and residual risk | inspection_summary |
| `next-steps.md` | generated packet summary | recommended next action | inspection_summary |
| `docs/BETA_1C_1_REQUIRED_EVIDENCE_REPORT.md` | `delivery/n1d/BETA_1C_1_REQUIRED_EVIDENCE_REPORT.md` | controller report | documentation |
| `artifacts/n1d-canonical-freeze-manifest.json` | `delivery/n1d/n1d-canonical-freeze-manifest.json` | N1D pinned identity | runtime_artifact |
| `artifacts/n1d1-attestation.json` | `delivery/n1d/n1d1-attestation.json` | N1D.1 attestation | runtime_artifact |
| `artifacts/n1f-origin-bundle.json` | `delivery/n1d/n1f-origin-bundle.json` | Hermes-origin bundle with refreshed host pipeline | runtime_artifact |
| `artifacts/tactical-knowledge-pack.json` | `generated/tactical-knowledge-pack.json` | regenerated model/tool contract | generated_report |
| `artifacts/capability-context.json` | `generated/capability-context.json` | regenerated capability context | generated_report |
| `artifacts/gate-s2i-verification-report.json` | `artifacts/m1.2/gate-s2i-verification-report.json` | knowledge-pack verification | generated_report |
| `route-smokes/live-hero-smoke.json` | live API smoke | deployed hero proof | route_response |
| `route-smokes/live-cache-hit-smoke.json` | live API smoke | corrected cache proof | route_response |
| `diffs/cf5b058-focused.diff` | `git show cf5b058 ...` | focused implementation diff | diff |
| `diffs/cf5b058-stat.txt` | `git show --stat --oneline cf5b058` | corrective commit stat | diff |
| `diffs/630b2b8-render-pin.diff` | `git show 630b2b8 -- .codex/render-target.json` | readiness pin diff | diff |
| `diffs/630b2b8-stat.txt` | `git show --stat --oneline 630b2b8` | deployment pin commit stat | diff |
| `commands/git-head-stat.txt` | `git show --stat --oneline HEAD` | current commit summary | command_output |
| `commands/git-status-short-after-packet.txt` | `git status --short` | worktree context at packet time | command_output |
| `source-files/m1_2.py` | `src/tqe/workshop/m1_2.py` | execution response contract | source_file |
| `source-files/app_service.py` | `src/tqe/workshop/app_service.py` | cache identity and API route path | source_file |
| `source-files/n1d.py` | `src/tqe/verification/n1d.py` | required-evidence gate | source_file |
| `source-files/n1d1.py` | `src/tqe/verification/n1d1.py` | attestation gate | source_file |
| `source-files/test_workbench_beta0_contract.py` | `tests/test_workbench_beta0_contract.py` | regression test | test |
| `source-files/workbench-App.tsx` | `apps/workbench-alpha/src/App.tsx` | UI completeness warning and copy | source_file |
| `source-files/workbench-presentation.ts` | `apps/workbench-alpha/src/presentation.ts` | provenance label mapper | source_file |
| `source-files/workbench-types.ts` | `apps/workbench-alpha/src/types.ts` | frontend execution response type | source_file |
