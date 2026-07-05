"""SCP2-1 bridge from meaning expression to compiler-search target."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coverage_map import compiler_search_reachability as search
from tqe.runtime.binder import bind_document
from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.semantic_compiler.meaning_expression import (
    DEFAULT_KNOWLEDGE_PACK_PATH,
    MeaningExpressionV0,
    render_meaning_sentence,
    search_constraint_payload,
)


def synthesize_search_target(expression: MeaningExpressionV0) -> dict[str, Any]:
    declaration = derived_semantic_correspondence(expression)
    return {
        "target_id": expression.target.target_id,
        "concept": expression.concept_identity,
        "held_out": expression.target.held_out,
        "multi_step": expression.target.multi_step,
        "semantic_correspondence": declaration,
        "target_contract": target_contract_payload(expression),
    }


def derived_semantic_correspondence(expression: MeaningExpressionV0) -> dict[str, Any]:
    payload = {
        clause.name: _json_ready(clause.value)
        for clause in sorted(expression.correspondence_clauses, key=lambda item: item.name)
        if clause.name != "coverage_row"
    }
    payload["coverage_row"] = expression.concept_identity
    payload["meaning"] = render_meaning_sentence(expression)
    if expression.concept_refs:
        payload["concept_refs"] = list(expression.concept_refs)
    if expression.operator_applications:
        payload["operator_applications"] = [
            item.model_dump(mode="json", exclude_none=True)
            for item in expression.operator_applications
        ]
    return payload


def target_contract_payload(expression: MeaningExpressionV0) -> dict[str, Any]:
    contract = expression.target_contract
    payload = {
        "desired_output": contract.desired_output,
        "required_evidence": list(contract.required_evidence),
        "required_modalities": list(contract.required_modalities),
        "status_semantics": [
            item.model_dump(mode="json", exclude_none=True)
            for item in contract.status_semantics
        ],
        "composition_constraints": [
            search_constraint_payload(item) for item in contract.composition_constraints
        ],
        "claim_boundary": contract.claim_boundary,
    }
    return name_free_contract_payload(payload, concept_identity=expression.concept_identity)


def name_free_contract_payload(payload: dict[str, Any], *, concept_identity: str) -> dict[str, Any]:
    return _scrub_concept_identity(_json_ready(payload), concept_identity)


def validate_correspondence_with_r1c_guard(target: dict[str, Any]) -> dict[str, Any]:
    return search.validated_semantic_correspondence(
        row={"concept": target["concept"]},
        result={
            "target_id": target["target_id"],
            "concept": target["concept"],
            "semantic_correspondence": target.get("semantic_correspondence"),
        },
    )


def synthesize_and_bind(
    expression: MeaningExpressionV0,
    *,
    coverage_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    target = synthesize_search_target(expression)
    validate_correspondence_with_r1c_guard(target)
    row = _coverage_row_or_synthetic(target["concept"], coverage_rows)
    failed_gate = search.target_certification_gate_result(target=target, row=row)
    if failed_gate is not None:
        raise search.SynthesisError(
            str(failed_gate.get("failure_taxonomy") or "certification_gate"),
            str(failed_gate.get("message") or "target failed certification gate"),
            dict(failed_gate.get("failure_details") or {}),
        )
    recipe_plan = exact_recipe_plan_for_expression(expression)
    if recipe_plan is not None:
        recipe_id, source_path, document = recipe_plan
        document_payload = document_payload_for_expression(
            expression=expression,
            document=document,
            default_invocation=document.get("default_invocation") or {},
            preserve_default_invocation=True,
        )
        bind_payload = bind_payload_for_document(document_payload)
        return {
            "target": target,
            "build": {
                "providers_used": [f"recipe:{recipe_id}"],
                "rules_used": ["generated_exact_typed_plan_ref"],
                "terminal_provider": f"recipe:{recipe_id}",
                "build_metadata": {
                    "recipe_id": recipe_id,
                    "source_path": str(source_path),
                },
                "field_sources": {},
            },
            "document": document_payload,
            "document_hash": stable_hash(document_payload),
            "bind": bind_payload,
        }
    primitive_build = synthesize_single_provider_without_model_composition(
        expression=expression,
        target=target,
        row=row,
        context=search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        ),
    )
    if primitive_build is not None:
        document_payload = document_payload_for_expression(
            expression=expression,
            document=primitive_build["document"],
            target_id_override=primitive_build.get("canonical_target_id"),
        )
        bind_payload = bind_payload_for_document(document_payload)
        return {
            "target": {
                **target,
                "target_contract": primitive_build["target_contract"],
            },
            "build": {
                key: _json_ready(value)
                for key, value in primitive_build.items()
                if key not in {"document", "target_contract"}
            },
            "document": document_payload,
            "document_hash": stable_hash(document_payload),
            "bind": bind_payload,
        }
    build = search.synthesize_by_search(
        target=target,
        row=row,
        context=search.SearchContext(
            catalog=search.CatalogIndex(),
            target_contract=target["target_contract"],
        ),
    )
    document_payload = document_payload_for_expression(
        expression=expression,
        document=build["document"],
    )
    bind_payload = bind_payload_for_document(document_payload)
    return {
        "target": target,
        "build": {
            key: _json_ready(value)
            for key, value in build.items()
            if key != "document"
        },
        "document": document_payload,
        "document_hash": stable_hash(document_payload),
        "bind": bind_payload,
    }


def synthesize_single_provider_without_model_composition(
    *,
    expression: MeaningExpressionV0,
    target: dict[str, Any],
    row: dict[str, Any],
    context: search.SearchContext,
) -> dict[str, Any] | None:
    concept_refs = set(expression.concept_refs)
    identity_values = {
        expression.concept_identity,
        expression.expression_id,
        expression.target.target_id,
    }
    has_model_composition = bool(expression.operator_applications or expression.target_contract.composition_constraints)
    has_provider_family_variant = any(
        value != ref and recipe_family_candidate_matches(ref, value)
        for ref in concept_refs
        for value in identity_values
    )
    if not has_model_composition and not has_provider_family_variant:
        return None
    stripped_contract = {
        **context.target_contract,
        "composition_constraints": [],
    }
    required_fields = search.required_target_fields(stripped_contract)
    providers = context.catalog.providers_for_fields(required_fields)
    if not providers:
        return None
    provider = next((entry for entry in providers if entry.name in concept_refs), providers[0])
    if has_provider_family_variant:
        stripped_contract = {
            **stripped_contract,
            "required_evidence": sorted(provider_requested_evidence_fields(provider)),
            "claim_boundary": f"Observed {provider.name} evidence only.",
        }
    canonical_target_id = f"{provider.name}_v0"
    stripped_target = {
        **target,
        "target_id": canonical_target_id,
        "concept": provider.name,
        "target_contract": stripped_contract,
    }
    stripped_context = search.SearchContext(
        catalog=context.catalog,
        target_contract=stripped_contract,
    )
    build = search.synthesize_by_search(target=stripped_target, row=row, context=stripped_context)
    if build.get("terminal_provider") != provider.name and provider.name in concept_refs:
        return None
    build["rules_used"] = sorted({*build.get("rules_used", []), "single_provider_composition_elision"})
    build["target_contract"] = stripped_contract
    build["canonical_target_id"] = canonical_target_id
    return build


def provider_requested_evidence_fields(provider: Any) -> set[str]:
    fields = set(provider.evidence_fields)
    for output in provider.outputs:
        fields.update(output.evidence_fields)
    return fields


def exact_recipe_plan_for_expression(
    expression: MeaningExpressionV0,
    *,
    pack_path: Path = DEFAULT_KNOWLEDGE_PACK_PATH,
) -> tuple[str, Path, dict[str, Any]] | None:
    candidates = recipe_identity_candidates(expression)
    if not candidates or not pack_path.exists():
        return None
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    for recipe in pack.get("recipes") or []:
        recipe_id = str(recipe.get("recipe_id") or "")
        if not recipe_id:
            continue
        base_id = recipe_base_id(recipe_id)
        if recipe_id not in candidates and not any(
            recipe_family_candidate_matches(base_id, candidate)
            for candidate in candidates
        ):
            continue
        source = recipe.get("exact_typed_plan_ref") or recipe.get("source_path")
        if not source:
            continue
        source_path = Path(str(source))
        if not source_path.exists():
            continue
        return recipe_id, source_path, json.loads(source_path.read_text(encoding="utf-8"))
    return None


def recipe_identity_candidates(expression: MeaningExpressionV0) -> set[str]:
    raw: set[str] = {expression.concept_identity, expression.target.target_id}
    for clause in expression.correspondence_clauses:
        if clause.name in {"recipe_id", "recipe"} and isinstance(clause.value, str):
            raw.add(clause.value)
    candidates: set[str] = set()
    for value in raw:
        normalized = value.strip()
        if not normalized:
            continue
        base = recipe_base_id(normalized)
        candidates.update({normalized, base, f"{base}_v1"})
    return candidates


def recipe_base_id(value: str) -> str:
    return re.sub(r"_v\d+$", "", re.sub(r"_v\d+_\d+$", "", value))


def recipe_family_candidate_matches(base_id: str, candidate: str) -> bool:
    if candidate == base_id or candidate.startswith(f"{base_id}_"):
        return True
    base_parts = base_id.split("_")
    candidate_parts = candidate.split("_")
    cursor = 0
    for part in candidate_parts:
        if cursor < len(base_parts) and part == base_parts[cursor]:
            cursor += 1
    return cursor == len(base_parts)


def document_payload_for_expression(
    *,
    expression: MeaningExpressionV0,
    document: dict[str, Any],
    default_invocation: dict[str, Any] | None = None,
    preserve_default_invocation: bool = False,
    target_id_override: str | None = None,
) -> dict[str, Any]:
    defaults = default_invocation or {}
    if preserve_default_invocation:
        match_ids = list(defaults.get("match_ids") or search.MATCH_IDS)
        periods = list(defaults.get("periods") or ["firstHalf", "secondHalf"])
        roles = [str(defaults.get("perspective_team_role") or "home")]
    else:
        match_ids = expression.population.match_ids or list(defaults.get("match_ids") or search.MATCH_IDS)
        periods = expression.population.periods or list(defaults.get("periods") or ["firstHalf", "secondHalf"])
        roles = expression.population.perspective_team_roles or [str(defaults.get("perspective_team_role") or "home")]
    role_documents: dict[str, dict[str, Any]] = {}
    for role in roles:
        role_doc = copy.deepcopy(document)
        invocation = role_doc["default_invocation"]
        invocation["match_ids"] = list(match_ids)
        invocation["periods"] = list(periods)
        invocation["perspective_team_role"] = role
        if len(roles) > 1:
            target_id = target_id_override or expression.target.target_id
            invocation["invocation_id"] = f"{target_id}_{role}_probe"
        role_documents[role] = role_doc
    if len(roles) == 1:
        return next(iter(role_documents.values()))
    return {
        "schema_version": "compiler_search_perspective_bundle.v1",
        "target_id": target_id_override or expression.target.target_id,
        "perspective_team_roles": list(roles),
        "documents": role_documents,
    }


def bind_payload_for_document(document_payload: dict[str, Any]) -> dict[str, Any]:
    if document_payload.get("schema_version") == "compiler_search_perspective_bundle.v1":
        roles: dict[str, Any] = {}
        for role, document in sorted(document_payload["documents"].items()):
            bound = bind_document(TacticalQueryDocument.model_validate(document))
            roles[role] = {
                "plan_hash": bound.plan_hash,
                "bound_plan_hash": bound.bound_plan_hash,
            }
        return {
            "status": "PASS",
            "roles": roles,
            "bundle_hash": stable_hash(document_payload),
        }
    bound = bind_document(TacticalQueryDocument.model_validate(document_payload))
    return {
        "status": "PASS",
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
    }


def target_file_payload(targets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "compiler_search_targets.v0",
        "strategy": "scp2_1.meaning_expression_to_target.v0",
        "sample_policy": "scp2_1_roundtrip_fixtures",
        "note": (
            "Generated from SCP2-1 meaning expressions. Coverage concepts are "
            "correspondence labels only; bridge code never writes the ledger."
        ),
        "targets": targets,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _coverage_row_or_synthetic(
    concept: str,
    coverage_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows = coverage_rows or []
    for row in rows:
        if row.get("concept") == concept:
            return row
    return {
        "concept": concept,
        "classification": "supported",
        "composition_maturity": "bridge_query",
        "composition_maturity_applicable": True,
    }


def _json_ready(payload: Any) -> Any:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json", exclude_none=True)
    if isinstance(payload, dict):
        return {str(key): _json_ready(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_json_ready(value) for value in payload]
    if isinstance(payload, tuple):
        return [_json_ready(value) for value in payload]
    return payload


def _scrub_concept_identity(value: Any, concept_identity: str) -> Any:
    if isinstance(value, dict):
        return {str(key): _scrub_concept_identity(child, concept_identity) for key, child in value.items()}
    if isinstance(value, list):
        return [_scrub_concept_identity(child, concept_identity) for child in value]
    if isinstance(value, str):
        return _name_free_string(value, concept_identity)
    return value


def _name_free_string(value: str, concept_identity: str) -> str:
    if not concept_identity:
        return value
    pattern = re.compile(re.escape(concept_identity), flags=re.IGNORECASE)
    cleaned = pattern.sub("requested_pattern", value)
    return " ".join(cleaned.split())
