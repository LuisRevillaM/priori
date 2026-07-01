# Validation Output

## Backend Contract Tests

Command:

```bash
.venv/bin/python -m unittest tests.test_workbench_beta0_contract
```

Result: pass, 13 tests.

Full output:

- `commands/backend-contract-tests.txt`

## N1 Proof Gates

Commands:

```bash
make n1d1-verify
make n1d-verify
make n1i-verify
```

Results:

- N1D.1: `VERIFIED`, no blocking reasons.
- N1D: pass, 12/12.
- N1I: pass, 10/10.

Full output:

- `commands/n1-proof-gates.txt`

## Workbench Acceptance

Command:

```bash
cd apps/workbench-alpha && npm run test:acceptance
```

Result: pass before packaging.

Summary:

- contracts: pass
- fixtures/no hardcoded tactical data: pass
- unit suites: pass
- Playwright E2E: 16 passed

Note: Playwright emitted existing local `BrokenPipeError` server noise from aborted replay/inspection responses; tests completed successfully.

## Live Route Smoke

Public route tested:

- `https://priori-integrated-alpha.onrender.com`

Result:

- health: `ALIVE`
- model status: `HERMES_CONFIGURED`
- protected runner status: 403 as expected
- interpretation: `PLAN_INTERPRETED`
- provenance: `HERMES_NOVEL_COMPOSITION`
- source: `hermes_attested_origin_bundle`
- validation: generic, bound hash `68e7d1a7cd29d7bd0490765694d8f4700c882046510e78a2579b8845358f1bb0`
- execution: 14 results
- first replay: 101 frames
- entry mode: `PRESENT_AT_OPEN`
- cache: `HIT`, because the same deterministic plan had already been executed by the protected N1I runner

Full response bundle:

- `route-smokes/live-beta1c-smoke.json`
