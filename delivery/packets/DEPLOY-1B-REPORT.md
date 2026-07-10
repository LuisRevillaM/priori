# DEPLOY-1B Report — DELIVERED with evidence, NOT DONE

- Date: 2026-07-10
- Branch: `packet/deploy-1b` from `8d29f64`
- Live service: `srv-d8skfoe7r5hc73fkn9d0`
- API-reported live URL: `https://priori-integrated-alpha.onrender.com`

## Outcome

The standing `REUSE-AND-RENAME` branch fired. The existing service is now
named `entrelineas-film-room`, remains on
`codex/afl08-passport-loop`, retains its usable 20 GB disk, and is live on
the required frontier commit with the packet's five environment variables
configured. No service was created, stopped, or deleted.

Acceptance is **not claimed**. Two real deployment defects prevented an
oracle PASS:

1. The Blueprint's `starter` plan OOM-kills the service at its 512 MiB
   limit. The already-paid `standard` plan was restored as the smallest
   safe deviation and awaits director ratification.
2. The frontier Docker image does not contain the two Film Room flagship
   plans or their certified tables. The service is live but logs both
   plans as `missing_plan`; bootstrap consequently remains `warming`
   without a gallery answer. A minimal Docker packaging repair is committed
   locally but cannot reach Render under the packet's `never push` law.

The fenced oracle was not modified. Its live-URL run from this executor
failed because the sandbox cannot resolve external DNS from Python. The
failure is preserved as R-AZ evidence, not presented as product evidence.

## Investigation — reported before mutation

The Render API returned 47 services, 24 disks totalling 230 GB, and zero
environment groups. Six services were suspended. Exactly one service was
attached to this repository.

The Priori service before mutation was:

| Field | API result |
| --- | --- |
| Service | `priori-integrated-alpha` / `srv-d8skfoe7r5hc73fkn9d0` |
| Repo / branch | `LuisRevillaM/priori` / `codex/afl08-passport-loop` |
| Runtime / region | Docker / Oregon |
| Plan | Standard |
| Health path | `/healthz` |
| URL | `https://priori-integrated-alpha.onrender.com` |
| Disk | `dsk-d8skge37uimc738gcd4g`, 20 GB at `/var/data` |
| Auto-deploy | enabled |

The disk is usable. Repeated Render logs, including the fresh DEPLOY-1B
generation, say `Demo data already satisfies manifest.` The service has a
bundle URL and bundle SHA configured. Provisioning is the committed
`scripts/render-start.sh` → `scripts/provision-demo-data.py` path: validate
the mounted canonical/raw/cache/runtime trees first; only if they are
missing, download the configured bundle, verify SHA-256, and replace the
trees atomically.

That made repointing clean and selected reuse rather than fresh creation.

## Configuration and deploy record

Required environment values were upserted through the API and read back:

| Key | Result |
| --- | --- |
| `TQE_PUBLIC_MODE` | `1` |
| `WORKBENCH_HERMES_ENABLED` | `0` |
| `DEMO_ACCESS_TOKEN` | configured; value never printed or committed |
| `TQE_EXECUTION_WORKERS` | `4` |
| `TQE_NODE_CACHE_ROOT` | `/var/data/cache/node-output` |

The repository, branch, Docker command, bundle source, and disk were not
changed. No Hermes credential was uploaded.

| Deploy | Plan | Commit | Result | Evidence |
| --- | --- | --- | --- | --- |
| `dep-d98976ok1i2s73c0jhrg` | Standard | `8d29f64` | LIVE | Independent auto-deploy already running during investigation; not triggered by this executor. |
| `dep-d9899oernols73eu2n6g` | Starter | `8d29f64` | `update_failed` | Build passed; data manifest passed; Render event records OOM at `512Mi`. |
| `dep-d989amd7vvec73975odg` | Standard | `8d29f64` | LIVE | Data manifest passed; required env active; Film Room plans missing from image. |

### Declared Blueprint divergences

- `render.yaml` requests Starter. Starter is empirically unrunnable at
  512 MiB. Standard is the working baseline and requires ratification.
- Render does not change a service's generated subdomain when its display
  name is renamed. The display name is `entrelineas-film-room`, but the
  immutable primary URL retains `priori-integrated-alpha`. Custom domain
  work is explicitly out of packet scope.
- The retained disk is 20 GB and keeps its old name; the Blueprint minimum
  is 10 GB. The larger existing disk was preserved exactly as the reuse
  ruling requires.

## Weak-oracle finding and packaging repair

The runtime image copies only selected `delivery/n1d` files. It does not
copy these committed Film Room inputs:

