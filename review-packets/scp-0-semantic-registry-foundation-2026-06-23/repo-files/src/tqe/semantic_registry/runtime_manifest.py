"""Runtime manifest introspection for SCP-0.

This module deliberately derives executable facts from the current code instead
of restating them in the semantic registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import stable_hash
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
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        recipe = document["recipe"]
        draft_plan = document["draft_plan"]
        recipes.append(
            {
                "path": str(path),
                "recipe_id": recipe["recipe_id"],
                "recipe_version": recipe["recipe_version"],
                "display_name": recipe["display_name"],
                "plan_id": draft_plan["plan_id"],
                "plan_version": draft_plan["plan_version"],
                "status": draft_plan["status"],
                "node_catalog_refs": [
                    node["catalog_ref"]
                    for node in draft_plan["nodes"]
                    if node["kind"] in {"primitive", "relation"}
                ],
                "operator_refs": [
                    node["operator"]["name"]
                    for node in draft_plan["nodes"]
                    if node["kind"] == "predicate"
                ],
            }
        )

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
