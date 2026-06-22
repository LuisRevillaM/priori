"""Generate the M1.2 S2I Tactical Knowledge Pack."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import stable_hash
from tqe.workshop.hermes_s2 import (
    CLARIFICATION_DISTANCE_THRESHOLD,
    CLARIFICATION_SUPPORT_DEFINITION,
    CLARIFICATION_TIME_WINDOW,
    GAP_BODY_ORIENTATION,
    GAP_BODY_SHAPE,
    GAP_COACH_INSTRUCTIONS,
    GAP_COMMUNICATION,
    GAP_CONFIRMATION_BYPASS,
    GAP_DECEPTION,
    GAP_DIRECT_EXECUTION,
    GAP_FACIAL_CUES,
    GAP_OPTIMALITY,
    GAP_PASS_PROBABILITY,
    GAP_PLAYER_INTENT,
    GAP_PRIMITIVE_MUTATION,
    GAP_SCANNING,
    GAP_VIDEO,
    compiler_classification_rules,
)
from tqe.workshop.m1_2 import (
    APPROVED_TOOL_NAMES,
    CAPABILITY_CONTEXT_PATH,
    FORBIDDEN_SURFACES,
    HERMES_S2_TOOL_NAMES,
    MANUAL_ONLY_TOOL_NAMES,
    CallerProfile,
    describe_capability,
    list_capabilities,
    tool_spec,
    utc_now_iso,
    write_json,
)


PACK_JSON_PATH = Path("generated/tactical-knowledge-pack.json")
PACK_MD_PATH = Path("generated/tactical-knowledge-pack.md")
QUERY_PLAN_SCHEMA_PATH = Path("generated/tactical-query-plan.schema.json")
QUERY_PLAN_TYPES_PATH = Path("generated/tactical-query-plan.types.ts")
RECIPE_PLAN_PATHS = [
    Path("config/query-plans/ball_side_block_shift.ir.v1.json"),
    Path("config/query-plans/possession_corridor_availability.experimental.v1.json"),
    Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json"),
]
SOURCE_PATHS = [
    Path("Makefile"),
    Path("src/tqe/runtime/catalog.py"),
    Path("src/tqe/runtime/ir.py"),
    Path("src/tqe/runtime/binder.py"),
    Path("src/tqe/runtime/executor.py"),
    Path("src/tqe/runtime/relations.py"),
    Path("src/tqe/workshop/m1_2.py"),
    Path("src/tqe/workshop/hermes_s2.py"),
    Path("src/tqe/workshop/knowledge_pack.py"),
    Path("src/tqe/verification/m1_2_gate_s2i.py"),
    QUERY_PLAN_SCHEMA_PATH,
    QUERY_PLAN_TYPES_PATH,
    CAPABILITY_CONTEXT_PATH,
    *RECIPE_PLAN_PATHS,
]
S2I_HERMES_MCP_TOOL_NAMES = [
    "list_capabilities",
    "search_recipes",
    "describe_capability",
    "submit_query_plan",
    "validate_query_plan",
    "inspect_result",
    "inspect_non_match",
    "retrieve_replay_window",
]
S2I_HOST_ONLY_TOOL_NAMES = [
    "host_confirm_bound_plan",
    "execute_query_plan",
    "record_feedback",
    "compare_query_versions",
    "save_experimental_recipe",
]


def build_tactical_knowledge_pack() -> dict[str, Any]:
    capability_context = list_capabilities(CallerProfile.HERMES_S2).model_dump(mode="json")
    catalog = default_catalog()
    recipes = [recipe_summary(path) for path in RECIPE_PLAN_PATHS]
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "knowledge_pack_version": "m1.2-s2i-a.0",
        "generated_at": "reproducible_from_source_hashes",
        "pack_identity": {
            "milestone": "M1.2",
            "slice": "S2I-A Tactical Knowledge Pack",
            "purpose": "Authoritative generated knowledge context for Hermes/frontier agents and human inspection.",
        },
        "source_hashes": source_hashes(SOURCE_PATHS),
        "architecture_posture": {
            "product_path": "Hermes/frontier model authors or selects typed tactical plans; deterministic host validates, confirms, executes, and serves replay.",
            "mcp_role": "Thin Hermes adapter over the host-owned application service; not a runtime, database, or permission layer.",
            "initial_mcp_transport": "local stdio",
            "future_mcp_transport": "streamable HTTP or remote MCP after the local product path works",
            "host_service_authority": [
                "validation and binding",
                "human confirmation",
                "execution",
                "handle persistence",
                "result, trace, evidence, and replay retrieval",
                "caller-profile enforcement",
            ],
            "deterministic_engine_authority": [
                "measure canonical match data",
                "emit PASS/FAIL/UNKNOWN predicate states",
                "produce evidence and provenance",
            ],
            "agent_authority": [
                "interpret football language",
                "search or describe recipes and capabilities",
                "select trusted recipes",
                "draft experimental typed plans",
                "ask clarification questions",
                "explain structured capability gaps",
            ],
        },
        "tool_surfaces": tool_surfaces(),
        "recipes": recipes,
        "primitives": [entry.model_dump(mode="json", exclude_none=True) for entry in catalog.primitives],
        "relations": [entry.model_dump(mode="json", exclude_none=True) for entry in catalog.relations],
        "operators": [operator.model_dump(mode="json", exclude_none=True) for operator in catalog.operators],
        "safe_composition_rules": capability_context["safe_operator_source_rules"],
        "complexity_limits": {
            "default": capability_context["default_complexity_limits"],
            "host_owned_ceilings": capability_context["host_owned_complexity_ceilings"],
        },
        "evidence_fields": capability_context["evidence_fields"],
        "ambiguity_dimensions": [
            {
                "code": CLARIFICATION_SUPPORT_DEFINITION,
                "label": "support",
                "description": "Clarify what support means: corridor, nearby teammate, receiving option, lane occupation, or another definition.",
            },
            {
                "code": CLARIFICATION_TIME_WINDOW,
                "label": "time window",
                "description": "Clarify when support must arrive relative to possession, carry, pass, or line break.",
            },
            {
                "code": CLARIFICATION_DISTANCE_THRESHOLD,
                "label": "distance threshold",
                "description": "Clarify proximity language with an explicit distance threshold.",
            },
        ],
        "capability_gap_codes": capability_gap_codes(),
        "claims_policy": claims_policy(recipes),
        "query_plan_schema": {
            "schema_path": str(QUERY_PLAN_SCHEMA_PATH),
            "schema_sha256": file_sha256(QUERY_PLAN_SCHEMA_PATH),
            "schema": read_json(QUERY_PLAN_SCHEMA_PATH),
        },
        "model_visible_tool_schemas": model_visible_tool_schemas(),
        "compiler_classification_rules": compiler_classification_rules(),
        "reference_harness": {
            "baseline_commit": "f9eb5d8",
            "model": "gpt-4o-mini",
            "role": "reference compiler harness, fallback, and evaluation control; not the target meeting runtime",
            "current_reference_harness_tools": HERMES_S2_TOOL_NAMES,
        },
    }
    base["knowledge_pack_sha256"] = stable_hash({k: v for k, v in base.items() if k != "knowledge_pack_sha256"})
    return base


def write_tactical_knowledge_pack(
    json_path: Path = PACK_JSON_PATH,
    md_path: Path = PACK_MD_PATH,
) -> dict[str, Any]:
    pack = build_tactical_knowledge_pack()
    write_json(json_path, pack)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(pack), encoding="utf-8")
    return pack


def source_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_sha256(path) for path in paths if path.exists()}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def recipe_summary(path: Path) -> dict[str, Any]:
    document = read_json(path)
    recipe = document["recipe"]
    state = "APPROVED" if recipe["recipe_id"] == "ball_side_block_shift_v1" else "EXPERIMENTAL"
    draft_plan = document["draft_plan"]
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "state": state,
        "source_path": str(path),
        "source_sha256": file_sha256(path),
        "display_name": recipe["display_name"],
        "description": recipe["description"],
        "allowed_claims": recipe.get("allowed_claims", []),
        "disallowed_claims": recipe.get("disallowed_claims", []),
        "limitations": recipe.get("limitations", []),
        "parameters": recipe.get("parameters", []),
        "output_classifications": recipe.get("output_classifications", []),
        "default_invocation": document.get("default_invocation", {}),
        "plan_summary": {
            "plan_id": draft_plan["plan_id"],
            "plan_version": draft_plan["plan_version"],
            "status": draft_plan["status"],
            "unknown_evidence_policy": draft_plan["unknown_evidence_policy"],
            "classification_mode": draft_plan["classification_mode"],
            "node_count": len(draft_plan.get("nodes", [])),
            "nodes": [
                {
                    "node_id": node["node_id"],
                    "kind": node["kind"],
                    "catalog_ref": node.get("catalog_ref"),
                    "operator": node.get("operator"),
                    "inputs": node.get("inputs", {}),
                    "input": node.get("input"),
                }
                for node in draft_plan.get("nodes", [])
            ],
            "classification_rules": draft_plan.get("classification_rules", []),
            "requested_evidence": draft_plan.get("requested_evidence", []),
        },
    }


def tool_surfaces() -> dict[str, Any]:
    return {
        "current_reference_harness_model_visible": {
            "description": "Existing S2 reference harness surface kept stable for regression tests.",
            "tools": HERMES_S2_TOOL_NAMES,
        },
        "s2i_target_hermes_mcp": {
            "description": "Target Hermes product-path allowlist. Execution and confirmation stay host-owned.",
            "transport": "local stdio first; remote MCP later only if needed",
            "tools": S2I_HERMES_MCP_TOOL_NAMES,
            "explicitly_not_exposed": S2I_HOST_ONLY_TOOL_NAMES + ["raw files", "raw coordinate dumps", "Python", "SQL"],
        },
        "host_only": {
            "tools": S2I_HOST_ONLY_TOOL_NAMES,
            "current_manual_tools": MANUAL_ONLY_TOOL_NAMES,
            "reference_harness_all_tools": APPROVED_TOOL_NAMES,
        },
        "forbidden_surfaces": FORBIDDEN_SURFACES,
    }


def model_visible_tool_schemas() -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    for name in sorted(set(HERMES_S2_TOOL_NAMES + MANUAL_ONLY_TOOL_NAMES)):
        spec = tool_spec(name).model_dump(mode="json")
        schemas[name] = {
            "status": "implemented_reference_harness_tool",
            "description": spec["description"],
            "input_schema": spec["input_schema"],
            "output_schema": spec["output_schema"],
            "reference_exposure": spec["exposure"],
            "s2i_target_exposure": "hermes_mcp" if name in S2I_HERMES_MCP_TOOL_NAMES else "host_only",
        }
    schemas["search_recipes"] = {
        "status": "planned_s2i_mcp_tool",
        "description": "Search generated recipe summaries by text query and optional recipe state.",
        "s2i_target_exposure": "hermes_mcp",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "states": {
                    "type": "array",
                    "items": {"enum": ["APPROVED", "USER_SAVED", "EXPERIMENTAL", "DEPRECATED"]},
                    "default": ["APPROVED", "EXPERIMENTAL"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ok": {"const": True},
                "recipes": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["ok", "recipes"],
        },
    }
    return {name: schemas[name] for name in S2I_HERMES_MCP_TOOL_NAMES + sorted(set(schemas) - set(S2I_HERMES_MCP_TOOL_NAMES))}


def capability_gap_codes() -> list[dict[str, str]]:
    return [
        {"code": GAP_PRIMITIVE_MUTATION, "label": "primitive mutation", "description": "Request would alter primitive or relation definitions."},
        {"code": GAP_CONFIRMATION_BYPASS, "label": "confirmation bypass", "description": "Request bypasses host-owned confirmation."},
        {"code": GAP_DIRECT_EXECUTION, "label": "direct execution", "description": "Request asks the agent to execute directly."},
        {"code": GAP_PLAYER_INTENT, "label": "player intent", "description": "Tracking data cannot prove player intent."},
        {"code": GAP_BODY_ORIENTATION, "label": "body orientation", "description": "No body-orientation primitive is available."},
        {"code": GAP_SCANNING, "label": "scanning", "description": "No head-check or scanning primitive is available."},
        {"code": GAP_PASS_PROBABILITY, "label": "pass probability", "description": "Pass-probability modelling is not available."},
        {"code": GAP_OPTIMALITY, "label": "optimality", "description": "Optimal decision claims are out of scope."},
        {"code": GAP_COMMUNICATION, "label": "communication", "description": "Communication is not represented in tracking data."},
        {"code": GAP_VIDEO, "label": "video", "description": "Video is outside the current data boundary."},
        {"code": GAP_BODY_SHAPE, "label": "body shape", "description": "No body-shape primitive is available."},
        {"code": GAP_DECEPTION, "label": "deception", "description": "Deception is not observable in current deterministic vocabulary."},
        {"code": GAP_COACH_INSTRUCTIONS, "label": "coach instructions", "description": "Coach instruction evidence is unavailable."},
        {"code": GAP_FACIAL_CUES, "label": "facial cues", "description": "Facial cues are unavailable without video/perception."},
    ]


def claims_policy(recipes: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = sorted({claim for recipe in recipes for claim in recipe["allowed_claims"]})
    disallowed = sorted({claim for recipe in recipes for claim in recipe["disallowed_claims"]})
    return {
        "allowed_claims_from_recipes": allowed,
        "disallowed_claims_from_recipes": disallowed,
        "global_allowed_claims": [
            "The system can report deterministic measurements present in returned traces and evidence.",
            "The system can say a typed plan matched or did not match according to PASS/FAIL/UNKNOWN semantics.",
            "The system can show coordinate replay from canonical IDSSE/DFL tracking data.",
        ],
        "global_disallowed_claims": [
            "The model measured the match.",
            "The system inferred player intent, body orientation, scanning, deception, or optimality.",
            "The result is backed by match video.",
            "The agent executed or confirmed a query without host authorization.",
            "Unsupported concepts were approximated silently.",
        ],
    }


def render_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# Tactical Knowledge Pack",
        "",
        f"Version: `{pack['knowledge_pack_version']}`",
        f"SHA-256: `{pack['knowledge_pack_sha256']}`",
        f"Generated: `{pack['generated_at']}`",
        "",
        "## Architecture",
        "",
        pack["architecture_posture"]["product_path"],
        "",
        f"MCP role: {pack['architecture_posture']['mcp_role']}",
        f"Initial MCP transport: `{pack['architecture_posture']['initial_mcp_transport']}`",
        "",
        "## S2I Hermes MCP Tool Allowlist",
        "",
    ]
    lines.extend(f"- `{tool}`" for tool in pack["tool_surfaces"]["s2i_target_hermes_mcp"]["tools"])
    lines.extend(["", "Host-only tools:", ""])
    lines.extend(f"- `{tool}`" for tool in pack["tool_surfaces"]["host_only"]["tools"])
    lines.extend(["", "## Recipes", ""])
    for recipe in pack["recipes"]:
        lines.extend(
            [
                f"### {recipe['display_name']} (`{recipe['recipe_id']}`)",
                "",
                f"State: `{recipe['state']}`",
                "",
                recipe["description"],
                "",
                "Allowed claims:",
                "",
                *[f"- {claim}" for claim in recipe["allowed_claims"]],
                "",
                "Disallowed claims:",
                "",
                *[f"- {claim}" for claim in recipe["disallowed_claims"]],
                "",
            ]
        )
    lines.extend(["## Ambiguity Dimensions", ""])
    lines.extend(f"- `{item['code']}`: {item['description']}" for item in pack["ambiguity_dimensions"])
    lines.extend(["", "## Capability Gap Codes", ""])
    lines.extend(f"- `{item['code']}`: {item['description']}" for item in pack["capability_gap_codes"])
    lines.extend(["", "## Source Hashes", ""])
    lines.extend(f"- `{path}`: `{sha}`" for path, sha in sorted(pack["source_hashes"].items()))
    lines.append("")
    return "\n".join(lines)


def verify_tactical_knowledge_pack(
    json_path: Path = PACK_JSON_PATH,
    md_path: Path = PACK_MD_PATH,
) -> list[dict[str, Any]]:
    checks = []
    pack = read_json(json_path)
    expected_hash = stable_hash({k: v for k, v in pack.items() if k != "knowledge_pack_sha256"})
    checks.append(check("pack.hash.matches_content", pack.get("knowledge_pack_sha256") == expected_hash, {"expected": expected_hash, "actual": pack.get("knowledge_pack_sha256")}))
    checks.append(check("pack.markdown.exists", md_path.exists(), {"path": str(md_path)}))
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    checks.append(check("pack.markdown.references_hash", pack.get("knowledge_pack_sha256", "") in markdown, {}))
    recipe_ids = {recipe["recipe_id"] for recipe in pack.get("recipes", [])}
    checks.append(check("pack.recipes.include_approved_m1", "ball_side_block_shift_v1" in recipe_ids, {"recipe_ids": sorted(recipe_ids)}))
    checks.append(check("pack.recipes.include_corridor", "possession_corridor_availability_v1" in recipe_ids, {"recipe_ids": sorted(recipe_ids)}))
    target_tools = set(pack["tool_surfaces"]["s2i_target_hermes_mcp"]["tools"])
    checks.append(check("pack.tools.include_search_recipes", "search_recipes" in target_tools, {"tools": sorted(target_tools)}))
    checks.append(check("pack.tools.exclude_execute_from_hermes_mcp", "execute_query_plan" not in target_tools, {"tools": sorted(target_tools)}))
    host_tools = set(pack["tool_surfaces"]["host_only"]["tools"])
    checks.append(check("pack.tools.host_owns_execution", {"host_confirm_bound_plan", "execute_query_plan"}.issubset(host_tools), {"host_tools": sorted(host_tools)}))
    gap_codes = {item["code"] for item in pack.get("capability_gap_codes", [])}
    checks.append(check("pack.gaps.include_safety_codes", {GAP_PRIMITIVE_MUTATION, GAP_CONFIRMATION_BYPASS, GAP_DIRECT_EXECUTION}.issubset(gap_codes), {"gap_codes": sorted(gap_codes)}))
    dimensions = {item["code"] for item in pack.get("ambiguity_dimensions", [])}
    checks.append(check("pack.ambiguity.include_required_dimensions", {CLARIFICATION_SUPPORT_DEFINITION, CLARIFICATION_TIME_WINDOW, CLARIFICATION_DISTANCE_THRESHOLD}.issubset(dimensions), {"dimensions": sorted(dimensions)}))
    checks.append(check("pack.schema.embedded", bool(pack.get("query_plan_schema", {}).get("schema")), {}))
    checks.append(check("pack.source_hashes.present", len(pack.get("source_hashes", {})) >= 8, {"count": len(pack.get("source_hashes", {}))}))
    return checks


def check(name: str, ok: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def main() -> None:
    pack = write_tactical_knowledge_pack()
    checks = verify_tactical_knowledge_pack()
    report = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "knowledge_pack_path": str(PACK_JSON_PATH),
        "knowledge_pack_markdown_path": str(PACK_MD_PATH),
        "knowledge_pack_sha256": pack["knowledge_pack_sha256"],
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
    }
    write_json(Path("artifacts/m1.2/s2i-knowledge-pack-report.json"), report)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
