# Known Gaps

## Full Validation Reproduction

Classification: `requires_full_repo`

What is missing: this packet does not include the complete repository, local virtualenv, or IDSSE canonical/raw data needed to rerun every verifier.

Why it matters: an external reviewer can inspect the verifier logic, diffs, reports, and protocol state, but cannot independently rerun the gates from this packet alone.

Default boundary: treat included generated reports as controller-provided evidence, not independent reproduction.

Next action: rerun validation in a full checkout if independent execution is required.

## External Approval

Classification: `requires_human_decision`

What is missing: external reviewer decision after inspecting M1.1R.

Why it matters: delivery state intentionally blocks M1.2 until external approval or required-change integration.

Default boundary: do not begin M1.2 implementation.

Next action: reviewer returns `APPROVE`, `APPROVE_WITH_REQUIRED_CHANGES`, or `REJECT`.

## Runtime Generality

Classification: `not_in_scope`

What is missing: proof that this is a universal tactical DSL or arbitrary graph engine.

Why it matters: M1.1R only claims a bounded explicit graph runtime for the current catalog/contracts.

Default boundary: do not treat M1.1R as a universal query language.

Next action: expand capability breadth in later milestones with separate specs and proof gates.

## Agent And UX Layers

Classification: `not_in_scope`

What is missing: Hermes natural-language drafting, analyst feedback, saved detectors, and UI.

Why it matters: those are downstream product capabilities, not R5 runtime proof.

Default boundary: M1.1R can be approved while those remain unimplemented.

Next action: begin M1.2 only after external approval.

## Priori And Video

Classification: `not_in_scope`

What is missing: Priori SDK/API integration and match-video ingestion/synchronization.

Why it matters: the project scope explicitly excludes these for the independent local demo.

Default boundary: make no Priori or video claims.

Next action: none for M1.1R.
