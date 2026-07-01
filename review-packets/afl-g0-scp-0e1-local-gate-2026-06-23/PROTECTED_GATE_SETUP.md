# Protected Gate Setup

The repo-local AFL-G0 gate can build candidate packets, run public checks, run
public canaries, and create gate-result/certificate artifacts. It is still
`SELF_VERIFIED` until the following authority boundary exists outside builder
control.

## Required Protected Boundary

A protected gate runner must provide:

- a non-builder CI or execution identity;
- a protected copy of the gate runner, or a protected workflow that cannot be
  changed by the candidate builder;
- hidden holdout and mutation suites;
- protected denominator definitions;
- a signing key supplied by the gate environment, never committed to the repo;
- a protected promotion channel, such as protected tags or signed certificate
  publication.

## Required Environment

The gate runner recognizes these environment variables:

```text
AFL_GATE_PROTECTION_LEVEL=PROTECTED_CI
AFL_PROTECTED_SUITE_ID=<stable suite id>
AFL_PROTECTED_SUITE_HASH=<hash of hidden suite and denominator set>
AFL_GATE_SIGNING_KEY=<secret supplied by protected gate identity>
```

Without all four, `make afl-g0-gate` must leave the gate result as `BLOCKED`.

## Expected Command

```bash
make scp-0-verify
make afl-g0-verify
make afl-g0-gate
```

The protected runner should archive:

- `artifacts/autonomous/afl-g0-scp-0e1-gate-result.json`
- `artifacts/autonomous/afl-g0-scp-0e1-promotion-certificate.json`
- `artifacts/autonomous/afl-g0-scp-0e1-canary-report.json`
- `review-packets/afl-g0-scp-0e1-local-gate-2026-06-23.zip`
- `review-packets/afl-g0-scp-0e1-local-gate-2026-06-23.zip.sha256`

## Promotion Rule

Only a gate result with:

```text
result = PROMOTED
protection_level = PROTECTED_CI
promotion_signature present
public verification PASS
canary verification PASS
protected suite hash present
```

can promote a milestone. A local `BLOCKED` result is useful evidence, but it is
not promotion.
