# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

Current commit at packet build:

```text
8d68e3d62c1683407efa6b8d9890c9b2231dc4f4
```

Branch:

```text
codex/m1-1-s1-ir-binder
```

## Commands Run

```text
make m1-1-gate-s7-verify
```

Result: pass, `{"fail": 0, "not_ready": 0, "pass": 7}`.

```text
make m1-1-gate-s6-verify
```

Result: pass, `{"fail": 0, "not_ready": 0, "pass": 8}`.

```text
make m1-1-gate-s5-verify
```

Result: pass, `{"fail": 0, "not_ready": 0, "pass": 6}`.

```text
make m1-1-gate-s4-verify
```

Result: pass, `{"fail": 0, "not_ready": 0, "pass": 16}`.

```text
make m1-1-gate-a-verify
```

Result: pass, `{"fail": 0, "not_ready": 0, "pass": 78}`.

```text
make test
```

Result: pass, 27 tests.

```text
git diff --check
```

Result: pass.

## Included Report Files

- `artifacts/gate-s7-verification-report.json`
- `artifacts/gate-s6-verification-report.json`
- `artifacts/gate-s5-verification-report.json`
- `artifacts/gate-s4-verification-report.json`
- `artifacts/gate-s3r-verification-report.json`
- `artifacts/gate-b-verification-report.json`
- `artifacts/binder-validation-report.json`

## Reproduction Limitation

This packet is inspection-only. Rerunning validation requires the full repository, Python dependencies, and local canonical data under `data/canonical/v1`.
