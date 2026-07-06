# SCP2-3 Report: Film Room

Branch: `packet/scp2-3`

Frontier base: `1a5ccdf` (`codex/afl08-passport-loop`)

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| Packet/design read | DONE | `docs/design/FILM_ROOM.md`, `docs/design/film-room-mockup.html`, `delivery/packets/SCP2-3-film-room.md` |
| Branch | DONE | Created `packet/scp2-3` from frontier |
| Push | NOT_DONE | Local commits only |
| Deviation | FLAGGED | Live Hermes does not produce the historical R2-4 certified plan hash for the flagship wording; no provenance masking was applied. |

## Implemented Surface

| Area | Result |
| --- | --- |
| Workbench route | Added `/film-room` on the existing Workbench Alpha React/Vite stack; no new framework. |
| Ask path | `POST /api/film-room/ask` calls `compile_nl_request` through the existing Hermes openai-codex subscription path, then runs `synthesize_and_bind`, submit/validate/confirm/execute, inspect, and replay retrieval. |
| Clarification/refusal | Film Room API preserves Hermes typed outcomes: expression, clarification, understood-but-not-expressible, unsupported modality. |
| Replay | Film Room pitch renders canonical replay frames from `retrieve_replay_window`; no placeholder players are drawn when replay is absent. |
| Replay-frame endpoint | `GET/POST /api/film-room/replay-frame` returns one canonical frame plus a canonical JSON byte hash. |
| Evidence rows | Committed certified table rows are used only when the executed plan hash matches a committed flagship table; otherwise the UI shows actual execution requested-evidence rows. |
| Interval law | `assertIntervalMetric` makes a point estimate without `observed`, `lower`, `upper`, and `unknown_count` unrenderable. |
| Prewarm | Film Room prewarm helper runs the R2-2 fragile-retention and R2-4 counterattack flagships through the same execution cache path. |

## Flagged Provenance Drift

The R2-4 committed flagship plan hash is:

```text
bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749
```

Live Hermes over `openai-codex/gpt-5.5` did not reproduce that committed hash.
Observed outcomes:

| Ask | Live result | Hash behavior |
| --- | --- | --- |
| `After a regain, does the team progress the ball by carry and keep it with a controlled pass?` | sequence expression without `aggregate_over`/`rate` | Plan hash `bba11ca6...`; not R2-4 |
| `After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?` | rate expression with `sequence_pattern`, `aggregate_over`, `rate` | Multiple target-id variants; passed e2e hash `2774bac2...`, not R2-4 |
| `When a team faces the fragile condition, how often is possession retained?` | expression returned, synthesis failed | `No registered operator composition satisfied the target contract` |

Ruling applied here: no silent substitution. The API reports the actual
executed document hash. When no committed certified table matches, the UI says
`executed moment`, leaves the interval card absent unless bounded interval
evidence exists, and records `certified_table_path: null`.

## Evidence

| Artifact | Notes |
| --- | --- |
| `delivery/packets/scp2-3-evidence/film-room-e2e.json` | API-only e2e summary; sampled replay frames byte-match canonical recomputation. |
| `delivery/packets/scp2-3-evidence/film-room-response.json` | Captured real Film Room response used to render the screenshot. |
| `delivery/packets/scp2-3-evidence/film-room.png` | Screenshot of the ratified-style Film Room UI rendering real replay entities. |
| `delivery/packets/scp2-3-evidence/film-room-service.log` | Service/Hermes diagnostics from the latest failed live screenshot run. |

API-only e2e result:

| Field | Value |
| --- | --- |
| Provider/model | `openai-codex/gpt-5.5` |
| Billing surface | ChatGPT subscription via Hermes CLI |
| Ask latency | `476640ms` |
| Replay sample fetch latency | `321ms` |
| Replay window | `replay_3fb28073bcf5062b` |
| Sampled frame hashes | `121865=ab077c33...`, `121915=6dbe759c...`, `121965=8b31ed86...` |
| Matches R2-4 certified table | `false` |

Long executions flagged:

