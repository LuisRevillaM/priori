# Performance And Cache Plan

## Recorded Baseline

The clean proof run records real host-service execution latencies in `artifacts/approved-proof.json` and `artifacts/experimental-proof.json`.

| Path | Execute And Initial Inspect | Result Selection | Rapid Final Selection | Replay Payload | Replay Frames | Cadence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Approved recipe | 29,409 ms | 307 ms | 679 ms | 296,144 bytes | 101 | 25 Hz |
| Experimental corridor | 46,938 ms | 262 ms | 678 ms | 296,102 bytes | 101 | 25 Hz |

## R1 Boundary

R1 records performance and keeps the UI responsive enough to show the host state. It does not implement execution caching or progress streaming.

## Integrated Alpha Plan

- Add a host-owned execution cache keyed by stable plan hash, bound plan ID, canonical source identity, match scope, and execution parameters.
- Keep cache entries below a host-owned cost/size limit and invalidate when canonical source hashes or runtime commit changes.
- Add progress events or polling for long-running execution phases: accepted request, canonical source loading, predicate evaluation, result materialization, replay materialization.
- Surface progress without exposing local artifact paths or host-only handles.
- Record cache hit/miss, execution duration, replay load duration, payload size, and render cadence in proof JSON.
- Keep public `/api` routes unable to mint confirmation authorization or execute unconfirmed plans.
