# Validation Output

## Summary

All S4-required checks passed locally.

| Command | Working Directory | Result | Evidence |
| --- | --- | --- | --- |
| `make m1-1-gate-s4-verify` | `/Users/luisrevilla/Documents/priori` | pass, 13/0/0 | `commands/make-m1-1-gate-s4-verify.txt`, `artifacts/gate-s4-verification-report.json` |
| `make m1-1-gate-s3r-verify` | `/Users/luisrevilla/Documents/priori` | pass, 13/0/0 | `artifacts/gate-s3r-verification-report.json` |
| `make m1-1-gate-e-verify` | `/Users/luisrevilla/Documents/priori` | pass, 21/0/0 | `artifacts/gate-e-verification-report.json` |
| `make test` | `/Users/luisrevilla/Documents/priori` | pass, 27 tests | controller run summary |
| `git diff --check` | `/Users/luisrevilla/Documents/priori` | pass | no output |
| packet secret scan | `/Users/luisrevilla/Documents/priori` | pass, no matches | `commands/secret-scan.txt` |

## S4 Report Highlights

- Result count: 15.
- Trace count: 105.
- Compatibility profile: `generic`.
- Labels: `DESTINATION_ENTERED`, `CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY`.
- Frozen M1 parity through explicit legacy helper: 180 results, 900 traces.

## Reproducibility Boundary

The included archive is inspection-only. Rerunning commands requires the full repo, local dependencies, and canonical/raw match data.