| Run | Elapsed | Result |
| --- | ---: | --- |
| First full R2-4 backend probe | `>300s` | Long; failed after execution on a helper-name bug, then cache rerun passed in `0.334s`. |
| R2-2 direct prewarm | `237.036s` | Completed; one role HIT, one role MISS then cached. |
| API-only live e2e | `476.640s ask latency` | PASS for actual executed document and canonical replay-frame hashes; long. |
| Screenshot-enabled live e2e | `~40s` | Failed with HTTP 500 after Hermes returned another target variant; screenshot later generated from captured response artifact. |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src:. .venv/bin/python -m py_compile src/tqe/workshop/app_service.py scripts/packets/scp2_3_film_room_e2e.py` | PASS | Python syntax/import check. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Regenerated contracts, `tsc --noEmit`, Vite build. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Includes `filmRoom.test.ts`; `tsx` needs sandbox-safe `TMPDIR`. |
| `PYTHONPATH=src:. .venv/bin/python scripts/packets/scp2_3_film_room_e2e.py --output-root /private/tmp/scp2_3_film_probe --timeout 600 --skip-prewarm --skip-screenshot` | PASS | Long; one live Hermes ask; no screenshot. |

## Mutation-Standard Guard

| Guard | Named Test |
| --- | --- |
| Boundless point estimate cannot render as interval | `apps/workbench-alpha/tests/filmRoom.test.ts` deletes `observed`, `lower`, `upper`, and `unknown_count` one at a time and asserts `assertIntervalMetric` throws. |

## Full-Suite Table

Committed implementation tree: `45fa857`.

| Command | Result | Notes |
| --- | --- | --- |
| `npm --prefix apps/workbench-alpha run test:contracts` | PASS | Generated API schemas/types are committed. |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS | No hardcoded tactical fixtures/canned replay frames found in frontend sources. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Film Room interval guard included. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, `tsc --noEmit`, Vite build. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 554 tests in `439.224s`; long run; attestation `VERIFIED`. |

---

# SCP2-3 Round 2 Report: R-AZ..R-BE

Round-1 report content above is retained as historical rejected material. This section is the round-2 report for implementation/evidence tree `c95066fc1b6e9c213b6532b33bd42929d6784983` (`HEAD^{tree}` `78bd3d7c23705d59a212b24e6c802455a9d1a181`). No push was performed.

## Rulings

| Ruling | Status | Evidence |
| --- | --- | --- |
| R-AZ evidence discipline | DONE | Evidence is produced by committed `scripts/packets/scp2_3_film_room_e2e.py`; final script SHA-256 `9c5ffea75942811f0594571047ff11aab6ec8da1b34dbdd1a796f78685db90ae`; final run `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/`. Round-1 artifacts were moved to `delivery/packets/scp2-3-evidence/round-1-rejected-artifacts/`. |
| R-BA null interval | DONE, FLAGGED machine-side repair | `rate.source_records` now preserves rate source rows; empty live-synthesized `population.periods` now falls back to canonical `firstHalf/secondHalf`. Final cold ask renders interval `observed=1.0`, `lower=0.008695652173913044`, `upper=1.0`, `unknown_count=114`. Raw evidence is hidden behind the Film Room JSON toggle. |
| R-BB chain moments | DONE | Final cold response has `moment_total_count=1`, `visible_moment_count=1`, `replay_window_id=replay_81c406e111a32e9b`; replay window reports `source_kind=chain_record`; sampled frames byte-match canonical recomputation. |
| R-BC overlays | DONE | Final bootstrap/cold moment overlays include an observed-anchor marker at frame `121915`; screenshot shows the anchor overlay and `1 stages · 0 trails`. |
| R-BD prewarm/cold ask | DONE | Startup prewarm uses the live execution-cache path; final cached prewarm rows are `81ms` and `125ms`. The UI first renders prewarmed committed content (`prewarmed_committed_plan/not_invoked`) and does not auto-fire a browser cold ask. Final cold ask latency is attributed as Hermes `72178ms`, synthesis `14ms`, execution `359131ms`, observed total `431376ms`. |
| R-BE mechanics | DONE | Header chips are derived from response data, provenance strip includes tree `2e420927c756f0c27ede9e06e9080ebde0b27422`, fields use `observed/lower/upper/unknown_count`, law-4 refusal rendering is typed, and outcome-class/front-end guards are covered by `filmRoom.test.ts`. |

## Final Evidence

Final successful evidence run:

| Field | Value |
| --- | --- |
| Run | `2026-07-06T05:06:09+00:00` |
| Producing commit | `55a7a506a43d746b089dbc35a24f67ce27aca17a` |
| Producing script hash | `9c5ffea75942811f0594571047ff11aab6ec8da1b34dbdd1a796f78685db90ae` |
| Billing surface | ChatGPT subscription via `openai-codex` Hermes CLI |
| Bootstrap/prewarmed row | fragile retention `81ms` HIT/HIT; counterattack `125ms` HIT/HIT |
| Cold ask row | observed `431376ms`; Hermes `72178ms`, synthesis `14ms`, execution `359131ms` |
| Interval | observed `1.0`, lower `0.008695652173913044`, upper `1.0`, unknown `114` |
| Chain moments | total `1`, visible `1` |
| Replay | `replay_81c406e111a32e9b`, frames `121865`, `121915`, `121965` byte-checked |
| Live synthesized hash | `7c7ca1e114a6e605219c588dbf76e476a2401cc974c2414624561b5ac453a75f` |
| Certified R2-4 hash | `bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749` |
| Certified table match | `false`; no table substitution applied |

Artifacts:

| Artifact | Notes |
| --- | --- |
| `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/film-room-bootstrap.json` | Prewarmed committed content, interval card source, overlay marker, tree. |
| `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/film-room-cold-response.json` | Live subscription-backed cold ask response with synthesized hash, latency attribution, interval, chain moment. |
| `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/film-room-replay-window.json` | Chain-record replay window used for byte-frame checks. |
| `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/film-room.png` | Browser screenshot; PNG contains script-hash, run timestamp, and git-tree tEXt metadata. |
| `delivery/packets/scp2-3-evidence/runs/2026-07-06T050609Z0000-9c5ffea75942/film-room-service.log` | Streamed service/Hermes log, stamped before app launch. |

Earlier script-produced diagnostic runs were also committed and retained: `2026-07-06T040335Z0000-a91271e75c6d` (invalid replay handle), `2026-07-06T042038Z0000-a91271e75c6d` (startup prewarm MISS timings, manually interrupted during cold ask), `2026-07-06T044114Z0000-9c5ffea75942` (HTTP 400 caused by empty synthesized periods), and `2026-07-06T045634Z0000-9c5ffea75942` (successful run before overlay fallback).

## Flags

| Flag | True observation |
| --- | --- |
| Long run | `2026-07-06T042038Z0000-a91271e75c6d` ran over five minutes; service log records startup prewarm MISS rows of `470426ms` and `386117ms`; run was manually interrupted during cold ask. |
| Long run | Direct live ask reproduction exceeded five minutes and was interrupted to capture stack location in runtime controlled-pass execution. |
| Long run | `2026-07-06T045634Z0000-9c5ffea75942` completed with cold ask `445199ms`. |
| Long run | Final evidence `2026-07-06T050609Z0000-9c5ffea75942` completed with cold ask `431376ms`. |
| Long run | Full Python suite completed in `436.650s`. |
| Provenance drift | Live Hermes/synthesis did not reproduce the committed R2-4 plan hash. The UI/API report actual synthesized hashes and `certified_table_path: null` for cold asks. |

## Verification

Verification was run on committed implementation/evidence tree `c95066fc1b6e9c213b6532b33bd42929d6784983` before this report addendum was committed.

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m py_compile src/tqe/workshop/app_service.py src/tqe/semantic_compiler/target_synthesis.py scripts/packets/scp2_3_film_room_e2e.py` | PASS | Syntax/import check. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_film_room_app tests.test_scp2_1_meaning_to_target.SCP2MeaningToTargetTests.test_empty_expression_periods_fall_back_to_canonical_periods tests.test_r2_2_rate.RateOperatorTests.test_rate_record_projects_interval_to_source_chain_anchor` | PASS | 3 tests in `0.006s`. |
| `npm --prefix apps/workbench-alpha run test:contracts` | PASS | Generated contracts clean. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Film Room outcome/refusal/chip/interval guards included. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Typecheck and Vite build passed; Vite chunk-size warning only. |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS | No hardcoded tactical fixtures/canned replay frames. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 557 tests in `436.650s`; attestation `VERIFIED`. |
