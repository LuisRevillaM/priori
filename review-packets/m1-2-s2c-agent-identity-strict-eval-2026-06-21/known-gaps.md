# Known Gaps

## Actual Hermes Runtime

Class: `not_in_scope`.

S2C intentionally does not instantiate a concrete Hermes runtime. It proves an
agent-neutral `ModelBackedTacticalQueryCompiler` over the bounded S2 tool
surface. Default boundary: do not claim Hermes runtime integration until an
adapter exists and is verified.

## S3 Revision Loop

Class: `not_in_scope`.

Feedback-driven revisions, semantic diffs, result deltas, and immutable recipe
versions are still S3. Default boundary: S3 must reuse S2C strict output,
semantic validation, trace, and confirmation contracts.

## Independent Reproduction

Class: `requires_full_repo`.

This packet is inspection-only. It includes source, diffs, reports, and trace
artifacts, but not the full repo, data, virtualenv, or credentials needed to
rerun model-backed verification.

## Model Reliability Scope

Class: `unknown`.

The blind corpus is modest and sufficient for this demo gate, but it is not a
production-grade language evaluation. Default boundary: do not broaden claims
beyond bounded recipe selection, corridor slot extraction, clarification, and
capability gaps.
