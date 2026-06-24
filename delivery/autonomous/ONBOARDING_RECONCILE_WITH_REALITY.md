# Onboarding Brief — Reconcile-With-Reality Addendum

Status: **binding addendum.** Where this document and the "Priori Football Language Onboarding Brief"
disagree, **this document wins.** The brief's *philosophy* stands (definition-before-implementation,
typed gaps, no overclaiming, evidence/replay obligations). Its *engineering instructions* did two
dangerous things this addendum corrects: it told you to hand-author a passport as source of truth, and
it told you to stand up a new milestone ladder. Both collide with machinery that already exists.

Read the source-of-truth files before acting. Do not act from the brief alone.

---

## The two non-negotiable corrections

### 1. The Capability Passport is a GENERATED projection, not a hand-authored artifact.
The source of truth is the **semantic registry** (`src/tqe/semantic_registry/models.py`): normalized,
typed objects linked by `subject_ref` — `Concept` (:133), `Operationalization` (:139),
`DefinitionProfile` (:152), `Implementation` (:160), `RuntimeBinding` (:197), `ClaimContract` (:235),
`EvidenceContract` (:243), `ExposurePolicy` (:251), `ProjectionPolicy` (:271),
`MaturityAssessment` (:279), `AtlasEntry` (:331).

The charter is explicit: `delivery/autonomous/priori_autonomous_delivery_charter.md:1329` —
"Every product-eligible capability must have a **generated** passport," and `:1379` —
"**The passport is generated from authoritative artifacts. It is not handwritten marketing.**"

> Do **not** create a new passport file as the upstream truth. Definition tasks *populate registry
> objects*; the passport is a **read-only projection** generated from registry state + the registry
> lock (`semantic-registry/registry.lock.json`). A hand-maintained passport store would instantly
> drift from the registry and invert the data flow.

### 2. Do NOT invent `SCP-2A / AFL-D0`. This is AFL-08 / AFL-09 under the PROTECTED contract.
`delivery/autonomous/afl_milestone_contract.yaml` already owns this territory:
- `:260` **AFL-08 — Standard Library Expansion and Atlas Closure** (deliverable `:265` `capability_passports`)
- `:281` **AFL-09 — Validation Factory and Proof-Carrying Results** (deliverable `:285` `capability_passport_generator`)

That contract is protected: `builder_may_not_modify: [protected_milestone_contracts, promotion_policy, …]`,
`promotion_authority: protected_gate`. It is machine-enforced by `src/tqe/verification/afl_g0.py`
(`PROTECTED_AUTHORITY_FIELDS`, `no_legacy_milestone_ids`, `dependencies_acyclic`, hard gates
non-waivable). Editing the contract to add `AFL-D0`, or minting new milestone IDs, **fails the
afl-g0 gate**. Running un-protected "SCP-2A" creates two parallel roadmaps.

> Run this work **as slices under AFL-08/AFL-09**. If a bridge milestone is genuinely needed, the
> **protected steward** amends the contract with a promotion certificate. A builder cannot
> self-authorize a protected milestone.

---

## Corrected operating model

```text
Raw atlas entry (AtlasEntry, PROPOSED_ATLAS, exposure_default DENIED)
→ author/refine REGISTRY OBJECTS (not a passport file):
     Concept · Operationalization · DefinitionProfile
     ClaimContract · EvidenceContract
     RuntimeBinding (only if runtime work is in scope)
     MaturityAssessment · ExposurePolicy
→ GENERATE the capability passport from registry state + lock
→ structural verifier checks registry consistency (schema, refs, claims, evidence, maturity, exposure)
→ implement runtime ONLY if runtime work is in scope (do not, for a definition-only slice)
→ RuntimeBinding + verification evidence
→ projection to AI / product ONLY if ExposurePolicy/ProjectionPolicy allows
```

Promotion authority stays with the **protected gate**. The five-reviewer idea is good, but only as
**advisory review evidence** recorded in the ledger — never as promotion.

---

## Concept → reality mapping (use the existing thing; don't reinvent)

