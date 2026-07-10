# DEPLOY-1C Report — DELIVERED with evidence, NOT DONE

Date: 2026-07-10

Branch: `packet/deploy-1c`

Packet base: `9eef466`

Implementation commit: `d495ea9`

Evidence-harness/failure-preservation commit: `ae440bc`

Review judgment remains external. This executor does not claim `DONE`, merge,
deployment, live acceptance, or director ratification. Nothing was pushed.

## Outcome

The Film Room now installs its committed certified-table gallery synchronously
and without plan execution. `WORKBENCH_PREWARM_FILM_ROOM` gates only the
background execution upgrade; `render.yaml` explicitly keeps that upgrade off.
A completed execution replaces a table answer only when it has both an interval
and servable moments, so an empty or failed execution cannot erase the gallery.

The bootstrap answer carries the committed plan/table hashes, certified interval,
certified rows, compiled labels, and 28 table-backed partition previews. Replay
metadata is registered during bootstrap, but canonical frames are materialized
only on the first request for a selected preview. The proved first replay contains
101 frames (`10230..10330`) and created no draft, bound-plan, or execution
artifacts.

No file under `src/tqe/semantic_compiler/` was touched.

## R-AZ evidence

Producer: `scripts/packets/deploy1c_evidence.py`

Final producer SHA-256:
`5682e0e10e09652421b590b6ff7ff57ee5fe26e44d3e9cfc1de3a44e5b1c0614`

Producing commit: `ae440bc37d7afde48dd8454ee96ef91fec3a640e`

Final run:
`delivery/packets/deploy-1c-evidence/runs/2026-07-10T085330Z00000000-5682e0e10e09/`

All nine final-run files carry the producing script hash and run timestamp.
The producer refuses an uncommitted/dirty script, allocates a unique run path,
and refuses overwrite.

The earlier immutable FAIL run remains at
`delivery/packets/deploy-1c-evidence/runs/2026-07-10T085007Z00000000-85b6862f2468/`.
Its product oracle, focused tests, UI test, typecheck, and replay proof passed;
the full suite failed because the isolated worktree had no raw/canonical corpus
and inherited public-mode flags. The committed producer then mounted the supplied
corpus read-only into ignored legacy paths and ran the suite in neutral mode.
No failed artifact was overwritten.

## Verification table

| Verification | Result | Evidence |
| --- | --- | --- |
| Committed R-AZ producer | PASS | Final run status `PASS` |
| Fenced `gallery_ready.py` | PASS | `state=ready`, interval PASS, moment PASS, `ORACLE PASS` |
| Supplemental replay request | PASS | Lazy before request; 101 frames served; requested bounds respected |
| Zero-execution proof | PASS | Answer executions empty; prewarm records `execution_performed=false`; draft/bound/execution artifact counts all zero |
| Focused Python | PASS | 20 tests in 3.371 s |
| Focused Film Room UI | PASS | Honest partition-preview labels exercised |
| TypeScript typecheck | PASS | `tsc --noEmit` |
| Generated API contract drift | PASS | `npm --prefix apps/workbench-alpha run test:contracts` after implementation commit |
| Full Python suite | PASS | 590 tests in 545.638 s; duration flagged over five minutes |
| Leg zero | PASS | Empty diff from `9eef466` across oracles, ledger, design docs, dev sets, blind pins, certified inputs, and semantic compiler |
| Independent fix review | PASS (advisory) | No remaining blocking defect; no acceptance claim |

## Deviation law — DEPLOY-1C-D1

Status: `RATIFICATION_REQUESTED`.

SCP2-3 R-BB requires rate moments to be population chain records. The committed
certified table intentionally strips those source-record populations. Under the
packet's simultaneous constraints — no plan execution and no fenced-table
mutation — certified chain witnesses cannot be reconstructed.

The implementation does not disguise aggregate partitions as chains. The API
uses `source_kind=certified_table_partition` and
`classification=CERTIFIED_TABLE_RATE_PARTITION`; the UI says “certified table
partition previews” and “no chain witness,” and describes replay as a period-open
preview rather than a witness window.

Requested director ruling: ratify these partition previews as a DEPLOY-1C
bootstrap-only exception to R-BB, or require a later certified-table version that
commits replayable chain witnesses. This executor does not decide that ruling.

## Lazy replay memory flag

Predicate filters restrict the materialized Arrow tables and public payload to
the requested frame window. The current canonical Parquet files use full-half row
groups, however, so overlapping row groups may still be scanned or decoded.
Physical window-bounded storage I/O must not be claimed until the canonical files
are partitioned or row-grouped by bounded frame ranges.

## Oracle and environment notes

- The fenced oracle verifies that a replay ID exists but does not request the
  endpoint. The R-AZ producer separately fetched the replay locally. Live
  acceptance should repeat that supplemental request after deployment.
- A fixed-port subprocess bind was denied by the known executor sandbox. The
  committed proof used the same `WorkbenchServer`/handler on an OS-assigned
  ephemeral port in-process; the fenced oracle still ran as a separate process
  against the HTTP service.
- `render.yaml` explicitly sets `WORKBENCH_PREWARM_FILM_ROOM="0"` until DEPLOY-2
  refreshes bundle caches.

## Files changed

- `src/tqe/workshop/app_service.py`
- `src/tqe/workshop/m1_2.py`
- `render.yaml`
- `apps/workbench-alpha/src/FilmRoom.tsx`
- `apps/workbench-alpha/src/types.ts`
- generated API schema/type projections
- Film Room Python/UI tests
- committed R-AZ producer and immutable evidence runs

## Remaining acceptance gates

1. Director adjudicates DEPLOY-1C-D1.
2. Director reproduces the local evidence if desired.
3. After merge/deploy, director runs the fenced live-URL oracle plus an explicit
   replay-window request. That live run, not this executor report, closes the
   packet.
