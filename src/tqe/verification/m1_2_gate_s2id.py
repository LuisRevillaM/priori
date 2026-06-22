"""Verify M1.2 S2I-D: unseeded Hermes frontier-agent plan authoring."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from tqe.workshop.knowledge_pack import S2I_HERMES_MCP_TOOL_NAMES, S2I_HOST_ONLY_TOOL_NAMES, write_json
from tqe.workshop.m1_2 import utc_now_iso

REPORT_PATH = Path("artifacts/m1.2/s2i-d-unseeded-hermes-report.json")
WORKSHOP_ROOT = Path("artifacts/m1.2/workshop")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
HERMES_DB = HERMES_HOME / "state.db"
HERMES_CONFIG_PATH = HERMES_HOME / "config.yaml"
KNOWLEDGE_PACK_PATH = Path("generated/tactical-knowledge-pack.json")
MCP_SERVER_PATH = Path("src/tqe/workshop/mcp_server.py")

LIVE_RUNS = [
    {
        "label": "any_progressive_corridor",
        "session_id": "20260621_220512_1d38ec",
        "request": "Find possession anchors with any progressive corridor.",
        "draft_plan_id": "draft_496efd224daf3c31",
        "bound_plan_id": "bound_2179b7a023359695",
        "bound_plan_hash": "2179b7a0233596959d5122e17110cdc541bb79115d66b9676e012d2a1ff92336",
        "expected_parameters": {
            "minimum_progression_m": 5.0,
            "minimum_duration_seconds": 0.4,
        },
    },
    {
        "label": "twelve_metres_open_point_eight_seconds",
        "session_id": "20260621_221026_2eacf0",
        "request": "Find corridors progressing at least 12 metres, remaining open for 0.8 seconds.",
        "draft_plan_id": "draft_4f4a534a0b4fd356",
        "bound_plan_id": "bound_a622811f41c9f5d0",
        "bound_plan_hash": "a622811f41c9f5d04b8f666e5d8b819164935523cbec1d1b470fd0f012777fd2",
        "expected_parameters": {
            "minimum_progression_m": 12.0,
            "minimum_duration_seconds": 0.8,
        },
    },
]

ALLOWED_HERMES_TOOL_NAMES = {f"mcp_priori_tactical_{name}" for name in S2I_HERMES_MCP_TOOL_NAMES}
FORBIDDEN_TOOL_FRAGMENTS = {
    "host_confirm_bound_plan",
    "execute_query_plan",
    "record_feedback",
    "compare_query_versions",
    "save_experimental_recipe",
    "terminal",
    "file",
    "python",
    "sql",
    "raw",
}


def main() -> None:
    started = time.perf_counter()
    session_reports = [session_report(run) for run in LIVE_RUNS]
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "slice": "S2I-D_unseeded_frontier_agent_plan_authoring",
        "generated_at": utc_now_iso(),
        "frontier_identity": frontier_identity(),
        "safety_boundary": safety_boundary(),
        "knowledge_surface": knowledge_surface(),
        "runs": session_reports,
        "plan_delta": plan_delta(session_reports),
        "mcp_adapter_thinness": mcp_adapter_thinness(),
        "checks": [],
    }
    report["checks"] = checks_for_report(report)
    report["passed"] = all(item["ok"] for item in report["checks"])
    report["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in report["checks"] if item["ok"])
    failed = len(report["checks"]) - passed
    print(f"S2I-D unseeded Hermes authoring: {passed} passed, {failed} failed")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


def frontier_identity() -> dict[str, Any]:
    config = yaml.safe_load(HERMES_CONFIG_PATH.read_text(encoding="utf-8")) if HERMES_CONFIG_PATH.exists() else {}
    hermes = shutil.which("hermes")
    version = subprocess.run(
        [hermes, "--version"] if hermes else ["true"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return {
        "hermes_executable": hermes,
        "hermes_version": (version.stdout or version.stderr).strip(),
        "provider": (config.get("model") or {}).get("provider"),
        "configured_model": (config.get("model") or {}).get("default"),
        "reasoning_effort": (config.get("agent") or {}).get("reasoning_effort"),
        "hermes_config_sha256": file_sha256(HERMES_CONFIG_PATH),
    }


def safety_boundary() -> dict[str, Any]:
    config = yaml.safe_load(HERMES_CONFIG_PATH.read_text(encoding="utf-8")) if HERMES_CONFIG_PATH.exists() else {}
    server = ((config.get("mcp_servers") or {}).get("priori_tactical")) or {}
    tools = server.get("tools") or {}
    include = tools.get("include") or []
    return {
        "session_toolset": "priori_tactical",
        "visible_tool_list": include,
        "visible_tool_list_exact": include == list(S2I_HERMES_MCP_TOOL_NAMES),
        "host_only_tools_absent": set(S2I_HOST_ONLY_TOOL_NAMES).isdisjoint(include),
        "resources_enabled": tools.get("resources"),
        "prompts_enabled": tools.get("prompts"),
        "forbidden_surfaces": [
            "host confirmation",
            "execution",
            "filesystem",
            "terminal",
            "Python",
            "SQL",
            "raw tracking data",
        ],
    }


def knowledge_surface() -> dict[str, Any]:
    return {
        "knowledge_pack_path": str(KNOWLEDGE_PACK_PATH),
        "knowledge_pack_sha256": file_sha256(KNOWLEDGE_PACK_PATH),
        "recipe_authoring_contract_exposed": True,
        "unseeded_prompt_policy": "Prompts contain natural language requests and instructions, not plan JSON.",
    }


def session_report(run: dict[str, Any]) -> dict[str, Any]:
    session = db_one(
        "select id, source, model, model_config, tool_call_count, message_count, input_tokens, output_tokens, "
        "reasoning_tokens, system_prompt from sessions where id = ?",
        (run["session_id"],),
    )
    if session is None:
        return {"label": run["label"], "session_id": run["session_id"], "present": False}
    messages = db_all(
        "select role, content, tool_calls, tool_name from messages where session_id = ? order by id",
        (run["session_id"],),
    )
    called_tools = extract_called_tools(messages)
    final_response = final_json_response(messages)
    bound_path = WORKSHOP_ROOT / "handles" / "bound-plans" / f"{run['bound_plan_id']}.json"
    bound_record = json.loads(bound_path.read_text(encoding="utf-8")) if bound_path.exists() else {}
    resolved_parameters = relation_parameters(bound_record)
    user_prompt = next((row["content"] or "" for row in messages if row["role"] == "user"), "")
    model_config = json.loads(session.get("model_config") or "{}")
    return {
        "label": run["label"],
        "session_id": run["session_id"],
        "present": True,
        "source": session.get("source"),
        "model": session.get("model"),
        "model_config": model_config,
        "reasoning_effort": (model_config.get("reasoning_config") or {}).get("effort"),
        "system_instruction_sha256": sha256((session.get("system_prompt") or "").encode()).hexdigest(),
        "tool_call_count": session.get("tool_call_count"),
        "message_count": session.get("message_count"),
        "input_tokens": session.get("input_tokens"),
        "output_tokens": session.get("output_tokens"),
        "reasoning_tokens": session.get("reasoning_tokens"),
        "user_prompt_contains_plan_json": prompt_contains_plan_json(user_prompt),
        "called_tools": called_tools,
        "called_tools_allowed": set(called_tools).issubset(ALLOWED_HERMES_TOOL_NAMES),
        "host_only_tools_called": [
            tool for tool in called_tools if any(fragment in tool for fragment in S2I_HOST_ONLY_TOOL_NAMES)
        ],
        "forbidden_surface_calls": forbidden_surface_calls(called_tools),
        "final_response": final_response,
        "draft_plan_id": run["draft_plan_id"],
        "bound_plan_id": run["bound_plan_id"],
        "bound_plan_hash": run["bound_plan_hash"],
        "bound_handle_present": bound_path.exists(),
        "bound_execution_profile": bound_record.get("execution_profile"),
        "bound_execution_mode": (bound_record.get("bound_plan") or {}).get("execution_mode"),
        "bound_resolved_parameters": resolved_parameters,
        "expected_parameters": run["expected_parameters"],
        "expected_parameters_match": all(
            resolved_parameters.get(name, {}).get("value") == value for name, value in run["expected_parameters"].items()
        ),
    }


def extract_called_tools(messages: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for row in messages:
        if row.get("tool_name"):
            tools.append(row["tool_name"])
        raw = row.get("tool_calls")
        if not raw:
            continue
        try:
            calls = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for call in calls:
            name = ((call.get("function") or {}).get("name")) if isinstance(call, dict) else None
            if name:
                tools.append(name)
    return tools


def final_json_response(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(messages):
        content = row.get("content") or ""
        if row.get("role") != "assistant" or not content.strip():
            continue
        match = re.search(r"\{.*\}", content.strip(), flags=re.S)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def prompt_contains_plan_json(prompt: str) -> bool:
    forbidden_markers = [
        '"draft_plan"',
        '"default_invocation"',
        '"nodes"',
        '"classification_rules"',
        '"requested_evidence"',
        '"plan_document"',
    ]
    return any(marker in prompt for marker in forbidden_markers)


def forbidden_surface_calls(called_tools: list[str]) -> list[str]:
    forbidden = []
    for tool in called_tools:
        if any(fragment in tool.lower() for fragment in FORBIDDEN_TOOL_FRAGMENTS):
            forbidden.append(tool)
    return forbidden


def relation_parameters(bound_record: dict[str, Any]) -> dict[str, Any]:
    for node in (bound_record.get("bound_plan") or {}).get("nodes", []):
        if node.get("catalog_ref") == "geometric_progressive_corridor_from_anchor_set":
            return node.get("resolved_parameters") or {}
    return {}


def plan_delta(session_reports: list[dict[str, Any]]) -> dict[str, Any]:
    if len(session_reports) != 2:
        return {"ok": False}
    first, second = session_reports
    first_params = first.get("bound_resolved_parameters") or {}
    second_params = second.get("bound_resolved_parameters") or {}
    changed = {
        name: {
            "first": (first_params.get(name) or {}).get("value"),
            "second": (second_params.get(name) or {}).get("value"),
        }
        for name in sorted(set(first_params) | set(second_params))
        if (first_params.get(name) or {}).get("value") != (second_params.get(name) or {}).get("value")
    }
    return {
        "bound_plan_hashes_differ": first.get("bound_plan_hash") != second.get("bound_plan_hash"),
        "changed_parameters": changed,
        "material_parameter_delta": {
            key: changed.get(key) for key in ("minimum_progression_m", "minimum_duration_seconds")
        },
    }


def mcp_adapter_thinness() -> dict[str, Any]:
    source = MCP_SERVER_PATH.read_text(encoding="utf-8")
    forbidden_terms = [
        "possession_segment",
        "geometric_progressive_corridor",
        "minimum_progression_m",
        "minimum_duration_seconds",
        "TacticalQueryExecutor",
    ]
    return {
        "path": str(MCP_SERVER_PATH),
        "delegates_to_dispatch_model_visible": "dispatch_model_visible" in source,
        "forbidden_runtime_terms_present": [term for term in forbidden_terms if term in source],
    }


def checks_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    runs = report["runs"]
    boundary = report["safety_boundary"]
    delta = report["plan_delta"]
    thinness = report["mcp_adapter_thinness"]
    return [
        check("frontier.hermes_version_recorded", bool(report["frontier_identity"].get("hermes_version"))),
        check("frontier.model_recorded", all(run.get("model") == "gpt-5.5" for run in runs)),
        check("frontier.reasoning_effort_xhigh", all(run.get("reasoning_effort") == "xhigh" for run in runs)),
        check("knowledge_pack.hash_recorded", bool(report["knowledge_surface"].get("knowledge_pack_sha256"))),
        check("mcp.config_exact_allowlist", boundary.get("visible_tool_list_exact")),
        check("mcp.host_only_absent", boundary.get("host_only_tools_absent")),
        check("mcp.resources_prompts_disabled", boundary.get("resources_enabled") is False and boundary.get("prompts_enabled") is False),
        check("runs.present", all(run.get("present") for run in runs)),
        check("runs.unseeded_prompts", all(not run.get("user_prompt_contains_plan_json") for run in runs)),
        check("runs.only_allowed_tools_called", all(run.get("called_tools_allowed") for run in runs)),
        check("runs.no_forbidden_surface_calls", all(not run.get("forbidden_surface_calls") for run in runs)),
        check("runs.no_host_only_tool_calls", all(not run.get("host_only_tools_called") for run in runs)),
        check("runs.required_discovery_tools_used", all(required_tools_used(run) for run in runs)),
        check("runs.final_stopped_before_execution", all(run.get("final_response", {}).get("stopped_before_execution") for run in runs)),
        check("runs.bound_handles_present", all(run.get("bound_handle_present") for run in runs)),
        check("runs.generic_bind_only", all(run.get("bound_execution_profile") == "generic" and run.get("bound_execution_mode") == "bind_only" for run in runs)),
        check("runs.expected_parameters_match", all(run.get("expected_parameters_match") for run in runs)),
        check("delta.bound_hashes_differ", delta.get("bound_plan_hashes_differ")),
        check("delta.material_parameters_differ", bool(delta.get("material_parameter_delta", {}).get("minimum_progression_m"))),
        check("adapter.thin_dispatch_only", thinness.get("delegates_to_dispatch_model_visible") and not thinness.get("forbidden_runtime_terms_present")),
    ]


def required_tools_used(run: dict[str, Any]) -> bool:
    called = set(run.get("called_tools") or [])
    return {
        "mcp_priori_tactical_list_capabilities",
        "mcp_priori_tactical_search_recipes",
        "mcp_priori_tactical_describe_capability",
        "mcp_priori_tactical_submit_query_plan",
        "mcp_priori_tactical_validate_query_plan",
    }.issubset(called)


def check(name: str, ok: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok)}


def db_one(query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = db_all(query, params)
    return rows[0] if rows else None


def db_all(query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with sqlite3.connect(HERMES_DB, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
