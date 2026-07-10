# DEPLOY-2 Report — STOPPED at the mandatory 2 GiB fork

Date: 2026-07-10

Branch: `packet/deploy-2`

Packet author/oracle commit: `fa412de`

Final code commit before this report: `8cd8f33`

Nothing was pushed. No Render or AWS mutation was made. Review judgment and
the fallback decision remain external.

## Verdict

The current-epoch cache bundle was built, hash-verified, and provisioned into
a fresh local container. The service then attempted execution prewarm with all
four generated execution-cache records present. Under the packet's exact
`docker --memory=2g` envelope it reached a sampled cgroup peak of
`2,147,487,744` bytes (`2048.004 MiB`) and was OOM-killed with exit code 137.

The packet's stop condition therefore fired. The fallback fork—keep the
certified-table gallery and add lazy chain hydration, or upgrade the Render
plan—is the director's ruling. This executor did not upload the bundle, change
Render environment variables, deploy, or run a live-URL oracle.

`WORKBENCH_PREWARM_FILM_ROOM` remains `0` in `render.yaml`; committing `1` after
this result would encode a known crash. The DEPLOY-1C-D1 exception remains
`RATIFIED` and has **not expired**, because DEPLOY-2 did not pass its live chain
oracle.

## Investigation before mutation

Read-only Render resolution confirmed the packet target before any local work:

| Field | API result |
| --- | --- |
| Owner | `tea-d0igqcidbo4c73eckab0` |
| Service | `entrelineas-film-room` / `srv-d8skfoe7r5hc73fkn9d0` |
| URL | `https://priori-integrated-alpha.onrender.com` |
| Repo / branch | `LuisRevillaM/priori` / `codex/afl08-passport-loop` |
| Plan / region | Standard / Oregon |
| Instances | 1 |
| Current execution prewarm | `WORKBENCH_PREWARM_FILM_ROOM=0` |
| Current workers | `TQE_EXECUTION_WORKERS=1` |
| Current bundle SHA | `9e680b8b41670eece292e736ccd62184470b87e7e719eb578135b5be462f64a0` |

The final read-only audit at `2026-07-10T16:28:53Z` found the latest deploy
still live as `dep-d98dgopoagis73dsv6dg`, commit `fa412de`, triggered by the
pre-existing remote `new_commit` event and finished at `11:35:41Z` before this
executor's first evidence run. The three environment values above remained
unchanged.

The configured bundle host is the existing project S3 bucket. AWS identity and
object inspection were attempted through the account wrapper but this executor
could not reach the STS or S3 endpoints. No AWS action occurred. The later
mandatory local STOP independently prohibited upload.

The retained-disk refresh path had two real defects:

1. Provisioning accepted “required dataset paths exist” without tying the
   installed trees to the configured archive SHA, so changing the SHA would not
   refresh an already-populated disk.
2. Background provisioning could replace cache trees while execution prewarm
   started against the old trees.

The committed repair writes an atomic archive-SHA install stamp only after all
verified trees are installed, requires the stamp for the idempotent fast path,
and supports blocking provisioning before service startup. Coach prewarm is
deferred until the service is bound. The Blueprint also records the live-safe
one-worker setting.

## Bundle provenance

Final local artifact (ignored, not committed):
`artifacts/cloud-alpha/entrelineas-cloud-workbench-alpha-seven-match-v1.tar.gz`

Its committed manifest copy is in the final R-AZ run.

| Property | Value |
| --- | --- |
| Archive SHA-256 | `2e2788d96c617fbd42f1f1065c7c85a5d04c5eab4c0163c8b3a178080b3cf127` |
| Compressed bytes | `658,553,795` |
| Manifest files | 303 |
| Runtime code epoch | `7f96daa1395b2a15af90a961e2a3c577888e517900bc62fe9976819d7036d7f5` |
| Bundle source commit | `4a532daaeaeb94fbc3953de5668bfd7c1347a633` |
| Source dirty | `false` |
| Generator billing | none; Hermes disabled, no model invocation |

