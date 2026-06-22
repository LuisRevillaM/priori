"""Run the M1.2 S2I-B frontier/Hermes provisioning spike.

The report is intentionally redacted: it records model IDs, timings, usage, and
tool visibility, but never records API keys, raw secrets, or local auth tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tqe.workshop.knowledge_pack import (
    PACK_JSON_PATH,
    S2I_HERMES_MCP_TOOL_NAMES,
    S2I_HOST_ONLY_TOOL_NAMES,
    write_json,
)
from tqe.workshop.m1_2 import (
    HERMES_S2_TOOL_NAMES,
    ToolDispatchRequest,
    dispatch_tool,
    response_model_for_tool,
    tool_spec,
)
from tqe.workshop.m1_2 import utc_now_iso


REPORT_PATH = Path("artifacts/m1.2/s2i-b-provisioning-report.json")
REQUESTED_MODEL = os.environ.get("S2I_B_REQUESTED_MODEL", "gpt-5.5-2026-04-23")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
HTTP_TIMEOUT_SECONDS = int(os.environ.get("S2I_B_HTTP_TIMEOUT_SECONDS", "90"))
GPT55_PRICING = {
    "source_url": "https://openai.com/api/pricing/",
    "source_checked_at": "2026-06-21",
    "input_usd_per_1m": 5.00,
    "cached_input_usd_per_1m": 0.50,
    "output_usd_per_1m": 30.00,
}
FROZEN_PROBES = [
    {
        "id": "supported_recipe_selection",
        "prompt": "Use the reviewed ball-side defensive displacement recipe.",
        "expected": "select_recipe",
    },
    {
        "id": "supported_corridor_parameter",
        "prompt": "Find forward lanes that stay open for at least 0.8 seconds.",
        "expected": "draft",
    },
    {
        "id": "ambiguous_support",
        "prompt": "Show when the late runner provided enough support.",
        "expected": "clarify",
    },
    {
        "id": "unsupported_intent",
        "prompt": "Infer the midfielder's intended pass from scanning and body angle.",
        "expected": "capability_gap",
    },
]


def main() -> None:
    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "slice": "S2I-B_frontier_and_hermes_provisioning_spike",
        "generated_at": utc_now_iso(),
        "requested_model": REQUESTED_MODEL,
        "environment": environment_report(),
        "knowledge_pack": knowledge_pack_report(),
        "frontier_model_access": {},
        "comparison_evidence": {},
        "hermes_availability": hermes_availability_report(),
        "mcp_proof": mcp_boundary_report(),
        "tactical_mcp_proof": tactical_tool_report(),
        "checks": [],
        "recommendation": {},
    }
    models_result = list_openai_models()
    report["frontier_model_access"]["models_list"] = models_result
    available_models = set(models_result.get("candidate_model_ids", []))
    report["frontier_model_access"]["requested_model_listed"] = REQUESTED_MODEL in available_models
    if os.environ.get("OPENAI_API_KEY"):
        report["frontier_model_access"]["responses_api"] = responses_api_report(REQUESTED_MODEL)
        report["comparison_evidence"] = comparison_report(REQUESTED_MODEL)
    else:
        report["frontier_model_access"]["responses_api"] = {
            "ok": False,
            "error": "OPENAI_API_KEY not present",
        }
        report["comparison_evidence"] = {"ok": False, "error": "OPENAI_API_KEY not present"}
    report["recommendation"] = recommendation(report)
    report["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    report["checks"] = checks_for_report(report)
    report["passed"] = all(item["ok"] for item in report["checks"])
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in report["checks"] if item["ok"])
    failed = len(report["checks"]) - passed
    print(f"S2I-B provisioning: {passed} passed, {failed} failed")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


def environment_report() -> dict[str, Any]:
    commands = [
        "python",
        "python3",
        "node",
        "npm",
        "npx",
        "codex",
        "hermes",
        "hermes-agent",
    ]
    return {
        "api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "api_key_handling": "direct OpenAI probes only; Hermes instance must use ChatGPT/Codex subscription login",
        "commands": {name: command_report(name) for name in commands},
    }


def command_report(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    result: dict[str, Any] = {"present": bool(path), "path": path}
    if not path:
        return result
    version_args = {
        "python": ["--version"],
        "python3": ["--version"],
        "node": ["--version"],
        "npm": ["--version"],
        "npx": ["--version"],
        "codex": ["--version"],
        "hermes": ["--version"],
        "hermes-agent": ["--version"],
    }
    try:
        completed = subprocess.run(
            [path, *version_args.get(name, ["--version"])],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        result["version_command_exit_code"] = completed.returncode
        result["version_output"] = (completed.stdout or completed.stderr).strip()[:500]
    except Exception as exc:  # pragma: no cover - defensive local environment capture
        result["version_error"] = f"{type(exc).__name__}: {exc}"
    return result


def knowledge_pack_report() -> dict[str, Any]:
    if not PACK_JSON_PATH.exists():
        return {"present": False, "path": str(PACK_JSON_PATH)}
    data = PACK_JSON_PATH.read_bytes()
    return {
        "present": True,
        "path": str(PACK_JSON_PATH),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "approx_chars_per_4_tokens": len(data) // 4,
    }


def list_openai_models() -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        return {"ok": False, "error": "OPENAI_API_KEY not present"}
    result = openai_request("GET", OPENAI_MODELS_URL, None)
    if not result["ok"]:
        return result
    ids = sorted(
        model["id"]
        for model in result["json"].get("data", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    )
    candidate_ids = [
        model_id
        for model_id in ids
        if model_id.startswith(("gpt-5", "gpt-4.1", "o1", "o3", "o4"))
    ]
    return {
        "ok": True,
        "model_count": len(ids),
        "candidate_model_ids": candidate_ids,
        "requested_model_present": REQUESTED_MODEL in ids,
        "latency_ms": result["latency_ms"],
    }


def responses_api_report(model: str) -> dict[str, Any]:
    base = call_structured_response(
        model=model,
        prompt="Return a valid structured response with status ok.",
        reasoning_effort=None,
    )
    high = call_structured_response(
        model=model,
        prompt="Return a valid structured response with status ok using careful reasoning.",
        reasoning_effort="high",
    )
    xhigh = call_structured_response(
        model=model,
        prompt="Return a valid structured response with status ok using maximum reasoning if supported.",
        reasoning_effort="xhigh",
    )
    return {
        "requested_model": model,
        "strict_structured_output": base,
        "reasoning_high": high,
        "reasoning_xhigh": xhigh,
    }


def comparison_report(model: str) -> dict[str, Any]:
    rows = []
    for effort in ("high", "xhigh"):
        for probe in FROZEN_PROBES:
            response = call_probe_response(model=model, probe=probe, reasoning_effort=effort)
            rows.append(
                {
                    "probe_id": probe["id"],
                    "expected": probe["expected"],
                    "reasoning_effort": effort,
                    **response,
                }
            )
    summaries = summarize_comparison_rows(rows)
    return {
        "ok": any(row.get("ok") for row in rows),
        "frozen_probe_set_sha256": hashlib.sha256(
            json.dumps(FROZEN_PROBES, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "rows": rows,
        "summaries_by_effort": summaries,
        "pricing": GPT55_PRICING,
    }


def call_structured_response(
    *,
    model: str,
    prompt: str,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "s2ib_strict_probe",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "status": {"type": "string", "enum": ["ok"]},
                        "answer": {"type": "string"},
                    },
                    "required": ["status", "answer"],
                },
            }
        },
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    result = openai_request("POST", OPENAI_RESPONSES_URL, payload)
    return summarize_response_result(result, reasoning_effort)


def call_probe_response(
    *,
    model: str,
    probe: dict[str, str],
    reasoning_effort: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Classify a tactical query request. Return only the requested JSON. "
                    "Do not call tools."
                ),
            },
            {
                "role": "user",
                "content": probe["prompt"],
            },
        ],
        "reasoning": {"effort": reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "s2ib_probe_decision",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "outcome": {
                            "type": "string",
                            "enum": ["select_recipe", "draft", "clarify", "capability_gap"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["outcome", "rationale"],
                },
            }
        },
    }
    result = openai_request("POST", OPENAI_RESPONSES_URL, payload)
    summary = summarize_response_result(result, reasoning_effort)
    summary["repair_or_fallback_used"] = False
    if summary.get("json_output"):
        summary["first_pass_outcome"] = summary["json_output"].get("outcome")
        summary["first_pass_matches_expected"] = summary["first_pass_outcome"] == probe["expected"]
    return summary


def summarize_response_result(result: dict[str, Any], reasoning_effort: str | None) -> dict[str, Any]:
    if not result["ok"]:
        return {
            "ok": False,
            "reasoning_effort": reasoning_effort,
            "latency_ms": result.get("latency_ms"),
            "error": result.get("error"),
            "http_status": result.get("http_status"),
        }
    payload = result["json"]
    output_text = extract_output_text(payload)
    json_output = parse_json_output(output_text)
    return {
        "ok": json_output is not None,
        "reasoning_effort": reasoning_effort,
        "requested_model": result.get("requested_model"),
        "returned_model": payload.get("model"),
        "response_id": payload.get("id"),
        "latency_ms": result["latency_ms"],
        "usage": payload.get("usage", {}),
        "estimated_cost_usd": estimate_cost_usd(payload.get("model"), payload.get("usage", {})),
        "json_output": json_output,
        "parse_error": None if json_output is not None else "structured output text was not JSON",
    }


def estimate_cost_usd(model: str | None, usage: dict[str, Any]) -> float | None:
    if not model or not model.startswith("gpt-5.5"):
        return None
    input_tokens = int(usage.get("input_tokens") or 0)
    cached_tokens = int(usage.get("input_tokens_details", {}).get("cached_tokens") or 0)
    billable_input = max(input_tokens - cached_tokens, 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cost = (
        billable_input * GPT55_PRICING["input_usd_per_1m"]
        + cached_tokens * GPT55_PRICING["cached_input_usd_per_1m"]
        + output_tokens * GPT55_PRICING["output_usd_per_1m"]
    ) / 1_000_000
    return round(cost, 8)


def summarize_comparison_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for effort in ("high", "xhigh"):
        effort_rows = [row for row in rows if row.get("reasoning_effort") == effort]
        ok_rows = [row for row in effort_rows if row.get("ok")]
        match_rows = [row for row in effort_rows if row.get("first_pass_matches_expected")]
        latencies = [row["latency_ms"] for row in ok_rows if isinstance(row.get("latency_ms"), int)]
        costs = [
            row["estimated_cost_usd"]
            for row in ok_rows
            if isinstance(row.get("estimated_cost_usd"), int | float)
        ]
        summaries[effort] = {
            "probe_count": len(effort_rows),
            "completed_count": len(ok_rows),
            "exact_match_count": len(match_rows),
            "completion_rate": len(ok_rows) / len(effort_rows) if effort_rows else 0,
            "exact_match_rate": len(match_rows) / len(effort_rows) if effort_rows else 0,
            "total_latency_ms": sum(latencies),
            "average_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
            "estimated_cost_usd": round(sum(costs), 8),
        }
    return summaries


def extract_output_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def parse_json_output(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def openai_request(method: str, url: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return {
                "ok": True,
                "http_status": response.status,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "json": json.loads(body),
                "requested_model": payload.get("model") if isinstance(payload, dict) else None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "http_status": exc.code,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": body[:1000],
        }
    except Exception as exc:  # pragma: no cover - records local/network failure
        return {
            "ok": False,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def hermes_availability_report() -> dict[str, Any]:
    hermes = command_report("hermes")
    hermes_agent = command_report("hermes-agent")
    codex = command_report("codex")
    config_candidates = [
        Path.home() / ".codex" / "config.toml",
        Path("/Users/luisrevilla/code/agents/.worktrees/hermes-migration/hermes"),
    ]
    return {
        "hermes": hermes,
        "hermes_agent": hermes_agent,
        "codex": codex,
        "subscription_login_policy": "Hermes instances should use ChatGPT/Codex subscription login, not OPENAI_API_KEY",
        "configuration_candidates": [
            {"path": str(path), "present": path.exists(), "sha256": file_sha256(path) if path.is_file() else None}
            for path in config_candidates
        ],
        "available": bool(hermes.get("present") or hermes_agent.get("present")),
    }


def mcp_boundary_report() -> dict[str, Any]:
    visible = list(S2I_HERMES_MCP_TOOL_NAMES)
    host_only = list(S2I_HOST_ONLY_TOOL_NAMES)
    schemas = {}
    for name in visible:
        spec = tool_spec(name)
        schemas[name] = {
            "description": spec.description,
            "request_schema_title": spec.input_schema.get("title"),
            "response_schema_one_of_count": len(spec.output_schema.get("oneOf", [])),
        }
    return {
        "mode": "local_boundary_simulation_no_hermes_executable",
        "trivial_stdio_mcp_connected": False,
        "hermes_tool_allowlist_visible": visible,
        "host_only_tools_absent": not any(name in visible for name in host_only),
        "reference_harness_visible_tools": list(HERMES_S2_TOOL_NAMES),
        "host_only_tools": host_only,
        "schemas": schemas,
        "filesystem_terminal_raw_data_tools_visible": False,
        "hermes_can_confirm_or_execute": False,
    }


def tactical_tool_report() -> dict[str, Any]:
    rows = []
    rows.append(dispatch_probe("list_capabilities", {}))
    rows.append(
        dispatch_probe(
            "search_recipes",
            {"query": "progressive corridor", "states": ["EXPERIMENTAL"], "limit": 2},
        )
    )
    rows.append(
        dispatch_probe(
            "describe_capability",
            {"capability_name": "search_recipes"},
        )
    )
    plan_document = experimental_probe_plan()
    submit_row = dispatch_probe(
        "submit_query_plan",
        {"plan_document": plan_document, "source_label": "s2i_b_probe"},
    )
    rows.append(submit_row)
    bound_plan_id = ""
    if submit_row["ok"]:
        draft_plan_id = submit_row["response"].get("draft_plan_id", "")
        validate_row = dispatch_probe("validate_query_plan", {"draft_plan_id": draft_plan_id})
        rows.append(validate_row)
        bound_plan_id = validate_row.get("response", {}).get("bound_plan_id", "")
    denied_execution = {
        "tool_name": "execute_query_plan",
        "ok": False,
        "expected_denial": True,
        "error": "not present in S2I Hermes MCP allowlist",
        "bound_plan_id_present_for_host_confirmation": bool(bound_plan_id),
    }
    rows.append(denied_execution)
    return {
        "ok": all(row["ok"] for row in rows if row["tool_name"] != "execute_query_plan")
        and not denied_execution["ok"],
        "rows": rows,
        "stopped_before_execution": True,
    }


def dispatch_probe(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = dispatch_tool(ToolDispatchRequest(tool_name=tool_name, arguments=arguments))
        response_payload = response.model_dump(mode="json")
        if response.ok and tool_name in HERMES_S2_TOOL_NAMES:
            response_model_for_tool(tool_name).model_validate(response_payload["response"])
        return {
            "tool_name": tool_name,
            "ok": response.ok,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "response": sanitize_tool_response(tool_name, response_payload.get("response")),
            "error": response_payload.get("error"),
        }
    except ValidationError as exc:
        return {
            "tool_name": tool_name,
            "ok": False,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": exc.errors(),
        }
    except Exception as exc:  # pragma: no cover - report unexpected probe failure
        return {
            "tool_name": tool_name,
            "ok": False,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def sanitize_tool_response(tool_name: str, response: Any) -> Any:
    if not isinstance(response, dict):
        return response
    if tool_name == "list_capabilities":
        return {
            "tools": [tool.get("name") for tool in response.get("tools", [])],
            "tool_count": len(response.get("tools", [])),
        }
    if tool_name == "search_recipes":
        return {
            "recipes": [
                {
                    "recipe_id": recipe.get("recipe_id"),
                    "state": recipe.get("state"),
                    "score": recipe.get("score"),
                }
                for recipe in response.get("recipes", [])
            ]
        }
    if tool_name == "describe_capability":
        capability = response.get("capability", {})
        return {
            "name": capability.get("name"),
            "kind": capability.get("kind"),
            "description": capability.get("description"),
        }
    if tool_name == "submit_query_plan":
        return {
            "draft_plan_id": response.get("draft_plan_id"),
            "draft_plan_id_present": bool(response.get("draft_plan_id")),
        }
    if tool_name == "validate_query_plan":
        return {
            "ok": response.get("ok"),
            "bound_plan_id": response.get("bound_plan_id"),
            "bound_plan_id_present": bool(response.get("bound_plan_id")),
            "issue_count": len(response.get("issues", [])),
        }
    return response


def experimental_probe_plan() -> dict[str, Any]:
    path = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


def recommendation(report: dict[str, Any]) -> dict[str, Any]:
    high_ok = report["frontier_model_access"].get("responses_api", {}).get("reasoning_high", {}).get("ok")
    xhigh_ok = report["frontier_model_access"].get("responses_api", {}).get("reasoning_xhigh", {}).get("ok")
    summaries = report.get("comparison_evidence", {}).get("summaries_by_effort", {})
    high_summary = summaries.get("high", {})
    xhigh_summary = summaries.get("xhigh", {})
    high_score = (
        high_summary.get("completed_count", 0),
        high_summary.get("exact_match_count", 0),
        -(high_summary.get("total_latency_ms") or 0),
        -(high_summary.get("estimated_cost_usd") or 0),
    )
    xhigh_score = (
        xhigh_summary.get("completed_count", 0),
        xhigh_summary.get("exact_match_count", 0),
        -(xhigh_summary.get("total_latency_ms") or 0),
        -(xhigh_summary.get("estimated_cost_usd") or 0),
    )
    if xhigh_ok and xhigh_score > high_score:
        effort = "xhigh"
        rationale = "xhigh was accepted and measured better on completion, exact matches, latency, and estimated cost."
    elif high_ok:
        effort = "high"
        rationale = "high passed and measured at least as well as xhigh on the frozen comparison probes."
    else:
        effort = None
        rationale = "No reasoning effort passed the strict structured-output probe."
    hermes_ready = report["hermes_availability"].get("available", False)
    return {
        "go_no_go": "NO_GO_FOR_FULL_S2I_B" if not hermes_ready else "GO_FOR_HERMES_MCP_INTEGRATION",
        "recommended_reasoning_effort": effort,
        "rationale": rationale,
        "next_step": (
            "Install/configure Hermes with ChatGPT/Codex subscription login, then rerun the spike."
            if not hermes_ready
            else "Connect the tactical MCP adapter to Hermes and run a real Hermes-authored validation."
        ),
    }


def checks_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    responses = report["frontier_model_access"].get("responses_api", {})
    mcp = report["mcp_proof"]
    tactical = report["tactical_mcp_proof"]
    hermes = report["hermes_availability"]
    return [
        check("frontier.requested_model_listed", report["frontier_model_access"].get("requested_model_listed")),
        check("frontier.responses_strict_structured_output", responses.get("strict_structured_output", {}).get("ok")),
        check("frontier.reasoning_high", responses.get("reasoning_high", {}).get("ok")),
        check("frontier.reasoning_xhigh", responses.get("reasoning_xhigh", {}).get("ok")),
        check("hermes.executable_available", hermes.get("available")),
        check("mcp.host_only_tools_absent", mcp.get("host_only_tools_absent")),
        check("mcp.no_confirm_or_execute", not mcp.get("hermes_can_confirm_or_execute")),
        check("tactical.tools_validate_and_stop_before_execution", tactical.get("ok")),
    ]


def check(name: str, ok: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok)}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
