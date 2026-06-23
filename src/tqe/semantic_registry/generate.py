"""Generate and validate SCP-0 semantic registry artifacts."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.semantic_registry.models import (
    AtlasEntry,
    AuthoringExposure,
    ClaimContract,
    EvidenceContract,
    RegistryLock,
    SemanticParityReport,
    SemanticRegistry,
    Status,
    ValidationFinding,
)
from tqe.semantic_registry.runtime_manifest import (
    GENERATOR_VERSION,
    generate_runtime_manifest,
    runtime_capability_keys,
    runtime_operator_keys,
)


ROOT = Path(".")
REGISTRY_PATH = Path("semantic-registry/registry.yaml")
ATLAS_MANIFEST_PATH = Path("semantic-registry/atlas/raw/five_year_capability_manifest.yaml")
OUTPUT_ROOT = Path("generated/semantic-registry")
SCHEMA_PATH = Path("semantic-registry/schemas/semantic-registry.schema.json")
LOCK_PATH = Path("semantic-registry/registry.lock.json")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", value.strip()).strip("_").lower()
    return slug or "unnamed"


def load_raw_atlas_entries(path: Path = ATLAS_MANIFEST_PATH) -> list[AtlasEntry]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries: list[AtlasEntry] = []
    for family in raw.get("families", []):
        family_id = family.get("id") or _slug(family.get("title", "unknown_family"))
        family_title = family.get("title", family_id)
        for item in family.get("capabilities", []):
            capability_id = item["id"]
            entries.append(
                AtlasEntry(
                    id=f"atlas.{_slug(capability_id)}",
                    version=str(raw.get("catalog_version", "0.1.0-concept")),
                    display_name=capability_id,
                    description=item.get("definition", capability_id),
                    status=Status.PROPOSED_ATLAS,
                    source_name=capability_id,
                    family=family_title,
                    provisional_kind="UNCLASSIFIED",
                    source_provenance={
                        "catalog_id": raw.get("catalog_id"),
                        "catalog_version": raw.get("catalog_version"),
                        "snapshot_date": str(raw.get("snapshot_date")),
                        "family_id": family_id,
                        "original_entry_id": capability_id,
                        "output_type": item.get("output_type"),
                        "semantic_tier": item.get("semantic_tier"),
                    },
                    exposure_default=AuthoringExposure.DENIED,
                )
            )
    return entries


def load_registry(path: Path = REGISTRY_PATH) -> SemanticRegistry:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload.setdefault("atlas_entries", [])
    payload["atlas_entries"].extend(
        item.model_dump(mode="json", exclude_none=True) for item in load_raw_atlas_entries()
    )
    return SemanticRegistry.model_validate(payload)


def make_registry_lock(registry: SemanticRegistry, runtime_manifest: dict[str, Any]) -> RegistryLock:
    registry_revision = stable_hash(registry.model_dump(mode="json", exclude_none=True))
    runtime_revision = str(runtime_manifest["runtime_manifest_revision"])
    policies = {policy.target.value: policy.id for policy in registry.projection_policies}
    lock_seed = {
        "registry_revision": registry_revision,
        "runtime_manifest_revision": runtime_revision,
        "generator_version": GENERATOR_VERSION,
        "product_projection_policy": policies.get("product", ""),
        "ai_projection_policy": policies.get("ai", ""),
        "recipe_projection_policy": policies.get("recipe_library", ""),
        "unsupported_projection_policy": policies.get("unsupported", ""),
        "research_atlas_projection_policy": policies.get("research_atlas", ""),
        "evidence_schema_version": "1.0",
        "typed_plan_schema_version": "1.0",
    }
    return RegistryLock(**lock_seed, lock_hash=stable_hash(lock_seed))


def _finding(code: str, message: str, path: str) -> ValidationFinding:
    return ValidationFinding(code=code, message=message, path=path)


def _index(items: list[Any]) -> dict[str, Any]:
    return {item.id: item for item in items}


def validate_registry(
    registry: SemanticRegistry, runtime_manifest: dict[str, Any], lock: RegistryLock
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    concepts = _index(registry.concepts)
    operationalizations = _index(registry.operationalizations)
    profiles = _index(registry.definition_profiles)
    implementations = _index(registry.implementations)
    claim_contracts = _index(registry.claim_contracts)
    evidence_contracts = _index(registry.evidence_contracts)
    exposure_policies = _index(registry.exposure_policies)
    maturity = {item.subject_ref: item for item in registry.maturity_assessments}
    exposure_by_subject = {item.subject_ref: item for item in registry.exposure_policies}
    runtime_keys = runtime_capability_keys(runtime_manifest)
    operator_keys = runtime_operator_keys(runtime_manifest)

    binding_keys: list[tuple[str, str, str]] = []
    for index, binding in enumerate(registry.runtime_bindings):
        key = (
            binding.runtime_capability.kind,
            binding.runtime_capability.id,
            binding.runtime_capability.version,
        )
        binding_keys.append(key)
        if key not in runtime_keys:
            findings.append(
                _finding(
                    "runtime_binding_missing_runtime_capability",
                    f"Runtime binding {binding.id} references missing runtime capability {key}.",
                    f"runtime_bindings[{index}]",
                )
            )
        if binding.implementation_ref not in implementations:
            findings.append(
                _finding(
                    "runtime_binding_missing_implementation",
                    f"Runtime binding {binding.id} references missing implementation {binding.implementation_ref}.",
                    f"runtime_bindings[{index}].implementation_ref",
                )
            )
        for ref in binding.implements:
            if ref not in operationalizations:
                findings.append(
                    _finding(
                        "runtime_binding_missing_operationalization",
                        f"Runtime binding {binding.id} implements unknown operationalization {ref}.",
                        f"runtime_bindings[{index}].implements",
                    )
                )

    duplicate_binding_keys = sorted({key for key in binding_keys if binding_keys.count(key) > 1})
    for key in duplicate_binding_keys:
        findings.append(
            _finding(
                "duplicate_runtime_binding",
                f"Multiple RuntimeBinding records claim runtime capability {key}.",
                "runtime_bindings",
            )
        )
    for key in sorted(runtime_keys - set(binding_keys)):
        findings.append(
            _finding(
                "orphan_runtime_capability",
                f"Runtime capability {key} has no canonical RuntimeBinding.",
                "runtime_manifest.capabilities",
            )
        )

    operator_definition_keys = {
        (item.operator_id, item.operator_version) for item in registry.operator_definitions
    }
    for key in sorted(operator_keys - operator_definition_keys):
        findings.append(
            _finding(
                "operator_missing_definition",
                f"Runtime operator {key} has no OperatorDefinition.",
                "operator_definitions",
            )
        )
    for key in sorted(operator_definition_keys - operator_keys):
        findings.append(
            _finding(
                "operator_definition_missing_runtime_operator",
                f"OperatorDefinition {key} has no runtime operator.",
                "operator_definitions",
            )
        )

    for item in registry.operationalizations:
        for concept_ref in item.concept_refs:
            if concept_ref not in concepts:
                findings.append(
                    _finding(
                        "operationalization_missing_concept",
                        f"{item.id} references missing concept {concept_ref}.",
                        f"operationalizations.{item.id}.concept_refs",
                    )
                )
        if item.claim_contract_ref not in claim_contracts:
            findings.append(
                _finding(
                    "operationalization_missing_claim_contract",
                    f"{item.id} references missing claim contract {item.claim_contract_ref}.",
                    f"operationalizations.{item.id}.claim_contract_ref",
                )
            )
        if item.evidence_contract_ref not in evidence_contracts:
            findings.append(
                _finding(
                    "operationalization_missing_evidence_contract",
                    f"{item.id} references missing evidence contract {item.evidence_contract_ref}.",
                    f"operationalizations.{item.id}.evidence_contract_ref",
                )
            )

    for item in registry.definition_profiles:
        if item.operationalization_ref not in operationalizations:
            findings.append(
                _finding(
                    "profile_missing_operationalization",
                    f"{item.id} references missing operationalization {item.operationalization_ref}.",
                    f"definition_profiles.{item.id}.operationalization_ref",
                )
            )
        if item.claim_contract_ref not in claim_contracts:
            findings.append(
                _finding(
                    "profile_missing_claim_contract",
                    f"{item.id} references missing claim contract {item.claim_contract_ref}.",
                    f"definition_profiles.{item.id}.claim_contract_ref",
                )
            )
        if item.evidence_contract_ref not in evidence_contracts:
            findings.append(
                _finding(
                    "profile_missing_evidence_contract",
                    f"{item.id} references missing evidence contract {item.evidence_contract_ref}.",
                    f"definition_profiles.{item.id}.evidence_contract_ref",
                )
            )

    for child in registry.claim_contracts:
        for parent_ref in child.inherits:
            parent = claim_contracts.get(parent_ref)
            if parent is None:
                findings.append(
                    _finding(
                        "claim_contract_missing_parent",
                        f"{child.id} inherits missing claim contract {parent_ref}.",
                        f"claim_contracts.{child.id}.inherits",
                    )
                )
                continue
            broadened = sorted(set(child.permitted) & set(parent.prohibited))
            if broadened:
                findings.append(
                    _finding(
                        "claim_contract_broadens_parent",
                        f"{child.id} permits claims prohibited upstream: {broadened}.",
                        f"claim_contracts.{child.id}.permitted",
                    )
                )

    for child in registry.evidence_contracts:
        for parent_ref in child.inherits:
            parent = evidence_contracts.get(parent_ref)
            if parent is None:
                findings.append(
                    _finding(
                        "evidence_contract_missing_parent",
                        f"{child.id} inherits missing evidence contract {parent_ref}.",
                        f"evidence_contracts.{child.id}.inherits",
                    )
                )
                continue
            missing_required = sorted(set(parent.required) - set(child.required))
            if missing_required:
                findings.append(
                    _finding(
                        "evidence_contract_removes_parent_required_evidence",
                        f"{child.id} omits required upstream evidence: {missing_required}.",
                        f"evidence_contracts.{child.id}.required",
                    )
                )

    runtime_subjects = {
        f"runtime:{kind}:{name}:{version}" for kind, name, version in runtime_keys
    }
    for subject in runtime_subjects:
        if subject not in maturity:
            findings.append(
                _finding("missing_maturity", f"{subject} has no MaturityAssessment.", subject)
            )
        if subject not in exposure_by_subject:
            findings.append(
                _finding("missing_exposure_policy", f"{subject} has no ExposurePolicy.", subject)
            )

    non_authorable = set(runtime_manifest.get("non_authorable_catalog_refs", []))
    for item in registry.runtime_bindings:
        subject = (
            f"runtime:{item.runtime_capability.kind}:"
            f"{item.runtime_capability.id}:{item.runtime_capability.version}"
        )
        policy = exposure_by_subject.get(subject)
        if (
            item.runtime_capability.id in non_authorable
            and policy is not None
            and policy.ai_compiler == AuthoringExposure.ALLOWED
        ):
            findings.append(
                _finding(
                    "reviewed_plan_only_capability_exposed_to_ai",
                    f"{item.runtime_capability.id} is non-authorable but AI exposure is ALLOWED.",
                    f"exposure_policies.{policy.id}",
                )
            )

    runtime_recipes = {
        (item["recipe_id"], item["recipe_version"]): item
        for item in runtime_manifest.get("recipes", [])
    }
    registry_recipes = {
        (item.recipe_id, item.recipe_version): item for item in registry.recipe_definitions
    }
    for key in sorted(set(runtime_recipes) - set(registry_recipes)):
        findings.append(
            _finding(
                "recipe_missing_registry_mapping",
                f"Runtime recipe {key} has no registry RecipeDefinition mapping.",
                "recipe_definitions",
            )
        )
    for key in sorted(set(registry_recipes) - set(runtime_recipes)):
        findings.append(
            _finding(
                "recipe_mapping_missing_runtime_recipe",
                f"Registry recipe mapping {key} has no runtime recipe package.",
                "recipe_definitions",
            )
        )

    plan_artifacts = _index(registry.plan_artifacts)
    for recipe in registry.recipe_definitions:
        artifact = plan_artifacts.get(recipe.plan_artifact_ref)
        if artifact is None:
            findings.append(
                _finding(
                    "recipe_missing_plan_artifact",
                    f"{recipe.id} references missing plan artifact {recipe.plan_artifact_ref}.",
                    f"recipe_definitions.{recipe.id}.plan_artifact_ref",
                )
            )
            continue
        plan_path = Path(artifact.exact_typed_plan_ref)
        if not plan_path.exists():
            findings.append(
                _finding(
                    "plan_artifact_path_missing",
                    f"{artifact.id} references missing typed plan {plan_path}.",
                    f"plan_artifacts.{artifact.id}.exact_typed_plan_ref",
                )
            )
            continue
        try:
            document = TacticalQueryDocument.model_validate(
                json.loads(plan_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            findings.append(
                _finding(
                    "plan_artifact_invalid_typed_plan",
                    f"{artifact.id} cannot validate as TacticalQueryDocument: {exc}.",
                    f"plan_artifacts.{artifact.id}",
                )
            )
            continue
        for node in document.draft_plan.nodes:
            if getattr(node, "kind", None) == "predicate":
                key = (node.operator.name, node.operator.version)
                if key not in operator_definition_keys:
                    findings.append(
                        _finding(
                            "recipe_references_unregistered_operator",
                            f"{artifact.id} references operator {key} without OperatorDefinition.",
                            f"plan_artifacts.{artifact.id}.draft_plan.nodes",
                        )
                    )
            else:
                runtime_key = (node.kind.value, node.catalog_ref, node.version)
                if runtime_key not in set(binding_keys):
                    findings.append(
                        _finding(
                            "recipe_references_unbound_runtime_capability",
                            f"{artifact.id} references unbound runtime capability {runtime_key}.",
                            f"plan_artifacts.{artifact.id}.draft_plan.nodes",
                        )
                    )
        if recipe.claim_contract_ref not in claim_contracts:
            findings.append(
                _finding(
                    "recipe_missing_claim_contract",
                    f"{recipe.id} references missing claim contract {recipe.claim_contract_ref}.",
                    f"recipe_definitions.{recipe.id}.claim_contract_ref",
                )
            )
        if recipe.evidence_contract_ref not in evidence_contracts:
            findings.append(
                _finding(
                    "recipe_missing_evidence_contract",
                    f"{recipe.id} references missing evidence contract {recipe.evidence_contract_ref}.",
                    f"recipe_definitions.{recipe.id}.evidence_contract_ref",
                )
            )
        for profile_ref in recipe.profile_refs:
            if profile_ref not in profiles:
                findings.append(
                    _finding(
                        "recipe_missing_profile",
                        f"{recipe.id} references missing profile {profile_ref}.",
                        f"recipe_definitions.{recipe.id}.profile_refs",
                    )
                )

    for composition in registry.composition_instances:
        if composition.plan_artifact_ref not in plan_artifacts:
            findings.append(
                _finding(
                    "composition_missing_plan_artifact",
                    f"{composition.id} references missing plan artifact {composition.plan_artifact_ref}.",
                    f"composition_instances.{composition.id}.plan_artifact_ref",
                )
            )

    for atlas in registry.atlas_entries:
        if atlas.status != Status.PROPOSED_ATLAS:
            findings.append(
                _finding(
                    "atlas_entry_not_proposed",
                    f"{atlas.id} is not marked PROPOSED_ATLAS.",
                    f"atlas_entries.{atlas.id}.status",
                )
            )
        if atlas.exposure_default != AuthoringExposure.DENIED:
            findings.append(
                _finding(
                    "atlas_entry_exposure_not_denied",
                    f"{atlas.id} default exposure must remain DENIED.",
                    f"atlas_entries.{atlas.id}.exposure_default",
                )
            )

    expected_policy_targets = {"product", "ai", "recipe_library", "unsupported", "research_atlas"}
    actual_policy_targets = {policy.target.value for policy in registry.projection_policies}
    for target in sorted(expected_policy_targets - actual_policy_targets):
        findings.append(
            _finding(
                "missing_projection_policy",
                f"Missing projection policy for {target}.",
                "projection_policies",
            )
        )

    if not lock.lock_hash:
        findings.append(
            _finding(
                "registry_lock_missing_hash",
                "Registry lock must include lock_hash.",
                "registry_lock.lock_hash",
            )
        )

    return findings


def _subject_policy(registry: SemanticRegistry) -> dict[str, Any]:
    return {item.subject_ref: item for item in registry.exposure_policies}


def _subject_maturity(registry: SemanticRegistry) -> dict[str, Any]:
    return {item.subject_ref: item for item in registry.maturity_assessments}


def build_projections(
    registry: SemanticRegistry, runtime_manifest: dict[str, Any], lock: RegistryLock
) -> dict[str, dict[str, Any]]:
    policies = _subject_policy(registry)
    maturities = _subject_maturity(registry)
    bindings_by_runtime_name = {
        item.runtime_capability.id: item for item in registry.runtime_bindings
    }
    lock_payload = lock.model_dump(mode="json")

    product_capabilities: list[dict[str, Any]] = []
    ai_capabilities: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []

    for binding in sorted(registry.runtime_bindings, key=lambda item: item.runtime_capability.id):
        subject = (
            f"runtime:{binding.runtime_capability.kind}:"
            f"{binding.runtime_capability.id}:{binding.runtime_capability.version}"
        )
        policy = policies.get(subject)
        maturity = maturities.get(subject)
        base = {
            "id": binding.runtime_capability.id,
            "version": binding.runtime_capability.version,
            "kind": binding.runtime_capability.kind,
            "binding_id": binding.id,
            "conformance": binding.conformance_status.value,
            "implements": binding.implements,
        }
        if policy and maturity and policy.product == AuthoringExposure.ALLOWED:
            product_capabilities.append(
                base
                | {
                    "product_exposure": policy.product.value,
                    "semantic_maturity": maturity.semantic.value,
                    "product_maturity": maturity.product.value,
                }
            )
        else:
            unsupported.append(base | {"reason": "PRODUCT_EXPOSURE_DENIED"})
        if policy and maturity and policy.ai_compiler == AuthoringExposure.ALLOWED:
            ai_capabilities.append(
                base
                | {
                    "ai_exposure": policy.ai_compiler.value,
                    "agent_safety_maturity": maturity.agent_safety.value,
                }
            )
        elif policy and policy.ai_compiler != AuthoringExposure.ALLOWED:
            unsupported.append(base | {"reason": "AGENT_EXPOSURE_DENIED"})

    ai_operators = [
        {
            "id": item.operator_id,
            "version": item.operator_version,
            "authorability": item.authorability.value,
            "unknown_semantics": item.unknown_semantics,
        }
        for item in registry.operator_definitions
        if item.authorability == AuthoringExposure.ALLOWED
    ]

    recipe_items: list[dict[str, Any]] = []
    for recipe in registry.recipe_definitions:
        artifact = next(item for item in registry.plan_artifacts if item.id == recipe.plan_artifact_ref)
        recipe_items.append(
            {
                "id": recipe.recipe_id,
                "version": recipe.recipe_version,
                "mapping_id": recipe.id,
                "plan_artifact_id": artifact.id,
                "exact_typed_plan_ref": artifact.exact_typed_plan_ref,
                "dependencies": recipe.dependency_refs,
                "profiles": recipe.profile_refs,
                "claim_contract_ref": recipe.claim_contract_ref,
                "evidence_contract_ref": recipe.evidence_contract_ref,
            }
        )

    compositions = [
        {
            "id": item.id,
            "plan_artifact_ref": item.plan_artifact_ref,
            "origin": item.origin,
            "promotion_status": item.promotion_status,
            "claim_contract_ref": item.claim_contract_ref,
            "evidence_contract_ref": item.evidence_contract_ref,
        }
        for item in registry.composition_instances
    ]

    atlas_summary = {
        "total": len(registry.atlas_entries),
        "families": sorted({item.family for item in registry.atlas_entries}),
        "entries": [
            {
                "id": item.id,
                "source_name": item.source_name,
                "family": item.family,
                "status": item.status.value,
                "exposure_default": item.exposure_default.value,
            }
            for item in registry.atlas_entries
        ],
    }

    projections = {
        "product": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "capabilities": product_capabilities,
            "recipes": recipe_items,
            "validated_compositions": compositions,
        },
        "ai": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "capabilities": ai_capabilities,
            "operators": ai_operators,
            "recipes": recipe_items,
            "validated_compositions": compositions,
        },
        "recipe_library": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "registered_recipe_count": len(recipe_items),
            "validated_ai_composition_count": len(compositions),
            "recipes": recipe_items,
            "validated_compositions": compositions,
        },
        "unsupported": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "items": unsupported,
            "atlas": {
                "total": len(registry.atlas_entries),
                "reason": "PROPOSED_ATLAS entries are not product-supported or AI-authorable.",
            },
        },
        "research_atlas": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "atlas": atlas_summary,
        },
    }
    return projections


def validate_projection_identities(
    projections: dict[str, dict[str, Any]], lock: RegistryLock
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for name, projection in projections.items():
        projection_lock = projection.get("registry_lock")
        if not isinstance(projection_lock, dict):
            findings.append(
                _finding(
                    "projection_missing_registry_lock",
                    f"{name} projection does not include registry_lock.",
                    f"projections.{name}.registry_lock",
                )
            )
            continue
        if projection_lock.get("lock_hash") != lock.lock_hash:
            findings.append(
                _finding(
                    "projection_registry_lock_mismatch",
                    f"{name} projection lock does not match current registry lock.",
                    f"projections.{name}.registry_lock.lock_hash",
                )
            )
    return findings


def build_pilot_report(
    registry: SemanticRegistry, projections: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    product_capability_ids = {
        item["id"] for item in projections["product"].get("capabilities", [])
    }
    ai_capability_ids = {item["id"] for item in projections["ai"].get("capabilities", [])}
    recipe_ids = {item["id"] for item in projections["recipe_library"].get("recipes", [])}
    composition_ids = {
        item["id"] for item in projections["recipe_library"].get("validated_compositions", [])
    }
    policies = _subject_policy(registry)

    outcome_policy = policies.get("runtime:primitive:outcome_classification:0.1.0")
    destination_wrapper_policy = policies.get(
        "runtime:primitive:relation_destination_entry_classification:0.1.0"
    )

    return {
        "high_bypass_completed_pass": {
            "recipe_mapped": "high_bypass_completed_pass_v1" in recipe_ids,
            "concepts": [
                "concept.controlled_ball_transfer",
                "concept.opponent_ball_side_transition_count",
            ],
            "runtime_capabilities": [
                "controlled_pass_episode",
                "opponents_bypassed_by_action",
            ],
            "runtime_capabilities_in_product_projection": all(
                item in product_capability_ids
                for item in ["controlled_pass_episode", "opponents_bypassed_by_action"]
            ),
            "runtime_capabilities_in_ai_projection": all(
                item in ai_capability_ids
                for item in ["controlled_pass_episode", "opponents_bypassed_by_action"]
            ),
            "claim_contract": "claim.high_bypass_completed_pass.v1",
            "evidence_contract": "evidence.high_bypass_completed_pass.v1",
        },
        "ball_side_block_shift": {
            "recipe_mapped": "ball_side_block_shift_v1" in recipe_ids,
            "concepts": [
                "concept.wide_ball_entry",
                "concept.defensive_block_lateral_shift",
            ],
            "runtime_capabilities": [
                "possession_segment",
                "ball_lateral_fraction",
                "defensive_outfield_centroid",
                "signed_lateral_shift",
                "outcome_classification",
            ],
            "reviewed_plan_only_classifier_preserved": (
                outcome_policy is not None
                and outcome_policy.ai_compiler == AuthoringExposure.REVIEWED_PLAN_ONLY
            ),
            "destination_wrapper_boundary_preserved": (
                destination_wrapper_policy is not None
                and destination_wrapper_policy.ai_compiler == AuthoringExposure.REVIEWED_PLAN_ONLY
            ),
            "claim_contract": "claim.ball_side_block_shift.v1",
            "evidence_contract": "evidence.ball_side_block_shift.v1",
        },
        "validated_ai_composition": {
            "composition_mapped": "composition.ai_corridor_destination.2026_06_23" in composition_ids,
            "is_recipe": False,
        },
    }


def build_parity_report(
    registry: SemanticRegistry,
    runtime_manifest: dict[str, Any],
    lock: RegistryLock,
    findings: list[ValidationFinding],
    projections: dict[str, dict[str, Any]],
) -> SemanticParityReport:
    runtime_keys = runtime_capability_keys(runtime_manifest)
    binding_keys = {
        (
            item.runtime_capability.kind,
            item.runtime_capability.id,
            item.runtime_capability.version,
        )
        for item in registry.runtime_bindings
    }
    duplicate_count = len(registry.runtime_bindings) - len(binding_keys)
    runtime_total = len(runtime_keys)
    operator_keys = runtime_operator_keys(runtime_manifest)
    operator_definition_keys = {
        (item.operator_id, item.operator_version) for item in registry.operator_definitions
    }
    runtime_recipes = {
        (item["recipe_id"], item["recipe_version"]) for item in runtime_manifest.get("recipes", [])
    }
    registry_recipes = {
        (item.recipe_id, item.recipe_version) for item in registry.recipe_definitions
    }

    atlas_leakage = {
        "product": sum(
            1
            for item in projections["product"].get("capabilities", [])
            if str(item.get("id", "")).startswith("atlas.")
        ),
        "ai": sum(
            1
            for item in projections["ai"].get("capabilities", [])
            if str(item.get("id", "")).startswith("atlas.")
        ),
    }

    report = SemanticParityReport(
        status="PASS" if not findings and atlas_leakage == {"product": 0, "ai": 0} else "FAIL",
        registry_lock=lock,
        findings=findings,
        runtime_capabilities={
            "runtime_total": runtime_total,
            "bound": len(binding_keys & runtime_keys),
            "orphaned": len(runtime_keys - binding_keys),
            "unresolved_bindings": len(binding_keys - runtime_keys),
            "duplicate_bindings": duplicate_count,
            "including_operators_total": runtime_total + len(operator_keys),
        },
        operators={
            "runtime_total": len(operator_keys),
            "semantically_defined": len(operator_definition_keys & operator_keys),
            "missing_definitions": len(operator_keys - operator_definition_keys),
        },
        recipes={
            "registered": len(runtime_recipes),
            "mapped": len(registry_recipes & runtime_recipes),
            "missing_plan_artifacts": sum(
                1
                for item in registry.recipe_definitions
                if item.plan_artifact_ref not in {artifact.id for artifact in registry.plan_artifacts}
            ),
        },
        validated_compositions={
            "total": len(registry.composition_instances),
            "mapped": sum(
                1
                for item in registry.composition_instances
                if item.plan_artifact_ref in {artifact.id for artifact in registry.plan_artifacts}
            ),
        },
        projection_differences={
            "product": {"added": [], "removed": [], "changed": []},
            "ai": {"added": [], "removed": [], "changed": []},
        },
        atlas_leakage=atlas_leakage,
        pilots=build_pilot_report(registry, projections),
    )
    return report


def generate_scp0_artifacts(
    registry_path: Path = REGISTRY_PATH,
    output_root: Path = OUTPUT_ROOT,
    write: bool = True,
) -> tuple[SemanticRegistry, dict[str, Any], RegistryLock, SemanticParityReport]:
    registry = load_registry(registry_path)
    runtime_manifest = generate_runtime_manifest()
    lock = make_registry_lock(registry, runtime_manifest)
    findings = validate_registry(registry, runtime_manifest, lock)
    projections = build_projections(registry, runtime_manifest, lock)
    findings.extend(validate_projection_identities(projections, lock))
    report = build_parity_report(registry, runtime_manifest, lock, findings, projections)

    if write:
        _write_json(SCHEMA_PATH, SemanticRegistry.model_json_schema())
        _write_json(output_root / "runtime-manifest.json", runtime_manifest)
        _write_json(LOCK_PATH, lock.model_dump(mode="json"))
        _write_json(output_root / "product-projection.json", projections["product"])
        _write_json(output_root / "ai-projection.json", projections["ai"])
        _write_json(output_root / "recipe-library-projection.json", projections["recipe_library"])
        _write_json(output_root / "unsupported-capability-projection.json", projections["unsupported"])
        _write_json(output_root / "research-atlas-projection.json", projections["research_atlas"])
        _write_json(output_root / "semantic-parity-report.json", report.model_dump(mode="json"))
    return registry, runtime_manifest, lock, report


def main() -> None:
    _, _, _, report = generate_scp0_artifacts(write=True)
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    if report.status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