Cold generation used four isolated one-role processes so the large execution
payloads did not accumulate before packaging. All four deterministic executions
completed and atomically wrote caches:

| Plan | Role | Cache before/after execute | Results | Cache file size |
| --- | --- | --- | ---: | ---: |
| Fragile retention | away | MISS / MISS (written) | 20 | 915 MiB |
| Fragile retention | home | MISS / MISS (written) | 20 | 912 MiB |
| Counterattack initiation | away | MISS / MISS (written) | 1 | 4.2 MiB |
| Counterattack initiation | home | MISS / MISS (written) | 0 | 2.3 MiB |

The final bundle includes those four execution records and 252 current-epoch
node-output cache files. Provisioning verified the archive SHA and every file
hash from the bundle manifest before publishing the trees.

## Mandatory 2 GiB proof

Canonical run:
`delivery/packets/deploy-2-evidence/runs/2026-07-10T153715.650914+0000-6a851d5e7be1-local/`

Producer: `scripts/packets/deploy2_evidence.py`

Producer SHA-256:
`6a851d5e7be16e63281d5e2489b103409bc8e9642dc70a2eb66e0fd0397a2f78`

Producing commit: `4a532daaeaeb94fbc3953de5668bfd7c1347a633`

| Check | Result |
| --- | --- |
| Producer committed and tracked tree clean before run | PASS |
| Three oracle hashes match author commit | PASS |
| Production image built from implementation commit | PASS; `sha256:f54d2b6e...` from `ac3746c` |
| Bundle SHA and per-file manifest verification | PASS |
| Docker memory limit | PASS; `2,147,483,648` bytes |
| Docker memory+swap limit | PASS; `2,147,483,648` bytes (no extra swap) |
| Blocking provisioning | PASS; `Demo data provisioned and verified.` |
| Execution prewarm entered | PASS; log reached the first execution flagship |
| Sampled cgroup peak | `2,147,487,744` bytes / `2048.004 MiB` |
| Container state | FAIL; exit 137, `OOMKilled=true` |
| Strict gallery oracle | NOT RUN; service died before upgraded readiness |
| Chain gallery oracle | NOT RUN; service died before upgraded readiness |
| Render deploy / stability / live oracle | NOT RUN by packet STOP law |

The sampled peak is one 4 KiB page above the nominal configured limit as
reported from the container cgroup immediately before Docker recorded the OOM.
The Docker inspect record independently preserves the exact limit, no-extra-swap
setting, exit code, and OOM flag.

## Earlier immutable failure runs

No failed artifact was overwritten.

| Run | Finding | Disposition |
| --- | --- | --- |
| `2026-07-10T114445.981708+0000-e01b0aa76c87-local` | Evidence producer incorrectly capped cold generation at 4 GiB; first flagship OOM. | Harness deviation preserved; cap removed. Not the packet fork. |
| `2026-07-10T130307.834607+0000-6e33e8501f53-local` | Rebuild after an evidence-only edit hit a package-index `fonttools` availability failure. | Transport/build failure preserved; intact ancestor product image reused only after proving the intervening diff evidence-only. |
| `2026-07-10T130741.722574+0000-9f541f3669fa-local` | Combined cold generator exhausted the Docker VM after writing two 913 MiB-class retention records. | Preparation failure preserved; generation isolated per role. Not the packet fork. |

## Deviation law

### DEPLOY-2-D1 — artificial 4 GiB generator cap

Status: `CORRECTED_AND_PRESERVED`.

The first producer version constrained cold cache generation even though the
packet constrains only the final cache-hit proof. The resulting OOM is retained
as failure evidence. The cap was removed before further generation.

### DEPLOY-2-D2 — evidence-only ancestor image reuse

Status: `DISCLOSED`.

The exact production image built successfully from `ac3746c`. A subsequent
evidence-only producer edit invalidated Docker's broad `COPY scripts` layer and
a fresh frontend dependency resolve failed because the package channel exposed
no compatible `fonttools`. The committed producer allowed reuse only after:

