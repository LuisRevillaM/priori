"""Runtime manifest introspection for SCP-0.

This module deliberately derives executable facts from the current code instead
of restating them in the semantic registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.workshop.m1_2 import NON_AUTHORABLE_CATALOG_REFS, RECIPE_PLAN_PATHS


GENERATOR_VERSION = "scp0.generator.v1"


def _json_ready(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _dedupe_preserve(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _typed_value_payload(value: Any) -> Any:
    if isinstance(value, dict) and value.get("kind") == "parameter":
        return {"parameter_ref": value["name"]}
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def plan_manifest_payload(path: Path) -> dict[str, Any]:
    document_payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    document = TacticalQueryDocument.model_validate(document_payload)
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
        item.name: _typed_value_payload(
            item.default.model_dump(mode="json", exclude_none=True) if item.default else None
        )
        for item in document.recipe.parameters
    }

    return {
        "path": str(path),
        "recipe_id": document.recipe.recipe_id,
        "recipe_version": document.recipe.recipe_version,
        "display_name": document.recipe.display_name,
        "plan_id": document.draft_plan.plan_id,
        "plan_version": document.draft_plan.plan_version,
        "status": document.draft_plan.status.value,
        "normalized_plan_hash": stable_hash(normalized_document),
        "node_catalog_refs": _dedupe_preserve(
            [item["name"] for item in capability_dependencies]
        ),
        "operator_refs": _dedupe_preserve([item["name"] for item in operator_dependencies]),
        "capability_dependencies": _dedupe_preserve(capability_dependencies),
        "operator_dependencies": _dedupe_preserve(operator_dependencies),
        "parameter_defaults": parameter_defaults,
        "referenced_parameters": sorted(referenced_parameters),
    }


def generate_runtime_manifest() -> dict[str, Any]:
    catalog = default_catalog()
    capabilities: list[dict[str, Any]] = []

    for entry in [*catalog.primitives, *catalog.relations]:
        payload = entry.model_dump(mode="json", exclude_none=True)
        payload["runtime_id"] = f"{entry.kind.value}:{entry.name}:{entry.version}"
        payload["ai_authorable_by_runtime_context"] = entry.name not in NON_AUTHORABLE_CATALOG_REFS
        capabilities.append(payload)

    operators = [
        item.model_dump(mode="json", exclude_none=True)
        | {"runtime_id": f"operator:{item.name}:{item.version}"}
        for item in catalog.operators
    ]

    recipes: list[dict[str, Any]] = []
    for path in RECIPE_PLAN_PATHS:
        recipes.append(plan_manifest_payload(Path(path)))

    manifest = {
        "schema_version": "1.0",
        "manifest_id": "priori.runtime_manifest.scp0",
        "generator_version": GENERATOR_VERSION,
        "capabilities": sorted(capabilities, key=lambda item: item["runtime_id"]),
        "operators": sorted(operators, key=lambda item: item["runtime_id"]),
        "recipes": sorted(recipes, key=lambda item: (item["recipe_id"], item["recipe_version"])),
        "non_authorable_catalog_refs": sorted(NON_AUTHORABLE_CATALOG_REFS),
        "default_complexity_limits": catalog.default_complexity_limits.model_dump(
            mode="json", exclude_none=True
        ),
    }
    manifest["runtime_manifest_revision"] = stable_hash(manifest)
    return manifest


def runtime_capability_keys(manifest: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (item["kind"], item["name"], item["version"])
        for item in manifest.get("capabilities", [])
    }


def runtime_operator_keys(manifest: dict[str, Any]) -> set[tuple[str, str]]:
    return {(item["name"], item["version"]) for item in manifest.get("operators", [])}
