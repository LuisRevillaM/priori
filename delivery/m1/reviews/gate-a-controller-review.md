# Gate A Controller Review

Date: 2026-06-19

Reviewer: controller

Decision: ACCEPT WITH OWNER-WAIVED INDEPENDENT REVIEW

## Scope

This review covers only M1 Gate A, using `J03WOH`:

- official IDSSE/DFL source lock;
- Floodlight-backed parse through a project-owned adapter boundary;
- canonical Parquet output;
- raw XML parity checks;
- quality, orientation, and resource reports;
- 30-second canonical replay bundle and screenshot;
- automated Gate A verifier.

It does not review Gate B corpus processing, Gate C tactical primitives, detector semantics, query calibration, or any UI beyond the Gate A proof replay.

## Evidence Reviewed

- `delivery/m1/SPEC.md`
- `Makefile`
- `pyproject.toml`
- `src/tqe/idsse/source_lock.py`
- `src/tqe/ports/idsse_reader.py`
- `src/tqe/adapters/floodlight_idsse_reader.py`
- `src/tqe/data/gate_a_build.py`
- `src/tqe/evidence/gate_a_replay.py`
- `src/tqe/verification/gate_a.py`
- `src/tqe/verification/m1.py`
- `tests/`
- `artifacts/m1/gate-a/source-manifest.json`
- `artifacts/m1/gate-a/canonical-summary.json`
- `artifacts/m1/gate-a/raw-parity-report.json`
- `artifacts/m1/gate-a/data-quality-report.json`
- `artifacts/m1/gate-a/resource-report.json`
- `artifacts/m1/gate-a/replay-bundle/manifest.json`
- `artifacts/m1/gate-a/replay-screenshot.png`
- `artifacts/m1/gate-a/verification-report.json`

## Verification Commands

```bash
make test
.venv/bin/python -m compileall -q src scripts tests
make gate-a-verify
```

Observed results:

- `make test`: pass, 2 tests.
- compileall: pass.
- `make gate-a-verify`: pass, 37 passing checks, 0 failures, 0 not-ready checks.

`make m1-verify` is expected to fail until Gate B and Gate C are implemented. That failure is not a Gate A blocker.

## Findings

No blocking findings for Gate A.

The source lock records official Figshare article metadata and checksums, and the raw local files match official sizes and MD5 values. The canonicalizer keeps Floodlight behind `FloodlightIDSSEReader` and writes project-owned canonical Parquet outputs rather than allowing Floodlight objects to become the domain model.

Raw XML parity passes on deterministic samples across first half, second half, home player, away player, and ball observations. The sample count is intentionally small for Gate A, but enough to prove that the canonical row identity and coordinate units match source XML for the checked cases.

Orientation is derived from valid `KickOff` events with `GameSection` in first and second half. Earlier kickoff-like events without `GameSection` were filtered out before this review, which avoids polluting orientation with non-period rows.

The replay bundle is generated from canonical Parquet and records canonical source hashes. The screenshot is non-empty and visually shows pitch, players, and ball from the replay bundle.

## Non-Blocking Concerns

- Raw parity is spot-check based, not exhaustive. Gate B should broaden or stratify parity checks across more entities and substitution intervals before corpus promotion.
- Position quality allows observations outside the strict pitch rectangle as long as they remain inside pitch plus 5m tolerance. Gate B should decide whether that tolerance remains acceptable corpus-wide.
- The replay proof is static and minimal. That is acceptable for Gate A, but the later TypeScript replay proof must validate bundle schema and coordinate rendering more rigorously.
- Independent review was attempted but did not complete. The owner explicitly instructed the controller to proceed with controller-only review, so this review does not satisfy the original independent-review preference; it records an owner waiver for Gate A only.

## Promotion Decision

Gate A is accepted for purposes of proceeding to Gate B.

The acceptance is narrow:

- Gate A automated evidence passes.
- Gate A has controller review.
- Gate A independent review is waived by owner instruction for this gate only.
- No tactical primitive or detector claim is made by this review.
