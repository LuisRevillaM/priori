# Workbench Alpha R1 Review Packet

packet_type: inspection_packet_only
created: 2026-06-22
source_repo: /Users/luisrevilla/Documents/priori
source_commit: 87b2441a626a67bd1222482f5be64e23e694a1f0
source_branch: codex/m1-1-s1-ir-binder
scope: Workbench Alpha R1 acceptance hardening

## Executive Summary

This packet packages the required Workbench Alpha R1 cleanup after external review. The implementation is committed as `87b2441a626a67bd1222482f5be64e23e694a1f0` and was verified again from a separate clean Git worktree at that same commit.

The work adds browser-level acceptance journeys, coordinate geometry and playback unit tests, generated host API schemas/types with runtime validation, replay race protection, public error/path hardening, and proof artifacts with source/build hashes. It does not implement S3 feedback/revision behavior, final visual polish, browser-to-MCP calls, a second tactical family, new primitives, or execution caching.

The clean proof run recorded Tactical Knowledge Pack hash `5bf10d06011c3c31cff18da6b02d30d6f68d6b15ed32ff99cd2646f3b865b6af` and empty clean/tracked Git status fields inside both proof JSON files.

## Review Map

| Area | Packet Path | Why It Matters |
| --- | --- | --- |
| Scope | `scope.md` | Defines the exact R1 acceptance scope and non-goals |
| Manifest | `MANIFEST.md` | Lists packaged files and why they are included |
| Validation | `validation-output.md` | Summarizes the clean proof run and test results |
| Commit patch | `diffs/commit-87b2441.patch` | Shows the isolated Workbench R1 implementation |
| Proof JSON | `artifacts/approved-proof.json`, `artifacts/experimental-proof.json` | Contains source commit, source/build hashes, TKP hash, replay payload hashes, and latency baselines |
| API traces | `api-traces/approved.json`, `api-traces/experimental.json` | Shows the real query, confirmation, execution, inspection, and replay route sequence |
| Browser report | `playwright-report/index.html` | Playwright HTML report with recordings in `playwright-report/data/` |
| Screenshots | `screenshots/` | Key UI states for interpretation, confirmation, result replay, timestamp inspection, and error/manual states |
| Contracts | `schemas/api-schemas.json`, `schemas/api-types.ts` | Generated response contracts used by runtime validation |
| App boundary | `docs/app-service-boundary.md` | Confirms `app_service.py` remains HTTP/orchestration, not primitive calculation |
| Performance plan | `docs/performance-cache-plan.md` | Records measured latency and cache/progress plan without implementing caching |

## What Is Real

- Query interpretation, validation, host confirmation, execution, result inspection, evidence aliases, predicate traces, and coordinate replay are exercised against the host application service. Proof: `api-traces/*.json`, `artifacts/*-proof.json`, `screenshots/*result-replay.png`.
- Execution cannot occur before host confirmation and the public API cannot mint authorization, choose a compatibility profile, execute unconfirmed plans, access local artifact paths, or invoke host-only operations. Proof: `tests/workbench-alpha.spec.ts`.
- Replay geometry derives from `replay.pitch.length_m` and `replay.pitch.width_m`; playback uses `replay.frame_rate_hz`. Proof: `source-excerpts/PitchCanvas.tsx`, `source-excerpts/pitchGeometry.ts`, `source-excerpts/playback.ts`, `tests/geometry.test.ts`, `tests/playback.test.ts`.
- API response contracts are generated from Pydantic models and enforced in the browser with AJV. Proof: `source-excerpts/app_service.py`, `source-excerpts/generate_contracts.py`, `source-excerpts/api.ts`, `schemas/`.

## What Is Fixture, Scenario, Generated, Or Local

- The proof uses local canonical match data available to the host service in the clean worktree. The packet is not self-contained for rerunning the service.
- Screenshots, videos, Playwright report, API traces, proof JSON, and schemas are generated local artifacts from the clean verification run.
- The app still runs in manual mode when model/Hermes access is unavailable; the packet does not claim model-backed planning availability.

## What Was Validated

| Command | Result | Evidence |
| --- | --- | --- |
| `make workbench-alpha-verify` in `/tmp/priori-workbench-r1-clean` | pass | `validation-output.md`, `artifacts/*-proof.json`, `playwright-report/index.html` |
| `npm run test:contracts` | pass inside acceptance command | `validation-output.md`, `schemas/` |
| `npm run test:fixtures` | pass inside acceptance command | `validation-output.md`, `tests/check-no-tactical-fixtures.mjs` |
| `npm run test:unit` | pass inside acceptance command | `tests/geometry.test.ts`, `tests/playback.test.ts` |
| `playwright test` | 5 passed | `playwright-report/index.html`, `videos/` |

## What This Packet Does Not Prove

- It does not prove a production deployment.
- It does not provide a self-contained rerunnable bundle; validation still requires the full repo, dependencies, and local canonical data.
- It does not implement execution caching, progress streaming, S3 revision behavior, final visual polish, a second tactical family, or new primitives.

## Reviewer Instructions

Start with:

1. `scope.md`
2. `changed-files.md`
3. `validation-output.md`
4. `diffs/commit-87b2441.patch`
5. `artifacts/approved-proof.json` and `artifacts/experimental-proof.json`
6. `playwright-report/index.html`

## Known Gaps

See `known-gaps.md`.
