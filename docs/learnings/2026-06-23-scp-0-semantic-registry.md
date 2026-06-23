# SCP-0 Semantic Registry Learnings

## 2026-06-23 - Initial Charter

**Fact:** The current runtime catalog and recipes are already executable and
must remain authoritative for what code exists.

**Decision:** SCP-0 is a shadow semantic parity and projection layer. It does
not replace runtime code, alter Hermes behavior, or expose proposed atlas items.

**Learning:** Product support must be the intersection of semantic registry,
runtime manifest, maturity, exposure policy, and projection policy. Any
disagreement should fail closed rather than choose a side.

**Evidence:** `delivery/scp-0/SPEC.md`

**Follow-up:** Implement runtime-manifest introspection and parity validation
before generating product or AI projections.

## 2026-06-23 - Parity Layer Implemented

**Fact:** SCP-0 can now generate a runtime manifest, registry lock, product
projection, AI projection, recipe-library projection, unsupported projection,
research-atlas projection, and semantic parity report.

**Decision:** The validated AI-authored corridor destination plan is represented
as a `CompositionInstance`, not as a `RecipeDefinition`.

**Learning:** The most important mechanical guarantee is fail-closed validation
against generated runtime truth. The registry can describe meaning and exposure,
but it must not claim executable support unless the runtime manifest has the
binding.

**Evidence:** `make scp-0-verify`; `generated/semantic-registry/semantic-parity-report.json`

**Follow-up:** Generate the external review packet and keep SCP-0 in shadow mode
until independent review is complete.

## 2026-06-23 - Generated Contract Drift

**Fact:** The focused SCP-0 verifier passed, but the first broader regression
run exposed that `generated/capability-catalog.json` was stale relative to the
current runtime catalog.

**Decision:** Refresh the existing M1.1 generated contract through the project
generator (`make m1-1-build`) instead of editing generated JSON manually.

**Learning:** A semantic registry that derives from runtime truth makes stale
generated contracts easier to detect, but it also means full-suite hygiene needs
to accompany foundation-layer work. Review packets should cite both the focused
semantic gate and the broader contract regression.

**Evidence:** `make m1-1-build`; `make scp-0-verify`; `make test` ran 92 tests
successfully after the generated catalog refresh.

**Follow-up:** Consider adding generated-contract freshness to future semantic
registry verification if SCP-0 graduates from shadow mode.

## 2026-06-23 - SCP-0C Hardening

**Fact:** External review approved the SCP-0 direction but correctly found that
the first implementation demonstrated registry coverage and atlas isolation
more strongly than true parity/policy execution.

**Decision:** Add SCP-0C as a corrective gate before SCP-1. The registry now
executes projection policy filters, reports real baseline projection
differences, hashes parsed plan artifacts into the lock, validates recipe and
composition plan integrity, checks transitive claim/evidence contracts, and
builds pilot reports through graph traversal.

**Learning:** A semantic control plane needs executable governance. Declaring
policy, provenance, and contract lineage is not enough; each declaration must
change projections, lock hashes, validation status, or generated evidence.

**Evidence:** `make scp-0-verify`; `make test` with 104 tests OK;
`generated/semantic-registry/plan-artifact-index.json`;
`generated/semantic-registry/semantic-parity-report.json`.

**Follow-up:** Produce an SCP-0C delta review packet. SCP-1 should wait until
the reviewer accepts this hardening or provides a focused correction.
