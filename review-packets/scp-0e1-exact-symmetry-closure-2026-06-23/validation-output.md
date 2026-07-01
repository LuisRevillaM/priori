# Validation Output

## `make scp-0-verify`

- working directory: `/Users/luisrevilla/Documents/priori`
- result: PASS
- evidence: `commands/make-scp-0-verify.txt`
- summary:
  - semantic parity report status: `PASS`
  - runtime capabilities bound: `11`
  - operators semantically defined: `8`
  - recipes mapped: `4`
  - validated compositions mapped: `1`
  - atlas leakage: product `0`, AI `0`
  - focused SCP-0 adversarial tests: `52` tests OK

## `make test`

- working directory: `/Users/luisrevilla/Documents/priori`
- result: PASS
- run completed before packet assembly in the same workspace
- summary:

```text
Ran 134 tests in 294.050s

OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

The full repository suite output is not copied into this inspection packet.
Rerunning it requires the full repository and local test data.

## `git diff --check`

- working directory: `/Users/luisrevilla/Documents/priori`
- result: PASS
- command was scoped to the SCP-0E.1 source, registry, tests, and delivery files.

## Git State Note

After commit `bb3195b`, unrelated pre-existing dirty files remain in the
workspace, including N1C/N1D artifacts and older review/audit packet files.
They were not staged or included in this commit.
