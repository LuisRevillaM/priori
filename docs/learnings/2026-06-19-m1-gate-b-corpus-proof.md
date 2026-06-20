# Learning - M1 Gate B Corpus Proof

Date: 2026-06-19

## Fact

All seven planned IDSSE/DFL matches can be source-locked from official Figshare files, parsed through Floodlight, and canonicalized locally as a sequential corpus.

## Decision

Gate B preserves the Gate A parser boundary and builds the corpus one match at a time. The canonical corpus includes player and ball tracking, not referee tracking. Referee frame sets found in `J03WMX` and `J03WN1` are excluded from raw parity sampling because they are outside the M1 tactical entity contract.

## Evidence

- `artifacts/m1/gate-b/source-manifest.json`
- `artifacts/m1/gate-b/corpus-summary.json`
- `artifacts/m1/gate-b/raw-parity-report.json`
- `artifacts/m1/gate-b/data-quality-report.json`
- `artifacts/m1/gate-b/resource-report.json`
- `artifacts/m1/gate-b/verification-report.json`
- `delivery/m1/reviews/gate-b-controller-review.md`

## Current Result

`make gate-b-verify` passes with 273 passing checks, zero failures, and zero not-ready checks. The corpus contains 22,876,878 canonical position observations and 126 deterministic raw parity samples with zero failures.

## Follow-Up

Gate C may begin. Treat Floodlight event `gameclock` warnings as a Gate C risk when deriving possession/outcome timing from event data.
