# Validation Output

## `make scp-0-verify`

Working directory:

`/Users/luisrevilla/Documents/priori`

Packet log:

`commands/make-scp-0-verify.txt`

Result:

`PASS`

Important lines:

```text
"status": "PASS"
Ran 22 tests in 5.205s
OK
```

Summary:

- 11 runtime capabilities bound.
- 8 runtime operators semantically defined.
- 4 registered recipes mapped.
- 1 validated composition mapped.
- 741 atlas entries remain isolated.
- 0 product atlas leakage.
- 0 AI atlas leakage.

## `make test`

Working directory:

`/Users/luisrevilla/Documents/priori`

Packet log:

`commands/make-test.txt`

Result:

`PASS`

Important lines:

```text
Ran 104 tests in 282.155s
OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

## SCP-0 Verification Summary Artifact

Packet summary:

`commands/scp0-verification-summary.json`

Copied source artifact:

`repo-files/artifacts/scp-0/verification-report.json`

Key result:

```text
status = PASS
projection_differences.product.added = ["composition:composition.ai_corridor_destination.2026_06_23"]
projection_differences.ai.added = ["composition:composition.ai_corridor_destination.2026_06_23"]
atlas_leakage.product = 0
atlas_leakage.ai = 0
```

The changed entries in projection parity are expected because SCP-0C projections now contain richer registry metadata than the legacy baseline catalog/knowledge-pack records.

