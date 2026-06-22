"""Workbench Alpha host application service.

The browser talks to this HTTP service. This service calls the host-owned
workshop dispatcher directly; it is not an MCP server and does not expose the
Hermes adapter boundary to the browser.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import time
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tqe.runtime.ir import TacticalQueryDocument, stable_hash
from tqe.workshop.m1_2 import (
    CallerProfile,
    CapabilityGap,
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_WORKSHOP_ROOT,
    ExecuteQueryPlanRequest,
    ExecuteQueryPlanResponse,
    HostConfirmationResponse,
    InspectNonMatchRequest,
    InspectResultRequest,
    ReplayWindowRequest,
    SubmitQueryPlanRequest,
    ValidateQueryPlanRequest,
    describe_capability,
    execute_query_plan,
    host_confirm_bound_plan,
    inspect_non_match,
    inspect_result,
    list_capabilities,
    read_json,
    read_handle,
    replay_artifact_path,
    retrieve_replay_window,
    submit_query_plan,
    stable_tool_error_code,
    validate_query_plan,
    write_handle,
    write_json,
)

APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
CORRIDOR_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
DEFAULT_STATIC_ROOT = Path("apps/workbench-alpha/dist")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
HERMES_DB = HERMES_HOME / "state.db"
HERMES_WORKSHOP_ROOT = Path(os.environ.get("WORKBENCH_HERMES_WORKSHOP_ROOT", "artifacts/m1.2/workshop"))
HERMES_PROVIDER = os.environ.get("WORKBENCH_HERMES_PROVIDER", "openai-codex")
HERMES_MODEL = os.environ.get("WORKBENCH_HERMES_MODEL", "gpt-5.5")
HERMES_TOOLSET = os.environ.get("WORKBENCH_HERMES_TOOLSET", "priori_tactical")
HERMES_TIMEOUT_SECONDS = int(os.environ.get("WORKBENCH_HERMES_TIMEOUT_SECONDS", "240"))
HERMES_MCP_TOOL_NAMES = {
    "mcp_priori_tactical_list_capabilities",
    "mcp_priori_tactical_search_recipes",
    "mcp_priori_tactical_describe_capability",
    "mcp_priori_tactical_submit_query_plan",
    "mcp_priori_tactical_validate_query_plan",
    "mcp_priori_tactical_inspect_result",
    "mcp_priori_tactical_inspect_non_match",
    "mcp_priori_tactical_retrieve_replay_window",
}
HERMES_FORBIDDEN_TOOL_FRAGMENTS = {
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


class WorkbenchResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(WorkbenchResponseModel):
    ok: Literal[False]
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RecipeCardResponse(WorkbenchResponseModel):
    recipe_id: str
    recipe_version: str
    state: Literal["APPROVED", "EXPERIMENTAL", "USER_SAVED", "DEPRECATED"]
    display_name: str
    description: str
    allowed_claims: list[str]
    disallowed_claims: list[str]
    limitations: list[str]
    output_classifications: list[str]


class ServiceStatusResponse(WorkbenchResponseModel):
    name: str
    mcp_adapter: bool


class ModelStatusResponse(WorkbenchResponseModel):
    available: bool
    status: str
    message: str


class PresetResponse(WorkbenchResponseModel):
    preset_id: Literal["approved_block_shift", "experimental_corridor"]
    label: str
    recipe: RecipeCardResponse
    plan_hash: str


class CapabilitySummaryResponse(WorkbenchResponseModel):
    primitive_count: int
    relation_count: int
    operator_count: int
    tools: list[str]
    execute_tool_description: dict[str, Any]


class BootstrapResponse(WorkbenchResponseModel):
    ok: Literal[True]
    service: ServiceStatusResponse
    model: ModelStatusResponse
    presets: list[PresetResponse]
    capabilities: CapabilitySummaryResponse


class HealthResponse(WorkbenchResponseModel):
    ok: Literal[True]
    service: str
    mcp_adapter: bool


class PlanResponse(WorkbenchResponseModel):
    ok: Literal[True]
    recipe: RecipeCardResponse
    plan_document: dict[str, Any]
    plan_hash: str


class CapabilityGapResponse(WorkbenchResponseModel):
    concept: str
    reason: str


class InterpretResponse(WorkbenchResponseModel):
    ok: Literal[True]
    status: Literal["PLAN_INTERPRETED", "CLARIFICATION_REQUIRED", "CAPABILITY_GAP", "MODEL_UNAVAILABLE"]
    query: str | None = None
    message: str | None = None
    source: str | None = None
    agent_session_id: str | None = None
    draft_plan_id: str | None = None
    bound_plan_id: str | None = None
    bound_plan_hash: str | None = None
    recipe: RecipeCardResponse | None = None
    plan_document: dict[str, Any] | None = None
    plan_hash: str | None = None
    clarification_questions: list[str] | None = None
    clarification_codes: list[str] | None = None
    capability_gaps: list[CapabilityGapResponse] | None = None
    manual_available: bool | None = None


class ExecutionProgressResponse(WorkbenchResponseModel):
    ok: Literal[True]
    cache_key: str
    cache_status: Literal["HIT", "MISS"]
    message: str
    stages: list[str]


class SubmitValidateResponseEnvelope(WorkbenchResponseModel):
    ok: Literal[True]
    submit: dict[str, Any]
    validation: dict[str, Any]


class ConfirmationResponseEnvelope(WorkbenchResponseModel):
    ok: Literal[True]
    confirmation: dict[str, Any]


class ExecutionResponseEnvelope(WorkbenchResponseModel):
    ok: Literal[True]
    execution: dict[str, Any]
    cache: ExecutionProgressResponse


class ReplayEntityResponse(WorkbenchResponseModel):
    team_id: str
    team_role: str
    entity_id: str
    entity_type: str
    x_m: float
    y_m: float


class ReplayFrameResponse(WorkbenchResponseModel):
    frame_id: int
    timestamp_utc: str | None = None
    entities: list[ReplayEntityResponse]


class PitchResponse(WorkbenchResponseModel):
    length_m: float
    width_m: float
    coordinate_contract: str


class ReplayPayloadResponse(WorkbenchResponseModel):
    schema_version: str
    replay_window_id: str
    source_kind: Literal["result", "target"]
    source_id: str
    match_id: str
    period: str
    frame_rate_hz: float
    start_frame_id: int
    end_frame_id: int
    anchor_frame_id: int
    generated_at: str
    canonical_sources: dict[str, str]
    pitch: PitchResponse
    frames: list[ReplayFrameResponse]


class InspectResultResponseEnvelope(WorkbenchResponseModel):
    ok: Literal[True]
    inspection: dict[str, Any]
    replay_window: dict[str, Any]
    replay: ReplayPayloadResponse


class InspectTimestampResponseEnvelope(WorkbenchResponseModel):
    ok: Literal[True]
    inspection: dict[str, Any]
    replay_window: dict[str, Any]
    replay: ReplayPayloadResponse


WORKBENCH_RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "ErrorResponse": ErrorResponse,
    "HealthResponse": HealthResponse,
    "BootstrapResponse": BootstrapResponse,
    "PlanResponse": PlanResponse,
    "InterpretResponse": InterpretResponse,
    "SubmitValidateResponse": SubmitValidateResponseEnvelope,
    "ConfirmationResponse": ConfirmationResponseEnvelope,
    "ExecutionResponse": ExecutionResponseEnvelope,
    "ExecutionProgressResponse": ExecutionProgressResponse,
    "InspectResultResponse": InspectResultResponseEnvelope,
    "InspectTimestampResponse": InspectTimestampResponseEnvelope,
}

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

PLANNED_GAPS = {
    "pressure": ("pressure_change", "Pressure change is not in the current deterministic vocabulary."),
    "counterpress": ("pressure_change", "Counterpress queries need a future pressure-change capability."),
    "pressing": ("pressure_change", "Pressing queries need a future pressure-change capability."),
    "defensive line": (
        "defensive_line_model",
        "Defensive-line modelling is planned for the second tactical family.",
    ),
    "line break": (
        "controlled_line_break_episode",
        "Controlled line-break episodes are planned but not implemented.",
    ),
    "third man": ("support_arrival_relation", "Third-player support needs a support-arrival relation."),
    "third-man": ("support_arrival_relation", "Third-player support needs a support-arrival relation."),
    "lane occupancy": ("lane_occupancy", "General lane occupancy is planned but not implemented."),
    "overload": (
        "local_numerical_difference",
        "Local numerical difference is planned or may be folded into support arrival.",
    ),
}


def json_response(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")


def ok(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, **(payload or {})}


def error_response(code: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False, "error_code": code, "message": message, "details": details or {}}


PUBLIC_ERROR_MESSAGES = {
    "REQUEST_SCHEMA_INVALID": "Request payload does not match the API contract.",
    "UNKNOWN_HANDLE": "Requested handle is unavailable.",
    "NO_REPLAY_WINDOW": "No replay window is available for that request.",
    "EXECUTION_NOT_CONFIRMED": "Execution requires host-generated confirmation authorization.",
    "CAPABILITY_GAP": "Requested capability is unavailable through this API.",
    "PLAN_NOT_FOUND": "Requested plan was not found.",
    "INTERNAL_ERROR": "Internal host service error.",
}


def public_error_message(code: str) -> str:
    return PUBLIC_ERROR_MESSAGES.get(code, "Request could not be completed.")


def validate_public_response(model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = WORKBENCH_RESPONSE_MODELS[model_name]
    return model.model_validate(payload).model_dump(mode="json")


def plan_for_recipe(recipe_id: str) -> dict[str, Any]:
    if recipe_id == "ball_side_block_shift_v1":
        return read_json(APPROVED_PLAN_PATH)
    if recipe_id == "possession_corridor_availability_v1":
        return read_json(CORRIDOR_PLAN_PATH)
    raise ValueError(f"Unsupported recipe_id: {recipe_id}")


def plan_path_for_preset(preset_id: str | None, selected_recipe_id: str | None) -> Path | None:
    key = (preset_id or selected_recipe_id or "").strip()
    if key in {"approved_block_shift", "ball_side_block_shift_v1"}:
        return APPROVED_PLAN_PATH
    if key in {"experimental_corridor", "possession_corridor_availability_v1"}:
        return CORRIDOR_PLAN_PATH
    return None


def load_plan_from_path(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    TacticalQueryDocument.model_validate(payload)
    return payload


def host_owned_plan_document(plan_document: dict[str, Any]) -> TacticalQueryDocument:
    candidate = TacticalQueryDocument.model_validate(plan_document)
    if (
        candidate.recipe.recipe_id == "ball_side_block_shift_v1"
        and candidate.draft_plan.status == "approved"
    ):
        return TacticalQueryDocument.model_validate(load_plan_from_path(APPROVED_PLAN_PATH))
    return candidate


def normalized(text: str) -> str:
    return " ".join(text.lower().strip().split())


def unsupported_gaps(text: str) -> list[dict[str, str]]:
    gaps = []
    for token, reason in UNSUPPORTED_CONCEPTS.items():
        if token in text:
            gaps.append({"concept": token, "reason": reason})
    seen_codes = set()
    for token, (code, reason) in PLANNED_GAPS.items():
        if token in text and code not in seen_codes:
            gaps.append({"concept": code, "reason": reason})
            seen_codes.add(code)
    return gaps


def needs_support_clarification(text: str, clarifications: list[str]) -> bool:
    if clarifications:
        return False
    if "support" not in text and "second runner" not in text and "teammate" not in text:
        return False
    return "corridor" not in text and "progressive lane" not in text and "passing lane" not in text


def infer_plan_path(query: str) -> Path | None:
    text = normalized(query)
    if "corridor" in text or "progressive lane" in text or "passing lane" in text:
        return CORRIDOR_PLAN_PATH
    if "block shift" in text:
        return APPROVED_PLAN_PATH
    if "ball side" in text and ("shift" in text or "defending block" in text or "block" in text):
        return APPROVED_PLAN_PATH
    if "wide" in text and "defending" in text and "shift" in text:
        return APPROVED_PLAN_PATH
    return None


def recipe_card(plan_document: dict[str, Any], state: str) -> dict[str, Any]:
    recipe = plan_document["recipe"]
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "state": state,
        "display_name": recipe["display_name"],
        "description": recipe["description"],
        "allowed_claims": recipe.get("allowed_claims", []),
        "disallowed_claims": recipe.get("disallowed_claims", []),
        "limitations": recipe.get("limitations", []),
        "output_classifications": recipe.get("output_classifications", []),
    }


def hermes_enabled() -> bool:
    return os.environ.get("WORKBENCH_HERMES_ENABLED") == "1"


def hermes_unavailable(query: str, message: str | None = None) -> dict[str, Any]:
    return ok(
        {
            "status": "MODEL_UNAVAILABLE",
            "query": query,
            "message": message or "Hermes frontier interpretation is not connected in this Workbench process. Manual mode remains available.",
            "source": "hermes_frontier_unavailable",
            "manual_available": True,
        }
    )


def hermes_interpret_request(query: str) -> dict[str, Any]:
    hermes = shutil.which("hermes")
    if not hermes:
        return hermes_unavailable(query, "Hermes executable was not found. Manual mode remains available.")
    if not HERMES_DB.exists():
        return hermes_unavailable(query, "Hermes session store was not found. Manual mode remains available.")
    surface = hermes_tool_surface(hermes)
    if not surface["safe"]:
        return hermes_unavailable(
            query,
            "Hermes did not expose the frozen priori_tactical-only tool surface. Manual mode remains available.",
        )
    started_at = newest_hermes_session_started_at()
    completed = subprocess.run(
        [
            hermes,
            "--provider",
            HERMES_PROVIDER,
            "--model",
            HERMES_MODEL,
            "--toolsets",
            HERMES_TOOLSET,
            "--oneshot",
            hermes_interpret_prompt(query),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=HERMES_TIMEOUT_SECONDS,
        env={**os.environ, "HERMES_HOME": str(HERMES_HOME), "CODEX_HOME": os.environ.get("CODEX_HOME", "/Users/luisrevilla/.codex")},
    )
    session = newest_hermes_session_after(started_at)
    final = parse_final_json(completed.stdout)
    if completed.returncode != 0 or not final:
        return hermes_unavailable(
            query,
            "Hermes did not return a valid structured interpretation. Manual mode remains available.",
        )
    return hermes_final_to_interpretation(query, final, session)


def hermes_tool_surface(hermes: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            hermes,
            "--provider",
            HERMES_PROVIDER,
            "--model",
            HERMES_MODEL,
            "--toolsets",
            HERMES_TOOLSET,
            "--oneshot",
            "Return only a JSON array of exact tool names you can call.",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
        env={**os.environ, "HERMES_HOME": str(HERMES_HOME), "CODEX_HOME": os.environ.get("CODEX_HOME", "/Users/luisrevilla/.codex")},
    )
    names = parse_tool_name_list(completed.stdout)
    normalized = {name.removeprefix("functions.") for name in names}
    forbidden = sorted(
        name
        for name in normalized
        if any(fragment in name.lower() for fragment in HERMES_FORBIDDEN_TOOL_FRAGMENTS)
    )
    return {
        "safe": completed.returncode == 0 and HERMES_MCP_TOOL_NAMES.issubset(normalized) and not forbidden,
        "tool_names": sorted(normalized),
        "forbidden": forbidden,
    }


def parse_tool_name_list(text: str) -> list[str]:
    match = re.search(r"\[.*\]", text.strip(), flags=re.S)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def hermes_interpret_prompt(query: str) -> str:
    return f"""
