# Known Gaps

## Full Reproduction Requires Full Repository

Classification:

`requires_full_repo`

This packet is inspection-only. It includes source files, artifacts, diffs, and logs, but not the full dependency/runtime environment required to rerun `make scp-0-verify` or `make test`.

Default boundary:

Treat included command logs and generated artifacts as inspection evidence, not as a standalone reproducible build.

## Registry Authority Is Still Shadow-Only

Classification:

`not_in_scope`

SCP-0C makes the semantic registry more trustworthy, but the tactical runtime is still the execution authority. The registry does not yet drive runtime execution or Hermes compilation decisions directly.

Default boundary:

Do not claim the registry has replaced the current runtime, compiler, or product catalog.

## Semantic Parity Is Baseline Comparison, Not External Acceptance

Classification:

`requires_human_decision`

SCP-0C now reports actual added/removed/changed differences against existing baseline artifacts, but the reviewer still needs to decide whether those differences are acceptable as registry enrichment rather than drift.

Default boundary:

Treat `semantic_parity` as `PARTIAL_BASELINE_COMPARISON_REPORTED` until external review accepts the interpretation.

## Research Atlas Remains Isolated

Classification:

`not_in_scope`

The 741 atlas entries are intentionally not projected into product or AI capability surfaces during SCP-0C.

Default boundary:

Atlas entries are research input only unless later slices promote them through explicit semantic bindings, maturity, exposure, and validation gates.

## Pre-Existing Workspace Noise

Classification:

`unknown`

The working tree contains unrelated modified/untracked files from prior milestones and review packets. The SCP-0C commit is cleanly represented by `git show HEAD`; unrelated workspace noise is captured in git status command logs but is not part of this review.

Default boundary:

Review only the SCP-0C commit and included SCP-0C packet files.

