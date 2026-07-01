# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

Date: 2026-06-21

## Commands

```bash
python -m py_compile src/tqe/workshop/m1_2.py src/tqe/verification/m1_2_gate_s0.py src/tqe/verification/m1_2_gate_s1.py
```

Result: pass.

```bash
make m1-2-verify
```

Result: pass.

Summary:

```json
{"status": "pass", "summary": {"fail": 0, "pass": 2}}
```

```bash
make m1-1-gate-s7r-verify
```

Result: pass.

Summary:

```json
{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 13}}
```

```bash
make test
```

Result: pass.

Summary:

```text
Ran 27 tests in 176.735s
OK
```

## Report Artifacts

- `reports/gate-s0-verification-report.json`
- `reports/gate-s1-verification-report.json`
- `reports/verification-report.json`
- `reports/m1-1-gate-s7r-verification-report.json`

## Full Repo Requirement

These commands require the full repository, local Python environment, canonical
data artifacts, and Make targets. They cannot be rerun from this packet alone.
