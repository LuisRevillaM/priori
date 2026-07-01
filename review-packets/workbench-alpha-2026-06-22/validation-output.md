# Validation Output

## `make workbench-alpha-verify`

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Status: pass

Summary:

```text
npm --prefix apps/workbench-alpha run test:acceptance
npm --prefix apps/workbench-alpha run test:fixtures
  ok: true
  violations: []
npm --prefix apps/workbench-alpha run test:e2e
  vite build passed
  5 Playwright tests passed in 1.8m
```

Covered journeys:

- approved recipe query to interpretation, host confirmation, execution, result,
  evidence, predicate trace, replay, playback/scrub, and known-timestamp
  inspection;
- experimental corridor query through the same host-owned path;
- clarification UI;
- capability-gap UI;
- model-unavailable state with manual fallback;
- host API denial checks;
- backend artifact dependency check.

Evidence:

- `playwright-report/index.html`
- `artifacts/proof/approved-proof.json`
- `artifacts/proof/experimental-proof.json`
- `artifacts/api-traces/approved.json`
- `artifacts/api-traces/experimental.json`
- `screenshots/`
- `videos/`

## `.venv/bin/python -m py_compile src/tqe/workshop/app_service.py`

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Status: pass

Output: no output; command exited successfully.

## `npm --prefix apps/workbench-alpha audit --json`

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Status: recorded advisory

Result:

```text
1 low-severity vulnerability
package: esbuild
advisory: GHSA-g7r4-m6w7-qqqr
title: esbuild allows arbitrary file read when running the development server on Windows
fixAvailable: true
```

Full JSON:

```text
commands/npm-audit.json
```
