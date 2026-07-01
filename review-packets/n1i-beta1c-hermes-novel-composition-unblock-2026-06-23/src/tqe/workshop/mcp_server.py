"""S2I Tactical MCP adapter for Hermes.

This is a thin stdio MCP server over the existing M1.2 workshop dispatcher. It
does not own runtime semantics, confirmation, execution, filesystem access, or
raw data access. Hermes sees only the S2I product-path allowlist.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from tqe.workshop.m1_2 import (
    CallerProfile,
    ToolDispatchRequest,
    dispatch_model_visible,
)

SERVER_NAME = "priori_tactical_query_workshop"
OUTPUT_ROOT_ENV = "TQE_WORKSHOP_OUTPUT_ROOT"
DEFAULT_OUTPUT_ROOT = Path("artifacts/m1.2/workshop")

mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "Use these tools to inspect Priori tactical-query capabilities, submit "
        "experimental typed plans, validate bound interpretations, and inspect "
        "host-created results/replay handles. Host confirmation and execution "
        "are intentionally unavailable."
    ),
)


def output_root() -> Path:
    return Path(os.environ.get(OUTPUT_ROOT_ENV, str(DEFAULT_OUTPUT_ROOT)))


def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return dispatch_model_visible(
        ToolDispatchRequest(tool_name=tool_name, arguments=arguments),
        output_root=output_root(),
        caller_profile=CallerProfile.HERMES_S2I_MCP,
    )


@mcp.tool()
def list_capabilities() -> dict[str, Any]:
    """Return the Hermes-safe S2I capability context."""

    return call_tool("list_capabilities", {})


@mcp.tool()
def search_recipes(
    query: str,
    states: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search approved and experimental recipe summaries."""

    arguments: dict[str, Any] = {"query": query, "limit": limit}
    if states is not None:
        arguments["states"] = states
    return call_tool("search_recipes", arguments)


@mcp.tool()
def describe_capability(capability_name: str) -> dict[str, Any]:
    """Describe one exposed tool, primitive, relation, or operator."""

    return call_tool("describe_capability", {"capability_name": capability_name})


@mcp.tool()
def submit_query_plan(plan_document: dict[str, Any], source_label: str = "hermes_mcp") -> dict[str, Any]:
    """Store an experimental typed query document and return an opaque draft_plan_id."""

    return call_tool(
        "submit_query_plan",
        {"plan_document": plan_document, "source_label": source_label},
    )


@mcp.tool()
def validate_query_plan(draft_plan_id: str) -> dict[str, Any]:
    """Bind and boundary-check a submitted typed query plan."""

    return call_tool("validate_query_plan", {"draft_plan_id": draft_plan_id})


@mcp.tool()
def inspect_result(execution_id: str, result_id: str) -> dict[str, Any]:
    """Return predicate traces and requested evidence for a host-created result."""

    return call_tool("inspect_result", {"execution_id": execution_id, "result_id": result_id})


@mcp.tool()
def inspect_non_match(execution_id: str, target: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a known timestamp target against a host-created execution."""

    return call_tool("inspect_non_match", {"execution_id": execution_id, "target": target})


@mcp.tool()
def retrieve_replay_window(
    execution_id: str,
    result_id: str | None = None,
    target: dict[str, Any] | None = None,
    padding_seconds: float = 2.0,
) -> dict[str, Any]:
    """Materialize a bounded coordinate replay artifact for a host-created result or target."""

    return call_tool(
        "retrieve_replay_window",
        {
            "execution_id": execution_id,
            "result_id": result_id,
            "target": target,
            "padding_seconds": padding_seconds,
        },
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
