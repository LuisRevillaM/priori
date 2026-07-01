# Validation Output

## Commands Claimed Green

Working directory:

```text
/Users/luisrevilla/Documents/priori
```

Commands:

```text
HERMES_HOME=/Users/luisrevilla/.hermes-priori CODEX_HOME=/Users/luisrevilla/.codex make m1-2-gate-s2ie-verify
HERMES_HOME=/Users/luisrevilla/.hermes-priori CODEX_HOME=/Users/luisrevilla/.codex make m1-2-gate-s2id-verify
HERMES_HOME=/Users/luisrevilla/.hermes-priori CODEX_HOME=/Users/luisrevilla/.codex make m1-2-gate-s2i-verify
make m1-2-gate-s0-verify
make test
git diff --check
```

Observed results:

```text
S2I-E frontier freeze: 17 passed, 0 failed
S2I-D unseeded Hermes authoring: 20 passed, 0 failed
S2I-A verification: 16 passed, 0 failed
S0 verification: 17 passed, 0 failed
Ran 27 tests in 188.358s, OK
git diff --check: no output
```

## Included Reports

- `artifacts/s2i-e-frontier-freeze-report.json`
- `artifacts/s2i-d-unseeded-hermes-report.json`
- `artifacts/gate-s2i-verification-report.json`

## Requires Full Repo

The packet cannot rerun validation because it omits:

- full Python package and tests
- local virtualenv
- local Hermes home and session database
- canonical data/artifact tree
- credentials and device-auth state

Treat included validation as local controller evidence, not independently reproducible proof.
