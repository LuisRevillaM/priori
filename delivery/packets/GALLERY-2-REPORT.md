# GALLERY-2 — pressing-map report

Requested branch: `packet/gallery-2`

Execution branch: `packet/gallery-2` in the writable clone
`/Users/luisrevilla/code/priori/.gallery2-executor`

Frontier base: `e225b6e92b9d146601b1f2500263c203b3cdff77`, a descendant of the
requested `cdf727e7` frontier

Implementation status: `IMPLEMENTED — ACCEPTANCE BLOCKED` by sandbox denial
of both the Docker daemon socket and localhost TCP binding. The executor does
not claim the mandatory sealed 2 GiB proof, committed HTTP oracle, or
Playwright capture as passed.

## Outcome

The first expressible fallback rung is **(a), orientation-aware pitch thirds**.
The synthesized perspective bundle binds for `home` and `away` using only
registered vocabulary:

1. one `transition_anchor` produces the observed regain population;
2. registered `structured_zone` nodes project defensive, middle, and final
   thirds from that same anchor stream; and
3. registered `aggregate_over` nodes count the population and zone verdicts.

No registry file changed. The canonical generator executed all seven matches,
both roles, and both halves. Its independent `--check` run reproduced every
committed byte.

| Population | Defensive third | Middle third | Attacking third | Location UNKNOWN |
| ---: | ---: | ---: | ---: | ---: |
| 2,811 | 1,204 | 1,054 | 500 | 53 |

The three located counts plus location-UNKNOWN reconcile exactly to 2,811.
The committed plan hash is
`41d80fb5308a7e90ad633327e4422f11ef3c5c404d01f6012aa90e080317925c`.
The semantic table hash is
`e40f1abc02d142eb96b644e12841e6ac5714b60c1f94817aecfbeda2d482e97e`;
the exact table-file SHA-256 is
`5a1db2c9513dff58d76fa642d371cd145fdf0a0a2ea78ca532c9c0e74eb2cd27`.

## Product path

- `pressing_map` is registered alongside the existing flagships. Its
  descriptor source is the certified table's 2,811 compact moment preimages,
  not an execution prewarm.
- A missing or code-epoch-stale fragment rebuilds from those committed
  preimages. Warming state and logs truthfully identify the source as
  `certified_moment_records`.
- Startup remains `WORKBENCH_PREWARM_FILM_ROOM=0`. It loads lightweight
  descriptors only; each replay request verifies one hydration shard and then
  materializes canonical frames for that regain.
- Bootstrap returns a keyed `flagship_responses` map while preserving the
  existing `prewarmed_response` compatibility field.
- The dictated two-tab switcher uses the exact labels `Where do they win it
  back?` and `After a regain, do they keep it?`. Switching replaces the answer,
  moment list, selected replay, and replay frame context.
- The pressing answer uses the established confident/rate-first panel tokens:
  2,811 observed regains, the located share, three orientation-aware counts,
  14 team-match rows, and 53 explicitly location-UNKNOWN records. Every regain
  remains a selectable lazy-hydration moment.
- The committed Playwright producer now covers the pressing tab with real
  committed table shapes and requests `pressing-map-answer.png`; it was not
  able to launch here because the configured server cannot bind localhost.

## R-Y reproduction

`scripts/packets/gallery2_pressing_map_generator.py` first synthesizes through
the standard envelope, then composes and binds the registered zone/aggregate
nodes. Both the generation run and `--check` returned:

```json
{"fallback_rung":"a_thirds","location_unknown_count":53,"moment_record_count":2811,"plan_hash":"41d80fb5308a7e90ad633327e4422f11ef3c5c404d01f6012aa90e080317925c","population_count":2811,"status":"reproduced","table_hash":"e40f1abc02d142eb96b644e12841e6ac5714b60c1f94817aecfbeda2d482e97e","third_counts":{"defensive_third":1204,"final_third":500,"middle_third":1054}}
```

The first producer implementation duplicated `transition_anchor` four times.
That amplified an existing linear possession-identity lookup and had not
finished after forty minutes, so it was interrupted before it wrote anything.
The final composition uses the intended registered relation shape—one regain
anchor stream feeding three `structured_zone` nodes—and is the artifact that
was generated and reproduced.

## Memory and lazy-hydration evidence

The committed `gallery2_local_proof.py` producer refuses to call a run sealed
unless it observes the requested cgroup limit. The available unsealed run
proved:

- execution prewarm `false`;
- bootstrap `ready`;
- both gallery asks servable;
- 2,811 pressing descriptors loaded with no full execution payloads;
- two separate hydration requests, each yielding 101 canonical frames and one
  location stage label; and
- process peak RSS `351,059,968` bytes (about 334.8 MiB).

That observation would leave about 1.67 GiB below a 2 GiB ceiling, but it is
**not** the mandatory proof because no cgroup was active. Evidence is in
`gallery-2-pressing-map/local-proof-unsealed.json`; the blocked-gate record is
`gallery-2-pressing-map/blocked-gates.json`.

The director's sealed command is:

```text
docker run --memory=2g ... python scripts/packets/gallery2_local_proof.py --require-memory-limit-bytes 2147483648
```

