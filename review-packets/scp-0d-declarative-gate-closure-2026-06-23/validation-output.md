# Validation Output

## Focused SCP-0 Verification

Command:

```bash
make scp-0-verify
```

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Result: `PASS`

Evidence:

- Full log: `commands/make-scp-0-verify.txt`
- Machine report: `repo-files/artifacts/scp-0/verification-report.json`

Summary:

```text
SCP-0 report status: PASS
Findings: []
Focused tests: 32 passed
Registry lock hash: 45c0e5d12effd16e18e44601a9b591e27866165b55a70707508814422173090f
Plan artifact revision: 93b306dfe9cadf241418824af082140a7dd23823155600f1f42722c94e7ff1d0
Baseline artifact revision: 9e5862c0d58c8b1a6e2a9af6504c1638bedd57a9f33dc5e0371d08bb01829786
```

## Full Repository Test Suite

Command:

```bash
make test
```

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Result: `PASS`

Evidence:

- Full log: `commands/make-test.txt`

Summary:

```text
Ran 114 tests in 310.172s
OK
{"attestation_status": "VERIFIED", "blocking_reasons": []}
```

## Packet Integrity

Commands:

```bash
shasum -a 256 -c SHA256SUMS
unzip -t scp-0d-declarative-gate-closure-2026-06-23.zip
```

Result: `PASS`

Evidence:

- `SHA256SUMS`
- Adjacent archive checksum: `review-packets/scp-0d-declarative-gate-closure-2026-06-23.zip.sha256`

## Workspace Caveat

`commands/git-status-short.txt` records unrelated dirty/untracked files that existed before and after this packet. They were not staged into SCP-0D and were not reverted.