- `delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json`
- `delivery/packets/r2-2-flagship/fragile_retention_rate_table.json`
- `delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_v0.json`
- `delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_table.json`

Fresh live logs therefore say `Film Room prewarm skipped missing plan` for
both flagships, followed by the misleading summary `Film Room prewarm
complete.` The bootstrap implementation remains `warming` whenever the
counterattack response is absent. The fenced oracle accepts `warming` and
skips replay when no moments exist, so it can PASS a deployment with no
gallery answer. This is a live-reality weakness in the oracle; the oracle
remains fenced and byte-untouched.

The minimal repair adds only four Docker `COPY` statements. It does not
alter any sealed plan or table. The evidence producer adds a separate
anti-vacuity leg: both `Prewarmed Film Room flagship ...` records must be
present and no `missing_plan` record may occur, in addition to the fenced
oracle PASS.

Local packet commits:

| Commit | Content |
| --- | --- |
| `f5a1f33` | Package the four existing flagship artifacts and add the DEPLOY-1B R-AZ producer. |
| `59b779e` | Make the producer verify the committed tree through an isolated index. |
| `9432600` | Preserve API/oracle transport failures as immutable evidence. |
| `db62f26` | Run the full suite with the repository's required import environment. |
| `7acc51a` | Correct the top-level run timestamp and add the explicit five-minute duration flag. |

Render cannot build these commits until they are present on the remote
repository. The packet forbids this executor from pushing, so the live
service remains on `8d29f64`. No runtime-command workaround or uncommitted
artifact injection was attempted.

## Fenced oracle

Oracle:
`delivery/oracles/DEPLOY-1/deploy_smoke.py`

SHA-256:
`708e90e81109c63462a4d3d97ba11ebd4e5c12f7d0bb084fcd710257b60a5dc2`

Invocation used no `--demo-token`, exactly as required. The Python runtime
could not resolve the API-reported hostname and the oracle exited 1. Its
unguarded final POST also emits a traceback after the three named DNS
failures. This is reported as a transport failure, not an oracle verdict on
the service.

The same sandbox also prevents Python from resolving `api.render.com` and
prevents the in-app/standalone browser fallbacks from running. Direct,
explicit Render API calls from the approved command channel succeeded and
produced the investigation above. One explicitly resolved request reached
`/film-room` with HTTP 200, while subsequent live requests were denied by
the sandbox channel.

## R-AZ evidence

The committed producer is
`scripts/packets/deploy1b_evidence.py`. It refuses a dirty tracked tree,
self-stamps its script/oracle hashes, branch, commit, tree and timestamp,
uses unique run directories, never overwrites, redacts secret environment
values, exposes only allowlisted operational values, and runs the fenced
oracle with no token.

Three failure runs are deliberately retained:

| Run | Producer commit | Result | Meaning |
| --- | --- | --- | --- |
| `delivery/packets/deploy-1b-evidence/runs/2026-07-10T065702Z00000000-c14bc47776ad/` | `9432600` | FAIL | First preserved attempt; full suite invocation lacked `PYTHONPATH`, API/oracle DNS blocked. Superseded, not erased. |
| `delivery/packets/deploy-1b-evidence/runs/2026-07-10T065749Z00000000-56fe8e7eb9c9/` | `db62f26` | FAIL | Correct full-suite invocation; API/oracle DNS blocked. Its top-level run timestamp was stamped at completion; superseded, not erased. |
| `delivery/packets/deploy-1b-evidence/runs/2026-07-10T071037Z00000000-81413e0057e7/` | `7acc51a` | FAIL | Canonical current failure envelope: accurate run start and duration flag; API/oracle DNS blocked; live image still lacks flagship inputs. |

The canonical run's full suite discovered 583 tests: 576 passed and 7 errored,
all seven because this sandbox denies localhost socket binding. The errors
are the five `test_deploy1_public_mode` server cases and two
`test_smoke1_honest_errors` server cases. Test-reported runtime was 634.142
seconds; producer wall time was 652.541 seconds and is explicitly flagged
as over five minutes. No assertion failure was observed.

| Verification | Result |
| --- | --- |
| Python compile for evidence producer | PASS |
| `git diff --check` | PASS |
| Full Python suite | 576 PASS / 7 sandbox socket-bind ERROR / 583 total |
| Local Docker build | NOT RUN — Docker daemon access denied by sandbox |
| Live fenced oracle | FAIL — Python DNS denied; no product verdict |
| Live data provisioning | PASS in Render logs (`already satisfies manifest`) |
| Live flagship prewarm | FAIL — both plans absent from frontier image |

