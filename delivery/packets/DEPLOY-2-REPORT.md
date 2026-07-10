# DEPLOY-2 Report — local memory PASS; shipping blocked on source availability

Status: BLOCKED BEFORE LIVE DEPLOY
Branch: `packet/deploy-2`
Implementation: `6fdaf4864ba8ad894110d1290e1330560d34d38a`
Local R-AZ run: `2026-07-10T174719.190195Z-c79f8e177bb9-local`

## Verdict

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
| `make test` | 594 run: 587 passed; 7 errors all from host-sandbox `PermissionError` on ephemeral `socket.bind` in existing HTTP-server tests. No assertion failure or DEPLOY-2 failure. |
| R-AZ local producer | PASS — cache rebuild, 2 GiB proof, bootstrap, two hydrations, and three fenced local oracles |

## Required next authority

Make `6fdaf48` available to Render's connected repository/branch, then issue a
fresh S3 presigned bundle URL if the current one has expired, set
`WORKBENCH_PREWARM_FILM_ROOM=1`, and deploy that exact commit. Only after five
minutes of stable service should the director run the live fenced chain oracle
for acceptance.
