# DEPLOY-2 Report — prewarm-off fix proven with material headroom

Status: FIX PROVEN LOCALLY — AWAITING DIRECTOR SHIP
Branch: `packet/deploy-2-fix`
Implementation: `5e011805e0645f387dd018ca7cf13a2e3a4d5d79`
Fix R-AZ run: `2026-07-10T192707.624506Z-f90b19f71268`

## Fix-round verdict

The descriptor index now loads synchronously from the retained disk cache's
committed fragments and hydration metadata, independently of
`WORKBENCH_PREWARM_FILM_ROOM`. The measured service ran with that flag set to
`0`; no plan execution or full execution-cache payload load occurred.

The proof pre-provisioned and hash-verified the retained disk outside the
measured container, matching the live redeploy path where the refreshed bundle
is already installed. The measured `--memory=2g --memory-swap=2g` container
then performed service startup, descriptor-index load, bootstrap, two distinct
hydrations, and all three fenced local oracles.

| Fix proof check | Result |
| --- | --- |
| Film Room execution prewarm | OFF |
| Cgroup memory limit | `2,147,483,648` bytes / `2048 MiB` |
| Cgroup peak | `605,818,880` bytes / `577.754 MiB` |
| Headroom | `1,541,664,768` bytes / `1470.246 MiB` / `71.789%` |
| Required minimum headroom | `512 MiB` |
| OOM / OOM-kill events | `0` / `0` |
| Full execution-cache payloads opened | `0` |
| Bootstrap | 115 `chain_record` descriptors |
| Hydrations | Two distinct replay windows; 101 and 301 frames; stage overlays present |
| DEPLOY-1 smoke oracle | PASS |
| DEPLOY-1C gallery oracle | PASS |
| DEPLOY-2 chain oracle | PASS |

Evidence is committed under
`delivery/packets/deploy-2-fix-evidence/runs/2026-07-10T192707.624506Z-f90b19f71268/`.
The producer and its helper were byte-identical to committed `5e01180`; the
image was built from a Git archive of that commit.

The prior zero-headroom proof is superseded: reaching exactly 2048 MiB is not
evidence of a shippable 2 GiB process even when the kernel records no OOM.

## Prior round verdict — superseded by the fix proof

The director's Option A implementation fits the 2 GiB service envelope under
the required workload: blocking provision, descriptor-index startup,
bootstrap, and two distinct lazy replay hydrations. It reached the cgroup cap
exactly but recorded no OOM event and was not OOM-killed. All three fenced
local oracles passed.

Shipping cannot continue honestly: Render rejected the explicit implementation
commit with `404 not found: service ... does not have commit
6fdaf4864ba8ad894110d1290e1330560d34d38a`. Render's latest live deploy remains
`dep-d98hv65ckfvc73dqe0ag`, commit `161bb13`. Deploying that older source with
Film Room prewarm enabled would not test the proofed implementation and could
re-enter the retired full-payload startup path. STOP is therefore mandatory.

`WORKBENCH_PREWARM_FILM_ROOM` was restored to `0` after the rejected deploy.
The refreshed bundle and its SHA are uploaded and configured, but they are not
activated by a deploy. No five-minute stability observation or live chain
oracle was run. The DEPLOY-1C D1 exception is **not expired**.

## Sealed local proof

Evidence is committed under
`delivery/packets/deploy-2-evidence/runs/2026-07-10T174719.190195Z-c79f8e177bb9-local/`.
The committed producer was byte-identical to its HEAD copy and used the
fenced oracle hashes recorded in `deploy2-evidence.json`.

| Check | Result |
| --- | --- |
| Docker limit | `2,147,483,648` bytes (`--memory=2g`, swap also 2 GiB) |
| Cgroup peak | `2,147,483,648` bytes / `2048.0` MiB |
| OOM / OOM-kill events | `0` / `0` |
| Container OOM-killed | `false` |
| Startup upgrade | Descriptor index; `full_execution_cache_payloads_opened=0` |
| Bootstrap | 115 `chain_record` descriptors |
| Hydration 1 | `replay_0e2ba8014f63667a`, 101 frames, one stage overlay |
| Hydration 2 | `replay_4f459a027b295d1e`, 301 frames, one stage overlay |
| DEPLOY-1 smoke oracle | PASS |
| DEPLOY-1C gallery oracle | PASS |
| DEPLOY-2 chain oracle | PASS (`115` chain records; hydrated overlay present) |

The 115 descriptors come from the counterattack-away execution. Both fragile
retention roles and counterattack-home honestly emitted zero chain descriptors;
they remain valid descriptor fragments and do not impersonate chain witnesses.

## Bundle and attempted ship

| Item | Result |
| --- | --- |
| Archive SHA-256 | `bc876fac20bf27229d282e809fb1e5e8c891a66769dfb5dce15dd99874c52760` |
| Archive bytes | `658,611,957` |
| Runtime code epoch | `7f96daa1395b2a15af90a961e2a3c577888e517900bc62fe9976819d7036d7f5` |
| S3 archive | Uploaded to `s3://priori-cloud-alpha-477665006166/priori/cloud-alpha/entrelineas-cloud-workbench-alpha-seven-match-v1.tar.gz`; single-part S3 SHA-256 checked against the local archive |
| S3 companion manifest | Uploaded beside the archive |
| Render owner/service | `tea-d0igqcidbo4c73eckab0` / `srv-d8skfoe7r5hc73fkn9d0` (`entrelineas-film-room`) |
| Render environment prepared | Fresh seven-day bundle presign (not recorded), archive SHA, `TQE_PROVISION_DATA_BACKGROUND=0`, `TQE_EXECUTION_WORKERS=1` |
| Render prewarm | Set to `1` for the intended deploy, then restored to `0` after commit rejection |
| Exact deploy request | Rejected with 404 because Render's connected repository lacks `6fdaf48` |

## Full-suite table

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_deploy2_lazy_hydration tests.test_deploy1c_gallery_from_tables tests.test_deploy1_public_mode` | PASS — 17 tests |
| `npm --prefix apps/workbench-alpha run build` | PASS |
| `make test` | PASS — 594 tests in 495.230 seconds; repository attestation VERIFIED |
| Fix R-AZ producer | PASS — prewarm off, retained-disk startup, descriptor bootstrap, two hydrations, three fenced local oracles, 1470.246 MiB headroom |

## Required next authority

The director deploys exact commit `5e01180` with
`WORKBENCH_PREWARM_FILM_ROOM=0` permanently. Issue a fresh S3 presigned bundle
URL only if the configured one has expired. After five minutes of stable
service, the director runs the live fenced chain oracle for acceptance.
