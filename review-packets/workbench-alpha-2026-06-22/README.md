# Workbench Alpha Review Packet

Packet type: `inspection_packet_only`

This packet is for an external reviewer who does not have repo access and needs
to inspect the Workbench Alpha implementation and acceptance evidence.

## Scope

Review commit:

```text
a38cd1d9d95cdf7e0eb2c07e357a3f233ec197d6 Add Workbench Alpha host UI
```

The commit adds a React/Vite Workbench Alpha app, a host-owned HTTP application
service, browser-level Playwright acceptance journeys, a frontend fixture scan,
and Workbench-specific acceptance documentation.

The browser uses `/api` on the host service. It does not call MCP, Hermes, the
model, or the analytical runtime directly.

## What Is Real

- Approved recipe and experimental corridor flows execute through real host
  validation, host confirmation, deterministic execution, result inspection, and
  canonical coordinate replay.
- Result rails, evidence aliases, predicate traces, replay windows, screenshots,
  videos, and API traces were generated from the local runtime during the
  post-commit acceptance run.
- Proof JSON records source commit, host-service commit, execution IDs, result
  IDs, replay IDs, replay hashes, payload byte sizes, frame counts, frame
  cadence, and API durations.

## What Is Local Or Generated

- Playwright screenshots, videos, reports, replay artifacts, and proof JSON are
  local generated evidence.
- This is not a standalone reproducible package; rerunning validation requires
  the full repository, local dependencies, and local data/artifact availability.

## Validation Run

The post-commit validation run passed:

```text
make workbench-alpha-verify
5 Playwright tests passed in 1.8m
```

Additional check:

```text
.venv/bin/python -m py_compile src/tqe/workshop/app_service.py
passed
```

`npm audit --json` reports one low-severity transitive `esbuild` advisory,
recorded in `commands/npm-audit.json`.

## Review Map

- `diffs/commit-a38cd1d.patch` - isolated implementation patch.
- `validation-output.md` - command summary and pass/fail status.
- `artifacts/proof/*.json` - execution IDs, result IDs, replay hashes, payload
  sizes, and performance baselines.
- `artifacts/api-traces/*.json` - host API request/response summaries.
- `screenshots/` - key UI states.
- `videos/` - short recordings for both real query paths and state handling.
- `playwright-report/index.html` - browser test report.
- `source-excerpts/app_service.py` - host HTTP boundary.
- `tests/workbench-alpha.spec.ts` - browser acceptance journeys and API denial
  checks.
- `tests/check-no-tactical-fixtures.mjs` - frontend fixture scanner.

## Not Proven

- Final visual polish is intentionally out of scope.
- S3 feedback/revision behavior is not implemented.
- Model-backed interpretation remains unavailable; manual fallback is covered.
- A second tactical family and new primitives are not implemented.
- The packet cannot independently rerun validation without the full repo.
