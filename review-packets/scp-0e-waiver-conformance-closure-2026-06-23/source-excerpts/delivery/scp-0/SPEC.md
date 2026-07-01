# SCP-0 - Semantic Registry Foundation

## Outcome

SCP-0 creates a versioned semantic parity and projection layer over the current
working Priori system. It binds football meaning, operational definitions,
runtime implementations, claims, evidence, maturity, and exposure without
changing execution behavior.

SCP-0 is successful when Priori can represent what it truthfully supports today,
validate that representation against the generated runtime manifest, and produce
safe product, AI, recipe, unsupported, and research-atlas projections in shadow
mode.

## Scope

SCP-0 covers four implementation slices:

### SCP-0A - Registry Schemas, Runtime Manifest, and Parity Skeleton

- Define semantic-registry schemas.
- Generate a runtime manifest from the current registered runtime catalog.
- Add registry lockfile generation.
- Add current operator definitions.
- Add current runtime capability bindings.
- Add fail-closed registry validation.
- Add adversarial tests for drift, illegal exposure, and reproducibility.

### SCP-0B - Current-System Mappings and Projections

- Map current recipe definitions and exact typed plan artifacts.
- Model the validated AI-authored corridor destination plan as a
  `CompositionInstance`, not a reusable recipe.
- Add claim contracts and evidence contracts.
- Add product, AI, recipe-library, unsupported, and research-atlas projections.
- Import the five-year atlas only as raw `PROPOSED_ATLAS` staging vocabulary.
- Prove two end-to-end semantic traversals:
  - High-Bypass Completed Pass.
  - Ball-Side Block Shift.
- Generate the SCP-0 parity report and external review packet.

### SCP-0C - Projection, Parity, and Integrity Hardening

- Execute projection policies instead of only declaring them.
- Compare generated product and AI projections against the current generated
  capability catalog and Tactical Knowledge Pack surfaces.
- Parse and hash every plan artifact, including the validated composition
  origin bundle.
- Add normalized plan hashes, dependencies, parameter defaults, and referenced
  parameters to the plan-artifact index and registry lock.
- Validate registry recipe declarations against parsed plan dependencies,
  recipe IDs, versions, and profile-bound parameter defaults.
- Generate pilot reports through a generic semantic graph resolver rather than
  hard-coded capability lists.
- Validate runtime and operator signatures against semantic declarations.
- Compute transitive claim/evidence inheritance, detect cycles, and catch
  upstream contradictions.
- Require explicit exposure and maturity records for runtime capabilities,
  recipes, and validated composition instances.

### SCP-0D - Declarative Gate Closure

- Evaluate `ProjectionPolicy.requires` values declaratively for product, AI,
  recipe-library, and research-atlas projections.
- Pin baseline source artifact hashes in the registry lock.
- Compare canonical support contracts rather than projection wrapper JSON.
- Report membership drift and contract drift separately.
- Fail projection parity on missing baselines or unapproved additions,
  removals, or contract changes.
- Add top-level concept references for recipes and composition instances.
- Require recipe and composition claim/evidence contracts to inherit their
  concept and profile/dependency contract minima.
- Pin both full AI origin bundle bytes and normalized selected typed-plan
  document hashes.
- Validate composition plans for unbound capabilities and undefined operators.
- Enforce exact binding port/parameter compatibility and require explicit
  field mappings/uncovered fields for partial or legacy bindings.
- Publish generated projections atomically only after validation passes.

### SCP-0E - Waiver and Conformance Closure

- Replace coarse runtime field mappings with explicit semantic input bindings,
  runtime output bindings, semantic parameter declarations, and parameter
  bindings.
- Represent implicit runtime-context inputs explicitly, rather than treating
  missing runtime inputs as exact by default.
- Validate exact and partial/legacy bindings in both directions across
  semantic inputs, runtime inputs, semantic outputs, runtime outputs, runtime
  parameters, and semantic parameters.
- Replace subject-wide parity exceptions with pinned waiver records containing
  difference kind, baseline contract hash, projection contract hash, permitted
  fields, rationale, and review condition.
- Fail parity when a waiver is stale, hash-drifted, or permits fewer fields
  than the observed canonical difference.
- Derive recipe and composition claim/evidence obligations from parsed plan
  runtime dependencies, not only from the top-level concept or manually
  declared profiles.
- Apply projection-policy filtering to AI operators and unsupported projection
  items.

## Non-Goals

SCP-0 must not add:

- runtime behavior changes;
- new tactical capabilities;
- a new executor;
- a new football IR;
- Hermes behavior changes;
- Workbench UI changes;
- graph database or ontology engine;
- manual semantic normalization of all five-year atlas declarations;
- product or AI exposure for atlas-only entries.

## Authority Model

During SCP-0, support is defined by intersection, not by one file alone.

```text
ProductSupported(item) =
  semantic_registry_has_valid_definition
  AND runtime_manifest_has_verified_binding
  AND maturity_allows_product_exposure
  AND exposure_policy_allows_product_exposure
  AND projection_policy_allows_inclusion
```

```text
AiAuthorable(item) =
  runtime_binding_exists
  AND semantic_contract_is_valid
  AND agent_safety_is_approved
  AND exposure_policy_allows_ai
  AND all_dependencies_are_ai_legal
  AND item_is_not_atlas_only
```

On disagreement, generation must fail closed.

## Registry Object Model

SCP-0 uses these first-class objects:

