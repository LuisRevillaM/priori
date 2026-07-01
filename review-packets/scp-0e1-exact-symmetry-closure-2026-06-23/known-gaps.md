# Known Gaps

## requires_full_repo

The packet is inspection-only. It contains representative source files, diffs,
generated artifacts, and validation summaries, but not the full repository or
test data needed to rerun `make test`.

Default boundary: treat command results as locally verified evidence from the
controller unless rerun in a full checkout.

Next action: rerun `make scp-0-verify` and `make test` in the full repository if
independent execution is required.

## not_in_scope

SCP-1 implementation is not included.

Default boundary: SCP-1 remains blocked until this exact-symmetry closure is
externally accepted.

Next action: after acceptance, start SCP-1 with
`SemanticExpression -> existing TacticalQueryDocument -> existing binder ->
existing deterministic runtime`.

## not_in_scope

This patch does not make partial or legacy bindings exact.

Default boundary: partial and legacy bindings remain explicitly non-exact and
must continue to declare mappings/uncovered elements honestly.

Next action: evaluate deeper operator conformance during SCP-1, especially
operator parameters, enum domains, cardinality, and missing-data semantics.
