# Validation Output

## Clean Proof Command

- command: `make workbench-alpha-verify`
- working directory: `/tmp/priori-workbench-r1-clean`
- source commit: `87b2441a626a67bd1222482f5be64e23e694a1f0`
- result: pass

Summary:

```text
npm --prefix apps/workbench-alpha run test:acceptance
test:contracts: pass
test:fixtures: pass, violations []
test:unit: pass, pitch geometry tests passed, playback tests passed
build: pass, Vite production build completed
playwright test: 5 passed
```

Playwright tests passed:

```text
approved recipe runs from query to replay with evidence and predicate trace
experimental corridor runs from query to replay with real result rail
clarification, capability-gap, and model-unavailable states remain explicit
host authority is enforced through public API routes
backend execution artifacts are the source of result inspection
```

## Clean Status Evidence

See:

- `commands/git-status-clean-worktree.txt`
- `artifacts/approved-proof.json`
- `artifacts/experimental-proof.json`

Both proof JSON files record empty `cleanGitStatus` and `trackedDirtyStatus`.

## Performance Baseline

Approved path:

- execute plus initial inspection: 29,409 ms
- selected result inspection: 307 ms
- rapid final inspection: 679 ms
- replay payload bytes: 296,144
- replay frames: 101
- replay cadence: 25 Hz

Experimental path:

- execute plus initial inspection: 46,938 ms
- selected result inspection: 262 ms
- rapid final inspection: 678 ms
- replay payload bytes: 296,102
- replay frames: 101
- replay cadence: 25 Hz

See `docs/performance-cache-plan.md` for the cache/progress plan.

## npm Audit

`npm audit --json` reports one low-severity vulnerability. It is recorded in `commands/npm-audit.json` and was not remediated in this R1 scope.
