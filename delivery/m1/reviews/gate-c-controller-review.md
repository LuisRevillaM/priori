# Gate C Controller Review

Date: 2026-06-19

Reviewer: controller

Decision: ACCEPT WITH CONTROLLER-ONLY REVIEW

## Scope

This review covers only M1 Gate C:

- frozen `ball_side_block_shift_v1` query configuration;
- calibration on `J03WOH`;
- unchanged evaluation on `J03WOY`, `J03WPY`, `J03WQQ`, and `J03WR9`;
- deterministic accepted-result and near-miss generation;
- typed evidence bundles and static replay JSON;
- minimal strict TypeScript replay-proof validation;
- Python verifier recomputation of accepted predicates and replay-to-canonical parity.

It does not review a polished dashboard, natural-language query compilation, generic tactical query language, provider integration, match video, or future multi-query breadth.

## Evidence Reviewed

- `config/queries/ball_side_block_shift.v1.yaml`
- `src/tqe/query/ball_side_block_shift.py`
- `src/tqe/evidence/gate_c_build.py`
- `src/tqe/verification/gate_c.py`
- `apps/replay-proof/src/verifyBundles.ts`
- `artifacts/m1/gate-c/query-freeze.json`
- `artifacts/m1/gate-c/calibration-report.json`
- `artifacts/m1/gate-c/evaluation-report.json`
- `artifacts/m1/gate-c/accepted-results.json`
- `artifacts/m1/gate-c/near-misses.json`
- `artifacts/m1/gate-c/proof-pack-manifest.json`
- `artifacts/m1/gate-c/replay-proof-report.json`
- `artifacts/m1/gate-c/verification-report.json`
- `docs/queries/ball-side-block-shift/semantic-gold-set.v1.json`
- `artifacts/m1/evidence/*/bundle.json`
- `artifacts/m1/evidence/*/replay.json`
- `artifacts/m1/verification-report.json`

## Verification Commands

```bash
make gate-c-build
make gate-c-verify
make test
.venv/bin/python -m compileall -q src tests
git diff --check
make m1-verify
```

Observed results:

- `make gate-c-build`: pass; generated 16 selected evidence bundles and replay-proof report.
- `make gate-c-verify`: pass; 304 passing Python checks, 0 failures, 0 not-ready checks.
- TypeScript replay proof inside Gate C: pass; 82 passing checks, 0 failures.
- `make test`: pass; 3 unit tests.
- Python compile pass: pass.
- `git diff --check`: pass.
- `make m1-verify`: pass; Gate A 37/0/0, Gate B 273/0/0, Gate C 304/0/0.

## Findings

No blocking findings remain for Gate C.

The query freeze hash is `af42853e6a3c8449e023dd98751ababbc7d34640f8751fbffa1c2bbbd0eab523`. The calibration report records 47 accepted candidates on `J03WOH`: 24 `LOST_BEFORE_SWITCH`, 13 `RETAINED_NO_SWITCH`, and 10 `SWITCHED`.

The unchanged evaluation pass records 180 accepted candidates across the four Fortuna evaluation matches. The deterministic proof selection contains 16 accepted real moments spanning all four evaluation matches: 11 `LOST_BEFORE_SWITCH`, 2 `RETAINED_NO_SWITCH`, and 3 `SWITCHED`. No selected result has `quality_status=fail`, and no match contributes more than 31.25 percent of selected results.

The TypeScript replay proof reads the generated proof manifest and each generated bundle/replay file. It does not hardcode tactical moments.

The Python verifier recomputes each accepted result's possession segment, wide entry, defensive baseline, signed shift, persistence, outcome classification, and replay coordinates from canonical/raw data. It does not accept detector-stored booleans as sufficient proof.

The semantic gold set records clear positives, borderline accepted cases, excluded stoppages, threshold near misses, data-quality failure controls, allowed claims, and disallowed claims for Query 1.

## Corrected Issue During Review

The first Gate C verification run failed because the detector classified outcomes using only the already-identified possession segment. That could label a moment `RETAINED_NO_SWITCH` even when possession changed immediately after the segment ended. The detector was corrected to classify over the full configured horizon after the anchor while keeping the block-shift search inside the eligible possession segment. The proof pack was regenerated after this correction and then passed verification.

## Non-Blocking Concerns

- Independent review was not performed for Gate C. This follows the current owner-requested controller-only execution mode after the prior review agent stalled.
- The TypeScript proof is a minimal static artifact validator, not the future analyst UI. It proves generated-bundle consumption and replay contract shape, not product delight.
- The selected proof set is deterministic but score-biased; future query-breadth work should add semantic gold sets and analyst-facing review labels before making stronger tactical claims.
- M1 proves coordinate replay and tactical predicates only. It does not prove intent, causation, optimality, pass-lane availability, or video-backed claims.

## Promotion Decision

Gate C is accepted for purposes of closing M1 controller verification.

The acceptance is narrow:

- Gate A remains accepted controller-only.
- Gate B remains accepted controller-only.
- Gate C automated evidence passes.
- Gate C has controller review.
- Final M1 owner acceptance is still pending.
