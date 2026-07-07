# DEPLOY-1 Report

Status: DELIVERED with evidence.

Branch: `packet/deploy-1`

Implementation commits:

- `c1bbb31` Implement DEPLOY-1 public Film Room
- `c4c47e9` / `3d96983` / `e3c093a` / `51f176c` / `c8921b0`: committed evidence-producer mechanics
- `cb4cf97` Bound public Film Room ask latency
- `2978bd3` Keep DEPLOY-1 evidence scratch out of packet

## Root Cause

The deploy surface had gallery and live-ask concerns coupled together: startup Film Room prewarm could block service bind, and the existing demo-token helper guarded the whole app instead of only public live asks. A public deploy also needed typed degradation when Hermes/auth is unavailable, plus a bounded response when a live ask is accepted but the model/synthesis/execution path does not complete inside the public smoke window.

## Changes

- Bind-before-warm: `WorkbenchServer` now binds before Film Room prewarm starts; prewarm runs in a daemon thread. `/api/film-room/bootstrap` returns `state: "warming"` with item status until prewarmed content is ready, and returns top-level `answer`/`provenance` when ready.
- UI warming: Film Room renders the bootstrap warming state and polls until ready instead of showing an indefinite generic load.
- Public live-ask gate: under `TQE_PUBLIC_MODE=1`, only `/api/film-room/ask` requires the demo token. Missing token returns typed `DEMO_TOKEN_REQUIRED`; gallery, bootstrap, and replay routes remain public.
- Hermes degradation: public asks return typed `ASKS_DISABLED` when Hermes is disabled, missing, or lacks auth. Accepted public asks are bounded by `TQE_PUBLIC_ASK_TIMEOUT_SECONDS` and return typed `INTERNAL_ERROR` with a correlation id on timeout.
- Render blueprint: `render.yaml` now defines `entrelineas-film-room`, health check `/film-room`, 10GB disk, public-mode env, cache roots, execution workers, and Hermes secret-file path `/etc/secrets/hermes/auth.json`.
- Demo bundle provisioning: bundle creation can include warmed cache/runtime artifacts; provisioning verifies per-scope manifest entries under dataset/cache/runtime roots and exits nonzero on mismatches.
- RB-001: owner steps updated for warmed bundle env vars and the exact Hermes secret-file path.

## Oracle Evidence

Final R-AZ run:

- JSON: `delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c/deploy1-evidence.json`
- Markdown: `delivery/packets/deploy-1-evidence/runs/2026-07-07T195358Z00000000-055df6fd620c/deploy1-evidence.md`
- Producer: `src/tqe/verification/deploy1_evidence.py`
- Producer SHA-256: `055df6fd620c63fa88fa432821ada184c68e3ece835e65ed1741c9eb6e98cc86`
- Oracle SHA-256: `9aead6611095a41c9ddcf9b7525dd8fcb85c186d20add691a7f6dbbc5e4b8f3f`
- Evidence commit/tree at run: `2978bd3e1fd515e023b3126801bbc6925c9d4ff5` / `967754322adebe301b0dfff97f664ee67c450263`

| Oracle mode | Status | Duration ms | Billing |
| --- | --- | ---: | --- |
| Public without token | PASS | 75.066 | No model call expected; gate answered before Hermes. |
| Public with token | PASS | 120204.815 | Subscription-billed Hermes path; typed timeout response accepted by oracle. |

Cache provenance: the local public-mode service used run-local `TQE_RUNTIME_ROOT`, `TQE_CACHE_ROOT`, and `TQE_NODE_CACHE_ROOT` under `/private/tmp/deploy1-evidence-scratch/2026-07-07T195358Z00000000-055df6fd620c`. No persistent local cache was reused.

## Failed Evidence Runs Disclosed

- `2026-07-07T191718Z...` and `2026-07-07T191816Z...`: pre-final Python producer attempts failed before a valid evidence payload because raw/in-process port probing was denied by the sandbox.
- `2026-07-07T191957Z...` and `2026-07-07T192109Z...`: Python producer wrote self-stamped FAIL payloads; child service bind was denied from that producer context.
- `2026-07-07T192307Z...` and `2026-07-07T192321Z...`: shell producer attempts stopped after focused-test bind denial in nested script context.
- `2026-07-07T192513Z...`: in-process producer ran the oracle; without-token passed, with-token timed out at 600216.073 ms. This exposed the public ask timeout defect fixed in `cb4cf97`.

Bulky uncommitted service cache/runtime scratch from failed attempts was removed before staging; retained evidence is the compact script output, oracle output, logs, and self-stamped JSON/Markdown.

## Verification Table

| Check | Status | Notes |
| --- | --- | --- |
| DEPLOY-1 R-AZ oracle evidence | PASS | Both committed oracle modes passed locally against public-mode service. |
| DEPLOY-1 focused Python | PASS | 6 tests in 3163.024 ms in final evidence run. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:contracts` | PASS | Generated contracts matched committed files. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | API, geometry, playback, presentation, state, overlay, moment-zero, Film Room tests passed. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run build` | PASS | Vite chunk-size warning only. |
| `PYTHON=.venv/bin/python PYTHONPATH=src make test` | PASS | 583 tests in 509.190 s; flagged over five minutes. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:acceptance` | FAIL | Contracts, fixtures, unit, and build passed; Playwright failed 16/16. Most failures expect legacy `/` workbench UI while current `/` serves the gallery/coach surface; one backend artifact test expected a broken inspection to fail but received success. |

## Deployment Notes

The committed Render blueprint does not push or perform dashboard actions. Owner must run RB-001 after merge, set `DEMO_ACCESS_TOKEN`, optionally add `/etc/secrets/hermes/auth.json`, configure the bundle URL/SHA, deploy, then run the committed oracle against the live URL.
