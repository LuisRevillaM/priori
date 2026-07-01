# Validation Output

## Command: `make scp-0-verify`

Working directory: `/Users/luisrevilla/Documents/priori`

Status: PASS

Transcript: `commands/make-scp-0-verify.txt`

Summary:

- SCP-0 report status: `PASS`.
- Runtime capabilities bound: 11.
- Runtime capabilities including operators: 19.
- Duplicate runtime bindings: 0.
- Orphan runtime capabilities: 0.
- Unresolved runtime bindings: 0.
- Operators semantically defined: 8 / 8.
- Recipes mapped: 4 / 4.
- Validated compositions mapped: 1 / 1.
- Atlas leakage into product projection: 0.
- Atlas leakage into AI projection: 0.
- Focused adversarial unit suite: 10 tests OK.

## Command: `make m1-1-build`

Working directory: `/Users/luisrevilla/Documents/priori`

Status: PASS

Purpose:

The first full-suite run exposed that `generated/capability-catalog.json` was stale relative to the current runtime catalog. The generated file was refreshed through the existing project generator before rerunning the full suite.

Generated hashes:

- `generated/capability-catalog.json`: `4e861a45d81466babc83f43250369e8cdb4d3d67613c321e3b34b3b187985c61`
- `generated/tactical-query-plan.schema.json`: `c0114fe65876fc12a8439ac370e68bfdf5486d516f0d8237f2b2c4cce78b5dbe`
- `generated/tactical-query-plan.types.ts`: `4176a3ddbc2e04d784fba11eb1d7d66ed6a134f44251bcaba0ab55e57e4fdf4c`

Only `generated/capability-catalog.json` changed.

## Command: `make test`

Working directory: `/Users/luisrevilla/Documents/priori`

Status: PASS

Terminal summary from the completed run:

```text
Ran 92 tests in 289.383s

OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

The full transcript is not included because the run was long and mostly progress dots. Reproduction requires the full repository and local environment.
