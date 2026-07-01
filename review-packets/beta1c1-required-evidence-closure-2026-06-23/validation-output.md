# Validation Output

All commands were run from:

```text
/Users/luisrevilla/Documents/priori
```

## Local Verification

```text
make m1-2-gate-s2i-verify
```

Result:

```text
S2I-A verification: 25 passed, 0 failed
```

```text
make n1d-freeze
make n1d-verify
```

Result:

```text
N1D freeze: frozen
N1D gate: pass, 15 passed, 0 failed
```

```text
make n1d1-verify
```

Result:

```text
attestation_status: VERIFIED
blocking_reasons: []
```

```text
make n1c-verify
make n1i-verify
```

Result:

```text
N1C: 8 passed, 0 failed
N1I: 10 passed, 0 failed
```

```text
.venv/bin/python -m unittest tests.test_workbench_beta0_contract
```

Result:

```text
14 tests OK
```

```text
.venv/bin/python -m unittest discover tests
```

Result:

```text
Ran 53 tests in 207.295s
OK
```

```text
npm --prefix apps/workbench-alpha run test:acceptance
```

Result:

```text
contracts passed
fixture scan passed
unit tests passed
build passed
16 Playwright tests passed
```

## Deployment Verification

Render deploy:

```text
cf5b058 -> dep-d8t75668bjmc73ec8fm0 -> live
630b2b8 -> dep-d8t79k7lk1mc73apb9l0 -> live
```

Live hero smoke:

```text
/healthz: ALIVE
/readyz: READY
/api/interpret: PLAN_INTERPRETED, HERMES_NOVEL_COMPOSITION
/api/execution-cache-status before first execution: MISS
/api/execute: pass, execution_complete=true, requested_evidence_failure_count=0
result count: 14
required missing count: 0
replay frames: 101
```

Repeat cache smoke:

```text
/api/execution-cache-status: HIT
/api/execute: HIT, pass, execution_complete=true, requested_evidence_failure_count=0
```
