"""Verify M1.2 S2I-E: frontier configuration freeze."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from tqe.workshop.knowledge_pack import S2I_HERMES_MCP_TOOL_NAMES, S2I_HOST_ONLY_TOOL_NAMES, write_json
from tqe.workshop.m1_2 import utc_now_iso


FREEZE_PATH = Path("delivery/m1.2/frontier-runtime-freeze.json")
REPORT_PATH = Path("artifacts/m1.2/s2i-e-frontier-freeze-report.json")
S2IB_REPORT_PATH = Path("artifacts/m1.2/s2i-b-provisioning-report.json")
S2ID_REPORT_PATH = Path("artifacts/m1.2/s2i-d-unseeded-hermes-report.json")
CAPABILITY_CONTEXT_PATH = Path("generated/capability-context.json")
KNOWLEDGE_PACK_PATH = Path("generated/tactical-knowledge-pack.json")
MCP_SERVER_PATH = Path("src/tqe/workshop/mcp_server.py")
WORKSHOP_SERVICE_PATH = Path("src/tqe/workshop/m1_2.py")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
HERMES_CONFIG_PATH = HERMES_HOME / "config.yaml"


def main() -> None:
    started = time.perf_counter()
    s2ib = read_json(S2IB_REPORT_PATH)
    s2id = read_json(S2ID_REPORT_PATH)
    config = read_yaml(HERMES_CONFIG_PATH)
    freeze = build_freeze(s2ib, s2id, config)
    write_json(FREEZE_PATH, freeze)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "slice": "S2I-E_frontier_configuration_freeze",
        "generated_at": utc_now_iso(),
        "freeze_path": str(FREEZE_PATH),
        "freeze_sha256": file_sha256(FREEZE_PATH),
        "freeze": freeze,
        "checks": checks_for_freeze(freeze, s2ib, s2id),
    }
    report["passed"] = all(item["ok"] for item in report["checks"])
    report["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in report["checks"] if item["ok"])
    failed = len(report["checks"]) - passed
    print(f"S2I-E frontier freeze: {passed} passed, {failed} failed")
    print(f"Freeze: {FREEZE_PATH}")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


def build_freeze(s2ib: dict[str, Any], s2id: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    model_config = config.get("model") or {}
    agent_config = config.get("agent") or {}
    mcp_config = ((config.get("mcp_servers") or {}).get("priori_tactical")) or {}
    tools_config = mcp_config.get("tools") or {}
    direct_rows = (s2ib.get("comparison_evidence") or {}).get("rows") or []
    returned_models = sorted({row.get("returned_model") for row in direct_rows if row.get("returned_model")})
    runs = s2id.get("runs") or []
    session_models = sorted({run.get("model") for run in runs if run.get("model")})
    session_instruction_hashes = sorted({run.get("system_instruction_sha256") for run in runs if run.get("system_instruction_sha256")})
    include = tools_config.get("include") or []
    return {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "slice": "S2I-E_frontier_configuration_freeze",
        "generated_at": utc_now_iso(),
        "status": "FROZEN_PENDING_FINAL_INDEPENDENT_EVALUATION",
        "selected_product_route": {
            "runtime": "Hermes Agent over local stdio Tactical MCP",
            "provider": model_config.get("provider"),
            "configured_model": model_config.get("default"),
            "reasoning_effort": agent_config.get("reasoning_effort"),
            "session_toolset": "priori_tactical",
            "auth_route": "openai-codex ChatGPT/Codex subscription login",
            "hermes_home": str(HERMES_HOME),
            "hermes_config_path": str(HERMES_CONFIG_PATH),
            "hermes_config_sha256": file_sha256(HERMES_CONFIG_PATH),
            "hermes_version": hermes_version(),
            "session_model_reports": session_models,
            "exact_snapshot_status": (
                "Hermes session metadata reports the product alias only; exact snapshot identity is proven "
                "through the direct Responses API control route."
            ),
        },
        "direct_api_control_route": {
            "role": "provisioning, control probes, and fallback evaluation evidence; not the product Hermes route",
            "requested_model": s2ib.get("requested_model"),
            "returned_models": returned_models,
            "strict_structured_output_verified": check_named(s2ib, "frontier.responses_strict_structured_output"),
            "reasoning_high_verified": check_named(s2ib, "frontier.reasoning_high"),
            "reasoning_xhigh_verified": check_named(s2ib, "frontier.reasoning_xhigh"),
            "comparison_evidence": s2ib.get("comparison_evidence", {}),
        },
        "reasoning_selection": {
            "selected_effort": agent_config.get("reasoning_effort"),
            "basis": [
                "S2I-B accepted high and xhigh for strict structured-output direct API probes.",
                "S2I-B recommendation selected xhigh after the final provisioning comparison.",
                "S2I-D live Hermes sessions validated two unseeded typed plans under xhigh.",
            ],
            "no_prompt_or_vocabulary_tuning_after_freeze_without_new_slice": True,
        },
        "mcp_boundary": {
            "server_name": "priori_tactical",
            "adapter_path": str(MCP_SERVER_PATH),
            "tool_allowlist": include,
            "expected_tool_allowlist": list(S2I_HERMES_MCP_TOOL_NAMES),
            "host_only_tools": list(S2I_HOST_ONLY_TOOL_NAMES),
            "resources_enabled": tools_config.get("resources"),
            "prompts_enabled": tools_config.get("prompts"),
            "filesystem_terminal_raw_data_tools_available": False,
        },
        "knowledge_and_schema_hashes": {
            "knowledge_pack_path": str(KNOWLEDGE_PACK_PATH),
            "knowledge_pack_sha256": file_sha256(KNOWLEDGE_PACK_PATH),
            "capability_context_path": str(CAPABILITY_CONTEXT_PATH),
            "capability_context_sha256": file_sha256(CAPABILITY_CONTEXT_PATH),
            "mcp_server_path": str(MCP_SERVER_PATH),
            "mcp_server_sha256": file_sha256(MCP_SERVER_PATH),
            "workshop_service_path": str(WORKSHOP_SERVICE_PATH),
            "workshop_service_sha256": file_sha256(WORKSHOP_SERVICE_PATH),
        },
        "s2id_unseeded_proof": {
            "report_path": str(S2ID_REPORT_PATH),
            "report_sha256": file_sha256(S2ID_REPORT_PATH),
            "run_count": len(runs),
            "session_ids": [run.get("session_id") for run in runs],
            "bound_plan_hashes": [run.get("bound_plan_hash") for run in runs],
            "system_instruction_sha256_values": session_instruction_hashes,
            "plan_delta": s2id.get("plan_delta"),
            "passed": s2id.get("passed"),
        },
        "final_independent_evaluation": {
            "status": "PENDING_EXTERNAL_INDEPENDENT_SET",
            "required_before_s3": True,
            "acceptance_thresholds": {
                "supported_accuracy": ">= 0.90",
                "ambiguous_accuracy": ">= 0.90",
                "unsupported_accuracy": "1.00",
                "schema_valid_or_refusal": "1.00",
                "unauthorized_calls": 0,
                "unconfirmed_executions": 0,
            },
            "instruction": (
                "Do not treat S2I-B probes or S2I-D live authoring as final sealed acceptance. "
                "Run a new independently authored evaluation after this freeze."
            ),
        },
        "non_claims": [
            "This freeze does not prove final sealed acceptance.",
            "This freeze does not grant Hermes host confirmation or execution authority.",
            "This freeze does not change runtime semantics, query IR, primitives, replay, UI, or recipe families.",
        ],
    }


def checks_for_freeze(freeze: dict[str, Any], s2ib: dict[str, Any], s2id: dict[str, Any]) -> list[dict[str, Any]]:
    route = freeze["selected_product_route"]
    control = freeze["direct_api_control_route"]
    boundary = freeze["mcp_boundary"]
    hashes = freeze["knowledge_and_schema_hashes"]
    s2id_proof = freeze["s2id_unseeded_proof"]
    return [
        check("s2ib.provisioning_report_passed", s2ib.get("passed")),
        check("s2id.unseeded_authoring_report_passed", s2id.get("passed")),
        check("product_route.provider_openai_codex", route.get("provider") == "openai-codex"),
        check("product_route.configured_model_gpt_5_5", route.get("configured_model") == "gpt-5.5"),
        check("product_route.reasoning_xhigh", route.get("reasoning_effort") == "xhigh"),
        check("direct_api.exact_snapshot_returned", control.get("returned_models") == ["gpt-5.5-2026-04-23"]),
        check("direct_api.strict_structured_output_verified", control.get("strict_structured_output_verified")),
        check("direct_api.high_and_xhigh_verified", control.get("reasoning_high_verified") and control.get("reasoning_xhigh_verified")),
        check("mcp.exact_tool_allowlist", boundary.get("tool_allowlist") == boundary.get("expected_tool_allowlist")),
        check("mcp.host_only_absent", set(boundary.get("host_only_tools") or []).isdisjoint(boundary.get("tool_allowlist") or [])),
        check("mcp.resources_and_prompts_disabled", boundary.get("resources_enabled") is False and boundary.get("prompts_enabled") is False),
        check("hashes.knowledge_pack_recorded", bool(hashes.get("knowledge_pack_sha256"))),
        check("hashes.capability_context_recorded", bool(hashes.get("capability_context_sha256"))),
        check("s2id.two_live_unseeded_runs", s2id_proof.get("run_count") == 2),
        check("s2id.bound_hashes_differ", (s2id.get("plan_delta") or {}).get("bound_plan_hashes_differ")),
        check("s2id.material_parameters_differ", bool((s2id.get("plan_delta") or {}).get("material_parameter_delta"))),
        check("final_eval.pending_not_claimed", freeze["final_independent_evaluation"].get("status") == "PENDING_EXTERNAL_INDEPENDENT_SET"),
    ]


def check_named(report: dict[str, Any], name: str) -> bool:
    return any(item.get("name") == name and item.get("ok") for item in report.get("checks", []))


def check(name: str, ok: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok)}


def hermes_version() -> str:
    hermes = shutil.which("hermes")
    if not hermes:
        return ""
    result = subprocess.run([hermes, "--version"], check=False, capture_output=True, text=True, timeout=15)
    return (result.stdout or result.stderr).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
