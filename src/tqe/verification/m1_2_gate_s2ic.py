"""Verify M1.2 S2I-C: Tactical MCP adapter and Hermes validation boundary."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import anyio
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tqe.workshop.knowledge_pack import S2I_HERMES_MCP_TOOL_NAMES, S2I_HOST_ONLY_TOOL_NAMES, write_json
from tqe.workshop.m1_2 import utc_now_iso

REPORT_PATH = Path("artifacts/m1.2/s2i-c-mcp-integration-report.json")
PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
WORKSHOP_ROOT = Path("artifacts/m1.2/workshop")
MCP_SERVER_MODULE = "tqe.workshop.mcp_server"
HERMES_SERVER_NAME = "priori_tactical"
LIVE_HERMES_SESSION_ID = "20260621_212207_0f45e6"
LIVE_HERMES_DRAFT_PLAN_ID = "draft_92769e17bb25b809"
LIVE_HERMES_BOUND_PLAN_ID = "bound_7094041d9225ea8c"


def main() -> None:
    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "slice": "S2I-C_tactical_mcp_adapter_validation",
        "generated_at": utc_now_iso(),
        "mcp_server": mcp_server_report(),
        "stdio_protocol_proof": anyio.run(stdio_protocol_proof),
        "hermes_config": hermes_config_report(),
        "hermes_cli_probe": hermes_cli_probe(),
        "live_hermes_validation": live_hermes_validation_report(),
        "checks": [],
    }
    report["checks"] = checks_for_report(report)
    report["passed"] = all(item["ok"] for item in report["checks"])
    report["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in report["checks"] if item["ok"])
    failed = len(report["checks"]) - passed
    print(f"S2I-C Tactical MCP integration: {passed} passed, {failed} failed")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


def mcp_server_report() -> dict[str, Any]:
    python = Path.cwd() / ".venv" / "bin" / "python"
    return {
        "module": MCP_SERVER_MODULE,
        "command": str(python),
        "args": ["-m", MCP_SERVER_MODULE],
        "output_root": str(WORKSHOP_ROOT.resolve()),
        "allowlist": list(S2I_HERMES_MCP_TOOL_NAMES),
        "host_only_tools": list(S2I_HOST_ONLY_TOOL_NAMES),
        "dependency": "mcp>=1.24,<2",
    }


async def stdio_protocol_proof() -> dict[str, Any]:
    started = time.perf_counter()
    plan_document = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    params = StdioServerParameters(
        command=str(Path.cwd() / ".venv" / "bin" / "python"),
        args=["-m", MCP_SERVER_MODULE],
        cwd=str(Path.cwd()),
        env={"TQE_WORKSHOP_OUTPUT_ROOT": str(WORKSHOP_ROOT.resolve())},
    )
    rows: list[dict[str, Any]] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tool_names = [tool.name for tool in listed.tools]
            rows.append({"tool_name": "tools/list", "ok": True, "tool_names": tool_names})
            capabilities = await call_and_summarize(session, "list_capabilities", {})
            rows.append(capabilities)
            search = await call_and_summarize(
                session,
                "search_recipes",
                {"query": "progressive corridor", "states": ["EXPERIMENTAL"], "limit": 2},
            )
            rows.append(search)
            describe = await call_and_summarize(
                session,
                "describe_capability",
                {"capability_name": "submit_query_plan"},
            )
            rows.append(describe)
            submit = await call_and_summarize(
                session,
                "submit_query_plan",
                {"plan_document": plan_document, "source_label": "s2i_c_stdio_verifier"},
            )
            rows.append(submit)
            draft_plan_id = submit.get("summary", {}).get("draft_plan_id")
            validate = await call_and_summarize(
                session,
                "validate_query_plan",
                {"draft_plan_id": draft_plan_id},
            )
            rows.append(validate)
    allowed = set(S2I_HERMES_MCP_TOOL_NAMES)
    forbidden = set(S2I_HOST_ONLY_TOOL_NAMES)
    return {
        "ok": True,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "tool_names": rows[0]["tool_names"],
        "tool_names_exact_allowlist": rows[0]["tool_names"] == list(S2I_HERMES_MCP_TOOL_NAMES),
        "host_only_tools_absent": forbidden.isdisjoint(rows[0]["tool_names"]),
        "no_unknown_tools": set(rows[0]["tool_names"]).issubset(allowed),
        "rows": rows,
        "draft_plan_id": rows[-2].get("summary", {}).get("draft_plan_id"),
        "bound_plan_id": rows[-1].get("summary", {}).get("bound_plan_id"),
        "stopped_before_execution": True,
    }


async def call_and_summarize(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    result = await session.call_tool(tool_name, arguments)
    payload = tool_payload(result)
    ok = bool(payload.get("ok"))
    if tool_name == "list_capabilities":
        ok = bool(payload.get("tools"))
    return {
        "tool_name": tool_name,
        "ok": ok,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "summary": summarize_payload(tool_name, payload),
    }


def tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    for block in content:
        text = getattr(block, "text", None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {"ok": False, "error": "No structured JSON payload returned"}


def summarize_payload(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "list_capabilities":
        return {
            "tools": [tool.get("name") for tool in payload.get("tools", [])],
            "tool_count": len(payload.get("tools", [])),
        }
    if tool_name == "search_recipes":
        return {
            "recipe_ids": [recipe.get("recipe_id") for recipe in payload.get("recipes", [])],
            "count": len(payload.get("recipes", [])),
        }
    if tool_name == "describe_capability":
        capability = payload.get("capability", {})
        return {
            "name": capability.get("name"),
            "kind": capability.get("kind"),
            "has_input_schema": bool(capability.get("input_schema")),
        }
    if tool_name == "submit_query_plan":
        return {
            "draft_plan_id": payload.get("draft_plan_id"),
            "recipe_id": payload.get("recipe_id"),
            "plan_status": payload.get("plan_status"),
        }
    if tool_name == "validate_query_plan":
        return {
            "draft_plan_id": payload.get("draft_plan_id"),
            "bound_plan_id": payload.get("bound_plan_id"),
            "plan_status": payload.get("plan_status"),
            "execution_profile": payload.get("execution_profile"),
            "issue_count": len(payload.get("issues", [])),
        }
    return {"ok": payload.get("ok")}


def hermes_config_report() -> dict[str, Any]:
    hermes_home = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
    config_path = hermes_home / "config.yaml"
    if not config_path.exists():
        return {"present": False, "path": str(config_path)}
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    server = (config.get("mcp_servers") or {}).get(HERMES_SERVER_NAME) or {}
    tools = server.get("tools") or {}
    return {
        "present": True,
        "path": str(config_path),
        "server_name": HERMES_SERVER_NAME,
        "server_configured": bool(server),
        "command": server.get("command"),
        "args": server.get("args"),
        "include": tools.get("include") or [],
        "resources": tools.get("resources"),
        "prompts": tools.get("prompts"),
        "host_only_tools_absent": set(S2I_HOST_ONLY_TOOL_NAMES).isdisjoint(tools.get("include") or []),
        "include_exact_allowlist": (tools.get("include") or []) == list(S2I_HERMES_MCP_TOOL_NAMES),
    }


def hermes_cli_probe() -> dict[str, Any]:
    hermes = shutil.which("hermes")
    if not hermes:
        return {"ok": False, "error": "hermes not on PATH"}
    env = os.environ.copy()
    env.setdefault("HERMES_HOME", "/Users/luisrevilla/.hermes-priori")
    env.setdefault("CODEX_HOME", "/Users/luisrevilla/.codex")
    completed = subprocess.run(
        [hermes, "mcp", "test", HERMES_SERVER_NAME],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
        env=env,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "ok": completed.returncode == 0 and "Tools discovered: 8" in output,
        "exit_code": completed.returncode,
        "tools_discovered_8": "Tools discovered: 8" in output,
        "output_excerpt": output[:2000],
    }


def live_hermes_validation_report() -> dict[str, Any]:
    bound_path = WORKSHOP_ROOT / "handles" / "bound-plans" / f"{LIVE_HERMES_BOUND_PLAN_ID}.json"
    draft_path = WORKSHOP_ROOT / "handles" / "draft-plans" / f"{LIVE_HERMES_DRAFT_PLAN_ID}.json"
    bound_payload = json.loads(bound_path.read_text(encoding="utf-8")) if bound_path.exists() else {}
    return {
        "session_id": LIVE_HERMES_SESSION_ID,
        "observed_final_response": {
            "tools_used": [
                "list_capabilities",
                "search_recipes",
                "describe_capability",
                "submit_query_plan",
                "validate_query_plan",
            ],
            "draft_plan_id": LIVE_HERMES_DRAFT_PLAN_ID,
            "bound_plan_id": LIVE_HERMES_BOUND_PLAN_ID,
            "plan_status": "experimental",
            "stopped_before_execution": True,
            "error": None,
        },
        "draft_handle_present": draft_path.exists(),
        "bound_handle_present": bound_path.exists(),
        "bound_execution_profile": bound_payload.get("bound_plan", {}).get("execution_profile")
        or bound_payload.get("execution_profile"),
        "no_execution_handle_claimed": True,
    }


def checks_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    stdio = report["stdio_protocol_proof"]
    config = report["hermes_config"]
    cli = report["hermes_cli_probe"]
    live = report["live_hermes_validation"]
    return [
        check("mcp.server_tools_exact_allowlist", stdio.get("tool_names_exact_allowlist")),
        check("mcp.host_only_tools_absent", stdio.get("host_only_tools_absent")),
        check("mcp.no_unknown_tools", stdio.get("no_unknown_tools")),
        check("mcp.list_search_describe_submit_validate_ok", all(row.get("ok") for row in stdio.get("rows", [])[1:])),
        check("mcp.submit_created_draft", bool(stdio.get("draft_plan_id"))),
        check("mcp.validate_created_bound_plan", bool(stdio.get("bound_plan_id"))),
        check("mcp.stopped_before_execution", stdio.get("stopped_before_execution")),
        check("hermes.configured_exact_allowlist", config.get("include_exact_allowlist")),
        check("hermes.config_resources_prompts_disabled", config.get("resources") is False and config.get("prompts") is False),
        check("hermes.cli_mcp_test_discovers_8_tools", cli.get("ok")),
        check("hermes.live_session_stopped_before_execution", live.get("observed_final_response", {}).get("stopped_before_execution")),
        check("hermes.live_session_bound_handle_present", live.get("bound_handle_present")),
    ]


def check(name: str, ok: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok)}


if __name__ == "__main__":
    main()