- the image revision was proved an ancestor of the producing commit; and
- every intervening path was either the DEPLOY-2 producer/cache-builder or
  immutable DEPLOY-2 evidence.

No runtime, configuration, UI, oracle, plan, table, or data input differed.

### DEPLOY-2-D3 — isolated cold cache generation

Status: `DISCLOSED`.

The normal combined prewarm path accumulated multi-gigabyte response objects
while generating caches and exhausted the Docker VM. Generation was therefore
performed one plan-role per fresh process against one shared cache tree. This
changed only preparation memory lifetime. The final service proof still used
the unmodified production startup/prewarm path and is the authoritative OOM.

### DEPLOY-2-D4 — immutable raw-log whitespace

Status: `DISCLOSED`.

`git diff --check` over the whole packet range reports trailing whitespace in
the first immutable raw Docker build log. Producer/application sources pass
`git diff --check`; the raw failed artifact was not rewritten to improve a
formatting check.

## Verification table

| Verification | Tree | Result |
| --- | --- | --- |
| Focused provisioning + Blueprint tests | `8cd8f33` | PASS, 3 tests in 0.159 s |
| Full Python suite, pre-hold corroboration | `dbe2bd3` | 591 total; 584 pass; 7 sandbox bind errors; 541.307 s |
| Full Python suite, final code tree | `8cd8f33` | 591 total; 584 pass; 7 sandbox bind errors; 543.676 s |
| Full-suite duration flag | `8cd8f33` | FLAG: exceeded five minutes |
| Application/producer source diff check | `8cd8f33` | PASS |
| Whole-range diff check | `fa412de..8cd8f33` | FLAG: immutable raw Docker log whitespace only |
| Local 2 GiB product gate | `4a532da` producer | FAIL: OOM at sampled 2048.004 MiB |
| Local fenced oracles | — | NOT RUN: OOM preceded service readiness |
| Live fenced chain oracle | — | NOT RUN: Render untouched after STOP |

All seven suite errors are `PermissionError: [Errno 1] Operation not permitted`
from localhost socket binding: five `test_deploy1_public_mode` cases and two
`test_smoke1_honest_errors` cases. This is the same executor-sandbox envelope
recorded and independently cleared in DEPLOY-1B/1C. No assertion failure was
observed.

## Leg zero and scope

Oracle hashes at the author commit and producing run:

- `DEPLOY-1/deploy_smoke.py`:
  `708e90e81109c63462a4d3d97ba11ebd4e5c12f7d0bb084fcd710257b60a5dc2`
- `DEPLOY-1C/gallery_ready.py`:
  `a3ef8770f86fea8762ace34a8675f3e9410809d77b68837b4e3d450a10f03d3c`
- `DEPLOY-2/chain_gallery.py`:
  `e3485b16fa6cb7b40be9a021befa535a402db1bff1c2d4436fc1c084124344b4`

`fa412de..8cd8f33` is empty across `delivery/oracles/**`,
`delivery/LEDGER.md`, `docs/design/**`, compiler dev/blind draw sets, both
certified flagship input trees, and prior sealed evidence. The DEPLOY-2 packet
and oracle remain byte-untouched.

Runtime semantic code under `src/tqe/**`, the UI, certified plans/tables, dev
sets, blind pins, and the constitution were not changed. Product-delivery
changes are limited to bundle provenance/refresh safety and truthful Blueprint
configuration; the remaining files are tests and R-AZ tooling/evidence.

The three pre-existing untracked user paths were not touched.

## Director ruling required

Choose one branch before any DEPLOY-2 resume:

1. retain the 2 GiB Standard plan, keep the certified-table bootstrap, and add
   lazy per-question/per-moment chain hydration that does not materialize both
   913 MiB retention payloads at startup; or
2. approve a plan upgrade large enough for the measured cache-hit assembly,
   then repeat the exact 2 GiB-or-revised-envelope proof under the new ruling.

Until that ruling, do not set `WORKBENCH_PREWARM_FILM_ROOM=1`, do not upload the
new bundle as the live SHA, and do not mark DEPLOY-1C-D1 expired.