- `Concept`
- `Operationalization`
- `DefinitionProfile`
- `Implementation`
- `RuntimeBinding`
- `OperatorDefinition`
- `RecipeDefinition`
- `PlanArtifact`
- `CompositionInstance`
- `ExecutionRecord`
- `ClaimContract`
- `EvidenceContract`
- `ExposurePolicy`
- `ProjectionPolicy`
- `MaturityAssessment`
- `AtlasEntry`

`TypeRef` is an embedded structured value used by operationalization inputs and
outputs.

## Contract Inheritance

Claim contracts narrow downward:

```text
Concept claim ceiling
  -> Operationalization claims
  -> Definition profile claims
  -> Recipe claims
```

Downstream objects may not permit claims prohibited upstream.

Evidence contracts accumulate downward:

```text
Concept minimum evidence
  + operationalization evidence
  + profile threshold evidence
  + recipe evidence
```

Downstream objects may require more evidence, but cannot remove mandatory
upstream evidence.

Exposure becomes more restrictive downward. A recipe cannot freely expose a
dependency whose own policy forbids AI composition.

## Required Artifacts

SCP-0 must produce:

1. Registry schemas.
2. Generated runtime manifest.
3. Current-system semantic mappings.
4. Operator definitions.
5. Exact recipe and plan-artifact mappings.
6. Raw proposed-atlas import.
7. Product projection.
8. AI projection.
9. Recipe-library projection.
10. Unsupported-capability projection.
11. Research-atlas projection.
12. Semantic parity report.
13. Registry lockfile.
14. Plan-artifact index.
15. CI/verification suite.

## Acceptance Criteria

SCP-0 passes only if:

1. Every current runtime capability ID/version has exactly one canonical
   `RuntimeBinding`.
2. Every binding resolves to the generated runtime manifest.
3. Every current operator has an `OperatorDefinition`.
4. Every current recipe has a structured expression or reference to its exact
   current typed plan.
5. Every reviewed-plan-only dependency remains forbidden from free AI
   composition.
6. Every operationalization has structured inputs, outputs, required modalities,
   semantic basis, and applicability.
7. Every user-facing concept has a claim contract.
8. Every executable recipe has an evidence contract.
9. Every implementation mapping declares `EXACT`, `PARTIAL`, or
   `LEGACY_APPROXIMATION`.
10. The product projection contains only product-approved items with verified
    runtime bindings or validated composition records.
11. The AI projection contains only agent-approved items and permitted
    parameters.
12. Reviewed-plan-only implementations may appear as dependencies of approved
    recipes, but not as free-standing AI-authorable capabilities.
13. `PROPOSED_ATLAS` entries are excluded by construction from product and AI
    projections.
14. Unsupported-capability output includes explicit reasons.
15. Generated artifacts are deterministic from registry revision, runtime
    manifest revision, generator version, and projection policy version.
16. Generated artifacts identify their registry lock.
17. Verification fails on orphan runtime capabilities, unresolved bindings,
    illegal recipe dependencies, missing evidence obligations, atlas leakage,
    duplicate runtime bindings, and projection identity drift.
18. High-Bypass Completed Pass can be traversed from concept through
    operationalization, profile, implementation, recipe, claims, evidence,
    product projection, and AI projection.
19. Ball-Side Block Shift can be traversed through the same chain while
    preserving its reviewed-plan-only classifier boundary.
20. Projection policy changes alter generated projections.
21. Plan-content changes alter the registry lock.
22. Registry/plan dependency disagreements fail generation.
23. Pilot paths are discovered from parsed plan artifacts rather than asserted.
24. Runtime and operator signature disagreements fail generation unless
    explicitly marked and explained as non-exact conformance.
25. Changing a `ProjectionPolicy.requires` value changes the generated
    projection.
26. Missing baseline artifacts fail parity instead of producing all-added
    reports.
27. Canonical shared product support contracts compare equal when current
    support is unchanged.
28. Unapproved baseline additions, removals, or contract drift fail parity.
29. Recipes and composition instances resolve to a top-level concept.
30. Recipe and composition contracts preserve inherited concept/profile claim
    prohibitions and evidence minima.
31. AI-origin bundle byte changes alter source artifact hashes even when the
    selected normalized plan is unchanged.
32. Composition plans with unbound capabilities or undefined operators fail
    validation.
33. Exact bindings fail on missing runtime/semantic ports or parameter mappings.
34. Failed generation leaves the last valid projection artifacts untouched.
35. Exact bindings fail when a required semantic input is neither bound to a
    node input nor explicitly bound to runtime context.
36. Runtime-context inputs pass only when declared as `RUNTIME_CONTEXT` with a
    context reference.
37. Partial or legacy bindings fail when a mapping key or target does not
    resolve to a real runtime or semantic element.
38. Partial or legacy bindings fail when a runtime parameter is neither mapped
    nor explicitly uncovered.
39. Exact parameter bindings fail when the semantic parameter target is absent
    or type/unit/requiredness-incompatible.
40. Accepted parity differences are pinned by exact baseline/projection hashes
    and permitted changed fields.
41. Stale parity waivers fail when their difference is no longer observed.
42. A same-ID accepted composition or recipe contract change fails unless the
    corresponding waiver hash and permitted fields are updated.
43. Composition contracts must preserve every dependency-derived claim and
    evidence obligation from the parsed plan, even if the composition concept
    is changed at the same time.
44. AI operator projection changes when the AI `ProjectionPolicy` excludes an
    operator.
45. Unsupported projection output changes when the unsupported
    `ProjectionPolicy` changes.

## Side Effects

SCP-0 is Tier 1 local reversible work. It writes registry files, generated
shadow artifacts, tests, documentation, and an external review packet. It does
not deploy or change production-facing behavior.
