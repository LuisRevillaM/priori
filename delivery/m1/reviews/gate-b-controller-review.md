# Gate B Controller Review

Date: 2026-06-19

Reviewer: controller

Decision: ACCEPT WITH CONTROLLER-ONLY REVIEW

## Scope

This review covers only M1 Gate B:

- source-locking all seven expected IDSSE/DFL matches;
- canonicalizing every match through the existing Floodlight adapter boundary;
- verifying corpus schemas, row counts, frame uniqueness, entity identity, coordinate bounds, orientation, and holdout perspectives;
- confirming corpus processing is sequential one match at a time.

It does not review tactical primitives, query calibration, detector result quality, evidence bundle semantics, or the future TypeScript replay proof.

## Evidence Reviewed

- `artifacts/m1/gate-b/source-manifest.json`
- `artifacts/m1/gate-b/corpus-summary.json`
- `artifacts/m1/gate-b/raw-parity-report.json`
- `artifacts/m1/gate-b/data-quality-report.json`
- `artifacts/m1/gate-b/resource-report.json`
- `artifacts/m1/gate-b/verification-report.json`
- `data/canonical/v1/matches.parquet`
- `data/canonical/v1/teams.parquet`
- `data/canonical/v1/players.parquet`
- `data/canonical/v1/orientation.parquet`
- `data/canonical/v1/frames/match_id=*/period=*.parquet`
- `data/canonical/v1/positions/match_id=*/period=*.parquet`
- `data/canonical/v1/events/match_id=*.parquet`
- `src/tqe/data/gate_b_build.py`
- `src/tqe/verification/gate_b.py`

## Verification Commands

```bash
make provision-corpus
make gate-b-build
make gate-b-verify
make m1-verify
```

Observed results:

- `make provision-corpus`: pass; all seven official matches source-locked.
- `make gate-b-build`: pass; seven matches, raw parity pass, data quality pass.
- `make gate-b-verify`: pass; 273 passing checks, 0 failures, 0 not-ready checks.
- `make m1-verify`: expected fail; Gate A and Gate B pass, Gate C is not ready.

## Findings

No blocking findings for Gate B.

The source manifest contains all seven expected match IDs and every raw metadata, event, and tracking XML file validates against official Figshare size, MD5, and local SHA-256.

The corpus canonicalizer processes one match at a time and writes canonical Parquet outputs per match/period. Aggregate metadata tables are then rebuilt across all seven matches.

Raw parity passes on 126 deterministic player/ball samples across the corpus with zero failures and zero coordinate delta. Referee tracking frame sets are present in `J03WMX` and `J03WN1`; those are intentionally excluded from raw parity because referee entities are not part of the M1 canonical tactical model.

Data quality passes across 22,876,878 canonical position observations. No coordinate exceeds pitch dimensions plus the accepted 5m tolerance.

Orientation and perspective checks pass, including Bayern as away perspective in `J03WMX` and Leverkusen as away perspective in `J03WN1`.

## Non-Blocking Concerns

- Floodlight emitted warnings that an event `gameclock` column does not match its internal defined range for some matches. Gate B does not depend on tactical event timing semantics yet, but Gate C possession and outcome logic must treat event-clock alignment as a risk.
- The accepted coordinate tolerance remains pitch plus 5m. Gate C tactical geometry should use canonical centered metres but avoid assuming all observations lie strictly inside the painted pitch.
- Raw parity is deterministic sampled parity, not exhaustive row-level parity. This is acceptable for Gate B because frame counts, schemas, identities, and data-quality checks are also enforced.
- Independent review was not performed for Gate B. This follows the current controller-only execution mode requested by the owner after the prior review agent stalled.

## Promotion Decision

Gate B is accepted for purposes of proceeding to Gate C.

The acceptance is narrow:

- Gate A remains accepted.
- Gate B automated evidence passes.
- Gate B has controller review.
- No tactical primitive, query, detector, or accepted tactical result is claimed by this review.
