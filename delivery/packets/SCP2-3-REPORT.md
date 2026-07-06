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

---

# SCP2-3 Round 3 Report: Focused Revision

Round-3 implementation/evidence tree before this report: `496182125a3ae9a66f070d275c97b2c5bd2a868e` (`HEAD^{tree}` `e7acc2c277b673df6ae6365c95f3c168ad697b44`). No push was performed. Executor status language below is `DELIVERED with evidence`; reviewer `DONE` judgment is not claimed here.

## Rulings

| Ruling | Status | Evidence |
| --- | --- | --- |
| R-AZ evidence discipline | DELIVERED with evidence | Fresh run `delivery/packets/scp2-3-evidence/runs/2026-07-06T062302Z0000-e35372e8b9d7/` was produced by committed `scripts/packets/scp2_3_film_room_e2e.py`; script SHA-256 `e35372e8b9d79da58b193537003ec0b52bc9e429a6cdc4863b1ce0e3c584ea2e`; run timestamp `2026-07-06T06:23:02+00:00`; producing commit `6f8e0e6606ee05ba58bff11e97fd483d89db50e9`; tree `1b026661f74bf211e857131d015c86c56dec7810`. PNGs carry script hash/timestamp/tree metadata. |
| R-BB chain-record moments | DELIVERED with evidence | Bootstrap and cold responses each render `115` total/visible moments, all with derived `source_kind=chain_record`, and `115` unique replay windows. Cold evidence includes PASS stage/trail replay `replay_9328db0c3b7a555f` and truncation UNKNOWN replay `replay_f55da46381136601`. |
| R-BB overlays and UNKNOWN slate | DELIVERED with evidence | Evidence script now fails unless stage labels, carry trails, UNKNOWN slates, and truncation UNKNOWN slate reasons are present. Cold PASS moment has labels `regain`, `carry >= 3m`, `pass` and carry trail `121945-122091`; UNKNOWN slate reason is `stage_2_window_truncated`. Screenshots: `film-room-stage-trail.png`, `film-room-unknown.png`. |
| source_kind derived | DELIVERED with evidence | `film_room_source_kind` derives from record shape; no constant stamping. Fresh cold response source kind set is only `chain_record`; stage/trail replay window reports `source_kind=chain_record` with source id `3a3144e50eb99e0b`. |
| Honest labels and fields | DELIVERED with evidence | Runtime intervals carry `source.evidence_kind=runtime`, UI headline is `Runtime evidence interval`; `certified_evidence_rows` remains empty when no certified table matches, `runtime_evidence_rows` contains the live row, and `evidence_rows_kind=runtime`. Null chain status renders as `chain_status not emitted`; UNKNOWN/PASS render truthfully. |
| Canonical-source double hash | DELIVERED with evidence | `public_canonical_sources` is idempotent. Cold provenance and replay-window payloads cross-reference `frames=canonical_source:323efd58ce461520` and `positions=canonical_source:40e0942910a7793c`, without `canonical_source:canonical_source:*`. |
| R-BD prewarm/cold latency | DELIVERED with evidence | Startup prewarm used live execution path with fresh cache root (`output_root_preexisting_at_start=false`). Service readiness including prewarm: `835650ms`; bootstrap prewarmed fetch: `104ms`; cold ask observed: `416266ms`; attribution Hermes `55121ms`, synthesis `12ms`, execution `361011ms`; replay fetches `16ms`, `269ms`, `327ms`. |

## Final Evidence

