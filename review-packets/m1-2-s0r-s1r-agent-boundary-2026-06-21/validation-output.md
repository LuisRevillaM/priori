# Validation Output

Command: `make m1-2-gate-s0-verify`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 10}}`
Evidence: `artifacts/m1.2/gate-s0-verification-report.json`

Command: `make m1-2-gate-s1-verify`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 8}}`
Evidence: `artifacts/m1.2/gate-s1-verification-report.json`

Command: `make m1-2-verify`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 2}}`
Evidence: `artifacts/m1.2/verification-report.json`

Command: `make m1-1-gate-s7r-verify`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 13}}`

Command: `make test`
Status: pass
Summary: `Ran 27 tests in 200.133s - OK`

Reproduction requires the full repo, virtualenv, and local canonical data.
