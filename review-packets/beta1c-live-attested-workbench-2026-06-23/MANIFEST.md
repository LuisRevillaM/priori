# Manifest

This packet is an `inspection_packet_only`.

## Source Files

- `source-excerpts/Dockerfile` <- `Dockerfile` (`source_file`): runtime image artifact copy list.
- `source-excerpts/app_service.py` <- `src/tqe/workshop/app_service.py` (`source_file`): backend Workbench routes, provenance, attestation gate.
- `source-excerpts/executor.py` <- `src/tqe/runtime/executor.py` (`source_file`): runtime evidence projection changes.
- `source-excerpts/n1d.py` <- `src/tqe/verification/n1d.py` (`validator`): N1D freeze/manifest verifier.
- `source-excerpts/n1d1.py` <- `src/tqe/verification/n1d1.py` (`validator`): N1D.1 attestation verifier.
- `source-excerpts/App.tsx` <- `apps/workbench-alpha/src/App.tsx` (`source_file`): Workbench UI.
- `source-excerpts/workbenchState.ts` <- `apps/workbench-alpha/src/workbenchState.ts` (`source_file`): frontend state machine.
- `source-excerpts/presentation.ts` <- `apps/workbench-alpha/src/presentation.ts` (`source_file`): provenance and entry-mode presentation helpers.
- `source-excerpts/types.ts` <- `apps/workbench-alpha/src/types.ts` (`schema`): frontend response types.
- `tests/test_workbench_beta0_contract.py` <- `tests/test_workbench_beta0_contract.py` (`test`): backend contract tests.

## Proof Artifacts

- `artifacts/n1d1-attestation.json` <- `delivery/n1d/n1d1-attestation.json` (`runtime_artifact`): verified N1D.1 attestation.
- `artifacts/n1d-canonical-freeze-manifest.json` <- `delivery/n1d/n1d-canonical-freeze-manifest.json` (`runtime_artifact`): pinned N1D manifest.
- `artifacts/n1f-origin-bundle.json` <- `delivery/n1d/n1f-origin-bundle.json` (`runtime_artifact`): Hermes-origin bundle with submitted draft and host pipeline.
- `docs/N1I_REPORT.md` <- `delivery/n1d/N1I_REPORT.md` (`generated_report`): N1I proof report.

## Diffs And Commands

- `diffs/beta1c-implementation.diff` (`diff`): implementation diff across reviewed files.
- `commands/git-log.txt` (`command_output`): recent commit log.
- `commands/git-status-short.txt` (`command_output`): working tree status at packet assembly.
- `commands/git-show-*.txt` (`command_output`): commit-level stats.
- `commands/backend-contract-tests.txt` (`command_output`): backend test output.
- `commands/n1-proof-gates.txt` (`command_output`): N1D/N1D.1/N1I gate output.
- `commands/workbench-acceptance-summary.txt` (`command_output`): Workbench acceptance summary.
- `commands/artifact-sha256s.txt` (`command_output`): SHA-256 checksums for copied proof artifacts and live smoke response.

## Live Route Evidence

- `route-smokes/live-beta1c-smoke.json` (`route_response`): public deployed API smoke covering health, interpretation, validation, confirmation, execution, and replay inspection.

## Packet Summaries

- `README.md` (`inspection_summary`)
- `scope.md` (`inspection_summary`)
- `changed-files.md` (`inspection_summary`)
- `validation-output.md` (`inspection_summary`)
- `known-gaps.md` (`inspection_summary`)
- `next-steps.md` (`inspection_summary`)