No application runtime semantics changed. The only product-delivery change
is Docker packaging; the remaining code is evidence tooling.

## Fence diff

Before report/evidence append, `8d29f64..db62f26` contained exactly:

- `Dockerfile`
- `scripts/packets/deploy1b_evidence.py`

Explicit diffs across `delivery/oracles/**`, `delivery/LEDGER.md`,
`docs/design/**`, `delivery/packets/r2-2-flagship/**`, and
`delivery/packets/scp2-3-evidence/**` were empty. The four sealed inputs are
copied, never edited. The pre-existing untracked sidecar, archive, and
visual-explainer files were not touched.

Normal `.git/index` writes are denied in this executor sandbox. Packet
commits were produced from clean temporary indexes derived from `HEAD`;
alternate-index status showed only the three pre-existing untracked user
paths. The repository's ordinary index was not modified.

The tracked `.codex/render-target.json` is also read-only to this executor,
so it still carries the old display name and pre-packet health/env defaults.
Its service ID remains authoritative and all API operations targeted that
ID explicitly. The director should align this local helper config when the
packet is integrated.

## Ratification and resume gate

Requested director rulings:

1. Ratify Standard as DEPLOY-1B's minimum Render plan based on the recorded
   Starter OOM, and amend `render.yaml` at the director boundary.
2. Ratify the old generated hostname as an unavoidable reuse-branch
   divergence until owner-controlled DNS/custom-domain work.
3. Merge/push the Docker packaging commits through the normal director
   path; the executor will not push them.

After the repaired commit is remote:

1. Deploy that commit to `srv-d8skfoe7r5hc73fkn9d0` on Standard.
2. Require manifest PASS plus two real `Prewarmed Film Room flagship`
   records and zero `missing_plan` records.
3. Run the committed producer from a network-capable execution channel:

   ```text
   .venv/bin/python scripts/packets/deploy1b_evidence.py \
     --base-url https://priori-integrated-alpha.onrender.com \
     --owner-id tea-d0igqcidbo4c73eckab0 \
     --service-id srv-d8skfoe7r5hc73fkn9d0 \
     --deploy-id <new-live-deploy-id>
   ```

4. Append the fresh PASS run and report addendum. Do not rewrite either
   failed run.

## Account service inventory