The script fails rather than certifying if the exact cgroup limit or cgroup
peak is unavailable.

## Verification table

| Gate / command | Result |
| --- | --- |
| Generator, followed by committed generator `--check` | PASS — exact byte reproduction; 2,811 = 1,204 + 1,054 + 500 + 53 |
| `python -m py_compile` for generator, local proof, and committed oracle | PASS |
| Focused backend: lazy hydration, certified gallery tables, Film Room app, and non-socket honest-error test | PASS — 24 tests |
| Fresh-cache pressing rebuild source assertion | PASS — 2,811 descriptors; source `certified_moment_records`; payload loaded `false` |
| Frontend unit suite through `node --import tsx` | PASS — all eight unit modules, including real table shapes, ratio-first mode, and tab switching |
| `npm --prefix apps/workbench-alpha run build` | PASS — contract generation, TypeScript, Vite |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS — 19 files scanned; no tactical fixtures or hidden fallback moments |
| Direct bootstrap + two-hydration producer | PASS (unsealed) — ready, both asks, 2,811 descriptors, 101 frames twice, 351,059,968-byte process peak |
| Canonical `make test` | BLOCKED / INVALID — initial broad run observed five localhost-bind errors and was interrupted in an unrelated heavy R1-5 executor test after greatly exceeding the repository's recorded duration; fail-fast rerun named the first error as sandbox `PermissionError` at `WorkbenchServer` bind after 92 passes |
| Seven existing `WorkbenchServer` socket tests | BLOCKED — sandbox denies `127.0.0.1` bind before product logic |
| Committed Playwright producer | BLOCKED — configured server exits at localhost bind before browser launch |
| `delivery/oracles/GALLERY-2/gallery_smoke.py --base-url <local>` | BLOCKED — no local HTTP listener can be created in this sandbox |
| Docker `--memory=2g` proof | BLOCKED — sandbox denies access to `/Users/luisrevilla/.docker/run/docker.sock` |
| `git diff --check` | PASS |

The failed `npm run test:unit` CLI attempt was environment-invalid: `tsx`
could not create its IPC socket under `/private/tmp`. Running the identical
eight modules through Node's `tsx` loader avoided the daemon socket and passed.

## Deviations and STOP disposition

- `git pull --ff-only` and branch creation in the primary worktree were denied
  because the sandbox cannot write its `.git` directory. The available local
  HEAD was `e225b6e`, already a descendant of requested frontier `cdf727e7`.
  Work moved to the writable clone named above, where `packet/gallery-2` was
  created. No push was attempted.
- The packet's 2 GiB law is touched because the flagship descriptor/index path
  changed. Docker proof is therefore mandatory and remains open. The unsealed
  RSS result is diagnostic evidence only.
- The HTTP oracle and visual capture remain open for the same sandbox policy,
  not because of an oracle mismatch. The oracle was not bent, given a snapshot
  mode, or presented as passed.
- No deploy, registry mutation, live ask, or external service mutation was
  attempted.

Under the packet's STOP law, the director should not deploy this commit until
the exact-cgroup proof and committed HTTP oracle pass in an environment that
permits Docker and localhost sockets.

## Hotfix round — flagship isolation and refreshed bundle (2026-07-16)

Status: **IMPLEMENTED; LOCAL LAYOUT PROOFS PASS; S3 UPLOAD AND SEALED DOCKER
PROOF BLOCKED BY SANDBOX POLICY.** The director deploys; no Render mutation was
attempted.

The live regression had two coupled causes:

1. `film_room_descriptor_code_epoch()` hashed the whole
   `app_service.py`. Adding the pressing flagship therefore invalidated every
   pre-existing retention fragment even though its descriptor contract had not
   changed. The old 115-moment fragment became an artificial cache miss.
2. `build_film_room_descriptor_index()` built all flagships in one loop and
   raised out of the whole build on the first missing/invalid flagship. The
   fail-safe caught only that shared exception, so no descriptor upgrades were
   installed. The certified-table bootstrap remained visible: counterattack at
   28 partition previews and fragile retention at zero. In the pristine old
   bundle, the matching counterattack execution cache is about 956 MB, above the
   bounded 64 MB rebuild guard, so re-reading that payload at boot is not an
   acceptable recovery path.

The hotfix makes the epoch a hash of the descriptor/hydration contract and
`FilmRoomMomentResponse` fields, not unrelated service code. A known v1
fragment is migrated only after every descriptor validates under v2 and every
hydration shard path and SHA verifies; the small fragment is atomically
re-keyed without opening the execution payload. Unknown or malformed schemas
still MISS and take the existing bounded execution-cache rebuild path.

Each flagship now has its own build boundary. An unavailable flagship emits an
`absent` index entry, a prewarm record, and a validated
`understood_but_not_expressible` response with a typed reason. In particular,
an old disk without pressing artifacts exposes
`FILM_ROOM_BUNDLED_DESCRIPTOR_EVIDENCE_ABSENT`; it does not synthesize the
2,811 shards from committed source data during startup. Other flagships keep
loading. The tab therefore remains selectable and tells the truth, while the
default retention ask upgrades to its 115 real chain moments.

