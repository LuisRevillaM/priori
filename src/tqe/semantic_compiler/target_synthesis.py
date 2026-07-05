"""SCP2-1 bridge from meaning expression to compiler-search target."""

from __future__ import annotations

import copy
import json
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
from tqe.semantic_compiler.meaning_expression import MeaningExpressionV0


class LedgerWriteForbiddenError(RuntimeError):
    """Bridge code answers questions but never mutates coverage rows."""


def update_coverage_rows(*_args: Any, **_kwargs: Any) -> None:
    raise LedgerWriteForbiddenError("SCP2 bridge code has no reachable ledger write path.")


def synthesize_search_target(expression: MeaningExpressionV0) -> dict[str, Any]:
    declaration = derived_semantic_correspondence(expression)
    return {
        "target_id": expression.target.target_id,
        "concept": expression.concept_identity,
        "held_out": expression.target.held_out,
        "multi_step": expression.target.multi_step,
        "semantic_correspondence": declaration,
        "target_contract": expression.target_contract.model_dump(mode="json", exclude_none=True),
    }


def derived_semantic_correspondence(expression: MeaningExpressionV0) -> dict[str, Any]:
    payload = {
        key: _json_ready(value)
        for key, value in sorted(expression.correspondence.items())
        if key != "coverage_row"
    }
    payload["coverage_row"] = expression.concept_identity
    payload["meaning"] = expression.meaning
    if expression.concept_refs:
        payload["concept_refs"] = list(expression.concept_refs)
    if expression.operator_applications:
        payload["operator_applications"] = [
            item.model_dump(mode="json", exclude_none=True)
            for item in expression.operator_applications
        ]
    return payload


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


def document_payload_for_expression(
    *,
    expression: MeaningExpressionV0,
    document: dict[str, Any],
) -> dict[str, Any]:
    match_ids = expression.population.match_ids or list(search.MATCH_IDS)
    periods = expression.population.periods
    roles = expression.population.perspective_team_roles or ["home"]
    role_documents: dict[str, dict[str, Any]] = {}
    for role in roles:
        role_doc = copy.deepcopy(document)
        invocation = role_doc["default_invocation"]
        invocation["match_ids"] = list(match_ids)
        invocation["periods"] = list(periods)
        invocation["perspective_team_role"] = role
        if len(roles) > 1:
            invocation["invocation_id"] = f"{expression.target.target_id}_{role}_probe"
        role_documents[role] = role_doc
    if len(roles) == 1:
        return next(iter(role_documents.values()))
    return {
        "schema_version": "compiler_search_perspective_bundle.v1",
        "target_id": expression.target.target_id,
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
