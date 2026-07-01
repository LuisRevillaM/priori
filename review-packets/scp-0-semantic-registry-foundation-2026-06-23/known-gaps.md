# Known Gaps

## Atlas Is Not Implemented

Classification: `not_in_scope`

The 741 atlas entries are imported only as `PROPOSED_ATLAS`. They are denied from product and AI projections.

Default boundary:

No atlas item should be treated as supported, authorable, or product-visible until it is separately promoted with runtime implementation, tests, exposure policy, and projection approval.

Next action:

Use future SCP slices to promote a small number of declarations through executable capability contracts.

## Semantic Registry Is Shadow-Only

Classification: `not_in_scope`

SCP-0 validates and projects semantic metadata, but does not yet drive the runtime catalog, Hermes knowledge pack, or Workbench UI.

Default boundary:

The executable runtime remains authoritative for execution. The registry may describe and constrain future exposure decisions, but does not replace runtime code.

Next action:

After review acceptance, define a follow-up migration slice that uses projections as an input to product/AI catalog generation without changing runtime semantics.

## Full Reproduction Requires The Repository

Classification: `requires_full_repo`

This packet includes source and generated evidence, but not the entire repository, Python virtual environment, canonical data, or all test fixtures.

Default boundary:

Treat this as an inspection packet. Re-run validation in the real repo before merging or promoting.

Next action:

Run `make scp-0-verify` and `make test` in the full repo.

## Registry Semantics Need Domain Review

Classification: `requires_human_decision`

SCP-0 proves mechanical parity and projection isolation. It does not prove that every concept name, claim-contract phrase, or maturity assessment is the best football-language representation.

Default boundary:

Mechanical acceptance can proceed while keeping naming and maturity wording open for future domain refinement.

Next action:

Reviewer should inspect `semantic-registry/registry.yaml`, especially concept definitions, claim contracts, evidence contracts, and maturity records.

## Existing Worktree Noise

Classification: `unknown`

The repo had unrelated modified/untracked files at packet generation time.

Default boundary:

Do not attribute unrelated N1C/N1D/audit/review-packet files to SCP-0.

Next action:

Before committing, stage only SCP-0 files and the generated capability-catalog refresh, or clean/resolve unrelated worktree noise separately.