| Field | Value |
| --- | --- |
| Run | `delivery/packets/scp2-3-evidence/runs/2026-07-06T062302Z0000-e35372e8b9d7/` |
| Billing surface | ChatGPT subscription via `openai-codex` Hermes CLI |
| Cache provenance | `/private/tmp/scp2-3-film-room-workshop-runs/2026-07-06T062302Z0000-e35372e8b9d7`; preexisting at start `false`; prewarm enabled `true` |
| Prewarm rows | fragile retention `MISS,MISS` `476363ms`, 40 results; counterattack `MISS,MISS` `358619ms`, 1 result |
| Runtime interval | observed `1.0`, lower `0.008695652173913044`, upper `1.0`, unknown `114`; source `execution_requested_evidence` |
| Live synthesized hash | `671f4828f72bce733823154e30de094f54b9668843c83253417db932b62313e9` |
| Certified R2-4 hash | `d8179a5a1af54ecdd45514e4fa3403b3ab515977fb79dd29b4a62f2ecfd9bb7e` |
| Certified table match | `false`; no certified-table substitution applied |
| Chain moment totals | bootstrap `115/115`, cold `115/115`; both `115` unique replay windows |
| Replay frame checks | Frames `100200`, `100250`, `100300` byte-match canonical recomputation |

Artifacts:

| Artifact | Notes |
| --- | --- |
| `film-room-e2e.json` | Top-level manifest with metadata, cache provenance, latency, frame checks, chain checks. |
| `film-room-bootstrap.json` | Startup prewarmed content served first. |
| `film-room-cold-response.json` | Live subscription-backed cold ask response with runtime interval and chain moments. |
| `film-room-replay-window.json` | First selected replay, used for canonical byte checks. |
| `film-room-unknown-replay-window.json` | Truncation UNKNOWN moment replay window. |
| `film-room-stage-trail-replay-window.json` | PASS stage/trail replay window; `603` frames from `121614` to `122216`. |
| `film-room.png` | Browser screenshot of the default prewarmed Film Room state. |
| `film-room-unknown.png` | Browser screenshot after selecting an UNKNOWN truncation slate. |
| `film-room-stage-trail.png` | Browser screenshot after selecting the PASS stage/trail moment. |
| `film-room-service.log` | Stamped service/Hermes log for the run. |

## Flags

| Flag | True observation |
| --- | --- |
| Long run | Fresh round-3 evidence run exceeded five minutes; service readiness including startup prewarm was `835650ms`, cold ask was `416266ms`. |
| Long run | R2-4 generator rerun for committed chain witnesses took `350.001s`. |
| Long run | Full suite took `443.482s`. |
| Provenance drift | Live Hermes/synthesis did not reproduce the certified R2-4 table hash. The response reports actual synthesized hash `671f4828...`, `certified_table_path=null`, `evidence_rows_kind=runtime`, and runtime interval labeling. |

## Verification

Verification was run on committed implementation/evidence tree `496182125a3ae9a66f070d275c97b2c5bd2a868e` before this report addendum was committed.

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m py_compile src/tqe/workshop/app_service.py scripts/coverage_map/compiler_search_reachability.py scripts/packets/scp2_3_film_room_e2e.py` | PASS | Syntax/import check. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_film_room_app tests.test_scp2_1_meaning_to_target.SCP2MeaningToTargetTests.test_r2_4_sequence_expression_uses_search_not_committed_certified_plan_ref` | PASS | 6 tests in `0.019s`; includes chain witness overlay/source-kind/canonical-source checks. |
| `npm --prefix apps/workbench-alpha run test:contracts` | PASS | Generated API schemas/types are clean. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Frontend Film Room interval headline, null chain status, outcome/refusal, and fixtures guards included. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, `tsc --noEmit`, Vite build; Vite chunk-size warning only. |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS | No hardcoded tactical fixtures/canned replay frames. |
| `PYTHONPATH=src:. .venv/bin/python scripts/packets/scp2_3_film_room_e2e.py --timeout 1200` | PASS | Fresh live R-AZ evidence run; long run flagged; committed run directory above. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 561 tests in `443.482s`; attestation `VERIFIED`; long run flagged. |

---

# SCP2-3 Fix Round Report: F-R2-4 Fence Repair

Fix-round implementation/evidence tree before this report: `e713a1176a3feff415b688417e8cac2cab10b76e` (`HEAD^{tree}` `c17a96dada7b0cb866b5689710a39f880a137e47`). No push was performed. Status language remains `DELIVERED with evidence`.

## Fix

