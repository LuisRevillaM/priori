# Learning - M1 Gate A Source Lock

Date: 2026-06-19

## Fact

The official IDSSE / Sportec Open DFL dataset is available through Figshare article `28196177`, version `1`, with article DOI `10.6084/m9.figshare.28196177.v1` and paper DOI `10.1038/s41597-025-04505-y`.

## Decision

Gate A locks the official Figshare files directly. Mirror metadata may be useful for orientation, but it is not source-of-truth for match IDs, sizes, checksums, or download URLs.

## Evidence

- `scripts/data/source_lock_idsse.py`
- `artifacts/m1/gate-a/source-manifest.json`
- `artifacts/m1/gate-a/verification-report.json`

## Current Result

The `J03WOH` metadata, events, and tracking XML files have been downloaded locally and validated against official Figshare sizes and MD5 checksums. Gate A verification currently reports source-lock checks as passing and downstream canonical/replay artifacts as not ready.

## Follow-Up

Implement the Floodlight-backed parser and canonical Parquet writer for `J03WOH`. Do not start tactical primitives until Gate A source, canonicalization, raw parity, quality, orientation, resource, and replay evidence all pass.
