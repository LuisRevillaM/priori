# Learning - M1 Gate C Tactical Proof

Date: 2026-06-19

## Fact

The frozen `ball_side_block_shift_v1` query can produce a verified proof pack from public IDSSE/DFL tracking data without match video, synthetic moments, or provider integration.

## Decision

Gate C uses a query-specific Python detector and a minimal strict TypeScript replay-proof validator. The tactical scan runs at 5 Hz while replay evidence stays anchored to canonical 25 Hz source frame IDs. Outcome classification runs over the configured horizon after the anchor; the defensive shift search remains inside the eligible possession segment.

## Evidence

- `config/queries/ball_side_block_shift.v1.yaml`
- `artifacts/m1/gate-c/query-freeze.json`
- `artifacts/m1/gate-c/calibration-report.json`
- `artifacts/m1/gate-c/evaluation-report.json`
- `artifacts/m1/gate-c/proof-pack-manifest.json`
- `artifacts/m1/gate-c/replay-proof-report.json`
- `artifacts/m1/gate-c/verification-report.json`
- `docs/queries/ball-side-block-shift/semantic-gold-set.v1.json`
- `artifacts/m1/evidence/*/bundle.json`
- `artifacts/m1/evidence/*/replay.json`
- `delivery/m1/reviews/gate-c-controller-review.md`

## Current Result

`make gate-c-verify` passes with 304 passing Python checks, zero failures, and zero not-ready checks. The TypeScript replay proof passes with 82 checks. The selected proof set contains 16 accepted real moments across all four Fortuna evaluation matches: 11 `LOST_BEFORE_SWITCH`, 2 `RETAINED_NO_SWITCH`, and 3 `SWITCHED`.

`make m1-verify` passes across all accepted gates: Gate A 37/0/0, Gate B 273/0/0, and Gate C 304/0/0.

## Follow-Up

Final M1 owner acceptance is still pending. M2 should add query breadth and semantic gold sets before broadening tactical claims or building natural-language query drafting.