| Item | Status | Evidence |
| --- | --- | --- |
| Restore sealed R2-4 packet | DELIVERED with evidence | `delivery/packets/r2-4-flagship/` was restored from pre-round-3 commit `ccef30a`; `git diff --name-status ccef30a..HEAD -- delivery/packets/r2-4-flagship` is empty. Restored provenance has plan hash `bf12768919f517f7b9412bd42622d2e4f262a6ceba6667319a597fae06921749`, table hash `49bf6720be24f417b179d17abfe2e4ee9231ce2fcab55194109697fa17def411`. |
| Relocate witness-enriched plan | DELIVERED with evidence | Witness plan lives under `delivery/packets/scp2-3-evidence/witness-plan/`, generated by committed wrapper `scripts/packets/scp2_3_witness_plan_generator.py` from committed R2-4 generator `scripts/packets/r2_4_flagship_generator.py`. |
| Witness provenance | DELIVERED with evidence | `witness-plan/provenance.json` records wrapper hash `b1bf6630bca27de5038106cd1a59fb53f557a834003272602295dd1aab86f346`, R2-4 generator hash `5135fe682825d85ca1bb0951c59a2c1ff3c8e1ff89adb3a815518c5ca7e0560b`, run timestamp `2026-07-06T07:06:21+00:00`, producing commit `091b9d481e820b6525048547c9213276c20d9826`, output hashes, and generator elapsed `358.377s`. |
| Film Room references | DELIVERED with evidence | `src/tqe/workshop/app_service.py` and `scripts/packets/scp2_3_film_room_e2e.py` now point the counterattack committed/witness plan to `delivery/packets/scp2-3-evidence/witness-plan/`. Fresh evidence prewarm row confirms path `delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_v0.json`. |

## Witness Plan

| Output | SHA-256 | Stable hash |
| --- | --- | --- |
| `counterattack_initiation_v0.json` | `a49acd43897a420c5491f0a53795ffdceb3724b219800407b36fcec645be43bd` | `d8179a5a1af54ecdd45514e4fa3403b3ab515977fb79dd29b4a62f2ecfd9bb7e` |
| `counterattack_initiation_table.json` | `d904fdc94c0a78b74244e6809f8c559df6d8b21e559eaef552c8d84f8eb8d19e` | `a9b2d257c9e36995b237ce13555047eeaaf09218473d0c3de2f98c01ab18fa65` |
| `counterattack_initiation_table.md` | `2307aae9ba7d2f66e523210293595c87040d93c48e3dc83c78aecdf082247c21` | n/a |
| `r2_4_generator_provenance.json` | `7ee02e3ef14790d45b033a7c4eed38c1df0982792c87d78aa21a0eee482418b5` | `1acd0f1f218bab8d7965faf40bce8dbd354bc2ba427848a0c67a510251d493c1` |

Witness generator totals: `a_count=1`, `b_count=0`, `c_count=2261`, `d2_count=549`, `population_count=2811`, `unknown_count=2810`, `rate_lower_bound=0.0003557452863749555`, `rate_observed=1`, `rate_upper_bound=1`.

## Fresh Evidence

Successful fix-round R-AZ run: `delivery/packets/scp2-3-evidence/runs/2026-07-06T073846Z0000-06516dd4e3d5/`.

| Field | Value |
| --- | --- |
| Producing commit/tree | `7048fae69f6a4537a7c89eb10f3958464024c971` / `74942a51f47a45d7437da6dfcf14486e3e810e21` |
| Producing script hash | `06516dd4e3d510dd4bc90a0cbeaf2ebdb2750c854fe6db753b6028dd90b1c399` |
| Run timestamp | `2026-07-06T07:38:46+00:00` |
| Cache provenance | output root `/private/tmp/scp2-3-film-room-workshop-runs/2026-07-06T073846Z0000-06516dd4e3d5`; preexisting at start `false`; prewarm enabled `true` |
| Prewarm rows | fragile retention `MISS,MISS` `470436ms`; counterattack witness plan `MISS,MISS` `352080ms` |
| Expected committed/witness plan hash | `d8179a5a1af54ecdd45514e4fa3403b3ab515977fb79dd29b4a62f2ecfd9bb7e` |
| Cold live synthesized hash | `67394d1afe4468e6e0d8d4a2d6f926c7206649bcca0c0c1945acc166b3c7fa23` |
| Certified table match | `false`; cold ask remains runtime evidence, no substitution |
| Moment checks | bootstrap `115/115`, cold `115/115`; both `115` unique replay windows; stage/trail and UNKNOWN slate exercised |
| Runtime interval | observed `1.0`, lower `0.008695652173913044`, upper `1.0`, unknown `114` |
| Cold latency attribution | Hermes `75069ms`, synthesis `12ms`, execution `354073ms`, observed total `429272ms` |