| Name | Service ID | Type | Branch | Plan | Disk ID | Suspension |
| --- | --- | --- | --- | --- | --- | --- |
| swapgraph-v0 | srv-d96l25t8nd3s73bu4j4g | web_service | main | starter | dsk-d96l2spkh4rs73c97rd0 | not_suspended |
| entrelineas-film-room | srv-d8skfoe7r5hc73fkn9d0 | web_service | codex/afl08-passport-loop | standard | dsk-d8skge37uimc738gcd4g | not_suspended |
| hermes-speculative-museum | srv-d8pc8vog4nts73fr6lq0 | private_service | codex/hermes-migration | starter | dsk-d8pcanb7uimc73a29drg | not_suspended |
| trip-guide-hermes | srv-d8nnuvrbc2fs73f8b4t0 | web_service | main | standard | dsk-d8nnv03bc2fs73f8b51g | not_suspended |
| trip-guide-api | srv-d8nns528qa3s73fa3omg | web_service | main | starter | — | not_suspended |
| benchmarkos-hermes-agent | srv-d8k2nogjo6nc73c4i480 | web_service | main | pro | dsk-d8k2u90g4nts73f7uri0 | not_suspended |
| signasl | srv-d8j2j367r5hc73de5qv0 | static_site | main | — | — | not_suspended |
| yourweddingvibes-legacy-may26 | srv-d8gq5ogjo6nc73es3s10 | web_service | codex/legacy-may26-engine-render | standard | dsk-d8gra7a8qa3s739ma5n0 | not_suspended |
| yourweddingvibes-staging | srv-d89hvdf7f7vs73c7vmrg | web_service | main | standard | dsk-d89i2rp9rddc739ahumg | not_suspended |
| rosewood-mayakoba-celiac-guide | srv-d89gdma8qa3s73e19jd0 | static_site | main | — | — | not_suspended |
| legal-etl-cl-jp-answer-private | srv-d86cmabbc2fs73ap54n0 | web_service | main | starter | dsk-d871djn7f7vs73f5647g | not_suspended |
| sudoku-wardrobe-world-worker | srv-d84sdqfavr4c73db3u60 | background_worker | main | starter | dsk-d84sdqfavr4c73db3umg | not_suspended |
| sudoku-wardrobe-world-web | srv-d84sdpugvqtc73d5pus0 | web_service | main | standard | dsk-d84sdpugvqtc73d5pvqg | not_suspended |
| hermes-reviewer | srv-d83jqqdckfvc73bochog | background_worker | main | pro_plus | dsk-d83jsmbtqb8s73dr99e0 | not_suspended |
| yourweddingvibes-web | srv-d81maesdirrc739nishg | web_service | main | standard | dsk-d81mdu1kh4rs73big3mg | not_suspended |
| summer-of-spas | srv-d7vvr33tqb8s73fnk7u0 | web_service | main | starter | — | not_suspended |
| speculative-museum | srv-d7qb9npugtpc73at6qi0 | web_service | main | starter | dsk-d8pf3c8k1i2s73f2r2k0 | not_suspended |
| hermes-founder | srv-d7p3il9kh4rs73bs3f6g | background_worker | main | standard | dsk-d7p3l4q8qa3s73etq840 | not_suspended |
| midway-recruiting-asset-factory | srv-d7ohs1bbc2fs738e4ik0 | web_service | main | starter | — | not_suspended |
| madrid-portugal-family-route | srv-d7nati37uimc73bbcleg | static_site | main | — | — | not_suspended |
| wilder-carts | srv-d7mo97a8qa3s739ql5rg | web_service | main | free | — | not_suspended |
| swapgraph-cards | srv-d7mco88k1i2s7392sfv0 | web_service | codex/render-prototype-deploy | starter | dsk-d7mcp3lckfvc73ed55v0 | not_suspended |
| beaches-be-crazy-web | srv-d7ls6s57vvec73asg890 | web_service | main | free | — | not_suspended |
| rcsolutions-web | srv-d7l4c18sfn5c73csp7a0 | web_service | main | starter | dsk-d7l4dlaqqhas738k7h3g | not_suspended |
| zing-payments-redesign | srv-d7l2hrreo5us73da2oug | web_service | main | free | — | not_suspended |
| beforewedo-worker | srv-d782bn1r0fns73dq19gg | background_worker | main | starter | — | not_suspended |
| beforewedo-web | srv-d782bmdm5p6s73ehai0g | web_service | main | starter | — | not_suspended |
| hermes-architects-dream | srv-d71gfli4d50c73bnn5l0 | background_worker | codex/hermes-migration | starter | dsk-d71gfqf5r7bs73dsvct0 | not_suspended |
| ultimate-celiac-guides | srv-d6v111c50q8c739c5eqg | web_service | master | starter | — | not_suspended |
| green-spain-journeys | srv-d6sph1p4tr6s7385uj50 | web_service | main | starter | — | not_suspended |
| swapgraph-agent-barter-ui | srv-d6so4e7pm1nc73bg81rg | web_service | marketplace-vnext-execution | starter | — | not_suspended |
| swapgraph-agent-barter-operator | srv-d6so4dpaae7s73dfin9g | background_worker | marketplace-vnext-execution | starter | — | suspended |
| swapgraph-agent-barter-api | srv-d6so03n5gffc738nducg | web_service | marketplace-vnext-execution | standard | dsk-d6so2dvdiees73cgsgeg | not_suspended |
| swapgraph-market-operator | srv-d6pholdm5p6s73fu5n60 | background_worker | marketplace-vnext-execution | starter | — | not_suspended |
| alltalklabs-web | srv-d6mr6ppaae7s73ef44mg | web_service | master | starter | — | not_suspended |
| swapgraph-market-vnext-ui | srv-d6m74jnkijhs73fqjnl0 | web_service | marketplace-vnext-execution | starter | — | not_suspended |
| swapgraph-market-vnext-api | srv-d6m7437kijhs73e72op0 | web_service | marketplace-vnext-execution | starter | dsk-d6m75vngi27c73dtv6d0 | suspended |
| graph-board-feed-worker | srv-d6k5i2rh46gs73eb5umg | background_worker | main | starter | — | suspended |
| swapgraph-marketplace-web | srv-d6f2qh41hm7c73avc9d0 | web_service | main | starter | — | not_suspended |
| coach-backend | srv-d6e4n78gjchc73ad6dm0 | web_service | main | starter | — | not_suspended |
| swapgraph-runtime-api | srv-d6dlfgvgi27c738jtkhg | web_service | main | starter | dsk-d6dlpg9r0fns73cuohl0 | not_suspended |
| graph-board | srv-d63hu1hr0fns73bm24ug | web_service | main | standard | dsk-d63hu1pr0fns73bm25a0 | not_suspended |
| childbirth-guide | srv-d52pbmemcj7s73b3cplg | static_site | main | — | — | not_suspended |
| immi-helper | srv-d4j0cieuk2gs73bhg1h0 | web_service | main | starter | dsk-d5ofgts9c44c739j1r9g | not_suspended |
| wine-deals-frontend | srv-d2llqav5r7bs73dskh60 | static_site | main | — | — | suspended |
| wine-deals-backend | srv-d2llqav5r7bs73dskh5g | web_service | main | starter | dsk-d2llqav5r7bs73dskhlg | suspended |
| popchoice-backend | srv-d0igt18dl3ps7397lcfg | web_service | main | starter | dsk-d0ja56euk2gs73bln5og | suspended |

