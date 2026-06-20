# Known Gaps

## Requires Full Repo

- This packet is not a full reproducibility bundle.
- The packet includes compact evidence and source snapshots, but the full local corpus and ignored replay artifacts remain outside the packet.
- Re-running verification requires the local repository plus local data/artifact state.

## Omitted Large Artifacts

These were omitted to keep the review packet practical:

- `artifacts/m1.1/inspector/inspector-data.json` and `.js`, roughly 51 MB.
- `artifacts/m1.1/experimental-evidence/*/bundle.json` and `replay.json`, roughly 66 MB total.

Included substitutes:

- `artifacts/m1.1/inspector/manifest.json`
- `artifacts/m1.1/experimental-evidence-manifest.json`
- `artifacts/m1.1/experimental-query-results.json`
- `artifacts/m1.1/predicate-trace-report.json`
- `artifacts/m1.1/relation-validation-report.json`
- `artifacts/m1.1/relation-visual-review/*.svg`

## Not In Scope

- Hermes/natural-language drafting.
- Query workshop UX.
- Analyst feedback and recipe revision.
- Saved detectors.
- Production persistence.
- Priori integration.
- Match video.

## Review Risks

- The executor implements known primitives. This is expected in M1.1, but the reviewer should decide whether it is bounded and reusable enough.
- The executor still carries some legacy naming, including result fields such as `query_id`, for compatibility with M1 proof artifacts.
- AST checks reject direct `if` branches on `query_id`, `recipe_id`, or `plan_id`, but cannot prove semantic decoupling by themselves.
- The experimental plan depends on `relation_destination_entry_classification`; the reviewer should decide whether this is genuinely generic or a disguised special case.
- The static inspector proves developer inspection, not analyst-grade UX.

## Acceptance Still Pending

- Independent external review: not started.
- Owner acceptance: not started.
