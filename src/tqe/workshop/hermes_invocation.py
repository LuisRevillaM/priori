"""Hermes invocation shim for the Workbench product path.

Hermes' one-shot CLI validates explicit toolsets before MCP discovery. The
Priori tactical toolset is dynamic, so the host invokes this module under the
Hermes Python environment: discover MCP tools first, verify the exact tool
surface, then run the one-shot agent with the dynamic MCP toolset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any


EXPECTED_TOOLSET = "mcp-priori_tactical"
EXPECTED_TOOL_NAMES = {
    "mcp_priori_tactical_list_capabilities",
    "mcp_priori_tactical_search_recipes",
    "mcp_priori_tactical_describe_capability",
    "mcp_priori_tactical_submit_query_plan",
    "mcp_priori_tactical_validate_query_plan",
    "mcp_priori_tactical_inspect_result",
    "mcp_priori_tactical_inspect_non_match",
    "mcp_priori_tactical_retrieve_replay_window",
}
FORBIDDEN_TOOL_FRAGMENTS = {
    "terminal",
    "process",
    "shell",
    "file",
    "read_file",
    "write_file",
    "python",
    "sql",
    "execute",
    "browser",
    "web_",
    "host_confirm_bound_plan",
    "execute_query_plan",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Hermes through the frozen Priori tactical MCP surface.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    probe = subcommands.add_parser("probe", help="Verify the model-visible MCP tool surface.")
    probe.add_argument("--toolset", default=EXPECTED_TOOLSET)

    interpret = subcommands.add_parser("interpret", help="Run a single Hermes interpretation prompt.")
    interpret.add_argument("--toolset", default=EXPECTED_TOOLSET)
    interpret.add_argument("--provider", required=True)
    interpret.add_argument("--model", required=True)
    interpret.add_argument("--prompt", required=True)

    args = parser.parse_args(argv)
    if args.command == "probe":
        emit_json(probe_tool_surface(args.toolset))
        return 0
    if args.command == "interpret":
        surface = probe_tool_surface(args.toolset)
        if not surface["safe"]:
            emit_json({"ok": False, "error_code": "UNSAFE_TOOL_SURFACE", "surface": surface})
            return 2
        result = run_hermes_agent(args.prompt, provider=args.provider, model=args.model, toolset=args.toolset)
        emit_json({"ok": result["exit_code"] == 0, "surface": surface, **result})
        return 0 if result["exit_code"] == 0 else 1
    raise AssertionError(f"Unhandled command: {args.command}")


def probe_tool_surface(toolset: str) -> dict[str, Any]:
    discovered = discover_mcp_tool_names()
    tool_names = model_visible_tool_names(toolset)
    normalized = {name.removeprefix("functions.") for name in tool_names}
    forbidden = sorted(
        name
        for name in normalized
        if any(fragment in name.lower() for fragment in FORBIDDEN_TOOL_FRAGMENTS)
    )
    return {
        "safe": normalized == EXPECTED_TOOL_NAMES and not forbidden,
        "toolset": toolset,
        "discovered_tool_names": sorted(discovered),
        "tool_names": sorted(normalized),
        "expected_tool_names": sorted(EXPECTED_TOOL_NAMES),
        "missing": sorted(EXPECTED_TOOL_NAMES - normalized),
        "extra": sorted(normalized - EXPECTED_TOOL_NAMES),
        "forbidden": forbidden,
    }


def discover_mcp_tool_names() -> list[str]:
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            from tools.mcp_tool import discover_mcp_tools

            return [str(name) for name in discover_mcp_tools()]


def model_visible_tool_names(toolset: str) -> set[str]:
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            from model_tools import get_tool_definitions
            from toolsets import validate_toolset

            if not validate_toolset(toolset):
                return set()
            definitions = get_tool_definitions(enabled_toolsets=[toolset], quiet_mode=True)
    names: set[str] = set()
    for definition in definitions:
        function = definition.get("function") if isinstance(definition, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if name:
            names.add(str(name))
    return names


def run_hermes_agent(prompt: str, *, provider: str, model: str, toolset: str) -> dict[str, Any]:
    os.environ["HERMES_YOLO_MODE"] = "1"
    os.environ["HERMES_ACCEPT_HOOKS"] = "1"
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            try:
                from hermes_cli.oneshot import _run_agent

                response = _run_agent(
                    prompt,
                    model=model,
                    provider=provider,
                    toolsets=[toolset],
                    use_config_toolsets=False,
                )
            except BaseException as exc:  # noqa: BLE001
                return {"exit_code": 1, "stdout": "", "stderr": str(exc)}
    if not (response or "").strip():
        return {"exit_code": 1, "stdout": "", "stderr": "Hermes produced no final response."}
    return {"exit_code": 0, "stdout": response, "stderr": ""}


def emit_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