You are the Priori M1.2 Integrated Alpha tactical query interpreter.

Use only the priori_tactical MCP tools. Do not use filesystem, terminal, Python,
SQL, raw coordinate dumps, host confirmation, or execution. Stop before
execution. If the request is supported, either select an approved recipe or
author an EXPERIMENTAL typed plan through submit_query_plan and validate it. If
the request is ambiguous, ask for clarification. If unsupported, report stable
capability gaps.

Return only one JSON object:
{{
  "outcome": "select_recipe" | "draft" | "clarify" | "capability_gap",
  "recipe_id": string | null,
  "draft_plan_id": string | null,
  "bound_plan_id": string | null,
  "bound_plan_hash": string | null,
  "clarification_questions": string[],
  "clarification_dimensions": string[],
  "capability_gaps": string[],
  "stopped_before_execution": true,
  "notes": string
}}

Tactical request:
{query}
""".strip()


def parse_final_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text.strip(), flags=re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def hermes_final_to_interpretation(query: str, final: dict[str, Any], session: dict[str, Any] | None) -> dict[str, Any]:
    outcome = normalize_outcome(final.get("outcome"))
    session_id = str(session.get("id")) if session else None
    base = {
        "query": query,
        "source": "hermes_frontier_agent",
        "agent_session_id": session_id,
        "draft_plan_id": final.get("draft_plan_id"),
        "bound_plan_id": final.get("bound_plan_id"),
        "bound_plan_hash": final.get("bound_plan_hash"),
        "manual_available": True,
    }
    if outcome == "clarify":
        questions = [str(item) for item in final.get("clarification_questions") or [] if str(item).strip()]
        dimensions = [str(item).upper().replace(" ", "_") for item in final.get("clarification_dimensions") or [] if str(item).strip()]
        return ok(
            {
                **base,
                "status": "CLARIFICATION_REQUIRED",
                "clarification_questions": questions or ["Please clarify the tactical definition before execution."],
                "clarification_codes": dimensions or ["TACTICAL_DEFINITION"],
            }
        )
    if outcome == "capability_gap":
        gaps = [{"concept": str(item), "reason": "Hermes reported this capability is outside the frozen tool boundary."} for item in final.get("capability_gaps") or []]
        return ok(
            {
                **base,
                "status": "CAPABILITY_GAP",
                "capability_gaps": gaps or [{"concept": "unsupported_request", "reason": "Hermes could not map the request to the frozen tactical capability set."}],
            }
        )
    if outcome == "select_recipe":
        recipe_id = str(final.get("recipe_id") or "")
        try:
            plan_document = plan_for_recipe(recipe_id)
        except ValueError:
            return hermes_unavailable(query, "Hermes selected an unknown recipe. Manual mode remains available.")
        state = "APPROVED" if recipe_id == "ball_side_block_shift_v1" else "EXPERIMENTAL"
        return ok(
            {
                **base,
                "status": "PLAN_INTERPRETED",
                "recipe": recipe_card(plan_document, state),
                "plan_document": plan_document,
                "plan_hash": stable_hash(plan_document),
            }
        )
    if outcome == "draft":
        bound_plan_id = str(final.get("bound_plan_id") or "")
        plan_document = hermes_bound_plan_document(bound_plan_id)
        if plan_document is None:
            return hermes_unavailable(query, "Hermes validated a draft but the host could not recover its bound plan handle.")
        return ok(
            {
                **base,
                "status": "PLAN_INTERPRETED",
                "recipe": recipe_card(plan_document, "EXPERIMENTAL"),
                "plan_document": plan_document,
                "plan_hash": stable_hash(plan_document),
            }
        )
    return hermes_unavailable(query, "Hermes returned an unsupported interpretation outcome. Manual mode remains available.")


def normalize_outcome(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "existing_recipe_selected": "select_recipe",
        "recipe_selected": "select_recipe",
        "draft_validated": "draft",
        "plan_interpreted": "draft",
        "clarification_required": "clarify",
    }
    return aliases.get(text, text)


def hermes_bound_plan_document(bound_plan_id: str) -> dict[str, Any] | None:
    if not bound_plan_id:
        return None
    for root in (HERMES_WORKSHOP_ROOT, DEFAULT_WORKSHOP_ROOT):
        try:
            record = read_handle("bound-plans", bound_plan_id, output_root=root)
        except CapabilityGap:
            continue
        document = record.get("document")
        if isinstance(document, dict):
            return document
    return None


def newest_hermes_session_started_at() -> float:
    row = hermes_db_one("select started_at from sessions order by started_at desc limit 1", ())
    return float(row["started_at"]) if row else 0.0


def newest_hermes_session_after(started_at: float) -> dict[str, Any] | None:
    return hermes_db_one(
        "select id, source, model, model_config, started_at, ended_at, tool_call_count, message_count, input_tokens, output_tokens, reasoning_tokens, estimated_cost_usd from sessions where started_at >= ? order by started_at desc limit 1",
        (started_at,),
    )


def hermes_db_one(query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    if not HERMES_DB.exists():
        return None
    with sqlite3.connect(HERMES_DB, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def interpret_request(payload: dict[str, Any], *, output_root: Path = DEFAULT_WORKSHOP_ROOT) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    mode = str(payload.get("mode") or "manual")
    clarifications = [str(item) for item in payload.get("clarifications") or [] if str(item).strip()]
    selected_recipe_id = payload.get("selected_recipe_id")
    preset_id = payload.get("preset_id")
    if mode == "model":
        if not hermes_enabled():
            return hermes_unavailable(query)
        return hermes_interpret_request(query)

    text = normalized(query)
    gaps = unsupported_gaps(text)
    if gaps:
        return ok(
            {
                "status": "CAPABILITY_GAP",
                "query": query,
                "source": "manual_host_interpreter",
                "capability_gaps": gaps,
                "message": "The request contains concepts outside the current deterministic capability set.",
            }
        )
    if needs_support_clarification(text, clarifications):
        return ok(
            {
                "status": "CLARIFICATION_REQUIRED",
                "query": query,
                "source": "manual_host_interpreter",
                "clarification_questions": [
                    "Should support mean a progressive corridor, a nearby teammate, or a distinct lane option?",
                    "What time window should count as support arriving after the anchor?",
                ],
                "clarification_codes": ["SUPPORT_DEFINITION", "TIME_WINDOW"],
            }
        )

    path = plan_path_for_preset(
        str(preset_id) if preset_id is not None else None,
        str(selected_recipe_id) if selected_recipe_id is not None else None,
    )
    if path is None:
        path = infer_plan_path(query)
    if path is None:
        return ok(
            {
                "status": "CLARIFICATION_REQUIRED",
                "query": query,
                "source": "manual_host_interpreter",
                "clarification_questions": [
                    "Select the approved block-shift recipe or the experimental corridor preset.",
                ],
                "clarification_codes": ["RECIPE_SELECTION"],
            }
        )

    plan_document = load_plan_from_path(path)
    state = "APPROVED" if path == APPROVED_PLAN_PATH else "EXPERIMENTAL"
    return ok(
        {
            "status": "PLAN_INTERPRETED",
            "query": query,
            "source": "manual_host_interpreter",
            "recipe": recipe_card(plan_document, state),
            "plan_document": plan_document,
            "plan_hash": stable_hash(plan_document),
        }
    )


def replay_payload(replay_window_id: str, *, output_root: Path) -> dict[str, Any]:
    return sanitize_replay_payload(read_json(replay_artifact_path(replay_window_id, output_root=output_root)))


def sanitize_replay_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("plan_path", None)
    public["canonical_sources"] = public_canonical_sources(payload.get("canonical_sources"))
    return public


def public_canonical_sources(raw: Any) -> dict[str, str]:
    sources = raw if isinstance(raw, dict) else {}
    public: dict[str, str] = {}
    for key, value in sources.items():
        public[str(key)] = f"canonical_source:{sha256(str(value).encode('utf-8')).hexdigest()[:16]}"
    return public


def canonical_data_hash() -> str:
    entries: list[dict[str, Any]] = []
    root = DEFAULT_CANONICAL_ROOT
    if root.exists():
        for path in sorted(root.rglob("*.parquet")):
            stat = path.stat()
            entries.append(
                {
                    "logical_id": path.relative_to(root).as_posix(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
    return stable_hash({"canonical_root": "DEFAULT_CANONICAL_ROOT", "entries": entries})


def cache_request_identity(request: ExecuteQueryPlanRequest, *, output_root: Path) -> dict[str, Any]:
    bound_record = read_handle("bound-plans", request.bound_plan_id, output_root=output_root)
    document = bound_record.get("document") or {}
    invocation = document.get("default_invocation") if isinstance(document, dict) else {}
    return {
        "schema_version": "1.0",
        "runtime_version": "workbench_alpha_execution_cache_v1",
        "canonical_data_hash": canonical_data_hash(),
        "bound_plan_hash": bound_record.get("bound_plan_hash"),
        "scope": {
            "match_ids": invocation.get("match_ids") if isinstance(invocation, dict) else None,
            "periods": invocation.get("periods") if isinstance(invocation, dict) else None,
            "perspective_team_role": invocation.get("perspective_team_role") if isinstance(invocation, dict) else None,
        },
        "parameters": invocation.get("parameters") if isinstance(invocation, dict) else None,
        "result_limit": request.result_limit,
    }


def assert_execution_authorized(request: ExecuteQueryPlanRequest, *, output_root: Path) -> None:
    bound_record = read_handle("bound-plans", request.bound_plan_id, output_root=output_root)
    auth_record = read_handle("authorizations", request.execution_authorization_id, output_root=output_root)
    if auth_record.get("bound_plan_id") != request.bound_plan_id:
        raise CapabilityGap("execution authorization does not match bound_plan_id")
    if auth_record.get("bound_plan_hash") != bound_record.get("bound_plan_hash"):
        raise CapabilityGap("execution authorization does not match bound_plan_hash")


def execution_cache_key(request: ExecuteQueryPlanRequest, *, output_root: Path) -> str:
    return stable_hash(cache_request_identity(request, output_root=output_root))


def execution_cache_path(cache_key: str, *, output_root: Path) -> Path:
    base = (output_root / "execution-cache").resolve()
    path = (base / f"{cache_key}.json").resolve()
    if base not in path.parents:
        raise CapabilityGap("Execution cache path escapes storage root.")
    return path


def execution_cache_status(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    request = ExecuteQueryPlanRequest.model_validate(payload)
    assert_execution_authorized(request, output_root=output_root)
    cache_key = execution_cache_key(request, output_root=output_root)
    hit = execution_cache_path(cache_key, output_root=output_root).exists()
    return ok(
        {
            "cache_key": cache_key,
            "cache_status": "HIT" if hit else "MISS",
            "message": "Cached execution is available." if hit else "Cache miss; deterministic runtime will execute on confirmation.",
            "stages": execution_progress_stages(hit),
        }
    )


def execution_progress_stages(cache_hit: bool) -> list[str]:
    if cache_hit:
        return ["authorization_checked", "cache_hit", "execution_handle_materialized"]
    return ["authorization_checked", "cache_miss", "deterministic_runtime_execution", "cache_record_written"]


def cached_execute_query_plan(request: ExecuteQueryPlanRequest, *, output_root: Path) -> dict[str, Any]:
    assert_execution_authorized(request, output_root=output_root)
    cache_key = execution_cache_key(request, output_root=output_root)
    cache_path = execution_cache_path(cache_key, output_root=output_root)
    if cache_path.exists():
        cached = read_json(cache_path)
        execution_record = cached.get("execution_record")
        if not isinstance(execution_record, dict):
            raise CapabilityGap("Invalid execution cache record.")
        write_handle("executions", str(execution_record["execution_id"]), execution_record, output_root=output_root)
        response = ExecuteQueryPlanResponse.model_validate(cached["response"]).model_dump(mode="json")
        return {
            "execution": response,
            "cache": {
                "ok": True,
                "cache_key": cache_key,
                "cache_status": "HIT",
                "message": "Returned cached deterministic execution.",
                "stages": execution_progress_stages(True),
            },
        }
    execution = execute_query_plan(request, output_root=output_root)
    execution_record = read_handle("executions", execution.execution_id, output_root=output_root)
    cache_payload = {
        "schema_version": "1.0",
        "cache_key": cache_key,
        "cache_identity": cache_request_identity(request, output_root=output_root),
        "response": execution.model_dump(mode="json"),
        "execution_record": execution_record,
    }
    write_json(cache_path, cache_payload)
    return {
        "execution": execution.model_dump(mode="json"),
        "cache": {
            "ok": True,
            "cache_key": cache_key,
            "cache_status": "MISS",
            "message": "Executed deterministic runtime and stored host-owned cache record.",
            "stages": execution_progress_stages(False),
        },
    }


def result_with_replay(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    padding_seconds = float(payload.get("padding_seconds", 2.0))
    inspected = inspect_result(
        InspectResultRequest.model_validate(
            {
                "execution_id": payload.get("execution_id"),
                "result_id": payload.get("result_id"),
            }
        ),
        output_root=output_root,
    )
    replay_summary = retrieve_replay_window(
        ReplayWindowRequest(
            execution_id=inspected.execution_id,
            result_id=payload["result_id"],
            padding_seconds=padding_seconds,
        ),
        output_root=output_root,
    )
    return ok(
        {
            "inspection": inspected.model_dump(mode="json"),
            "replay_window": replay_summary.model_dump(mode="json"),
            "replay": replay_payload(replay_summary.replay_window_id, output_root=output_root),
        }
    )


def timestamp_inspection(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    padding_seconds = float(payload.get("padding_seconds", 2.0))
    request = InspectNonMatchRequest.model_validate(
        {
            "execution_id": payload.get("execution_id"),
            "target": payload.get("target"),
        }
    )
    inspection = inspect_non_match(request, output_root=output_root)
    replay_summary = retrieve_replay_window(
        ReplayWindowRequest(
            execution_id=request.execution_id,
            target=request.target,
            padding_seconds=padding_seconds,
        ),
        output_root=output_root,
    )
    return ok(
        {
            "inspection": inspection.model_dump(mode="json"),
            "replay_window": replay_summary.model_dump(mode="json"),
            "replay": replay_payload(replay_summary.replay_window_id, output_root=output_root),
        }
    )


class WorkbenchServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler: type[BaseHTTPRequestHandler],
        *,
        static_root: Path,
        output_root: Path,
    ) -> None:
        super().__init__(server_address, request_handler)
        self.static_root = static_root.resolve()
        self.output_root = output_root


class WorkbenchHandler(BaseHTTPRequestHandler):
    server: WorkbenchServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_response(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path: str) -> None:
        route = path if path != "/" else "/index.html"
        relative = route.lstrip("/")
        target = (self.server.static_root / relative).resolve()
        if self.server.static_root not in target.parents and target != self.server.static_root:
            self.send_json(error_response("PATH_ESCAPE", "Static path escapes root."), HTTPStatus.BAD_REQUEST)
            return
        if not target.exists() or target.is_dir():
            if route != "/" and Path(relative).suffix:
                self.send_json(error_response("STATIC_NOT_FOUND", "Static asset was not found."), HTTPStatus.NOT_FOUND)
                return
            target = self.server.static_root / "index.html"
        if not target.exists():
            self.send_json(
                error_response(
                    "STATIC_BUILD_MISSING",
                    "Workbench static build is missing. Run npm --prefix apps/workbench-alpha run build.",
                ),
                HTTPStatus.NOT_FOUND,
            )
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(ok({"service": "workbench_alpha_host", "mcp_adapter": False}))
            return
        if parsed.path == "/api/bootstrap":
            self.send_json(self.bootstrap())
            return
        if parsed.path == "/api/plan":
            query = parse_qs(parsed.query)
            recipe_id = (query.get("recipe_id") or [""])[0]
            try:
                plan = plan_for_recipe(recipe_id)
                state = "APPROVED" if recipe_id == "ball_side_block_shift_v1" else "EXPERIMENTAL"
                self.send_json(ok({"recipe": recipe_card(plan, state), "plan_document": plan, "plan_hash": stable_hash(plan)}))
            except Exception:
                self.send_json(error_response("PLAN_NOT_FOUND", public_error_message("PLAN_NOT_FOUND")), HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/api/"):
            self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
            return
        self.send_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_body()
            if parsed.path == "/api/interpret":
                self.send_json(interpret_request(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/execution-cache-status":
                self.send_json(execution_cache_status(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/submit-validate":
                plan_document = host_owned_plan_document(payload["plan_document"])
                submitted = submit_query_plan(
                    SubmitQueryPlanRequest(plan_document=plan_document, source_label="workbench_alpha"),
                    output_root=self.server.output_root,
                    caller_profile=CallerProfile.HOST_MANUAL,
                )
                validation = validate_query_plan(
                    ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
                    output_root=self.server.output_root,
                    caller_profile=CallerProfile.HOST_MANUAL,
                )
                self.send_json(
                    ok(
                        {
                            "submit": submitted.model_dump(mode="json"),
                            "validation": validation.model_dump(mode="json"),
                        }
                    )
                )
            elif parsed.path == "/api/confirm":
                confirmation: HostConfirmationResponse = host_confirm_bound_plan(
                    str(payload["bound_plan_id"]),
                    reviewer=str(payload.get("reviewer") or "workbench_alpha_host"),
                    output_root=self.server.output_root,
                )
                self.send_json(ok({"confirmation": confirmation.model_dump(mode="json")}))
            elif parsed.path == "/api/execute":
                executed = cached_execute_query_plan(
                    ExecuteQueryPlanRequest.model_validate(payload),
                    output_root=self.server.output_root,
                )
                self.send_json(validate_public_response("ExecutionResponse", ok(executed)))
            elif parsed.path == "/api/inspect-result":
                self.send_json(result_with_replay(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/inspect-timestamp":
                self.send_json(timestamp_inspection(payload, output_root=self.server.output_root))
            else:
                self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
        except (KeyError, ValueError, ValidationError):
            self.send_json(
                error_response(
                    "REQUEST_SCHEMA_INVALID",
                    public_error_message("REQUEST_SCHEMA_INVALID"),
                ),
                HTTPStatus.BAD_REQUEST,
            )
        except CapabilityGap as exc:
            code = stable_tool_error_code(exc)
            self.send_json(
                error_response(code, public_error_message(code)),
                HTTPStatus.FORBIDDEN,
            )
        except Exception:
            self.send_json(
                error_response("INTERNAL_ERROR", public_error_message("INTERNAL_ERROR")),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def bootstrap(self) -> dict[str, Any]:
        approved_plan = load_plan_from_path(APPROVED_PLAN_PATH)
        corridor_plan = load_plan_from_path(CORRIDOR_PLAN_PATH)
        context = list_capabilities(CallerProfile.HOST_MANUAL)
        return ok(
            {
                "service": {
                    "name": "workbench_alpha_host",
                    "mcp_adapter": False,
                },
                "model": {
                    "available": hermes_enabled() and shutil.which("hermes") is not None,
                    "status": "HERMES_FRONTIER_READY" if hermes_enabled() and shutil.which("hermes") is not None else "MODEL_UNAVAILABLE",
                    "message": (
                        "Hermes frontier interpretation is available through the host service."
                        if hermes_enabled() and shutil.which("hermes") is not None
                        else "Manual mode is active; Hermes frontier interpretation is disabled for this Workbench process."
                    ),
                },
                "presets": [
                    {
                        "preset_id": "approved_block_shift",
                        "label": "Approved block shift",
                        "recipe": recipe_card(approved_plan, "APPROVED"),
                        "plan_hash": stable_hash(approved_plan),
                    },
                    {
                        "preset_id": "experimental_corridor",
                        "label": "Experimental corridor",
                        "recipe": recipe_card(corridor_plan, "EXPERIMENTAL"),
                        "plan_hash": stable_hash(corridor_plan),
                    },
                ],
                "capabilities": {
                    "primitive_count": len(context.primitives),
                    "relation_count": len(context.relations),
                    "operator_count": len(context.operators),
                    "tools": [tool.name for tool in context.tools],
                    "execute_tool_description": describe_capability(
                        "execute_query_plan",
                        CallerProfile.HOST_MANUAL,
                    ),
                },
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Workbench Alpha host app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_WORKSHOP_ROOT)
    args = parser.parse_args()
    server = WorkbenchServer(
        (args.host, args.port),
        WorkbenchHandler,
        static_root=args.static_root,
        output_root=args.output_root,
    )
    print(f"Workbench Alpha host service: http://{args.host}:{args.port}")
    print(f"Static root: {args.static_root}")
    print(f"Output root: {args.output_root}")
    server.serve_forever()


if __name__ == "__main__":
    main()
