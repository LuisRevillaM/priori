"""Generate and validate SCP-0 semantic registry artifacts."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from hashlib import sha256
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.semantic_registry.models import (
    AtlasEntry,
    AuthoringExposure,
    ClaimContract,
    ConformanceStatus,
    EvidenceContract,
    MaturityLevel,
    PlanArtifact,
    ProjectionTarget,
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
CAPABILITY_CATALOG_BASELINE_PATH = Path("generated/capability-catalog.json")
KNOWLEDGE_PACK_BASELINE_PATH = Path("generated/tactical-knowledge-pack.json")
BASELINE_PATHS = {
    "capability_catalog": CAPABILITY_CATALOG_BASELINE_PATH,
    "tactical_knowledge_pack": KNOWLEDGE_PACK_BASELINE_PATH,
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_artifact_manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    for name, path in BASELINE_PATHS.items():
        manifest[name] = {
            "path": str(path),
            "exists": path.exists(),
            "source_artifact_sha256": _sha256_bytes(path) if path.exists() else None,
        }
    manifest["baseline_artifact_revision"] = stable_hash(manifest)
    return manifest


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
    plan_index = build_plan_artifact_index(registry)
    policies = {policy.target.value: policy.id for policy in registry.projection_policies}
    lock_seed = {
        "registry_revision": registry_revision,
        "runtime_manifest_revision": runtime_revision,
        "plan_artifact_revision": plan_index["plan_artifact_revision"],
        "baseline_artifact_revision": baseline_artifact_manifest()[
            "baseline_artifact_revision"
        ],
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


def _dedupe_preserve(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _load_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _typed_value_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict) and value.get("kind") == "parameter":
        return {"parameter_ref": value["name"]}
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _document_from_plan_artifact(artifact: PlanArtifact) -> tuple[dict[str, Any], str]:
    path = Path(artifact.exact_typed_plan_ref)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "recipe" in payload and "draft_plan" in payload:
        return payload, "typed_plan"
    if str(payload.get("schema_version", "")).startswith("n1f.origin_bundle"):
        augmented = payload.get("host_augmentation", {}).get("augmented_document")
        draft = payload.get("hermes_origin", {}).get("draft_document")
        if isinstance(augmented, dict):
            return augmented, "n1f_origin_bundle.host_augmented_document"
        if isinstance(draft, dict):
            return draft, "n1f_origin_bundle.hermes_draft_document"
    raise ValueError(f"{path} is not a TacticalQueryDocument or supported origin bundle")


def extract_plan_artifact_details(artifact: PlanArtifact) -> dict[str, Any]:
    path = Path(artifact.exact_typed_plan_ref)
    if not path.exists():
        return {
            "artifact_id": artifact.id,
            "path": str(path),
            "exists": False,
            "valid_typed_plan": False,
            "error": "path_missing",
        }
    source_artifact_sha256 = _sha256_bytes(path)
    try:
        document_payload, source_kind = _document_from_plan_artifact(artifact)
        document = TacticalQueryDocument.model_validate(document_payload)
    except Exception as exc:
        return {
            "artifact_id": artifact.id,
            "path": str(path),
            "exists": True,
            "valid_typed_plan": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    normalized_document = document.model_dump(mode="json", exclude_none=True)
    capability_dependencies: list[dict[str, str]] = []
    operator_dependencies: list[dict[str, str]] = []
    referenced_parameters: set[str] = set()

    for node in document.draft_plan.nodes:
        if getattr(node, "kind", None) == "predicate":
            operator_dependencies.append(
                {"name": node.operator.name, "version": node.operator.version}
            )
            for arg in (node.compare, node.duration):
                if getattr(arg, "kind", None) == "parameter":
                    referenced_parameters.add(arg.name)
            continue

        capability_dependencies.append(
            {
                "kind": node.kind.value,
                "name": node.catalog_ref,
                "version": node.version,
            }
        )
        for arg in (node.parameters or {}).values():
            if getattr(arg, "kind", None) == "parameter":
                referenced_parameters.add(arg.name)

    parameter_defaults = {
        item.name: _typed_value_payload(item.default)
        for item in document.recipe.parameters
    }

    return {
        "artifact_id": artifact.id,
        "path": str(path),
        "exists": True,
        "valid_typed_plan": True,
        "source_artifact_sha256": source_artifact_sha256,
        "source_kind": source_kind,
        "origin": artifact.origin,
        "promotion_status": artifact.promotion_status,
        "normalized_plan_hash": stable_hash(normalized_document),
        "normalized_selected_document_hash": stable_hash(normalized_document),
        "plan_id": document.draft_plan.plan_id,
        "plan_version": document.draft_plan.plan_version,
        "recipe_id": document.recipe.recipe_id,
        "recipe_version": document.recipe.recipe_version,
        "draft_status": document.draft_plan.status.value,
        "capability_dependencies": _dedupe_preserve(capability_dependencies),
        "operator_dependencies": _dedupe_preserve(operator_dependencies),
        "dependency_refs": _dedupe_preserve(
            [item["name"] for item in capability_dependencies]
            + [item["name"] for item in operator_dependencies]
        ),
        "parameter_defaults": parameter_defaults,
        "referenced_parameters": sorted(referenced_parameters),
    }


def build_plan_artifact_index(registry: SemanticRegistry) -> dict[str, Any]:
    artifacts = {
        artifact.id: extract_plan_artifact_details(artifact)
        for artifact in sorted(registry.plan_artifacts, key=lambda item: item.id)
    }
    return {
        "schema_version": "1.0",
        "artifacts": artifacts,
        "plan_artifact_revision": stable_hash(artifacts),
    }


def _type_value_to_runtime(value: str) -> str:
    return {
        "Any": "any",
        "Scalar": "number",
        "Boolean": "boolean",
        "Enum": "enum",
        "AnchorRef": "anchor_ref",
        "RelationRef": "relation_ref",
        "EntitySet": "entity_set",
        "Point": "point",
    }.get(value, value.lower())


def _type_container_to_runtime(value: str) -> str:
    return {
        "FrameSignal": "frame_signal",
        "EpisodeSet": "episode_set",
        "RelationEpisodeSet": "relation_episode_set",
        "Scalar": "scalar",
    }.get(value, value.lower())


def _type_signature(field: Any) -> dict[str, str]:
    if hasattr(field, "type"):
        type_ref = field.type
        return {
            "payload_type": _type_value_to_runtime(type_ref.value),
            "temporal_type": _type_container_to_runtime(type_ref.container),
            "unit": type_ref.unit,
        }
    return {
        "payload_type": field["payload_type"],
        "temporal_type": field["temporal_type"],
        "unit": field.get("unit", "none"),
    }


def _runtime_by_key(runtime_manifest: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (item["kind"], item["name"], item["version"]): item
        for item in runtime_manifest.get("capabilities", [])
    }


def _operator_by_key(runtime_manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (item["name"], item["version"]): item
        for item in runtime_manifest.get("operators", [])
    }


def _closure(
    object_id: str,
    items: dict[str, Any],
    finding_code: str,
    path_prefix: str,
) -> tuple[set[str], list[ValidationFinding]]:
    findings: list[ValidationFinding] = []
    visited: set[str] = set()
    stack: set[str] = set()

    def visit(current: str) -> None:
        if current in stack:
            findings.append(
                _finding(
                    finding_code,
                    f"Inheritance cycle detected at {current}.",
                    f"{path_prefix}.{object_id}.inherits",
                )
            )
            return
        item = items.get(current)
        if item is None:
            findings.append(
                _finding(
                    f"{finding_code}_missing_parent",
                    f"{object_id} inherits missing contract {current}.",
                    f"{path_prefix}.{object_id}.inherits",
                )
            )
            return
        if current in visited:
            return
        stack.add(current)
        for parent_ref in item.inherits:
            visit(parent_ref)
        stack.remove(current)
        visited.add(current)

    visit(object_id)
    return visited - {object_id}, findings


def _effective_claim_contract(
    contract_id: str, claim_contracts: dict[str, ClaimContract]
) -> tuple[dict[str, set[str]], list[ValidationFinding]]:
    ancestors, findings = _closure(
        contract_id, claim_contracts, "claim_contract_inheritance_cycle", "claim_contracts"
    )
    contract = claim_contracts[contract_id]
    permitted = set(contract.permitted)
    prohibited = set(contract.prohibited)
    for ancestor_ref in ancestors:
        ancestor = claim_contracts[ancestor_ref]
        permitted.update(ancestor.permitted)
        prohibited.update(ancestor.prohibited)
    return {"ancestors": ancestors, "permitted": permitted, "prohibited": prohibited}, findings


def _effective_evidence_contract(
    contract_id: str, evidence_contracts: dict[str, EvidenceContract]
) -> tuple[dict[str, set[str]], list[ValidationFinding]]:
    ancestors, findings = _closure(
        contract_id, evidence_contracts, "evidence_contract_inheritance_cycle", "evidence_contracts"
    )
    contract = evidence_contracts[contract_id]
    required = set(contract.required)
    optional = set(contract.optional)
    replay_projection = set(contract.replay_projection)
    for ancestor_ref in ancestors:
        ancestor = evidence_contracts[ancestor_ref]
        required.update(ancestor.required)
        optional.update(ancestor.optional)
        replay_projection.update(ancestor.replay_projection)
    return {
        "ancestors": ancestors,
        "required": required,
        "optional": optional,
        "replay_projection": replay_projection,
    }, findings


def _field_map(fields: list[Any]) -> dict[str, Any]:
    return {field.name if hasattr(field, "name") else field["name"]: field for field in fields}


def _signature_mismatch(
    semantic_field: Any, runtime_field: Any, *, allow_any_unit: bool = False
) -> list[str]:
    semantic = _type_signature(semantic_field)
    runtime = _type_signature(runtime_field)
    mismatches: list[str] = []
    if semantic["payload_type"] != "any" and semantic["payload_type"] != runtime["payload_type"]:
        mismatches.append(f"payload {semantic['payload_type']} != {runtime['payload_type']}")
    if semantic["temporal_type"] != "any" and semantic["temporal_type"] != runtime["temporal_type"]:
        mismatches.append(f"temporal {semantic['temporal_type']} != {runtime['temporal_type']}")
    if (
        not allow_any_unit
        and semantic["unit"] not in {"any", runtime["unit"]}
        and runtime["unit"] != "none"
    ):
        mismatches.append(f"unit {semantic['unit']} != {runtime['unit']}")
    return mismatches


def _parameter_signature_mismatch(semantic_field: Any, runtime_parameter: dict[str, Any]) -> list[str]:
    semantic_type = semantic_field.type
    semantic_payload = _type_value_to_runtime(semantic_type.value)
    mismatches: list[str] = []
    if semantic_payload != "any" and semantic_payload != runtime_parameter.get("payload_type"):
        mismatches.append(
            f"payload {semantic_payload} != {runtime_parameter.get('payload_type')}"
        )
    if (
        semantic_type.unit not in {"any", runtime_parameter.get("unit", "none")}
        and runtime_parameter.get("unit", "none") != "none"
    ):
        mismatches.append(f"unit {semantic_type.unit} != {runtime_parameter.get('unit')}")
    if bool(getattr(semantic_field, "required", True)) != bool(
        runtime_parameter.get("required", False)
    ):
        mismatches.append(
            f"required {bool(getattr(semantic_field, 'required', True))} != {bool(runtime_parameter.get('required', False))}"
        )
    return mismatches


def _uncovered_binding_values(binding: Any) -> dict[str, list[str]]:
    return {
        "uncovered_runtime_inputs": list(binding.uncovered_runtime_inputs),
        "uncovered_runtime_outputs": list(binding.uncovered_runtime_outputs),
        "uncovered_runtime_parameters": list(binding.uncovered_runtime_parameters),
        "uncovered_semantic_inputs": list(binding.uncovered_semantic_inputs),
        "uncovered_semantic_outputs": list(binding.uncovered_semantic_outputs),
        "uncovered_semantic_parameters": list(binding.uncovered_semantic_parameters),
    }


def _contract_inherits_or_is(
    child_ref: str, required_ref: str, contracts: dict[str, Any], *, kind: str
) -> tuple[bool, list[ValidationFinding]]:
    if child_ref not in contracts or required_ref not in contracts:
        return False, []
    if child_ref == required_ref:
        return True, []
    closure, findings = (
        _effective_claim_contract(child_ref, contracts)
        if kind == "claim"
        else _effective_evidence_contract(child_ref, contracts)
    )
    return required_ref in closure["ancestors"], findings


def _runtime_binding_for_dependency(registry: Any, dep: dict[str, str]) -> Any | None:
    return next(
        (
            item
            for item in registry.runtime_bindings
            if item.runtime_capability.kind == dep["kind"]
            and item.runtime_capability.id == dep["name"]
            and item.runtime_capability.version == dep["version"]
        ),
        None,
    )


def validate_plan_dependency_contract_closure(
    *,
    registry: Any,
    plan_details: dict[str, Any],
    claim_contract_ref: str,
    evidence_contract_ref: str,
    claim_contracts: dict[str, ClaimContract],
    evidence_contracts: dict[str, EvidenceContract],
    operationalizations: dict[str, Any],
    subject_path: str,
    subject_id: str,
    finding_prefix: str,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for dep in plan_details.get("capability_dependencies", []):
        binding = _runtime_binding_for_dependency(registry, dep)
        if binding is None:
            continue
        for op_ref in binding.implements:
            op = operationalizations.get(op_ref)
            if op is None:
                continue
            if claim_contract_ref in claim_contracts and op.claim_contract_ref in claim_contracts:
                inherits, closure_findings = _contract_inherits_or_is(
                    claim_contract_ref,
                    op.claim_contract_ref,
                    claim_contracts,
                    kind="claim",
                )
                findings.extend(closure_findings)
                if not inherits:
                    findings.append(
                        _finding(
                            f"{finding_prefix}_claim_omits_dependency_contract",
                            f"{subject_id} claim contract {claim_contract_ref} does not inherit dependency {dep['name']} claim {op.claim_contract_ref}.",
                            f"{subject_path}.claim_contract_ref",
                        )
                    )
            if (
                evidence_contract_ref in evidence_contracts
                and op.evidence_contract_ref in evidence_contracts
            ):
                inherits, closure_findings = _contract_inherits_or_is(
                    evidence_contract_ref,
                    op.evidence_contract_ref,
                    evidence_contracts,
                    kind="evidence",
                )
                findings.extend(closure_findings)
                if not inherits:
                    findings.append(
                        _finding(
                            f"{finding_prefix}_evidence_omits_dependency_contract",
                            f"{subject_id} evidence contract {evidence_contract_ref} does not inherit dependency {dep['name']} evidence {op.evidence_contract_ref}.",
                            f"{subject_path}.evidence_contract_ref",
                        )
                    )
    return findings


def validate_runtime_signature_compatibility(
    binding: Any,
    runtime_entry: dict[str, Any],
    operationalizations: dict[str, Any],
    path: str,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    semantic_inputs: dict[str, Any] = {}
    semantic_outputs: dict[str, Any] = {}
    for op_ref in binding.implements:
        op = operationalizations.get(op_ref)
        if op is None:
            continue
        semantic_inputs.update(_field_map(op.inputs))
        semantic_outputs.update(_field_map(op.outputs))

    runtime_inputs = {item["name"]: item for item in runtime_entry.get("inputs", [])}
    runtime_outputs = {item["name"]: item for item in runtime_entry.get("outputs", [])}
    runtime_parameters = {item["name"]: item for item in runtime_entry.get("parameters", [])}
    semantic_parameters = _field_map(binding.semantic_parameters)

    mapped_runtime_inputs: set[str] = set()
    for semantic_name, input_binding in binding.input_bindings.items():
        semantic_field = semantic_inputs.get(semantic_name)
        if semantic_field is None:
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} input binding targets undeclared semantic input {semantic_name}.",
                    f"{path}.input_bindings.{semantic_name}",
                )
            )
            continue
        if input_binding.source == "NODE_INPUT":
            runtime_port = input_binding.runtime_port
            runtime_input = runtime_inputs.get(runtime_port)
            if runtime_input is None:
                findings.append(
                    _finding(
                        "runtime_signature_mismatch",
                        f"{binding.id} semantic input {semantic_name} maps to unknown runtime input {runtime_port}.",
                        f"{path}.input_bindings.{semantic_name}.runtime_port",
                    )
                )
                continue
            mapped_runtime_inputs.add(str(runtime_port))
            mismatches = _signature_mismatch(semantic_field, runtime_input)
            if mismatches:
                findings.append(
                    _finding(
                        "runtime_signature_mismatch",
                        f"{binding.id} input {runtime_port} mismatch: {mismatches}.",
                        f"{path}.input_bindings.{semantic_name}",
                    )
                )
    for semantic_name, semantic_field in semantic_inputs.items():
        if (
            getattr(semantic_field, "required", True)
            and semantic_name not in binding.input_bindings
            and semantic_name not in binding.uncovered_semantic_inputs
        ):
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} semantic input {semantic_name} is required but is neither bound nor explicitly uncovered.",
                    f"{path}.input_bindings.{semantic_name}",
                )
            )
    for runtime_name in runtime_inputs:
        if (
            runtime_name not in mapped_runtime_inputs
            and runtime_name not in binding.uncovered_runtime_inputs
        ):
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} runtime input {runtime_name} is neither mapped nor explicitly uncovered.",
                    f"{path}.uncovered_runtime_inputs",
                )
            )

    mapped_runtime_outputs: set[str] = set()
    for semantic_name, output_binding in binding.output_bindings.items():
        semantic_field = semantic_outputs.get(semantic_name)
        if semantic_field is None:
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} output binding targets undeclared semantic output {semantic_name}.",
                    f"{path}.output_bindings.{semantic_name}",
                )
            )
            continue
        runtime_output = runtime_outputs.get(output_binding.runtime_port)
        if runtime_output is None:
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} semantic output {semantic_name} maps to unknown runtime output {output_binding.runtime_port}.",
                    f"{path}.output_bindings.{semantic_name}.runtime_port",
                )
            )
            continue
        mapped_runtime_outputs.add(output_binding.runtime_port)
        mismatches = _signature_mismatch(semantic_field, runtime_output)
        if mismatches:
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} output {output_binding.runtime_port} mismatch: {mismatches}.",
                    f"{path}.output_bindings.{semantic_name}",
                )
            )
    for semantic_name, semantic_field in semantic_outputs.items():
        if (
            getattr(semantic_field, "required", True)
            and semantic_name not in binding.output_bindings
            and semantic_name not in binding.uncovered_semantic_outputs
        ):
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} semantic output {semantic_name} is required but is neither bound nor explicitly uncovered.",
                    f"{path}.output_bindings.{semantic_name}",
                )
            )
    for runtime_name in runtime_outputs:
        if (
            runtime_name not in mapped_runtime_outputs
            and runtime_name not in binding.uncovered_runtime_outputs
        ):
            findings.append(
                _finding(
                    "runtime_signature_mismatch",
                    f"{binding.id} runtime output {runtime_name} is neither mapped nor explicitly uncovered.",
                    f"{path}.uncovered_runtime_outputs",
                )
            )

    mapped_semantic_parameters: set[str] = set()
    for runtime_name, semantic_name in binding.parameter_bindings.items():
        runtime_parameter = runtime_parameters.get(runtime_name)
        if runtime_parameter is None:
            findings.append(
                _finding(
                    "runtime_parameter_signature_mismatch",
                    f"{binding.id} maps unknown runtime parameter {runtime_name}.",
                    f"{path}.parameter_bindings.{runtime_name}",
                )
            )
            continue
        semantic_parameter = semantic_parameters.get(semantic_name)
        if semantic_parameter is None:
            findings.append(
                _finding(
                    "runtime_parameter_signature_mismatch",
                    f"{binding.id} runtime parameter {runtime_name} maps to undeclared semantic parameter {semantic_name}.",
                    f"{path}.parameter_bindings.{runtime_name}",
                )
            )
            continue
        mapped_semantic_parameters.add(semantic_name)
        mismatches = _parameter_signature_mismatch(semantic_parameter, runtime_parameter)
        if mismatches:
            findings.append(
                _finding(
                    "runtime_parameter_signature_mismatch",
                    f"{binding.id} parameter {runtime_name} mismatch: {mismatches}.",
                    f"{path}.parameter_bindings.{runtime_name}",
                )
            )
    for runtime_name in runtime_parameters:
        if (
            runtime_name not in binding.parameter_bindings
            and runtime_name not in binding.uncovered_runtime_parameters
        ):
            findings.append(
                _finding(
                    "runtime_parameter_signature_mismatch",
                    f"{binding.id} runtime parameter {runtime_name} is neither mapped nor explicitly uncovered.",
                    f"{path}.uncovered_runtime_parameters",
                )
            )
    for semantic_name, semantic_parameter in semantic_parameters.items():
        if (
            semantic_name not in mapped_semantic_parameters
            and semantic_name not in binding.uncovered_semantic_parameters
        ):
            findings.append(
                _finding(
                    "runtime_parameter_signature_mismatch",
                    f"{binding.id} semantic parameter {semantic_name} is neither mapped nor explicitly uncovered.",
                    f"{path}.semantic_parameters.{semantic_name}",
                )
            )
    if binding.conformance_status == ConformanceStatus.EXACT:
        uncovered = {key: value for key, value in _uncovered_binding_values(binding).items() if value}
        if uncovered:
            findings.append(
                _finding(
                    "exact_binding_has_uncovered_elements",
                    f"{binding.id} is EXACT but declares uncovered elements {uncovered}.",
                    f"{path}.conformance_status",
                )
            )
    return findings


def validate_operator_signature_compatibility(
    operator_definition: Any, runtime_operator: dict[str, Any], path: str
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    input_payload = _type_value_to_runtime(operator_definition.input.value)
    input_temporal = _type_container_to_runtime(operator_definition.input.container)
    output_payload = _type_value_to_runtime(operator_definition.output.value)
    output_temporal = _type_container_to_runtime(operator_definition.output.container)

    if input_payload != "any" and input_payload not in runtime_operator["input_payload_types"]:
        findings.append(
            _finding(
                "operator_signature_mismatch",
                f"{operator_definition.id} input payload {input_payload} is not supported by runtime {runtime_operator['input_payload_types']}.",
                f"{path}.input",
            )
        )
    if input_temporal != "any" and input_temporal not in runtime_operator["input_temporal_types"]:
        findings.append(
            _finding(
                "operator_signature_mismatch",
                f"{operator_definition.id} input temporal {input_temporal} is not supported by runtime {runtime_operator['input_temporal_types']}.",
                f"{path}.input",
            )
        )
    if output_payload != runtime_operator["output_payload_type"]:
        findings.append(
            _finding(
                "operator_signature_mismatch",
                f"{operator_definition.id} output payload {output_payload} != runtime {runtime_operator['output_payload_type']}.",
                f"{path}.output",
            )
        )
    if output_temporal != runtime_operator["output_temporal_type"]:
        findings.append(
            _finding(
                "operator_signature_mismatch",
                f"{operator_definition.id} output temporal {output_temporal} != runtime {runtime_operator['output_temporal_type']}.",
                f"{path}.output",
            )
        )
    if runtime_operator.get("compare_required") and operator_definition.compare is None:
        findings.append(
            _finding(
                "operator_signature_mismatch",
                f"{operator_definition.id} runtime requires compare but semantic definition omits it.",
                f"{path}.compare",
            )
        )
    if operator_definition.compare is not None:
        compare_payload = _type_value_to_runtime(operator_definition.compare.value)
        if compare_payload != "any" and compare_payload not in runtime_operator["compare_payload_types"]:
            findings.append(
                _finding(
                    "operator_signature_mismatch",
                    f"{operator_definition.id} compare payload {compare_payload} is not supported by runtime {runtime_operator['compare_payload_types']}.",
                    f"{path}.compare",
                )
            )
        if (
            runtime_operator.get("compare_unit_must_match")
            and operator_definition.input.unit != "any"
            and operator_definition.compare.unit != "any"
            and operator_definition.input.unit != operator_definition.compare.unit
        ):
            findings.append(
                _finding(
                    "operator_signature_mismatch",
                    f"{operator_definition.id} compare unit {operator_definition.compare.unit} must match input unit {operator_definition.input.unit}.",
                    f"{path}.compare.unit",
                )
            )
    return findings


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
    maturity_subjects = [item.subject_ref for item in registry.maturity_assessments]
    exposure_subjects = [item.subject_ref for item in registry.exposure_policies]
    projection_targets = [item.target.value for item in registry.projection_policies]
    maturity = {item.subject_ref: item for item in registry.maturity_assessments}
    exposure_by_subject = {item.subject_ref: item for item in registry.exposure_policies}
    runtime_keys = runtime_capability_keys(runtime_manifest)
    operator_keys = runtime_operator_keys(runtime_manifest)
    runtime_by_key = _runtime_by_key(runtime_manifest)
    operators_by_key = _operator_by_key(runtime_manifest)
    plan_artifacts = _index(registry.plan_artifacts)
    plan_index = build_plan_artifact_index(registry)

    for subject in sorted({item for item in maturity_subjects if maturity_subjects.count(item) > 1}):
        findings.append(
            _finding(
                "duplicate_maturity_subject",
                f"Multiple MaturityAssessment records target {subject}.",
                "maturity_assessments",
            )
        )
    for subject in sorted({item for item in exposure_subjects if exposure_subjects.count(item) > 1}):
        findings.append(
            _finding(
                "duplicate_exposure_subject",
                f"Multiple ExposurePolicy records target {subject}.",
                "exposure_policies",
            )
        )
    for target in sorted({item for item in projection_targets if projection_targets.count(item) > 1}):
        findings.append(
            _finding(
                "duplicate_projection_policy_target",
                f"Multiple ProjectionPolicy records target {target}.",
                "projection_policies",
            )
        )

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
            implementation = None
        else:
            implementation = implementations[binding.implementation_ref]
            if set(binding.implements) != set(implementation.implements):
                findings.append(
                    _finding(
                        "binding_implementation_operationalization_mismatch",
                        f"{binding.id} implements {binding.implements}, but {implementation.id} implements {implementation.implements}.",
                        f"runtime_bindings[{index}].implements",
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
        if binding.conformance_status in {
            ConformanceStatus.PARTIAL,
            ConformanceStatus.LEGACY_APPROXIMATION,
        }:
            if not binding.known_deviations:
                findings.append(
                    _finding(
                        "non_exact_binding_missing_deviation",
                        f"{binding.id} is {binding.conformance_status.value} but declares no known_deviations.",
                        f"runtime_bindings[{index}].known_deviations",
                    )
                )
            if not binding.input_bindings and not binding.output_bindings and not binding.parameter_bindings:
                findings.append(
                    _finding(
                        "non_exact_binding_missing_bindings",
                        f"{binding.id} is {binding.conformance_status.value} but declares no input, output, or parameter bindings.",
                        f"runtime_bindings[{index}]",
                    )
                )
        runtime_entry = runtime_by_key.get(key)
        if runtime_entry is not None:
            findings.extend(
                validate_runtime_signature_compatibility(
                    binding, runtime_entry, operationalizations, f"runtime_bindings[{index}]"
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

    for concept in registry.concepts:
        if concept.claim_contract_ref not in claim_contracts:
            findings.append(
                _finding(
                    "concept_missing_claim_contract",
                    f"{concept.id} references missing claim contract {concept.claim_contract_ref}.",
                    f"concepts.{concept.id}.claim_contract_ref",
                )
            )
        if concept.evidence_contract_ref and concept.evidence_contract_ref not in evidence_contracts:
            findings.append(
                _finding(
                    "concept_missing_evidence_contract",
                    f"{concept.id} references missing evidence contract {concept.evidence_contract_ref}.",
                    f"concepts.{concept.id}.evidence_contract_ref",
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
    for index, item in enumerate(registry.operator_definitions):
        runtime_operator = operators_by_key.get((item.operator_id, item.operator_version))
        if runtime_operator is not None:
            findings.extend(
                validate_operator_signature_compatibility(
                    item, runtime_operator, f"operator_definitions[{index}]"
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
                continue
            concept = concepts[concept_ref]
            if item.claim_contract_ref in claim_contracts and concept.claim_contract_ref in claim_contracts:
                effective, closure_findings = _effective_claim_contract(
                    item.claim_contract_ref, claim_contracts
                )
                findings.extend(closure_findings)
                if (
                    item.claim_contract_ref != concept.claim_contract_ref
                    and concept.claim_contract_ref not in effective["ancestors"]
                ):
                    findings.append(
                        _finding(
                            "operationalization_claim_not_derived_from_concept",
                            f"{item.id} claim contract {item.claim_contract_ref} does not inherit concept claim {concept.claim_contract_ref}.",
                            f"operationalizations.{item.id}.claim_contract_ref",
                        )
                    )
            if (
                item.evidence_contract_ref in evidence_contracts
                and concept.evidence_contract_ref
                and concept.evidence_contract_ref in evidence_contracts
            ):
                effective_evidence, closure_findings = _effective_evidence_contract(
                    item.evidence_contract_ref, evidence_contracts
                )
                findings.extend(closure_findings)
                if (
                    item.evidence_contract_ref != concept.evidence_contract_ref
                    and concept.evidence_contract_ref not in effective_evidence["ancestors"]
                ):
                    findings.append(
                        _finding(
                            "operationalization_evidence_not_derived_from_concept",
                            f"{item.id} evidence contract {item.evidence_contract_ref} does not inherit concept evidence {concept.evidence_contract_ref}.",
                            f"operationalizations.{item.id}.evidence_contract_ref",
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
            operationalization = None
        else:
            operationalization = operationalizations[item.operationalization_ref]
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
        if (
            operationalization is not None
            and item.claim_contract_ref in claim_contracts
            and operationalization.claim_contract_ref in claim_contracts
        ):
            effective, closure_findings = _effective_claim_contract(
                item.claim_contract_ref, claim_contracts
            )
            findings.extend(closure_findings)
            if (
                item.claim_contract_ref != operationalization.claim_contract_ref
                and operationalization.claim_contract_ref not in effective["ancestors"]
            ):
                findings.append(
                    _finding(
                        "profile_claim_not_derived_from_operationalization",
                        f"{item.id} claim contract {item.claim_contract_ref} does not inherit operationalization claim {operationalization.claim_contract_ref}.",
                        f"definition_profiles.{item.id}.claim_contract_ref",
                    )
                )
        if (
            operationalization is not None
            and item.evidence_contract_ref in evidence_contracts
            and operationalization.evidence_contract_ref in evidence_contracts
        ):
            effective_evidence, closure_findings = _effective_evidence_contract(
                item.evidence_contract_ref, evidence_contracts
            )
            findings.extend(closure_findings)
            if (
                item.evidence_contract_ref != operationalization.evidence_contract_ref
                and operationalization.evidence_contract_ref not in effective_evidence["ancestors"]
            ):
                findings.append(
                    _finding(
                        "profile_evidence_not_derived_from_operationalization",
                        f"{item.id} evidence contract {item.evidence_contract_ref} does not inherit operationalization evidence {operationalization.evidence_contract_ref}.",
                        f"definition_profiles.{item.id}.evidence_contract_ref",
                    )
                )

    for child in registry.claim_contracts:
        effective, closure_findings = _effective_claim_contract(child.id, claim_contracts)
        findings.extend(closure_findings)
        broadened = sorted(set(child.permitted) & effective["prohibited"])
        if broadened:
            findings.append(
                _finding(
                    "claim_contract_broadens_parent",
                    f"{child.id} permits claims prohibited upstream: {broadened}.",
                    f"claim_contracts.{child.id}.permitted",
                )
            )

    for child in registry.evidence_contracts:
        effective_evidence, closure_findings = _effective_evidence_contract(
            child.id, evidence_contracts
        )
        findings.extend(closure_findings)
        missing_required = sorted(effective_evidence["required"] - set(child.required))
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
    recipe_subjects = {
        f"recipe:{item.recipe_id}:{item.recipe_version}" for item in registry.recipe_definitions
    }
    composition_subjects = {f"composition:{item.id}" for item in registry.composition_instances}
    for subject in runtime_subjects | recipe_subjects | composition_subjects:
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

    for recipe in registry.recipe_definitions:
        if recipe.concept_ref not in concepts:
            findings.append(
                _finding(
                    "recipe_missing_concept",
                    f"{recipe.id} references missing concept {recipe.concept_ref}.",
                    f"recipe_definitions.{recipe.id}.concept_ref",
                )
            )
            recipe_concept = None
        else:
            recipe_concept = concepts[recipe.concept_ref]
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
        if artifact.recipe_ref != recipe.id:
            findings.append(
                _finding(
                    "plan_artifact_recipe_ref_mismatch",
                    f"{artifact.id} recipe_ref {artifact.recipe_ref} does not point back to {recipe.id}.",
                    f"plan_artifacts.{artifact.id}.recipe_ref",
                )
            )
            continue
        plan_details = plan_index["artifacts"].get(artifact.id, {})
        if not plan_details.get("exists"):
            findings.append(
                _finding(
                    "plan_artifact_path_missing",
                    f"{artifact.id} references missing typed plan {artifact.exact_typed_plan_ref}.",
                    f"plan_artifacts.{artifact.id}.exact_typed_plan_ref",
                )
            )
            continue
        if not plan_details.get("valid_typed_plan"):
            findings.append(
                _finding(
                    "plan_artifact_invalid_typed_plan",
                    f"{artifact.id} cannot validate as TacticalQueryDocument: {plan_details.get('error')}.",
                    f"plan_artifacts.{artifact.id}",
                )
            )
            continue
        if (
            plan_details.get("recipe_id") != recipe.recipe_id
            or plan_details.get("recipe_version") != recipe.recipe_version
        ):
            findings.append(
                _finding(
                    "plan_artifact_recipe_identity_mismatch",
                    f"{artifact.id} parsed recipe {(plan_details.get('recipe_id'), plan_details.get('recipe_version'))} does not match registry {(recipe.recipe_id, recipe.recipe_version)}.",
                    f"plan_artifacts.{artifact.id}",
                )
            )
        extracted_dependencies = sorted(plan_details.get("dependency_refs", []))
        declared_dependencies = sorted(recipe.dependency_refs)
        if extracted_dependencies != declared_dependencies:
            findings.append(
                _finding(
                    "recipe_dependency_mismatch",
                    f"{recipe.id} declares {declared_dependencies}, but parsed plan has {extracted_dependencies}.",
                    f"recipe_definitions.{recipe.id}.dependency_refs",
                )
            )
        for dep in plan_details.get("capability_dependencies", []):
            runtime_key = (dep["kind"], dep["name"], dep["version"])
            if runtime_key not in set(binding_keys):
                findings.append(
                    _finding(
                        "recipe_references_unbound_runtime_capability",
                        f"{artifact.id} references unbound runtime capability {runtime_key}.",
                        f"plan_artifacts.{artifact.id}.draft_plan.nodes",
                    )
                )
        for dep in plan_details.get("operator_dependencies", []):
            key = (dep["name"], dep["version"])
            if key not in operator_definition_keys:
                findings.append(
                    _finding(
                        "recipe_references_unregistered_operator",
                        f"{artifact.id} references operator {key} without OperatorDefinition.",
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
        if (
            recipe_concept is not None
            and recipe.claim_contract_ref in claim_contracts
            and recipe_concept.claim_contract_ref in claim_contracts
        ):
            inherits, closure_findings = _contract_inherits_or_is(
                recipe.claim_contract_ref,
                recipe_concept.claim_contract_ref,
                claim_contracts,
                kind="claim",
            )
            findings.extend(closure_findings)
            if not inherits:
                findings.append(
                    _finding(
                        "recipe_claim_not_derived_from_concept",
                        f"{recipe.id} claim contract {recipe.claim_contract_ref} does not inherit concept claim {recipe_concept.claim_contract_ref}.",
                        f"recipe_definitions.{recipe.id}.claim_contract_ref",
                    )
                )
        if (
            recipe_concept is not None
            and recipe.evidence_contract_ref in evidence_contracts
            and recipe_concept.evidence_contract_ref
            and recipe_concept.evidence_contract_ref in evidence_contracts
        ):
            inherits, closure_findings = _contract_inherits_or_is(
                recipe.evidence_contract_ref,
                recipe_concept.evidence_contract_ref,
                evidence_contracts,
                kind="evidence",
            )
            findings.extend(closure_findings)
            if not inherits:
                findings.append(
                    _finding(
                        "recipe_evidence_not_derived_from_concept",
                        f"{recipe.id} evidence contract {recipe.evidence_contract_ref} does not inherit concept evidence {recipe_concept.evidence_contract_ref}.",
                        f"recipe_definitions.{recipe.id}.evidence_contract_ref",
                    )
                )
        if recipe.claim_contract_ref in claim_contracts and recipe.evidence_contract_ref in evidence_contracts:
            findings.extend(
                validate_plan_dependency_contract_closure(
                    registry=registry,
                    plan_details=plan_details,
                    claim_contract_ref=recipe.claim_contract_ref,
                    evidence_contract_ref=recipe.evidence_contract_ref,
                    claim_contracts=claim_contracts,
                    evidence_contracts=evidence_contracts,
                    operationalizations=operationalizations,
                    subject_path=f"recipe_definitions.{recipe.id}",
                    subject_id=recipe.id,
                    finding_prefix="recipe",
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
                continue
            profile = profiles[profile_ref]
            if (
                recipe.claim_contract_ref in claim_contracts
                and profile.claim_contract_ref in claim_contracts
            ):
                inherits, closure_findings = _contract_inherits_or_is(
                    recipe.claim_contract_ref,
                    profile.claim_contract_ref,
                    claim_contracts,
                    kind="claim",
                )
                findings.extend(closure_findings)
                if not inherits:
                    findings.append(
                        _finding(
                            "recipe_claim_omits_profile_contract",
                            f"{recipe.id} claim contract {recipe.claim_contract_ref} does not inherit profile claim {profile.claim_contract_ref}.",
                            f"recipe_definitions.{recipe.id}.claim_contract_ref",
                        )
                    )
            if (
                recipe.evidence_contract_ref in evidence_contracts
                and profile.evidence_contract_ref in evidence_contracts
            ):
                inherits, closure_findings = _contract_inherits_or_is(
                    recipe.evidence_contract_ref,
                    profile.evidence_contract_ref,
                    evidence_contracts,
                    kind="evidence",
                )
                findings.extend(closure_findings)
                if not inherits:
                    findings.append(
                        _finding(
                            "recipe_evidence_omits_profile_contract",
                            f"{recipe.id} evidence contract {recipe.evidence_contract_ref} does not inherit profile evidence {profile.evidence_contract_ref}.",
                            f"recipe_definitions.{recipe.id}.evidence_contract_ref",
                        )
                    )
            defaults = plan_details.get("parameter_defaults", {})
            for name, value in profile.bindings.items():
                if name in defaults and defaults[name] != value:
                    findings.append(
                        _finding(
                            "profile_binding_plan_parameter_mismatch",
                            f"{recipe.id} profile {profile_ref} binding {name}={value!r} does not match plan default {defaults[name]!r}.",
                            f"definition_profiles.{profile_ref}.bindings.{name}",
                        )
                    )

    for composition in registry.composition_instances:
        if composition.concept_ref not in concepts:
            findings.append(
                _finding(
                    "composition_missing_concept",
                    f"{composition.id} references missing concept {composition.concept_ref}.",
                    f"composition_instances.{composition.id}.concept_ref",
                )
            )
            composition_concept = None
        else:
            composition_concept = concepts[composition.concept_ref]
        artifact = plan_artifacts.get(composition.plan_artifact_ref)
        if artifact is None:
            findings.append(
                _finding(
                    "composition_missing_plan_artifact",
                    f"{composition.id} references missing plan artifact {composition.plan_artifact_ref}.",
                    f"composition_instances.{composition.id}.plan_artifact_ref",
                )
            )
            continue
        plan_details = plan_index["artifacts"].get(artifact.id, {})
        if artifact.origin != composition.origin:
            findings.append(
                _finding(
                    "composition_origin_mismatch",
                    f"{composition.id} origin {composition.origin} does not match plan artifact origin {artifact.origin}.",
                    f"composition_instances.{composition.id}.origin",
                )
            )
        if artifact.promotion_status != composition.promotion_status:
            findings.append(
                _finding(
                    "composition_promotion_status_mismatch",
                    f"{composition.id} promotion {composition.promotion_status} does not match plan artifact promotion {artifact.promotion_status}.",
                    f"composition_instances.{composition.id}.promotion_status",
                )
            )
        if not plan_details.get("valid_typed_plan"):
            findings.append(
                _finding(
                    "composition_plan_artifact_invalid",
                    f"{composition.id} plan artifact is not a valid typed plan: {plan_details.get('error')}.",
                    f"composition_instances.{composition.id}.plan_artifact_ref",
                )
            )
        for dep in plan_details.get("capability_dependencies", []):
            runtime_key = (dep["kind"], dep["name"], dep["version"])
            if runtime_key not in set(binding_keys):
                findings.append(
                    _finding(
                        "composition_references_unbound_runtime_capability",
                        f"{artifact.id} references unbound runtime capability {runtime_key}.",
                        f"plan_artifacts.{artifact.id}.draft_plan.nodes",
                    )
                )
        for dep in plan_details.get("operator_dependencies", []):
            key = (dep["name"], dep["version"])
            if key not in operator_definition_keys:
                findings.append(
                    _finding(
                        "composition_references_unregistered_operator",
                        f"{artifact.id} references operator {key} without OperatorDefinition.",
                        f"plan_artifacts.{artifact.id}.draft_plan.nodes",
                    )
                )
        if artifact.origin == "AI_AUTHORED" and not str(plan_details.get("source_kind", "")).startswith(
            "n1f_origin_bundle"
        ):
            findings.append(
                _finding(
                    "composition_artifact_not_origin_bundle",
                    f"{composition.id} AI-authored composition must point to a supported origin bundle, not {plan_details.get('source_kind')}.",
                    f"plan_artifacts.{artifact.id}.exact_typed_plan_ref",
                )
            )
        if composition.claim_contract_ref not in claim_contracts:
            findings.append(
                _finding(
                    "composition_missing_claim_contract",
                    f"{composition.id} references missing claim contract {composition.claim_contract_ref}.",
                    f"composition_instances.{composition.id}.claim_contract_ref",
                )
            )
        if composition.evidence_contract_ref not in evidence_contracts:
            findings.append(
                _finding(
                    "composition_missing_evidence_contract",
                    f"{composition.id} references missing evidence contract {composition.evidence_contract_ref}.",
                    f"composition_instances.{composition.id}.evidence_contract_ref",
                )
            )
        if (
            composition_concept is not None
            and composition.claim_contract_ref in claim_contracts
            and composition_concept.claim_contract_ref in claim_contracts
        ):
            inherits, closure_findings = _contract_inherits_or_is(
                composition.claim_contract_ref,
                composition_concept.claim_contract_ref,
                claim_contracts,
                kind="claim",
            )
            findings.extend(closure_findings)
            if not inherits:
                findings.append(
                    _finding(
                        "composition_claim_not_derived_from_concept",
                        f"{composition.id} claim contract {composition.claim_contract_ref} does not inherit concept claim {composition_concept.claim_contract_ref}.",
                        f"composition_instances.{composition.id}.claim_contract_ref",
                    )
                )
        if (
            composition_concept is not None
            and composition.evidence_contract_ref in evidence_contracts
            and composition_concept.evidence_contract_ref
            and composition_concept.evidence_contract_ref in evidence_contracts
        ):
            inherits, closure_findings = _contract_inherits_or_is(
                composition.evidence_contract_ref,
                composition_concept.evidence_contract_ref,
                evidence_contracts,
                kind="evidence",
            )
            findings.extend(closure_findings)
            if not inherits:
                findings.append(
                    _finding(
                        "composition_evidence_not_derived_from_concept",
                        f"{composition.id} evidence contract {composition.evidence_contract_ref} does not inherit concept evidence {composition_concept.evidence_contract_ref}.",
                        f"composition_instances.{composition.id}.evidence_contract_ref",
                    )
                )
        if (
            composition.claim_contract_ref in claim_contracts
            and composition.evidence_contract_ref in evidence_contracts
        ):
            findings.extend(
                validate_plan_dependency_contract_closure(
                    registry=registry,
                    plan_details=plan_details,
                    claim_contract_ref=composition.claim_contract_ref,
                    evidence_contract_ref=composition.evidence_contract_ref,
                    claim_contracts=claim_contracts,
                    evidence_contracts=evidence_contracts,
                    operationalizations=operationalizations,
                    subject_path=f"composition_instances.{composition.id}",
                    subject_id=composition.id,
                    finding_prefix="composition",
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
    supported_requires = {
        "runtime_binding",
        "product_exposure",
        "product_maturity",
        "ai_compiler",
        "agent_safety",
        "validation",
        "plan_artifact",
        "status",
    }
    for policy in registry.projection_policies:
        unknown_requires = sorted(set(policy.requires) - supported_requires)
        if unknown_requires:
            findings.append(
                _finding(
                    "projection_policy_unknown_requirement",
                    f"{policy.id} has unsupported requires keys {unknown_requires}.",
                    f"projection_policies.{policy.id}.requires",
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


def _projection_policy(registry: SemanticRegistry, target: ProjectionTarget) -> Any | None:
    for policy in registry.projection_policies:
        if policy.target == target:
            return policy
    return None


def _is_excluded(policy: Any | None, *, subject: str, status: str = "CURRENT") -> bool:
    if policy is None:
        return True
    excludes = set(policy.excludes)
    return subject in excludes or status in excludes


def _projection_requirement_context(
    *,
    policy: Any | None,
    maturity: Any | None,
    runtime_binding_verified: bool = False,
    plan_artifact_exists: bool | None = None,
    status: str = "CURRENT",
) -> dict[str, str]:
    context = {
        "runtime_binding": "VERIFIED" if runtime_binding_verified else "MISSING",
        "product_exposure": policy.product.value if policy else "MISSING",
        "product_maturity": maturity.product.value if maturity else "MISSING",
        "ai_compiler": policy.ai_compiler.value if policy else "MISSING",
        "agent_safety": maturity.agent_safety.value if maturity else "MISSING",
        "validation": maturity.validation.value if maturity else "MISSING",
        "status": status,
    }
    if plan_artifact_exists is not None:
        context["plan_artifact"] = "EXISTS" if plan_artifact_exists else "MISSING"
    return context


def _projection_requirements_met(projection_policy: Any | None, context: dict[str, str]) -> bool:
    if projection_policy is None:
        return False
    for key, expected in projection_policy.requires.items():
        actual = context.get(key, "MISSING")
        if isinstance(expected, list):
            if actual not in {str(item) for item in expected}:
                return False
        elif actual != str(expected):
            return False
    return True


def _projection_allowed(
    projection_policy: Any | None,
    *,
    subject: str,
    context: dict[str, str],
    status: str = "CURRENT",
) -> bool:
    return (
        not _is_excluded(projection_policy, subject=subject, status=status)
        and _projection_requirements_met(projection_policy, context)
    )


def _capability_allowed_for_product(
    subject: str, policy: Any, maturity: Any, projection_policy: Any
) -> bool:
    context = _projection_requirement_context(
        policy=policy, maturity=maturity, runtime_binding_verified=True
    )
    return policy is not None and maturity is not None and _projection_allowed(
        projection_policy, subject=subject, context=context
    )


def _capability_allowed_for_ai(subject: str, policy: Any, maturity: Any, projection_policy: Any) -> bool:
    context = _projection_requirement_context(
        policy=policy, maturity=maturity, runtime_binding_verified=True
    )
    return policy is not None and maturity is not None and _projection_allowed(
        projection_policy, subject=subject, context=context
    )


def _plan_subject_allowed(
    subject: str,
    policies: dict[str, Any],
    maturities: dict[str, Any],
    projection_policy: Any,
    *,
    plan_artifact_exists: bool,
    dependency_bindings_verified: bool,
) -> bool:
    policy = policies.get(subject)
    maturity = maturities.get(subject)
    context = _projection_requirement_context(
        policy=policy,
        maturity=maturity,
        runtime_binding_verified=dependency_bindings_verified,
        plan_artifact_exists=plan_artifact_exists,
    )
    return policy is not None and maturity is not None and _projection_allowed(
        projection_policy, subject=subject, context=context
    )


def _runtime_contract_for_binding(
    runtime_manifest: dict[str, Any], binding: Any
) -> dict[str, Any] | None:
    return _runtime_by_key(runtime_manifest).get(
        (
            binding.runtime_capability.kind,
            binding.runtime_capability.id,
            binding.runtime_capability.version,
        )
    )


def build_projections(
    registry: SemanticRegistry, runtime_manifest: dict[str, Any], lock: RegistryLock
) -> dict[str, dict[str, Any]]:
    policies = _subject_policy(registry)
    maturities = _subject_maturity(registry)
    lock_payload = lock.model_dump(mode="json")
    plan_index = build_plan_artifact_index(registry)
    product_policy = _projection_policy(registry, ProjectionTarget.PRODUCT)
    ai_policy = _projection_policy(registry, ProjectionTarget.AI)
    recipe_policy = _projection_policy(registry, ProjectionTarget.RECIPE_LIBRARY)
    unsupported_policy = _projection_policy(registry, ProjectionTarget.UNSUPPORTED)
    research_policy = _projection_policy(registry, ProjectionTarget.RESEARCH_ATLAS)

    product_capabilities: list[dict[str, Any]] = []
    ai_capabilities: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    bound_runtime_keys = {
        (
            item.runtime_capability.kind,
            item.runtime_capability.id,
            item.runtime_capability.version,
        )
        for item in registry.runtime_bindings
    }

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
            "runtime_contract": _runtime_contract_for_binding(runtime_manifest, binding),
        }
        if _capability_allowed_for_product(subject, policy, maturity, product_policy):
            product_capabilities.append(
                base
                | {
                    "product_exposure": policy.product.value,
                    "semantic_maturity": maturity.semantic.value,
                    "product_maturity": maturity.product.value,
                }
            )
        else:
            unsupported.append(
                base
                | {
                    "reason": "PRODUCT_PROJECTION_POLICY_DENIED",
                    "product_exposure": policy.product.value if policy else "MISSING",
                    "product_maturity": maturity.product.value if maturity else "MISSING",
                    "validation_maturity": maturity.validation.value if maturity else "MISSING",
                }
            )
        if _capability_allowed_for_ai(subject, policy, maturity, ai_policy):
            ai_capabilities.append(
                base
                | {
                    "ai_exposure": policy.ai_compiler.value,
                    "agent_safety_maturity": maturity.agent_safety.value,
                }
            )
        else:
            unsupported.append(
                base
                | {
                    "reason": "AI_PROJECTION_POLICY_DENIED",
                    "ai_exposure": policy.ai_compiler.value if policy else "MISSING",
                    "agent_safety_maturity": maturity.agent_safety.value if maturity else "MISSING",
                    "validation_maturity": maturity.validation.value if maturity else "MISSING",
                }
            )

    ai_operators = []
    for item in registry.operator_definitions:
        subject = f"operator:{item.operator_id}:{item.operator_version}"
        context = {
            "runtime_binding": "VERIFIED",
            "ai_compiler": item.authorability.value,
            "agent_safety": "APPROVED",
            "validation": "VERIFIED",
            "product_exposure": "MISSING",
            "product_maturity": "MISSING",
            "status": item.status.value,
        }
        if item.authorability == AuthoringExposure.ALLOWED and _projection_allowed(
            ai_policy, subject=subject, context=context, status=item.status.value
        ):
            ai_operators.append(
                {
                    "id": item.operator_id,
                    "version": item.operator_version,
                    "authorability": item.authorability.value,
                    "unknown_semantics": item.unknown_semantics,
                }
            )

    recipe_items: list[dict[str, Any]] = []
    for recipe in registry.recipe_definitions:
        artifact = next(item for item in registry.plan_artifacts if item.id == recipe.plan_artifact_ref)
        plan_integrity = plan_index["artifacts"].get(artifact.id, {})
        dependency_bindings_verified = all(
            (item["kind"], item["name"], item["version"]) in bound_runtime_keys
            for item in plan_integrity.get("capability_dependencies", [])
        )
        subject = f"recipe:{recipe.recipe_id}:{recipe.recipe_version}"
        recipe_items.append(
            {
                "id": recipe.recipe_id,
                "version": recipe.recipe_version,
                "subject_ref": subject,
                "mapping_id": recipe.id,
                "concept_ref": recipe.concept_ref,
                "plan_artifact_id": artifact.id,
                "exact_typed_plan_ref": artifact.exact_typed_plan_ref,
                "plan_integrity": plan_integrity,
                "plan_artifact_exists": bool(plan_integrity.get("exists")),
                "dependency_bindings_verified": dependency_bindings_verified,
                "dependencies": recipe.dependency_refs,
                "profiles": recipe.profile_refs,
                "claim_contract_ref": recipe.claim_contract_ref,
                "evidence_contract_ref": recipe.evidence_contract_ref,
            }
        )

    product_recipes = [
        item
        for item in recipe_items
        if _plan_subject_allowed(
            item["subject_ref"],
            policies,
            maturities,
            product_policy,
            plan_artifact_exists=item["plan_artifact_exists"],
            dependency_bindings_verified=item["dependency_bindings_verified"],
        )
    ]
    ai_recipes = [
        item
        for item in recipe_items
        if _plan_subject_allowed(
            item["subject_ref"],
            policies,
            maturities,
            ai_policy,
            plan_artifact_exists=item["plan_artifact_exists"],
            dependency_bindings_verified=item["dependency_bindings_verified"],
        )
    ]
    recipe_library_items = [
        item
        for item in recipe_items
        if _projection_allowed(
            recipe_policy,
            subject=item["subject_ref"],
            context=_projection_requirement_context(
                policy=policies.get(item["subject_ref"]),
                maturity=maturities.get(item["subject_ref"]),
                plan_artifact_exists=item["plan_artifact_exists"],
                runtime_binding_verified=item["dependency_bindings_verified"],
            ),
        )
    ]

    composition_items = []
    for item in registry.composition_instances:
        subject = f"composition:{item.id}"
        plan_integrity = plan_index["artifacts"].get(item.plan_artifact_ref, {})
        dependency_bindings_verified = all(
            (dep["kind"], dep["name"], dep["version"]) in bound_runtime_keys
            for dep in plan_integrity.get("capability_dependencies", [])
        )
        composition_items.append(
            {
                "id": item.id,
                "subject_ref": subject,
                "concept_ref": item.concept_ref,
                "plan_artifact_ref": item.plan_artifact_ref,
                "origin": item.origin,
                "promotion_status": item.promotion_status,
                "plan_integrity": plan_integrity,
                "plan_artifact_exists": bool(plan_integrity.get("exists")),
                "dependency_bindings_verified": dependency_bindings_verified,
                "claim_contract_ref": item.claim_contract_ref,
                "evidence_contract_ref": item.evidence_contract_ref,
            }
        )

    product_compositions = [
        item
        for item in composition_items
        if _plan_subject_allowed(
            item["subject_ref"],
            policies,
            maturities,
            product_policy,
            plan_artifact_exists=item["plan_artifact_exists"],
            dependency_bindings_verified=item["dependency_bindings_verified"],
        )
    ]
    ai_compositions = [
        item
        for item in composition_items
        if _plan_subject_allowed(
            item["subject_ref"],
            policies,
            maturities,
            ai_policy,
            plan_artifact_exists=item["plan_artifact_exists"],
            dependency_bindings_verified=item["dependency_bindings_verified"],
        )
    ]
    recipe_library_compositions = [
        item
        for item in composition_items
        if _projection_allowed(
            recipe_policy,
            subject=item["subject_ref"],
            context=_projection_requirement_context(
                policy=policies.get(item["subject_ref"]),
                maturity=maturities.get(item["subject_ref"]),
                plan_artifact_exists=item["plan_artifact_exists"],
                runtime_binding_verified=item["dependency_bindings_verified"],
            ),
        )
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
            if _projection_allowed(
                research_policy,
                subject=item.id,
                status=item.status.value,
                context=_projection_requirement_context(
                    policy=None,
                    maturity=None,
                    status=item.status.value,
                ),
            )
        ],
    }

    filtered_unsupported = [
        item
        for item in unsupported
        if _projection_allowed(
            unsupported_policy,
            subject=f"runtime:{item['kind']}:{item['id']}:{item['version']}",
            context={
                "runtime_binding": "VERIFIED",
                "product_exposure": item.get("product_exposure", "MISSING"),
                "product_maturity": item.get("product_maturity", "MISSING"),
                "ai_compiler": item.get("ai_exposure", "MISSING"),
                "agent_safety": item.get("agent_safety_maturity", "MISSING"),
                "validation": item.get("validation_maturity", "MISSING"),
                "status": "CURRENT",
            },
        )
    ]

    projections = {
        "product": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "capabilities": product_capabilities,
            "recipes": product_recipes,
            "validated_compositions": product_compositions,
        },
        "ai": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "capabilities": ai_capabilities,
            "operators": ai_operators,
            "recipes": ai_recipes,
            "validated_compositions": ai_compositions,
        },
        "recipe_library": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "registered_recipe_count": len(recipe_library_items),
            "validated_ai_composition_count": len(recipe_library_compositions),
            "recipes": recipe_library_items,
            "validated_compositions": recipe_library_compositions,
        },
        "unsupported": {
            "schema_version": "1.0",
            "registry_lock": lock_payload,
            "items": filtered_unsupported,
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


def _canonical_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "name": item.get("name"),
                "payload_type": item.get("payload_type"),
                "temporal_type": item.get("temporal_type"),
                "unit": item.get("unit", "none"),
                "cardinality": item.get("cardinality"),
                "entity_scope": item.get("entity_scope"),
                "required": item.get("required", False),
                "missing_data_semantics": item.get("missing_data_semantics"),
                "evidence_fields": sorted(item.get("evidence_fields", [])),
                "allowed_values": item.get("allowed_values"),
            }
            for item in fields
        ],
        key=lambda item: str(item.get("name")),
    )


def _canonical_capability_contract(item: dict[str, Any]) -> dict[str, Any]:
    contract = item.get("runtime_contract") if isinstance(item.get("runtime_contract"), dict) else item
    return {
        "kind": contract.get("kind") or item.get("kind"),
        "name": contract.get("name") or item.get("id") or item.get("name"),
        "version": contract.get("version") or item.get("version"),
        "inputs": _canonical_fields(contract.get("inputs", [])),
        "outputs": _canonical_fields(contract.get("outputs", [])),
        "parameters": _canonical_fields(contract.get("parameters", [])),
        "evidence_fields": sorted(contract.get("evidence_fields", [])),
        "missing_data_semantics": contract.get("missing_data_semantics") or "unknown",
        "limitations": sorted(contract.get("limitations", [])),
        "purpose": contract.get("purpose"),
    }


def _canonical_operator_contract(item: dict[str, Any], runtime_operator: dict[str, Any] | None = None) -> dict[str, Any]:
    source = runtime_operator or item
    return {
        "name": source.get("name") or item.get("id"),
        "version": source.get("version") or item.get("version"),
        "input_payload_types": sorted(source.get("input_payload_types", [])),
        "input_temporal_types": sorted(source.get("input_temporal_types", [])),
        "compare_payload_types": sorted(source.get("compare_payload_types", [])),
        "compare_required": bool(source.get("compare_required", False)),
        "compare_unit_must_match": bool(source.get("compare_unit_must_match", False)),
        "duration_required": bool(source.get("duration_required", False)),
        "output_payload_type": source.get("output_payload_type"),
        "output_temporal_type": source.get("output_temporal_type"),
        "output_unit": source.get("output_unit", "none"),
    }


def _canonical_recipe_contract(item: dict[str, Any]) -> dict[str, Any]:
    integrity = item.get("plan_integrity", item)
    authoring_contract = item.get("authoring_contract", {})
    authorable_nodes = authoring_contract.get("authorable_nodes", [])
    capability_dependencies = integrity.get("capability_dependencies")
    if capability_dependencies is None:
        capability_dependencies = [
            {
                "kind": node.get("kind"),
                "name": node.get("catalog_ref"),
                "version": node.get("version"),
            }
            for node in authorable_nodes
        ]
    operator_dependencies = integrity.get("operator_dependencies", [])
    if not operator_dependencies:
        operator_dependencies = [
            {"name": ref, "version": "1.0.0"}
            for ref in item.get("operator_refs", [])
        ]
    parameter_defaults = integrity.get("parameter_defaults", {})
    if not parameter_defaults:
        parameter_defaults = {
            parameter.get("name"): _typed_value_payload(parameter.get("default"))
            for parameter in item.get("parameters", [])
            if isinstance(parameter, dict) and "name" in parameter
        }
    return {
        "recipe_id": item.get("id") or item.get("recipe_id"),
        "recipe_version": item.get("version") or item.get("recipe_version"),
        "capability_dependencies": sorted(
            capability_dependencies,
            key=lambda dep: (str(dep.get("kind")), str(dep.get("name")), str(dep.get("version"))),
        ),
        "operator_dependencies": sorted(
            operator_dependencies,
            key=lambda dep: (str(dep.get("name")), str(dep.get("version"))),
        ),
        "parameter_defaults": parameter_defaults,
        "normalized_plan_hash": integrity.get("normalized_plan_hash")
        or item.get("normalized_plan_hash")
        or item.get("source_sha256"),
    }


def _projection_identities(
    projection: dict[str, Any],
    *,
    include_operators: bool = False,
    runtime_manifest: dict[str, Any] | None = None,
) -> dict[str, str]:
    return {
        subject: stable_hash(contract)
        for subject, contract in _projection_contracts(
            projection, include_operators=include_operators, runtime_manifest=runtime_manifest
        ).items()
    }


def _projection_contracts(
    projection: dict[str, Any],
    *,
    include_operators: bool = False,
    runtime_manifest: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    runtime_operators = _operator_by_key(runtime_manifest or {})
    for item in projection.get("capabilities", []):
        subject = f"runtime:{item['kind']}:{item['id']}:{item['version']}"
        contracts[subject] = _canonical_capability_contract(item)
    for item in projection.get("recipes", []):
        subject = f"recipe:{item['id']}:{item['version']}"
        contracts[subject] = _canonical_recipe_contract(item)
    for item in projection.get("validated_compositions", []):
        subject = f"composition:{item['id']}"
        contracts[subject] = _canonical_recipe_contract(item)
    if include_operators:
        for item in projection.get("operators", []):
            subject = f"operator:{item['id']}:{item['version']}"
            contracts[subject] = _canonical_operator_contract(
                item, runtime_operators.get((item["id"], item["version"]))
            )
    return contracts


def _baseline_contracts(runtime_manifest: dict[str, Any]) -> dict[str, Any]:
    product: dict[str, dict[str, Any]] = {}
    ai: dict[str, dict[str, Any]] = {}
    sources = baseline_artifact_manifest()
    capability_catalog = _load_json_if_exists(CAPABILITY_CATALOG_BASELINE_PATH)
    if isinstance(capability_catalog, dict):
        for key in ("primitives", "relations"):
            for item in capability_catalog.get(key, []):
                subject = f"runtime:{item['kind']}:{item['name']}:{item['version']}"
                product[subject] = _canonical_capability_contract(item)
        for item in runtime_manifest.get("recipes", []):
            subject = f"recipe:{item['recipe_id']}:{item['recipe_version']}"
            product[subject] = _canonical_recipe_contract(item)

    knowledge_pack = _load_json_if_exists(KNOWLEDGE_PACK_BASELINE_PATH)
    if isinstance(knowledge_pack, dict):
        for key in ("primitives", "relations"):
            for item in knowledge_pack.get(key, []):
                if item.get("agent_authorable") is True:
                    subject = f"runtime:{item['kind']}:{item['name']}:{item['version']}"
                    ai[subject] = _canonical_capability_contract(item)
        for item in knowledge_pack.get("operators", []):
            subject = f"operator:{item['name']}:{item['version']}"
            ai[subject] = _canonical_operator_contract(item)
        for item in knowledge_pack.get("recipes", []):
            subject = f"recipe:{item['recipe_id']}:{item['recipe_version']}"
            ai[subject] = _canonical_recipe_contract(item)

    return {"product": product, "ai": ai, "sources": sources}


def _baseline_identities(runtime_manifest: dict[str, Any]) -> dict[str, Any]:
    contracts = _baseline_contracts(runtime_manifest)
    return {
        "product": {subject: stable_hash(contract) for subject, contract in contracts["product"].items()},
        "ai": {subject: stable_hash(contract) for subject, contract in contracts["ai"].items()},
        "sources": contracts["sources"],
    }


def _changed_fields(baseline_contract: dict[str, Any], projection_contract: dict[str, Any]) -> list[str]:
    fields = set(baseline_contract) | set(projection_contract)
    return sorted(
        field
        for field in fields
        if baseline_contract.get(field) != projection_contract.get(field)
    )


def _identity_diff(
    baseline_contracts: dict[str, dict[str, Any]],
    projection_contracts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline = {
        subject: stable_hash(contract) for subject, contract in baseline_contracts.items()
    }
    projection = {
        subject: stable_hash(contract) for subject, contract in projection_contracts.items()
    }
    baseline_keys = set(baseline)
    projection_keys = set(projection)
    common = baseline_keys & projection_keys
    changed = sorted(key for key in common if baseline[key] != projection[key])
    return {
        "added": sorted(projection_keys - baseline_keys),
        "removed": sorted(baseline_keys - projection_keys),
        "contract_changed": changed,
        "added_details": {
            key: {"projection_contract_hash": projection[key]}
            for key in sorted(projection_keys - baseline_keys)
        },
        "removed_details": {
            key: {"baseline_contract_hash": baseline[key]}
            for key in sorted(baseline_keys - projection_keys)
        },
        "contract_changed_details": {
            key: {
                "baseline_contract_hash": baseline[key],
                "projection_contract_hash": projection[key],
                "changed_fields": _changed_fields(
                    baseline_contracts[key], projection_contracts[key]
                ),
            }
            for key in changed
        },
        "baseline_count": len(baseline_keys),
        "projection_count": len(projection_keys),
        "shared_count": len(common),
    }


def build_projection_differences(
    runtime_manifest: dict[str, Any], projections: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    baselines = _baseline_contracts(runtime_manifest)
    return {
        "baseline_sources": baselines["sources"],
        "product": _identity_diff(
            baselines["product"],
            _projection_contracts(projections["product"], runtime_manifest=runtime_manifest),
        ),
        "ai": _identity_diff(
            baselines["ai"],
            _projection_contracts(
                projections["ai"], include_operators=True, runtime_manifest=runtime_manifest
            ),
        ),
    }


def validate_projection_parity(
    registry: SemanticRegistry,
    runtime_manifest: dict[str, Any],
    projections: dict[str, dict[str, Any]],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    baseline_sources = baseline_artifact_manifest()
    for source_name, source in baseline_sources.items():
        if source_name == "baseline_artifact_revision":
            continue
        if not source.get("exists"):
            findings.append(
                _finding(
                    "projection_baseline_missing",
                    f"Required parity baseline {source_name} is missing at {source.get('path')}.",
                    f"baselines.{source_name}",
                )
            )
    if findings:
        return findings

    policy_by_target = {policy.target.value: policy for policy in registry.projection_policies}
    differences = build_projection_differences(runtime_manifest, projections)
    for target in ("product", "ai"):
        diff = differences[target]
        policy = policy_by_target.get(target)
        waivers = policy.accepted_differences if policy else []
        observed: set[tuple[str, str]] = set()
        waiver_by_key = {
            (waiver.difference_kind.lower(), waiver.subject_ref): waiver
            for waiver in waivers
        }
        for key in ("added", "removed", "contract_changed"):
            details_key = f"{key}_details"
            for subject in diff.get(key, []):
                waiver = waiver_by_key.get((key, subject))
                if waiver is None:
                    findings.append(
                        _finding(
                            "projection_parity_unapproved_difference",
                            f"{target} projection has unapproved {key}: {subject}.",
                            f"projection_policies.{target}.accepted_differences",
                        )
                    )
                    continue
                observed.add((key, subject))
                details = diff.get(details_key, {}).get(subject, {})
                baseline_hash = details.get("baseline_contract_hash")
                projection_hash = details.get("projection_contract_hash")
                if key in {"removed", "contract_changed"} and (
                    not waiver.baseline_contract_hash
                    or waiver.baseline_contract_hash != baseline_hash
                ):
                    findings.append(
                        _finding(
                            "projection_parity_waiver_hash_mismatch",
                            f"{target} waiver for {subject} expected baseline hash {waiver.baseline_contract_hash}, observed {baseline_hash}.",
                            f"projection_policies.{target}.accepted_differences.{subject}",
                        )
                    )
                if key in {"added", "contract_changed"} and (
                    not waiver.projection_contract_hash
                    or waiver.projection_contract_hash != projection_hash
                ):
                    findings.append(
                        _finding(
                            "projection_parity_waiver_hash_mismatch",
                            f"{target} waiver for {subject} expected projection hash {waiver.projection_contract_hash}, observed {projection_hash}.",
                            f"projection_policies.{target}.accepted_differences.{subject}",
                        )
                    )
                if key == "contract_changed":
                    changed_fields = set(details.get("changed_fields", []))
                    permitted_fields = set(waiver.permitted_fields)
                    unpermitted_fields = sorted(changed_fields - permitted_fields)
                    if unpermitted_fields:
                        findings.append(
                            _finding(
                                "projection_parity_waiver_field_mismatch",
                                f"{target} waiver for {subject} does not permit changed fields {unpermitted_fields}.",
                                f"projection_policies.{target}.accepted_differences.{subject}.permitted_fields",
                            )
                        )
        for waiver in waivers:
            observed_key = (waiver.difference_kind.lower(), waiver.subject_ref)
            if observed_key not in observed:
                findings.append(
                    _finding(
                        "projection_parity_stale_waiver",
                        f"{target} waiver for {waiver.subject_ref} {waiver.difference_kind} is not currently observed.",
                        f"projection_policies.{target}.accepted_differences.{waiver.subject_ref}",
                    )
                )
    return findings


def _binding_path_for_capability(
    registry: SemanticRegistry,
    capability: dict[str, str],
    projections: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    implementations = _index(registry.implementations)
    operationalizations = _index(registry.operationalizations)
    concepts = _index(registry.concepts)
    claim_contracts = _index(registry.claim_contracts)
    evidence_contracts = _index(registry.evidence_contracts)
    binding = next(
        (
            item
            for item in registry.runtime_bindings
            if item.runtime_capability.kind == capability["kind"]
            and item.runtime_capability.id == capability["name"]
            and item.runtime_capability.version == capability["version"]
        ),
        None,
    )
    if binding is None:
        return {"capability": capability, "binding_found": False}
    implementation = implementations.get(binding.implementation_ref)
    ops = [operationalizations[ref] for ref in binding.implements if ref in operationalizations]
    concept_refs = _dedupe_preserve(
        [concept_ref for op in ops for concept_ref in op.concept_refs]
    )
    product_ids = {
        f"runtime:{item['kind']}:{item['id']}:{item['version']}"
        for item in projections["product"].get("capabilities", [])
    }
    ai_ids = {
        f"runtime:{item['kind']}:{item['id']}:{item['version']}"
        for item in projections["ai"].get("capabilities", [])
    }
    subject = (
        f"runtime:{binding.runtime_capability.kind}:"
        f"{binding.runtime_capability.id}:{binding.runtime_capability.version}"
    )
    return {
        "capability": capability,
        "subject_ref": subject,
        "binding_found": True,
        "binding_id": binding.id,
        "conformance": binding.conformance_status.value,
        "implementation_id": implementation.id if implementation else None,
        "operationalizations": [op.id for op in ops],
        "concepts": concept_refs,
        "claim_contracts": [concepts[ref].claim_contract_ref for ref in concept_refs if ref in concepts],
        "evidence_contracts": [
            concepts[ref].evidence_contract_ref for ref in concept_refs if ref in concepts
        ],
        "effective_claims": {
            ref: sorted(_effective_claim_contract(ref, claim_contracts)[0]["permitted"])
            for ref in [op.claim_contract_ref for op in ops if op.claim_contract_ref in claim_contracts]
        },
        "effective_evidence": {
            ref: sorted(_effective_evidence_contract(ref, evidence_contracts)[0]["required"])
            for ref in [op.evidence_contract_ref for op in ops if op.evidence_contract_ref in evidence_contracts]
        },
        "in_product_projection": subject in product_ids,
        "in_ai_projection": subject in ai_ids,
    }


def resolve_recipe_semantic_path(
    registry: SemanticRegistry,
    projections: dict[str, dict[str, Any]],
    recipe_id: str,
    recipe_version: str,
) -> dict[str, Any]:
    plan_index = build_plan_artifact_index(registry)
    recipe = next(
        (
            item
            for item in registry.recipe_definitions
            if item.recipe_id == recipe_id and item.recipe_version == recipe_version
        ),
        None,
    )
    if recipe is None:
        return {"recipe_id": recipe_id, "recipe_version": recipe_version, "recipe_mapped": False}
    artifact = next(item for item in registry.plan_artifacts if item.id == recipe.plan_artifact_ref)
    plan_details = plan_index["artifacts"].get(artifact.id, {})
    capability_paths = [
        _binding_path_for_capability(registry, capability, projections)
        for capability in plan_details.get("capability_dependencies", [])
    ]
    operator_ids = {
        f"{item.operator_id}:{item.operator_version}" for item in registry.operator_definitions
    }
    return {
        "recipe_id": recipe_id,
        "recipe_version": recipe_version,
        "recipe_mapped": True,
        "mapping_id": recipe.id,
        "plan_artifact_id": artifact.id,
        "plan_integrity": plan_details,
        "capability_paths": capability_paths,
        "operator_paths": [
            {
                "operator": operator,
                "definition_found": f"{operator['name']}:{operator['version']}" in operator_ids,
            }
            for operator in plan_details.get("operator_dependencies", [])
        ],
        "profiles": recipe.profile_refs,
        "claim_contract": recipe.claim_contract_ref,
        "evidence_contract": recipe.evidence_contract_ref,
    }


def resolve_composition_semantic_path(
    registry: SemanticRegistry, projections: dict[str, dict[str, Any]], composition_id: str
) -> dict[str, Any]:
    plan_index = build_plan_artifact_index(registry)
    composition = next(
        (item for item in registry.composition_instances if item.id == composition_id), None
    )
    if composition is None:
        return {"id": composition_id, "composition_mapped": False}
    artifact = next(item for item in registry.plan_artifacts if item.id == composition.plan_artifact_ref)
    plan_details = plan_index["artifacts"].get(artifact.id, {})
    return {
        "id": composition.id,
        "composition_mapped": True,
        "is_recipe": False,
        "plan_artifact_id": artifact.id,
        "origin": composition.origin,
        "promotion_status": composition.promotion_status,
        "plan_integrity": plan_details,
        "capability_paths": [
            _binding_path_for_capability(registry, capability, projections)
            for capability in plan_details.get("capability_dependencies", [])
        ],
        "claim_contract": composition.claim_contract_ref,
        "evidence_contract": composition.evidence_contract_ref,
    }


def build_pilot_report(
    registry: SemanticRegistry, projections: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "high_bypass_completed_pass": resolve_recipe_semantic_path(
            registry, projections, "high_bypass_completed_pass_v1", "0.1.0"
        ),
        "ball_side_block_shift": resolve_recipe_semantic_path(
            registry, projections, "ball_side_block_shift_v1", "1.0.0"
        ),
        "validated_ai_composition": resolve_composition_semantic_path(
            registry, projections, "composition.ai_corridor_destination.2026_06_23"
        ),
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
            "plan_artifact_revision": build_plan_artifact_index(registry)[
                "plan_artifact_revision"
            ],
            "parsed_plan_artifacts": sum(
                1
                for item in build_plan_artifact_index(registry)["artifacts"].values()
                if item.get("valid_typed_plan")
            ),
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
        projection_differences=build_projection_differences(runtime_manifest, projections),
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
    plan_index = build_plan_artifact_index(registry)
    findings = validate_registry(registry, runtime_manifest, lock)
    projections = build_projections(registry, runtime_manifest, lock)
    findings.extend(validate_projection_identities(projections, lock))
    findings.extend(validate_projection_parity(registry, runtime_manifest, projections))
    report = build_parity_report(registry, runtime_manifest, lock, findings, projections)

    if write:
        if report.status == "PASS":
            write_targets = {
                SCHEMA_PATH: SemanticRegistry.model_json_schema(),
                output_root / "runtime-manifest.json": runtime_manifest,
                output_root / "plan-artifact-index.json": plan_index,
                LOCK_PATH: lock.model_dump(mode="json"),
                output_root / "product-projection.json": projections["product"],
                output_root / "ai-projection.json": projections["ai"],
                output_root / "recipe-library-projection.json": projections["recipe_library"],
                output_root / "unsupported-capability-projection.json": projections["unsupported"],
                output_root / "research-atlas-projection.json": projections["research_atlas"],
                output_root / "semantic-parity-report.json": report.model_dump(mode="json"),
            }
            with tempfile.TemporaryDirectory(prefix="scp0-generate-") as tmp_name:
                tmp_root = Path(tmp_name)
                staged: list[tuple[Path, Path]] = []
                for target, payload in write_targets.items():
                    staged_path = tmp_root / target
                    _write_json(staged_path, payload)
                    staged.append((staged_path, target))
                for staged_path, target in staged:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged_path), str(target))
    return registry, runtime_manifest, lock, report


def main() -> None:
    _, _, _, report = generate_scp0_artifacts(write=True)
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    if report.status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
