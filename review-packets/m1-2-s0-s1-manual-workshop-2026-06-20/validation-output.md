# Validation Output

Command: `make m1-2-gate-s0-verify`
Working directory: `/Users/luisrevilla/Documents/priori`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 8}}`
Evidence: `artifacts/m1.2/gate-s0-verification-report.json`

Command: `make m1-2-gate-s1-verify`
Working directory: `/Users/luisrevilla/Documents/priori`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 8}}`
Evidence: `artifacts/m1.2/gate-s1-verification-report.json`

Command: `make m1-2-verify`
Working directory: `/Users/luisrevilla/Documents/priori`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "pass": 2}}`
Evidence: `artifacts/m1.2/verification-report.json`

Command: `make m1-1-gate-s7r-verify`
Working directory: `/Users/luisrevilla/Documents/priori`
Status: pass
Summary: `{"status": "pass", "summary": {"fail": 0, "not_ready": 0, "pass": 13}}`
Evidence: `artifacts/m1.1/gate-s7r-verification-report.json` in full repo; command output summarized here.

Command: `make test`
Working directory: `/Users/luisrevilla/Documents/priori`
Status: pass
Summary: `Ran 27 tests in 169.012s - OK`

Validation requiring full repo:
- all Make targets require source tree, Python environment, and canonical data.
- coordinate replay verification requires local canonical parquet files, not included in this packet.
