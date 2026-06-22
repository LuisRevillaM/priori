# Workbench Alpha Acceptance

Workbench Alpha is implemented and locally verified as a host-owned query-to-replay
surface. The browser talks only to the host `/api` service in
`src/tqe/workshop/app_service.py`; it does not call MCP, Hermes, the model, or
the analytical runtime directly.

## Boundary

`app_service.py` is an HTTP/orchestration boundary. It serves the built React
app, translates public `/api` requests, reloads the approved recipe from
host-owned config before validation, calls existing workshop/runtime functions,
and returns DTOs for plans, validation, confirmation, execution, inspection, and
replay.

It does not calculate tactical primitives, reconstruct predicate traces, parse
raw tracking data, or mint browser-provided execution authorization IDs.

## Verification

Run:

```bash
make workbench-alpha-verify
```

This runs:

```bash
npm --prefix apps/workbench-alpha run test:fixtures
npm --prefix apps/workbench-alpha run test:e2e
```

The acceptance suite covers:

- approved recipe query to interpretation, host confirmation, execution, result,
  evidence, predicate trace, coordinate replay, scrub/playback, and known
  timestamp inspection;
- experimental corridor query through the same path;
- clarification, capability-gap, model-unavailable, and manual fallback states;
- honest interpretation source labels for manual preset and manual host
  interpreter paths;
- generated success and error response contract validation;
- host-owned execution cache status, cache-hit proof after execution, and
  visible cache progress;
- public replay DTO sanitization: no `plan_path`, no local filesystem paths, and
  stable logical canonical-source IDs;
- public API denial checks for forged authorization, compatibility-profile
  override, unconfirmed execution, cache-hit authorization bypass, local artifact
  paths, and host-only routes;
- frontend source scanning for hardcoded result IDs, match timestamps,
  coordinates, replay frames, and fallback tactical moments.

## Proof Artifacts

Playwright writes local review evidence under:

```text
artifacts/workbench-alpha/
```

Relevant subdirectories:

- `review-proof/` for API traces, screenshots, source hashes, build hashes,
  replay payload hashes, and performance baselines;
- `playwright-report/` for the HTML/JSON report;
- `playwright-output/` for videos, traces, and failure artifacts.

## Performance Baseline

The Playwright proof JSON records API durations for interpretation, validation,
confirmation, execution, result inspection, replay loading, and result selection.
Replay frame count, frame cadence, payload byte size, and replay payload hash are
recorded per real query path.

## Dependency Advisory

`npm audit --json` currently reports one low-severity transitive `esbuild`
advisory (`GHSA-g7r4-m6w7-qqqr`) through the browser build toolchain. It is
recorded but not broadly upgraded in this slice.

## Non-Goals

This slice does not add final visual polish, S3 feedback/revision behavior, a
second tactical family, model-backed interpretation, browser-to-MCP calls, or
new tactical primitives.
