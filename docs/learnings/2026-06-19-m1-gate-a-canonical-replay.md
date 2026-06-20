# Learning - M1 Gate A Canonical Replay

Date: 2026-06-19

## Fact

Floodlight `1.2.0` can parse the source-locked `J03WOH` tracking and event XML files locally. The full tracking parse took about 21-24 seconds during Gate A builds and stayed below 750 MB max resident set size in the local run.

## Decision

Gate A canonical positions are written from Floodlight's DFL position arrays, using raw XML ball frames as the authoritative frame ID and timestamp index. This preserves the M1 boundary: Floodlight remains behind the adapter, while canonical Parquet is the project-owned data contract.

## Evidence

- `src/tqe/adapters/floodlight_idsse_reader.py`
- `src/tqe/data/gate_a_build.py`
- `src/tqe/evidence/gate_a_replay.py`
- `artifacts/m1/gate-a/canonical-summary.json`
- `artifacts/m1/gate-a/raw-parity-report.json`
- `artifacts/m1/gate-a/data-quality-report.json`
- `artifacts/m1/gate-a/resource-report.json`
- `artifacts/m1/gate-a/replay-bundle/manifest.json`
- `artifacts/m1/gate-a/replay-screenshot.png`

## Current Result

`make gate-a-verify` passes with 37 passing checks, zero failures, and zero not-ready checks. Gate A is still pending independent review and owner acceptance; no tactical primitive or detector work should begin until that review is complete.

## Follow-Up

Send a focused Gate A review packet before promoting Gate A to accepted. The review should check source provenance, Floodlight boundary, canonical schema sanity, raw parity adequacy, orientation derivation, replay-source provenance, and whether the 5m out-of-pitch tolerance should be tightened before Gate B.
