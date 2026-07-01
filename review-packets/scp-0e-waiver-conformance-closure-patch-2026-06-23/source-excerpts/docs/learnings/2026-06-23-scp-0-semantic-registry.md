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

## 2026-06-23 - SCP-0D Declarative Closure

**Fact:** External review of SCP-0C found that some policy and parity surfaces
were still too decorative: `ProjectionPolicy.requires` values were validated
but not executed, baseline parity compared incompatible wrapper shapes, recipe
contracts did not preserve all profile lineage, and generated projections could
be overwritten before a failed report exited.

**Decision:** Add SCP-0D as a narrow closure slice before SCP-1. Projection
requirements are now evaluated from the declared values, baseline source hashes
are pinned in the registry lock, parity compares canonical support contracts,
recipe and composition contracts inherit concept/profile evidence minima and
claim restrictions, full AI origin bundle bytes are hashed separately from the
selected normalized typed plan, and generated artifacts publish only after a
PASS report.

**Learning:** A semantic control plane is only trustworthy when every governance
declaration has a behavioral consequence. Policy values must alter projections,
source bytes must alter provenance hashes, missing baselines must fail, and
failed generation must not disturb the last valid artifacts.

**Evidence:** `make scp-0-verify` with 32 focused adversarial tests OK;
`make test` with 114 repository tests OK and attestation VERIFIED;
`generated/semantic-registry/semantic-parity-report.json`;
`generated/semantic-registry/plan-artifact-index.json`;
`semantic-registry/registry.lock.json`.

**Follow-up:** Generate an SCP-0D review packet. SCP-1 executable-algebra work
should remain blocked until external review accepts this closure.

## 2026-06-23 - SCP-0E Waiver and Conformance Closure

**Fact:** External review of SCP-0D found that signature conformance still had
false exactness, parity waivers were subject-wide rather than evidence-pinned,
composition lineage could be made circular, and some projection items still
bypassed their declared projection policies.

**Decision:** Add SCP-0E as one more narrow closure before SCP-1. Runtime
bindings now declare explicit semantic input/output/parameter bindings,
including runtime-context inputs. Exact and partial/legacy conformance is
validated in both directions. Parity waivers now pin the difference kind,
baseline hash, projection hash, permitted changed fields, rationale, and review
condition. Recipe and composition contracts must preserve dependency-derived
claim/evidence obligations from parsed plans. AI operators and unsupported
items now pass through projection-policy filtering.

**Learning:** Waivers must be evidence, not permission. A subject-level waiver
is a future drift hole; a hash- and field-pinned waiver is reviewable,
auditable, and self-invalidating when reality changes.

**Evidence:** `make scp-0-verify` with 42 focused adversarial tests OK;
`make test` with 124 repository tests OK and attestation VERIFIED;
`generated/semantic-registry/semantic-parity-report.json`;
`semantic-registry/registry.lock.json`.

**Follow-up:** Generate an SCP-0E review packet. SCP-1 should unblock
immediately after external acceptance, with no additional SCP-0 architecture
cycle unless a concrete failing gate appears.

## 2026-06-23 - SCP-0E Closure Patch

**Fact:** External review of the SCP-0E packet found that explicit mappings and
pinned waivers were real, but exactness still had false positives: runtime
contexts were not resolved, exact conformance ignored cardinality/entity
scope/requiredness and parameter bounds/defaults, uncovered declarations could
name nonexistent fields, duplicate waiver keys were accepted, and product recipe
parity was described too strongly.

**Decision:** Close the remaining issues as a small SCP-0E patch rather than a
new milestone. Runtime context references now resolve against a generated typed
runtime-context manifest. Exact field checks compare unit, cardinality, entity
scope, coordinate frame where declared, and input requiredness. Parameter specs
now include bounds, defaults, and allowed values. Uncovered names must resolve
and be unique. Waiver keys are unique by projection target, difference kind, and
subject. Product recipe comparison is explicitly labeled as current-runtime
alignment until a pinned product recipe baseline artifact exists.

**Learning:** A registry cannot use the word `EXACT` unless every compared
dimension is either enforced or explicitly outside the manifest. If the runtime
manifest does not expose an independent frozen baseline, the report should name
the weaker guarantee rather than borrowing stronger parity language.

**Evidence:** `make scp-0-verify` with 49 focused adversarial tests OK;
`make test` with 131 repository tests OK and attestation VERIFIED.

**Follow-up:** Generate the SCP-0E closure-patch packet. If external review
accepts it, begin SCP-1 immediately with the existing-runtime compiler pilot.
