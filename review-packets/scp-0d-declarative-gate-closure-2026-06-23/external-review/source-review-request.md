## Decision

**Changes required before SCP-1, but only a narrow closure slice.**

SCP-0C is a substantial improvement: checksums pass, the packet records 22 focused tests and 104 repository tests passing, all 11 runtime capabilities and eight operators are mapped, five plan artifacts are parsed, and the 741 atlas entries remain isolated. It also preserves Priori’s existing deterministic authority chain and authorability boundaries rather than rewriting them.  

I would call the remaining slice:

```text
SCP-0D — Declarative Gate Closure
```

### Blocking findings

**1. `ProjectionPolicy.requires` is still decorative.**

The generator validates the names of `requires` keys, but never reads their values when building projections. Product and AI requirements are hard-coded in `_capability_allowed_for_*`; recipe-library and research-atlas requirements are largely ignored.

Therefore this would not change behavior:

```yaml
requires:
  product_maturity: NOT_EXPOSED
```

Only `excludes` has genuinely declarative behavior. This fails the acceptance criterion that projection-policy changes alter projections.

Either implement a typed requirement evaluator or remove `requires` and admit the policy is code-owned.

**2. The parity comparison reports differences, but cannot establish parity.**

The report marks every shared product item and every shared AI item as `changed` because it hashes structurally different representations:

```text
baseline catalog item
vs
semantic projection wrapper containing runtime_contract
```

Consequently:

```text
product: 15 of 15 shared records changed
AI:      21 of 21 shared records changed
```

The report also:

* passes even when differences exist;
* silently treats missing baseline files as empty baselines;
* does not pin baseline hashes in the lock;
* omits the two baseline files from the review packet.

This is useful identity-coverage reporting, but not semantic parity. Create canonical baseline adapters, report membership and contract drift separately, fail when baselines are unavailable, and require an explicit allowlist for accepted differences.

**3. Claim/evidence lineage stops before the recipe layer.**

Operationalization and profile lineage are checked, but recipe and composition contracts are only checked for existence.

There is already a concrete inconsistency:

```text
opposite_corridor_after_shift_v1
  profiles:
    ball_side_block_shift
    progressive_corridor
    destination_entry

  claim/evidence:
    ai_corridor_destination_composition
```

That contract does not inherit the ball-side block-shift claim or evidence contracts, despite the recipe depending on that behavior.

Additionally, `RecipeDefinition` and `CompositionInstance` have no top-level `concept_ref`, so `concept.high_bypass_completed_pass` is not actually connected to its recipe. Add concept references and require recipe/composition contracts to preserve all dependency and profile prohibitions and evidence minima.

**4. The AI origin bundle is not fully pinned.**

The lock hashes the normalized selected `TacticalQueryDocument`, not the complete N1F origin bundle. Changes to Hermes provenance, draft material, augmentation metadata, or other bundle content can leave the lock unchanged if the selected document stays identical.

Add both:

```text
source_artifact_sha256
normalized_selected_document_hash
```

Composition validation should also reject unbound capabilities, undefined operators, and incompatible claim/evidence contracts, just as recipe validation does.

**5. Signature validation remains one-directional.**

For `EXACT` bindings, runtime fields must appear in the semantic declaration, but semantic required fields do not have to appear in runtime. Parameters, cardinality, nullability, coordinate frame, entity scope, and missing-data behavior are not compared. `PARTIAL` and `LEGACY_APPROXIMATION` require prose deviations but no field mapping.

At minimum:

```text
EXACT:
  bidirectional port and parameter compatibility

PARTIAL:
  explicit field mapping
  explicit uncovered fields
  explicit semantic deviations
```

**6. Generation does not fully fail closed.**

`generate_scp0_artifacts()` writes projections before `main()` exits on a failed report. An invalid registry can therefore overwrite generated projection files even though CI subsequently fails.

Generate into a temporary directory and atomically publish only after validation passes. On failure, write only the diagnostic report.

## Required acceptance tests for SCP-0D

```text
Changing a ProjectionPolicy.requires value changes its projection.

Removing a required baseline produces FAIL, not an all-added PASS.

Canonical shared records compare equal when their support contracts are equal.

An unapproved baseline addition, removal, or contract change fails parity.

A recipe whose contract omits one profile's claims/evidence fails.

Every recipe and composition resolves to a top-level concept.

Changing any byte of an AI origin bundle changes source_artifact_sha256.

A composition containing an unbound capability or undefined operator fails.

An EXACT binding with a missing semantic/runtime port or parameter fails.

A failed generation leaves the last valid projections untouched.
```

## Next packet contents

Include the five exact typed plans, the complete N1F origin bundle, `generated/capability-catalog.json`, and `generated/tactical-knowledge-pack.json`. Those source artifacts are necessary to independently verify the reported plan hashes and parity results.

## Recommended disposition

```yaml
registry_coverage: VERIFIED
runtime_binding_coverage: VERIFIED
atlas_isolation: VERIFIED
plan_document_integrity: VERIFIED
full_origin_provenance_integrity: PARTIAL
projection_policy_enforcement: PARTIAL
semantic_parity: PARTIAL
recipe_contract_lineage: PARTIAL
scp_1_gate: BLOCKED_ON_SCP_0D
```

This does not justify reopening the architecture. It is a focused integrity closure. SCP-1 design work can proceed in parallel, but the executable-algebra milestone should not be declared underway until SCP-0D passes.
