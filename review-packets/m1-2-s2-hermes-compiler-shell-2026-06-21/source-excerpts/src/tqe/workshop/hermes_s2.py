"""M1.2 S2 bounded Hermes compiler shell.

This module is deterministic test scaffolding for the Hermes client contract. It
does not call a model and does not widen the tool boundary. It records the
language-to-plan trace that a future model-backed Hermes instance must preserve.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tqe.workshop.m1_2 import (
    CallerProfile,
    DEFAULT_WORKSHOP_ROOT,
    ToolDispatchRequest,
    dispatch_model_visible,
    stable_hash,
    utc_now_iso,
    write_json,
)

APPROVED_M1_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
EXPERIMENTAL_CORRIDOR_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
TRACE_DIR = DEFAULT_WORKSHOP_ROOT / "hermes-traces"

UNSUPPORTED_CONCEPTS = {
    "body orientation": "No body-orientation primitive is exposed.",
    "orientation": "No body-orientation primitive is exposed.",
    "intent": "Intent is not observable in the current deterministic vocabulary.",
    "optimal": "Optimal-action claims are outside the approved claims.",
    "should": "Normative decision-quality claims are outside the approved claims.",
    "communication": "Communication is not represented in the tracking data.",
    "pass probability": "Pass-probability modelling is not available.",
    "video": "Video is outside the current dataset/tool boundary.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HermesCompileStatus(StrEnum):
    DRAFT_VALIDATED = "DRAFT_VALIDATED"
    EXISTING_RECIPE_SELECTED = "EXISTING_RECIPE_SELECTED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    CAPABILITY_GAP = "CAPABILITY_GAP"


class HermesCompileRequest(StrictModel):
    original_language: str = Field(min_length=1, max_length=1000)
    clarifications: list[str] = Field(default_factory=list)
    requester: str = Field(default="analyst", min_length=1, max_length=80)


class HermesCompileResponse(StrictModel):
    ok: bool
    status: HermesCompileStatus
    trace_id: str
    original_language: str
    interpretation: dict[str, Any]
    selected_recipe: dict[str, Any] | None = None
    draft_plan_id: str | None = None
    draft_plan_hash: str | None = None
    bound_plan_id: str | None = None
    bound_plan_hash: str | None = None
    validation_result: dict[str, Any] | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    capability_gaps: list[dict[str, str]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


def compile_hermes_request(
    request: HermesCompileRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> HermesCompileResponse:
    text = normalize_text(request.original_language)
    tool_calls: list[dict[str, Any]] = []
    capabilities = hermes_tool_call("list_capabilities", {}, tool_calls, output_root=output_root)

    gaps = unsupported_gaps(text)
    if gaps:
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CAPABILITY_GAP,
            trace_id=trace_id_for(request, "capability_gap", gaps),
            original_language=request.original_language,
            interpretation={
                "intent": "unsupported_tactical_request",
                "reason": "The request asks for concepts outside the exposed capability context.",
                "available_tool_count": len(capabilities.get("tools", [])),
            },
            capability_gaps=gaps,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if asks_for_block_shift(text):
        selected = trusted_recipe_summary(APPROVED_M1_PLAN_PATH, state="APPROVED")
        response = HermesCompileResponse(
            ok=True,
            status=HermesCompileStatus.EXISTING_RECIPE_SELECTED,
            trace_id=trace_id_for(request, "existing_recipe", selected),
            original_language=request.original_language,
            interpretation={
                "intent": "reuse_trusted_recipe",
                "summary": "Use the trusted approved ball-side block-shift recipe.",
                "requires_host_recipe_load": True,
                "automatic_execution": False,
            },
            selected_recipe=selected,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if ambiguous_support_request(text):
        questions = [
            "Should support mean an open progressive corridor from possession?",
            "How long may the support option take to appear?",
            "Should the receiver have to be inside the corridor, or is geometric availability enough?",
        ]
        response = HermesCompileResponse(
            ok=False,
            status=HermesCompileStatus.CLARIFICATION_REQUIRED,
            trace_id=trace_id_for(request, "clarification", questions),
            original_language=request.original_language,
            interpretation={
                "intent": "ambiguous_support_request",
                "reason": "The current vocabulary can measure possession anchors and progressive corridors, but support has multiple tactical meanings.",
                "automatic_execution": False,
            },
            clarification_questions=questions,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    if asks_for_progressive_corridor(text):
        hermes_tool_call(
            "describe_capability",
            {"capability_name": "geometric_progressive_corridor_from_anchor_set"},
            tool_calls,
            output_root=output_root,
        )
        plan_document = experimental_corridor_plan_for_request(request)
        submit = hermes_tool_call(
            "submit_query_plan",
            {"plan_document": plan_document, "source_label": "hermes_s2"},
            tool_calls,
            output_root=output_root,
        )
        validation = hermes_tool_call(
            "validate_query_plan",
            {"draft_plan_id": submit["draft_plan_id"]},
            tool_calls,
            output_root=output_root,
        )
        response = HermesCompileResponse(
            ok=bool(validation.get("ok")),
            status=HermesCompileStatus.DRAFT_VALIDATED,
            trace_id=trace_id_for(request, "draft_validated", validation),
            original_language=request.original_language,
            interpretation={
                "intent": "draft_experimental_progressive_corridor_query",
                "summary": "Detect possession anchors where a geometric progressive corridor becomes available.",
                "recipe_state": "EXPERIMENTAL",
                "automatic_execution": False,
                "allowed_claims": [
                    "The team had an active-ball possession anchor.",
                    "A geometric progressive corridor appeared under configured thresholds.",
                    "Replay coordinates come from canonical tracking frames.",
                ],
                "disallowed_claims": [
                    "Intent, optimality, pass probability, or video-backed claims.",
                ],
            },
            selected_recipe=trusted_recipe_summary(EXPERIMENTAL_CORRIDOR_PLAN_PATH, state="EXPERIMENTAL"),
            draft_plan_id=submit.get("draft_plan_id"),
            draft_plan_hash=submit.get("draft_plan_hash"),
            bound_plan_id=validation.get("bound_plan_id"),
            bound_plan_hash=validation.get("bound_plan_hash"),
            validation_result=validation,
            tool_calls=tool_calls,
        )
        persist_compile_trace(response, output_root=output_root)
        return response

    response = HermesCompileResponse(
        ok=False,
        status=HermesCompileStatus.CLARIFICATION_REQUIRED,
        trace_id=trace_id_for(request, "unclassified", text),
        original_language=request.original_language,
        interpretation={
            "intent": "unclassified_tactical_request",
            "reason": "The request did not clearly name a supported recipe or experimental corridor concept.",
            "automatic_execution": False,
        },
        clarification_questions=[
            "Do you want the approved ball-side block-shift recipe or the experimental progressive-corridor recipe?",
        ],
        tool_calls=tool_calls,
    )
    persist_compile_trace(response, output_root=output_root)
    return response


def hermes_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    *,
    output_root: Path,
) -> dict[str, Any]:
    payload = dispatch_model_visible(
        ToolDispatchRequest(tool_name=tool_name, arguments=arguments),
        output_root=output_root,
        caller_profile=CallerProfile.HERMES_S2,
    )
    tool_calls.append(
        {
            "tool_name": tool_name,
            "caller_profile": CallerProfile.HERMES_S2.value,
            "arguments_summary": summarize_arguments(arguments),
            "ok": payload.get("ok", True) is not False,
            "response_keys": sorted(payload.keys()),
            "error_code": payload.get("error_code"),
        }
    )
    return payload


def experimental_corridor_plan_for_request(request: HermesCompileRequest) -> dict[str, Any]:
    payload = read_json(EXPERIMENTAL_CORRIDOR_PLAN_PATH)
    payload = deepcopy(payload)
    payload["draft_plan"]["plan_id"] = "hermes_s2_progressive_corridor_experimental"
    payload["default_invocation"]["invocation_id"] = "hermes_s2_progressive_corridor"
    return payload


def trusted_recipe_summary(path: Path, *, state: Literal["APPROVED", "EXPERIMENTAL"]) -> dict[str, Any]:
    payload = read_json(path)
    recipe = payload["recipe"]
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "display_name": recipe["display_name"],
        "state": state,
        "output_classifications": recipe.get("output_classifications", []),
        "allowed_claims": recipe.get("allowed_claims", []),
        "limitations": recipe.get("limitations", []),
    }


def record_confirmed_execution_trace(
    *,
    compile_response: HermesCompileResponse,
    execution_authorization_id: str,
    execution: dict[str, Any],
    inspection: dict[str, Any],
    replay: dict[str, Any],
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "trace_kind": "hermes_confirmed_execution",
        "recorded_at": utc_now_iso(),
        "compile_trace_id": compile_response.trace_id,
        "original_language": compile_response.original_language,
        "clarification_turns": [],
        "selected_recipe": compile_response.selected_recipe,
        "draft_plan_id": compile_response.draft_plan_id,
        "draft_plan_hash": compile_response.draft_plan_hash,
        "bound_plan_id": compile_response.bound_plan_id,
        "bound_plan_hash": compile_response.bound_plan_hash,
        "validation_result": compile_response.validation_result,
        "human_confirmation_event": {
            "source": "host_manual",
            "execution_authorization_id": execution_authorization_id,
        },
        "execution_id": execution["execution_id"],
        "result_ids": [result["result_id"] for result in execution.get("results", [])],
        "tool_calls": compile_response.tool_calls,
        "post_execution": {
            "inspection_keys": sorted(inspection.keys()),
            "replay_window_id": replay.get("replay_window_id"),
        },
    }
    trace_id = "hermes_exec_" + stable_hash(payload)[:16]
    path = output_root / "hermes-traces" / f"{trace_id}.json"
    write_json(path, {"trace_id": trace_id, **payload})
    return {"trace_id": trace_id, **payload}


def persist_compile_trace(response: HermesCompileResponse, *, output_root: Path) -> None:
    path = output_root / "hermes-traces" / f"{response.trace_id}.json"
    write_json(path, response.model_dump(mode="json"))


def trace_id_for(request: HermesCompileRequest, outcome: str, payload: Any) -> str:
    return "hermes_" + stable_hash(
        {
            "original_language": request.original_language,
            "clarifications": request.clarifications,
            "requester": request.requester,
            "outcome": outcome,
            "payload": payload,
            "recorded_at": utc_now_iso(),
        }
    )[:16]


def summarize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in arguments.items():
        if key == "plan_document":
            summary[key] = {
                "recipe_id": value.get("recipe", {}).get("recipe_id") if isinstance(value, dict) else None,
                "plan_id": value.get("draft_plan", {}).get("plan_id") if isinstance(value, dict) else None,
                "status": value.get("draft_plan", {}).get("status") if isinstance(value, dict) else None,
            }
        else:
            summary[key] = value
    return summary


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def unsupported_gaps(text: str) -> list[dict[str, str]]:
    gaps = []
    for token, reason in UNSUPPORTED_CONCEPTS.items():
        if token in text:
            gaps.append({"concept": token, "reason": reason})
    return gaps


def asks_for_block_shift(text: str) -> bool:
    return "block shift" in text or ("ball side" in text and "shift" in text)


def asks_for_progressive_corridor(text: str) -> bool:
    return "corridor" in text or "passing lane" in text or "progressive lane" in text


def ambiguous_support_request(text: str) -> bool:
    return "support" in text and not asks_for_progressive_corridor(text)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