| Brief concept | Use this instead (real) | Source |
|---|---|---|
| Capability Passport (authored, pre-impl) | **Generated** passport projected from registry objects + lock | charter §9 (`:1327`–`:1379`); AFL-09 `capability_passport_generator` |
| Passport fields: meaning / does-not-claim | `Concept` + `ClaimContract` (permitted/prohibited) | `semantic_registry/models.py:133,235` |
| Passport fields: evidence / replay obligations | `EvidenceContract` | `:243` |
| Passport fields: inputs/outputs/units/temporal | `Operationalization` + `DefinitionProfile` (+ runtime catalog `CatalogOutput`/`CatalogInput`) | `:139,152`; `runtime/ir.py` |
| Passport fields: runtime binding | `RuntimeBinding` → catalog `name@version` | `:197`; `runtime/catalog.py` |
| Passport fields: exposure tier | `ExposurePolicy` + `ProjectionPolicy` (NOT a new field) | `:251,271` |
| Lifecycle `RAW→…→PRODUCT_VISIBLE` (linear) | `Status{CURRENT,PROPOSED_ATLAS,DEPRECATED,SHADOW}` + **5-dim** `MaturityAssessment{semantic,implementation,validation,agent_safety,product}` | `:39,279` |
| 4 visibility tiers | **Authoritative:** runtime allowlist at the MCP surface (`authorable_catalog_refs` / `NON_AUTHORABLE_CATALOG_REFS`); **registry:** `AuthoringExposure{ALLOWED,DENIED,REVIEWED_PLAN_ONLY}` + projection targets | `workshop/m1_2.py:105`; `generated/capability-context.json`; registry |
| 5 reviewer roles (APPROVE/…/REJECT) | Advisory **review evidence** in ledger + `delivery/**/reviews/`; promotion = protected gate only | `afl_milestone_contract.yaml` authority block |
| Definition verifier | Structural/schema verifier (no runtime execution) — follow precedent | `verification/afl_g0.py`, `verification/n1d1.py` |
| Forbidden-claim lint (scanning/intent/optimality…) | **Reuse** `UNSUPPORTED_CONCEPTS` (+ planned-gaps dict) | `workshop/app_service.py:345` |
| 741 atlas | `AtlasEntry` already typed + `PROPOSED_ATLAS` + `DENIED` | `generated/semantic-registry/research-atlas-projection.json` |
| "required data modalities" checked | No modality enum exists today (modality is prose in catalog `limitations`). Declare-from-vocabulary only, **or** first build a modality vocabulary + per-match availability manifest. Do not claim "verified against data" without it. | `runtime/catalog.py` (limitations); `runtime/ir.py` (only `temporal_type` is structured) |

---

## "Frozen definition" means versioned and reviewable — NOT proven-true-forever
A definition can be semantically REVIEWED while still **not identifiable, not implemented, and not
validated** — those are *separate* dimensions in `MaturityAssessment`. A frozen definition must be
**revocable/supersedable** until `implementation`/`validation` reach VERIFIED with runtime evidence.
Freezing must never imply identifiability, runtime support, or a product claim. (This is the exact
N1D/N1E trap — "frozen before proof" blocked Beta 1C; do not repeat it.)

---

## Your job (next agent)

```text
Your job is NOT to author hand-written passports.
Your job is to build the AFL-08 / AFL-09 registry-to-passport pathway:
  - refine registry object schemas if needed (StrictModel, extra="forbid");
  - author definition-task mechanics AGAINST registry objects (not a passport file);
  - generate capability passports from registry state + lock;
  - validate maturity / exposure / claim / evidence consistency (structural verifier);
  - keep atlas-only entries DENIED from AI/product projection;
  - produce review EVIDENCE, not self-promotion.
```

Concrete first targets (validate the registry→passport pathway, no new runtime):
`controlled_pass_episode` and `opponents_bypassed_by_action` are **addressable catalog entries**
(`runtime/catalog.py`) with existing/expressible `RuntimeBinding`s — use them to prove
passport↔runtime mapping. Note "High-Bypass Completed Pass" is a **recipe/composition**
(`config/query-plans/high_bypass_completed_pass.experimental.v1.json`), not a primitive — passport
shape for a composition differs from a primitive.

---

## Already built — do not rebuild
- FQNF (the 8 slots SCOPE…RETURN), `SemanticExpression`, `SemanticGap` (9 typed kinds incl.
  `MODALITY_GAP`/`CLARIFICATION_REQUIRED`), and lowering into `TacticalQueryDocument`:
  implemented, typed, tested — `src/tqe/semantic_compiler/`.
- The 16-object semantic registry + lock — `src/tqe/semantic_registry/`, `semantic-registry/`.
- The 741 atlas (typed, DENIED by default) — `generated/semantic-registry/research-atlas-projection.json`.
- Non-runtime structural-verifier precedent — `verification/afl_g0.py`, `verification/n1d1.py`.
- Conventions: `StrictModel(extra="forbid")`, JSON-schema files (`delivery/autonomous/schemas/`),
  `schema_version`+checks+summary report shape, Makefile `*-verify`, `delivery/ledger.jsonl`,
  review-packets.

## Guardrails (what you may not touch)
- `builder_may_not_modify`: protected milestone contracts, promotion policy, trusted/protected gate,
  holdouts, scoring policy, signing key. Promotion authority = `protected_gate`.
- Do not make atlas-only / unverified capabilities AI- or product-visible.
- Do not broaden runtime claims because a result looks plausible. Preserve PASS/FAIL/UNKNOWN and
  evidence/replay obligations. Never infer video/scanning/body-orientation/intent/optimality/causality
  from tracking/events.
- This slice does not change the Workbench UI, deploy, rewrite `TacticalQueryDocument`/executor, or
  make the atlas executable.