Artifacts:

| Artifact | Notes |
| --- | --- |
| `film-room-e2e.json` | Manifest with metadata, relocated prewarm path, cache provenance, latency, frame checks, chain checks. |
| `film-room-bootstrap.json` | Prewarmed response from witness-plan committed content. |
| `film-room-cold-response.json` | Live subscription-backed cold ask with runtime interval and 115 chain moments. |
| `film-room-replay-window.json` | First selected replay for canonical frame checks. |
| `film-room-unknown-replay-window.json` | Truncation UNKNOWN replay window. |
| `film-room-stage-trail-replay-window.json` | PASS stage/trail replay window. |
| `film-room.png`, `film-room-unknown.png`, `film-room-stage-trail.png` | Browser screenshots with PNG metadata. |
| `film-room-service.log` | Stamped service/Hermes log proving the relocated witness-plan prewarm path. |

## Flags

| Flag | True observation |
| --- | --- |
| Long run | Witness-plan generation took `358.377s`. |
| Long run | Successful fresh R-AZ evidence run had service readiness including startup prewarm `823582ms` and cold ask `429272ms`. |
| Long run | Full suite took `437.719s`. |
| Diagnostic failure | First fresh evidence attempt in this fix round hit HTTP 500 during cold ask after proving relocated prewarm; stamped diagnostic preserved outside the packet at `/private/tmp/scp2-3-fix-round-http500-diagnostic-2026-07-06T071239Z0000-06516dd4e3d5`. A direct same-root invocation then completed with 115 moments; final committed run above passed. |

## Verification

Verification was run on committed implementation/evidence tree `e713a1176a3feff415b688417e8cac2cab10b76e` before this report addendum was committed.

| Command | Result | Notes |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/python -m py_compile src/tqe/workshop/app_service.py scripts/packets/scp2_3_film_room_e2e.py scripts/packets/scp2_3_witness_plan_generator.py` | PASS | Syntax/import check. |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_film_room_app tests.test_scp2_1_meaning_to_target.SCP2MeaningToTargetTests.test_r2_4_sequence_expression_uses_search_not_committed_certified_plan_ref` | PASS | 6 tests in `0.018s`. |
| `npm --prefix apps/workbench-alpha run test:contracts` | PASS | Generated contracts clean. |
| `TMPDIR=/private/tmp npm --prefix apps/workbench-alpha run test:unit` | PASS | Frontend unit suite including Film Room checks. |
| `npm --prefix apps/workbench-alpha run build` | PASS | Contract generation, `tsc --noEmit`, Vite build; Vite chunk-size warning only. |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS | No hardcoded tactical fixtures/canned replay frames. |
| `PYTHONPATH=src:. .venv/bin/python scripts/packets/scp2_3_witness_plan_generator.py` | PASS | Generated relocated witness plan; long run flagged. |
| `PYTHONPATH=src:. .venv/bin/python scripts/packets/scp2_3_film_room_e2e.py --timeout 1200` | PASS | Fresh live R-AZ evidence run; long run flagged; committed run directory above. |
| `UV_CACHE_DIR=/private/tmp/uv-cache-priori make PYTHON=/Users/luisrevilla/code/priori/.venv/bin/python test` | PASS | 561 tests in `437.719s`; attestation `VERIFIED`; long run flagged. |
