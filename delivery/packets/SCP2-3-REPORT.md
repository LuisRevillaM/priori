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