### Old and refreshed layout proofs

The exact predecessor DEPLOY-2 archive (SHA
`bc876fac20bf27229d282e809fb1e5e8c891a66769dfb5dce15dd99874c52760`)
was unpacked to `/private/tmp/gallery2-hotfix-old-bundle-r1` and exercised with
execution prewarm off. It reached `ready`, served retention with 115 moments,
served pressing as a typed absence with zero moments, migrated four v1
fragments, opened zero execution-cache payload bytes for migration, and
hydrated two retention windows. Peak process RSS was 301,301,760 bytes (287.3
MiB). This is 1,846,181,888 bytes (1,760.7 MiB) below 2 GiB arithmetically, but
it is explicitly unsealed because no cgroup was active.

The canonical `deploy2_cache_builder.py` machinery then generated the pressing
execution caches and lazy sidecars against a copy of that seven-match layout:
1,407 away descriptors plus 1,404 home descriptors. The refreshed layout
reached `ready` with 2,811 pressing moments and 115 retention moments and
hydrated one window from each ask. Peak process RSS was 322,830,336 bytes
(307.9 MiB), arithmetically 1,824,653,312 bytes (1,740.1 MiB) below 2 GiB;
this observation is also unsealed.

The committed proof producer is
`scripts/packets/gallery2_hotfix_proof.py`. Its R-AZ outputs are
`gallery-2-hotfix/old-layout-proof.json` and
`gallery-2-hotfix/refreshed-layout-proof.json`.

### Bundle refresh

`scripts/create-demo-data-bundle.py` produced:

- archive:
  `/private/tmp/gallery2-hotfix-bundle-r1/entrelineas-cloud-workbench-alpha-seven-match-v1.tar.gz`;
- SHA-256:
  `32f44347187219383dcf2289ba47c993b88da6c6704f1cdfade182e0eaa5dbd9`;
- compressed / expanded bytes: 662,912,564 / 5,118,311,742;
- 3,350 files, including six execution caches and 2,926 hydration shards
  (2,811 pressing + 115 retention); and
- pressing fragment SHAs
  `8e70ce9c8e2bab61bbb6ee8c4253a738ab9bf991bfdfbb49c23c1f708274322d`
  (away) and
  `3459e916d2e847a96747cd40fedd99232730694d8b0315f49ba26f7a83739691`
  (home).

An independent `shasum -a 256` matched the manifest. The manifest honestly
records `source_dirty=true`: `.git` is read-only in this sandbox, so the data
producer ran from the clean-ordered hotfix diff rather than a scribe commit.
During the run the checked-out frontier advanced from requested `a048e523` to
its ledger-only descendant `1439b841`; no hotfix source was overwritten.

AWS upload stopped before any write. The required account-first identity check
could not reach `https://sts.us-east-1.amazonaws.com/`, so account
`477665006166` could not be verified in this sandbox. The target remains
`s3://priori-cloud-alpha-477665006166/priori/cloud-alpha/entrelineas-cloud-workbench-alpha-seven-match-v1.tar.gz`.
The local bundle summary and exact blocked state are in
`gallery-2-hotfix/bundle-summary.json` and
`gallery-2-hotfix/blocked-gates.json`.

### Hotfix verification table

| Gate / command | Result |
| --- | --- |
| Focused `tests.test_deploy2_lazy_hydration` | PASS — 10/10 standalone in 23.915s, including exact 115/typed-zero isolation |
| Exact old-bundle proof, prewarm 0 | PASS — ready; retention 115; pressing typed absence 0; two hydrations; zero execution payload bytes opened by migration |
| Refreshed-layout proof, prewarm 0 | PASS — ready; pressing 2,811; retention 115; one hydration per ask |
| Pressing cache producers | PASS — away 1,407 + home 1,404; both execution cache MISSes materialized current artifacts |
| Deterministic bundle + independent SHA | PASS — `32f44347…5dbd9`; 662,912,564 bytes; 2,926 hydration shards |
| `python -m py_compile` for changed Python and proof producer | PASS |
| Frontend unit suite through Node's `tsx` loader | PASS — 8/8 modules |
| `npm --prefix apps/workbench-alpha run build` | PASS — generated contracts, TypeScript, Vite |
| `npm --prefix apps/workbench-alpha run test:fixtures` | PASS — 19 files, no tactical fixtures or hidden fallback moments |
| Canonical `make test` | ENVIRONMENT-INVALID — 607 ran in 4,731.989s; 600 passed; seven errors, all sandbox-denied `socket.bind()` calls (five DEPLOY-1 public-mode, two honest-error HTTP) |
| Docker exact `--memory=2g` proof | BLOCKED before build/run — daemon socket access is denied; unsealed peaks above are not promoted |
| AWS identity then S3 upload | BLOCKED before write — STS endpoint unreachable; credentials were neither printed nor bypassed |
| `git diff --check` | PASS |

No registry, frontend serving contract, error shape, Render service, or live URL
was changed. The director must scribe-commit the ordered worktree, run the exact
2 GiB proof in a Docker-capable seat, upload the hash-locked bundle, and then
update/deploy the bundle env.
