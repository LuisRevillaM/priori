# Scope

## Included

- Workbench Alpha R1 acceptance hardening at commit `87b2441a626a67bd1222482f5be64e23e694a1f0`.
- Browser journeys for approved recipe, experimental corridor, clarification state, capability-gap state, model-unavailable/manual fallback, and known-timestamp inspection.
- Assertions for interpretation-before-confirmation, host confirmation before execution, execution/result/replay ID correlation, nonzero canonical replay frames, evidence and predicate trace visibility, no console errors, and public API authority boundaries.
- Frontend fixture scan for hardcoded result IDs, timestamps, coordinates, replay frames, and fallback tactical moments.
- Coordinate geometry and playback unit tests.
- Generated host API JSON Schema and TypeScript response types plus browser runtime response validation.
- Clean-worktree proof artifacts, screenshots, Playwright report, videos, API traces, and source/build hashes.

## Excluded

- Final visual polish.
- S3 feedback or revision behavior.
- Browser-to-MCP calls.
- Second tactical family.
- New primitives.
- Execution cache implementation.
- Production deployment.

## Clean Source State

The proof run used a separate worktree at `/tmp/priori-workbench-r1-clean`, detached at `87b2441a626a67bd1222482f5be64e23e694a1f0`. Runtime symlinks for ignored local dependencies/data were excluded from Git status. The proof JSON records:

- `cleanGitStatus`: empty string
- `trackedDirtyStatus`: empty string
- Tactical Knowledge Pack hash: `5bf10d06011c3c31cff18da6b02d30d6f68d6b15ed32ff99cd2646f3b865b6af`

The main workspace still contains unrelated untracked review packets and parallel local artifacts; they were not staged into the Workbench R1 commit.