## Account disk inventory

| Name | Disk ID | Service ID | Size GB | Mount |
| --- | --- | --- | ---: | --- |
| disk | dsk-d0ja56euk2gs73bln5og | srv-d0igt18dl3ps7397lcfg | 10 | /var/data |
| data | dsk-d2llqav5r7bs73dskhlg | srv-d2llqav5r7bs73dskh5g | 1 | /data |
| disk | dsk-d5ofgts9c44c739j1r9g | srv-d4j0cieuk2gs73bhg1h0 | 10 | /app/packages/server/tmp |
| disk | dsk-d63hu1pr0fns73bm25a0 | srv-d63hu1hr0fns73bm24ug | 10 | /app/artifacts |
| swapgraph-state | dsk-d6dlpg9r0fns73cuohl0 | srv-d6dlfgvgi27c738jtkhg | 1 | /var/data |
| app-state | dsk-d6m75vngi27c73dtv6d0 | srv-d6m7437kijhs73e72op0 | 1 | /var/data |
| app-state | dsk-d6so2dvdiees73cgsgeg | srv-d6so03n5gffc738nducg | 1 | /var/data |
| hermes-architects-dream-state | dsk-d71gfqf5r7bs73dsvct0 | srv-d71gfli4d50c73bnn5l0 | 20 | /var/data |
| app-state | dsk-d7l4dlaqqhas738k7h3g | srv-d7l4c18sfn5c73csp7a0 | 1 | /var/data |
| prototype-data | dsk-d7mcp3lckfvc73ed55v0 | srv-d7mco88k1i2s7392sfv0 | 1 | /var/data |
| hermes-founder-state | dsk-d7p3l4q8qa3s73etq840 | srv-d7p3il9kh4rs73bs3f6g | 20 | /var/data |
| yourweddingvibes-artifacts | dsk-d81mdu1kh4rs73big3mg | srv-d81maesdirrc739nishg | 10 | /app/artifacts |
| hermes-reviewer-state | dsk-d83jsmbtqb8s73dr99e0 | srv-d83jqqdckfvc73bochog | 30 | /var/data |
| sudoku-wardrobe-world-artifacts | dsk-d84sdpugvqtc73d5pvqg | srv-d84sdpugvqtc73d5pus0 | 10 | /app/artifacts |
| sudoku-wardrobe-world-worker-artifacts | dsk-d84sdqfavr4c73db3umg | srv-d84sdqfavr4c73db3u60 | 10 | /app/artifacts |
| app-state | dsk-d871djn7f7vs73f5647g | srv-d86cmabbc2fs73ap54n0 | 1 | /var/data |
| yourweddingvibes-staging-artifacts | dsk-d89i2rp9rddc739ahumg | srv-d89hvdf7f7vs73c7vmrg | 10 | /app/artifacts |
| ywv-legacy-may26-artifacts | dsk-d8gra7a8qa3s739ma5n0 | srv-d8gq5ogjo6nc73es3s10 | 1 | /app/artifacts |
| benchmarkos-hermes-state | dsk-d8k2u90g4nts73f7uri0 | srv-d8k2nogjo6nc73c4i480 | 20 | /var/data |
| trip-guide-hermes-state | dsk-d8nnv03bc2fs73f8b51g | srv-d8nnuvrbc2fs73f8b4t0 | 20 | /var/data |
| hermes-speculative-museum-state | dsk-d8pcanb7uimc73a29drg | srv-d8pc8vog4nts73fr6lq0 | 20 | /var/data |
| app-state | dsk-d8pf3c8k1i2s73f2r2k0 | srv-d7qb9npugtpc73at6qi0 | 1 | /var/data |
| priori-integrated-alpha-data | dsk-d8skge37uimc738gcd4g | srv-d8skfoe7r5hc73fkn9d0 | 20 | /var/data |
| kernel-state | dsk-d96l2spkh4rs73c97rd0 | srv-d96l25t8nd3s73bu4j4g | 1 | /var/data |

Environment groups: none.
