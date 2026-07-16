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
