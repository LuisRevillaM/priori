# Validation Output

Working directory: `/Users/luisrevilla/Documents/priori`

## Passed

`make m1-1-gate-s1-verify`

- status: pass
- summary: 8 pass, 0 fail, 0 not_ready
- report: `artifacts/gate-s1-verification-report.json`

`make m1-1-gate-s2-verify`

- status: pass
- summary: 4 pass, 0 fail, 0 not_ready
- report: `artifacts/gate-s2-verification-report.json`

`make m1-1-gate-s3-verify`

- status: pass
- summary: 5 pass, 0 fail, 0 not_ready
- report: `artifacts/gate-s3-verification-report.json`

`make m1-1-gate-c-verify`

- status: pass
- summary: 10 pass, 0 fail, 0 not_ready
- report: `artifacts/gate-c-verification-report.json`

`make m1-1-gate-r5-verify`

- status: pass
- summary: 10 pass, 0 fail, 0 not_ready
- report: `artifacts/gate-r5-verification-report.json`

`make test`

- status: pass
- summary: 26 tests OK

`git diff --check`

- status: pass

## Requires Full Repo

All validation commands require the full repository, Python environment, and local data artifacts. This packet is inspection-only.
