# Validation Output

## Latest Local Verification

`make m1-1-gate-f-verify`

- Status: pass.
- Summary: 13 pass, 0 fail, 0 not-ready.
- Evidence: `artifacts/m1.1/gate-f-verification-report.json`.

`make m1-1-verify`

- Status: pass.
- Summary: 118 pass, 0 fail, 0 not-ready.
- Evidence: `artifacts/m1.1/verification-report.json`.

`make test`

- Status: pass.
- Summary: 20 tests passed.

`make m1-verify`

- Status: pass.
- M1 Gate A: 37 pass, 0 fail, 0 not-ready.
- M1 Gate B: 273 pass, 0 fail, 0 not-ready.
- M1 Gate C: 304 pass, 0 fail, 0 not-ready.

`git diff --check`

- Status: pass.
- Output: no whitespace errors.

## M1.1 Aggregate Gate Summary

From `artifacts/m1.1/verification-report.json`:

| Gate | Status | Pass | Fail | Not Ready |
| --- | --- | ---: | ---: | ---: |
| Gate A | pass | 49 | 0 | 0 |
| Gate B | pass | 14 | 0 | 0 |
| Gate C | pass | 10 | 0 | 0 |
| Gate D | pass | 11 | 0 | 0 |
| Gate E | pass | 21 | 0 | 0 |
| Gate F | pass | 13 | 0 | 0 |

## Inspector Summary

From `artifacts/m1.1/inspector/manifest.json`:

- Status: pass.
- Generated at: `2026-06-20T03:49:29+00:00`.
- Plan count: 2.
- Result count: 57.
- Non-match evaluation count: 3.

## Non-Fatal Runtime Notes

Earlier local runs emitted PyArrow/Matplotlib cache warnings in the sandbox. They were non-fatal and did not affect pass/fail status.
