"""Workbench Alpha host application service.

The browser talks to this HTTP service. This service calls the host-owned
workshop dispatcher directly; it is not an MCP server and does not expose the
Hermes adapter boundary to the browser.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime
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
    DEFAULT_RAW_ROOT,
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

REPO_ROOT = Path(__file__).resolve().parents[3]
APPROVED_PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
CORRIDOR_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
DEFAULT_STATIC_ROOT = Path("apps/workbench-alpha/dist")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
HERMES_DB = HERMES_HOME / "state.db"
HERMES_WORKSHOP_ROOT = Path(os.environ.get("WORKBENCH_HERMES_WORKSHOP_ROOT", "artifacts/m1.2/workshop"))
HERMES_PROVIDER = os.environ.get("WORKBENCH_HERMES_PROVIDER", "openai-codex")
HERMES_MODEL = os.environ.get("WORKBENCH_HERMES_MODEL", "gpt-5.5")
HERMES_TOOLSET = os.environ.get("WORKBENCH_HERMES_TOOLSET", "mcp-priori_tactical")
HERMES_TIMEOUT_SECONDS = int(os.environ.get("WORKBENCH_HERMES_TIMEOUT_SECONDS", "240"))
N1E_RUNNER_ENABLED = os.environ.get("ENABLE_N1E_RUNNER", "").strip() == "1"
N1E_RUN_TOKEN = os.environ.get("N1E_RUN_TOKEN", "").strip()
N1E_RESULT_LIMIT = int(os.environ.get("N1E_RESULT_LIMIT", "25"))
DEMO_ACCESS_TOKEN = os.environ.get("DEMO_ACCESS_TOKEN", "").strip()
DEMO_ACCESS_QUERY_TOKEN_ENABLED = os.environ.get("DEMO_ACCESS_QUERY_TOKEN_ENABLED", "").strip() == "1"
WORKBENCH_PREWARM_EXECUTION_CACHE = os.environ.get("WORKBENCH_PREWARM_EXECUTION_CACHE", "").strip() == "1"
WORKBENCH_PREWARM_RESULT_LIMIT = int(os.environ.get("WORKBENCH_PREWARM_RESULT_LIMIT", "3"))
WORKBENCH_PREWARM_RECIPE_IDS = tuple(
    recipe_id.strip()
    for recipe_id in os.environ.get(
        "WORKBENCH_PREWARM_RECIPE_IDS",
        "ball_side_block_shift_v1,possession_corridor_availability_v1",
    ).split(",")
    if recipe_id.strip()
)
KNOWLEDGE_PACK_PATH = Path(os.environ.get("TQE_KNOWLEDGE_PACK_PATH", "generated/tactical-knowledge-pack.json"))
EXPECTED_KNOWLEDGE_PACK_SHA256 = os.environ.get("TQE_EXPECTED_KNOWLEDGE_PACK_SHA256", "").strip()
DATA_MANIFEST_PATH = Path(os.environ.get("TQE_DATA_MANIFEST_PATH", "config/deploy/demo-data-manifest.json"))
CACHE_ROOT = Path(os.environ["TQE_CACHE_ROOT"]) if os.environ.get("TQE_CACHE_ROOT") else None
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
N1E_JOB_THREADS: dict[str, threading.Thread] = {}
N1E_JOB_THREADS_LOCK = threading.Lock()
N1F_CLARIFICATION_ANSWER: dict[str, Any] = {
    "match_ids": ["J03WOY"],
    "periods": ["firstHalf"],
    "perspective_team_role": "home",
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


class MatchSummaryResponse(WorkbenchResponseModel):
    match_id: str
    match_title: str
    home_team: str
    away_team: str
    result: str | None = None
    match_day: str | None = None
    kickoff_time_utc: str | None = None


class MatchLibraryResponse(WorkbenchResponseModel):
    ok: Literal[True]
    perspective_team: str
    default_match_ids: list[str]
    matches: list[MatchSummaryResponse]


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


ProvenanceSource = Literal[
    "REVIEWED_RECIPE",
    "MANUAL_PRESET",
    "HERMES_RECIPE_SELECTION",
    "HERMES_NOVEL_COMPOSITION",
    "DETERMINISTIC_REPAIR",
    "CAPABILITY_GAP",
    "MODEL_UNAVAILABLE",
]


class InterpretResponse(WorkbenchResponseModel):
    ok: Literal[True]
    status: Literal["PLAN_INTERPRETED", "CLARIFICATION_REQUIRED", "CAPABILITY_GAP", "MODEL_UNAVAILABLE"]
    provenance_source: ProvenanceSource
    query: str | None = None
    message: str | None = None
    source: str | None = None
    agent_session_id: str | None = None
    model_session_id: str | None = None
    draft_plan_id: str | None = None
    draft_plan_hash: str | None = None
    bound_plan_id: str | None = None
    bound_plan_hash: str | None = None
    recipe_id: str | None = None
    recipe: RecipeCardResponse | None = None
    plan_document: dict[str, Any] | None = None
    plan_hash: str | None = None
    clarification_questions: list[str] | None = None
    clarification_codes: list[str] | None = None
    capability_gaps: list[CapabilityGapResponse] | None = None
    manual_available: bool | None = None
    repair_applied: bool = False
    fallback_reason: str | None = None


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
    "MatchLibraryResponse": MatchLibraryResponse,
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
    "body angle": "No body-orientation primitive is exposed.",
    "body shape": "No body-orientation primitive is exposed.",
    "hip angle": "No body-orientation primitive is exposed.",
    "torso": "No body-orientation primitive is exposed.",
    "head check": "Scanning/head-check evidence is not represented in the current tracking data.",
    "head checks": "Scanning/head-check evidence is not represented in the current tracking data.",
    "scanning": "Scanning/head-check evidence is not represented in the current tracking data.",
    "scan": "Scanning/head-check evidence is not represented in the current tracking data.",
    "glance": "Scanning/head-check evidence is not represented in the current tracking data.",
    "intent": "Intent is not observable in the current deterministic vocabulary.",
    "intended": "Intent is not observable in the current deterministic vocabulary.",
    "meant to do": "Intent is not observable in the current deterministic vocabulary.",
    "meant to find": "Intent is not observable in the current deterministic vocabulary.",
    "optimal": "Optimal-action claims are outside the approved claims.",
    "best pass": "Optimal-action claims are outside the approved claims.",
    "should": "Normative decision-quality claims are outside the approved claims.",
    "communication": "Communication is not represented in the tracking data.",
    "pass probability": "Pass-probability modelling is not available.",
    "probability": "Pass-probability modelling is not available.",
    "likelihood": "Pass-probability modelling is not available.",
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


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def match_library() -> dict[str, Any]:
    manifest = read_deploy_manifest(DATA_MANIFEST_PATH)
    manifest_ids = [str(item) for item in manifest.get("match_ids", []) if str(item).strip()]
    rows: list[dict[str, Any]] = []
    matches_path = DEFAULT_CANONICAL_ROOT / "matches.parquet"
    if matches_path.exists():
        try:
            import pandas as pd

            frame = pd.read_parquet(matches_path)
            if manifest_ids:
                frame = frame[frame["match_id"].isin(manifest_ids)]
            for record in frame.to_dict(orient="records"):
                match_id = str(record.get("match_id") or "")
                title = str(record.get("match_title") or match_id)
                home_team, separator, away_team = title.partition(":")
                rows.append(
                    {
                        "match_id": match_id,
                        "match_title": title,
                        "home_team": home_team if separator else "Fortuna Düsseldorf",
                        "away_team": away_team if separator else title,
                        "result": None if record.get("result") is None else str(record.get("result")),
                        "match_day": None if record.get("match_day") is None else str(record.get("match_day")),
                        "kickoff_time_utc": None
                        if record.get("kickoff_time_utc") is None
                        else str(record.get("kickoff_time_utc")),
                    }
                )
        except Exception:  # noqa: BLE001 - display metadata must not break the workbench.
            rows = []
    if not rows:
        rows = [
            {
                "match_id": match_id,
                "match_title": f"Fortuna Düsseldorf match {match_id}",
                "home_team": "Fortuna Düsseldorf",
                "away_team": match_id,
                "result": None,
                "match_day": None,
                "kickoff_time_utc": None,
            }
            for match_id in manifest_ids
        ]
    order = {match_id: index for index, match_id in enumerate(manifest_ids)}
    rows.sort(key=lambda item: order.get(str(item["match_id"]), len(order)))
    return ok(
        {
            "perspective_team": "Fortuna Düsseldorf",
            "default_match_ids": manifest_ids or [str(item["match_id"]) for item in rows],
            "matches": rows,
        }
    )


def host_owned_plan_document(plan_document: dict[str, Any]) -> TacticalQueryDocument:
    candidate = TacticalQueryDocument.model_validate(plan_document)
    if (
        candidate.recipe.recipe_id == "ball_side_block_shift_v1"
        and candidate.draft_plan.status == "approved"
    ):
        canonical = load_plan_from_path(APPROVED_PLAN_PATH)
        canonical_invocation = canonical.setdefault("default_invocation", {})
        requested_invocation = plan_document.get("default_invocation") if isinstance(plan_document, dict) else None
        if isinstance(requested_invocation, dict):
            for key in ("match_ids", "periods", "perspective_team_role"):
                if key in requested_invocation:
                    canonical_invocation[key] = requested_invocation[key]
        return TacticalQueryDocument.model_validate(canonical)
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


def hermes_unavailable(
    query: str,
    message: str | None = None,
    *,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    return ok(
        {
            "status": "MODEL_UNAVAILABLE",
            "provenance_source": "MODEL_UNAVAILABLE",
            "query": query,
            "message": message or "Hermes frontier interpretation is not connected in this Workbench process. Manual mode remains available.",
            "source": "hermes_frontier_unavailable",
            "model_session_id": None,
            "manual_available": True,
            "repair_applied": False,
            "fallback_reason": fallback_reason,
        }
    )


def hermes_interpret_request(query: str) -> dict[str, Any]:
    try:
        hermes = shutil.which("hermes")
        log_hermes_event(
            "interpret_start",
            {
                "hermes": path_state(hermes),
                "configured_python": path_state(os.environ.get("WORKBENCH_HERMES_PYTHON")),
                "repo_root": path_state(str(REPO_ROOT)),
                "hermes_home": path_state(str(HERMES_HOME)),
                "toolset": HERMES_TOOLSET,
                "provider": HERMES_PROVIDER,
                "model": HERMES_MODEL,
            },
        )
        if not hermes:
            return hermes_unavailable(query, "Hermes executable was not found. Manual mode remains available.", fallback_reason="hermes_executable_missing")
        surface = hermes_tool_surface(hermes)
        if not surface["safe"]:
            return hermes_unavailable(
                query,
                "Hermes did not expose the frozen priori_tactical-only tool surface. Manual mode remains available.",
                fallback_reason="unsafe_tool_surface",
            )
        started_at = newest_hermes_session_started_at()
        completed = run_hermes_invocation(
            hermes,
            [
                "interpret",
                "--provider",
                HERMES_PROVIDER,
                "--model",
                HERMES_MODEL,
                "--toolset",
                HERMES_TOOLSET,
                "--prompt",
                hermes_interpret_prompt(query),
            ],
            timeout=HERMES_TIMEOUT_SECONDS,
        )
        session = newest_hermes_session_after(started_at)
        invocation = parse_invocation_json(completed.stdout)
        final = parse_final_json(str(invocation.get("stdout") or ""))
        if completed.returncode != 0 or not invocation.get("ok") or not final:
            return hermes_unavailable(
                query,
                "Hermes did not return a valid structured interpretation. Manual mode remains available.",
                fallback_reason="invalid_structured_interpretation",
            )
        return hermes_final_to_interpretation(query, final, session)
    except subprocess.TimeoutExpired:
        return hermes_unavailable(
            query,
            "Hermes interpretation timed out before returning a safe bounded response. Manual recipes remain available.",
            fallback_reason="hermes_timeout",
        )
    except FileNotFoundError as exc:
        detail = file_not_found_detail(exc)
        log_hermes_event("file_not_found", detail)
        return hermes_unavailable(
            query,
            "Hermes interpretation failed before returning a safe bounded response. Manual recipes remain available.",
            fallback_reason=detail["fallback_reason"],
        )
    except Exception as exc:  # noqa: BLE001 - model invocation failures must be typed product states.
        log_hermes_event(
            "exception",
            {
                "type": type(exc).__name__,
                "message": short_text(str(exc), 240),
            },
        )
        return hermes_unavailable(
            query,
            "Hermes interpretation failed before returning a safe bounded response. Manual recipes remain available.",
            fallback_reason=type(exc).__name__,
        )


def hermes_tool_surface(hermes: str) -> dict[str, Any]:
    completed = run_hermes_invocation(hermes, ["probe", "--toolset", HERMES_TOOLSET], timeout=60)
    payload = parse_invocation_json(completed.stdout)
    names = {str(name).removeprefix("functions.") for name in payload.get("tool_names") or []}
    forbidden = [str(name) for name in payload.get("forbidden") or []]
    return {
        "safe": completed.returncode == 0 and payload.get("safe") is True and names == HERMES_MCP_TOOL_NAMES and not forbidden,
        "tool_names": sorted(names),
        "forbidden": forbidden,
        "missing": payload.get("missing") or sorted(HERMES_MCP_TOOL_NAMES - names),
        "extra": payload.get("extra") or sorted(names - HERMES_MCP_TOOL_NAMES),
    }


def run_hermes_invocation(hermes: str, args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    hermes_python = hermes_python_executable(hermes)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(HERMES_HOME)
    env.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
    env["PYTHONPATH"] = hermes_pythonpath(env.get("PYTHONPATH"))
    log_hermes_event(
        "subprocess_start",
        {
            "subcommand": args[0] if args else "",
            "python": path_state(hermes_python),
            "hermes": path_state(hermes),
            "cwd": path_state(str(REPO_ROOT)),
            "pythonpath_entries": len(env["PYTHONPATH"].split(os.pathsep)),
        },
    )
    completed = subprocess.run(
        [hermes_python, "-m", "tqe.workshop.hermes_invocation", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=REPO_ROOT,
    )
    log_hermes_event(
        "subprocess_complete",
        {
            "subcommand": args[0] if args else "",
            "returncode": completed.returncode,
            "stdout_prefix": short_text(completed.stdout, 240),
            "stderr_prefix": short_text(completed.stderr, 240),
        },
    )
    return completed


def hermes_python_executable(hermes: str) -> str:
    configured = os.environ.get("WORKBENCH_HERMES_PYTHON")
    if configured:
        configured_path = shutil.which(configured) or configured
        if Path(configured_path).exists() and os.access(configured_path, os.X_OK):
            return configured_path
    try:
        first_line = Path(hermes).read_text(encoding="utf-8").splitlines()[0]
    except OSError:
        return sys.executable
    if first_line.startswith("#!"):
        executable = first_line[2:].strip()
        if executable and Path(executable).exists() and os.access(executable, os.X_OK):
            return executable
    return sys.executable


def path_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {"path": None, "exists": False, "executable": False}
    candidate = Path(path)
    return {
        "path": str(candidate),
        "exists": candidate.exists(),
        "executable": os.access(candidate, os.X_OK),
        "is_symlink": candidate.is_symlink(),
    }


def short_text(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:limit]


def file_not_found_detail(exc: FileNotFoundError) -> dict[str, Any]:
    filename = str(exc.filename or "")
    return {
        "type": type(exc).__name__,
        "filename": filename,
        "filename_basename": Path(filename).name if filename else "",
        "errno": exc.errno,
        "strerror": exc.strerror,
        "fallback_reason": f"FileNotFoundError:{Path(filename).name if filename else 'unknown'}",
    }


def log_hermes_event(event: str, details: dict[str, Any]) -> None:
    payload = {"event": event, "details": details}
    print(f"hermes_diagnostic={json.dumps(payload, sort_keys=True)}", flush=True)


def hermes_pythonpath(existing: str | None) -> str:
    entries = [str(REPO_ROOT / "src")]
    hermes_source = os.environ.get("HERMES_AGENT_SOURCE")
    if hermes_source:
        entries.append(hermes_source)
    if existing:
        entries.append(existing)
    return os.pathsep.join(entries)


def parse_invocation_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def hermes_interpret_prompt(query: str) -> str:
    return f"""
You are the Priori M1.2 Integrated Alpha tactical query interpreter.

Use only the priori_tactical MCP tools. Do not use filesystem, terminal, Python,
SQL, raw coordinate dumps, host confirmation, or execution. Stop before
execution. If the request is supported, either select an approved recipe or
author an EXPERIMENTAL typed plan through submit_query_plan and validate it. If
the request is ambiguous, ask for clarification. If unsupported, report stable
capability gaps.

When authoring a plan, keep default_invocation.execution_mode="execute".
validate_query_plan binds and checks the plan without executing it; host
confirmation remains the only path to execution.

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
        "model_session_id": session_id,
        "draft_plan_id": final.get("draft_plan_id"),
        "bound_plan_id": final.get("bound_plan_id"),
        "bound_plan_hash": final.get("bound_plan_hash"),
        "manual_available": True,
        "repair_applied": False,
        "fallback_reason": None,
    }
    if outcome == "clarify":
        questions = [str(item) for item in final.get("clarification_questions") or [] if str(item).strip()]
        dimensions = [str(item).upper().replace(" ", "_") for item in final.get("clarification_dimensions") or [] if str(item).strip()]
        return ok(
            {
                **base,
                "status": "CLARIFICATION_REQUIRED",
                "provenance_source": "DETERMINISTIC_REPAIR",
                "repair_applied": True,
                "fallback_reason": "clarification_required",
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
                "provenance_source": "CAPABILITY_GAP",
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
                "provenance_source": "HERMES_RECIPE_SELECTION",
                "recipe_id": recipe_id,
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
                "provenance_source": hermes_plan_provenance(plan_document),
                "recipe_id": str(plan_document.get("recipe", {}).get("recipe_id") or ""),
                "recipe": recipe_card(plan_document, "EXPERIMENTAL"),
                "plan_document": plan_document,
                "plan_hash": stable_hash(plan_document),
                "draft_plan_hash": stable_hash(plan_document),
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


def hermes_plan_provenance(plan_document: dict[str, Any]) -> str:
    recipe = plan_document.get("recipe") if isinstance(plan_document, dict) else None
    recipe_id = str(recipe.get("recipe_id") or "") if isinstance(recipe, dict) else ""
    if recipe_id in {"ball_side_block_shift_v1", "possession_corridor_availability_v1"}:
        return "HERMES_RECIPE_SELECTION"
    return "HERMES_NOVEL_COMPOSITION"


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


def hermes_db_all(query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    if not HERMES_DB.exists():
        return []
    with sqlite3.connect(HERMES_DB, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def stable_json_sha256(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def runtime_commit_identifier() -> str:
    for key in ("RENDER_GIT_COMMIT", "RENDER_COMMIT", "SOURCE_VERSION", "GIT_COMMIT"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=REPO_ROOT,
        )
    except Exception:  # noqa: BLE001 - commit metadata is useful but non-critical.
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if not isinstance(value, str):
        return str(value)
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def normalize_tool_arguments(value: Any) -> Any:
    parsed = parse_jsonish(value)
    if isinstance(parsed, str):
        nested = parse_jsonish(parsed)
        return nested if not isinstance(nested, str) else parsed
    return parsed


def sanitized_hermes_message(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "session_id": row.get("session_id"),
        "role": row.get("role"),
        "content": row.get("content"),
        "tool_call_id": row.get("tool_call_id"),
        "tool_calls": parse_jsonish(row.get("tool_calls")),
        "tool_name": row.get("tool_name"),
        "timestamp": row.get("timestamp"),
        "finish_reason": row.get("finish_reason"),
    }


def extract_ordered_tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in messages:
        raw_calls = message.get("tool_calls")
        if not isinstance(raw_calls, list):
            continue
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                continue
            function = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
            name = raw_call.get("name") or function.get("name")
            arguments = raw_call.get("arguments") if "arguments" in raw_call else function.get("arguments")
            calls.append(
                {
                    "order": len(calls),
                    "message_id": message.get("id"),
                    "tool_call_id": raw_call.get("id") or raw_call.get("tool_call_id"),
                    "name": name,
                    "arguments": normalize_tool_arguments(arguments),
                }
            )
    return calls


def extract_tool_responses(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        responses.append(
            {
                "order": len(responses),
                "message_id": message.get("id"),
                "tool_call_id": message.get("tool_call_id"),
                "tool_name": message.get("tool_name"),
                "content": parse_jsonish(message.get("content")),
            }
        )
    return responses


def export_hermes_session_trace(
    session_id: str | None,
    *,
    invocation: dict[str, Any],
    final_decision: dict[str, Any],
) -> dict[str, Any]:
    if not session_id:
        return {
            "session": None,
            "messages": [],
            "ordered_tool_calls": [],
            "tool_responses": [],
            "raw_model_output": {
                "invocation_stdout": invocation.get("stdout"),
                "final_decision": final_decision,
                "note": "No Hermes session id was recorded.",
            },
            "trace_persisted": False,
        }
    session = hermes_db_one(
        "select id, source, model, model_config, started_at, ended_at, tool_call_count, message_count, "
        "input_tokens, output_tokens, reasoning_tokens, estimated_cost_usd from sessions where id = ?",
        (session_id,),
    )
    rows = hermes_db_all(
        "select id, session_id, role, content, tool_call_id, tool_calls, tool_name, timestamp, finish_reason "
        "from messages where session_id = ? order by timestamp asc, id asc",
        (session_id,),
    )
    messages = [sanitized_hermes_message(row) for row in rows]
    assistant_contents = [
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "assistant" and str(message.get("content") or "").strip()
    ]
    raw_model_output = {
        "invocation_stdout": invocation.get("stdout"),
        "final_assistant_content": assistant_contents[-1] if assistant_contents else None,
        "final_decision": final_decision,
    }
    return {
        "session": session,
        "messages": messages,
        "ordered_tool_calls": extract_ordered_tool_calls(messages),
        "tool_responses": extract_tool_responses(messages),
        "raw_model_output": raw_model_output,
        "trace_persisted": bool(session and messages),
    }


def add_n1e_entry_mode_evidence(document: dict[str, Any]) -> dict[str, Any]:
    from tqe.verification.n1d import ENTRY_MODE_EVIDENCE

    augmented = deepcopy(document)
    requested = augmented["draft_plan"].setdefault("requested_evidence", [])
    present_aliases = {str(item.get("alias")) for item in requested if isinstance(item, dict)}
    for evidence in ENTRY_MODE_EVIDENCE:
        if str(evidence.get("alias")) not in present_aliases:
            requested.append(deepcopy(evidence))
    return augmented


def run_host_authority_pipeline(document: dict[str, Any], *, output_root: Path, source_label: str) -> dict[str, Any]:
    plan_document = TacticalQueryDocument.model_validate(document)
    submitted = submit_query_plan(
        SubmitQueryPlanRequest(plan_document=plan_document, source_label=source_label),
        output_root=output_root,
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    validation = validate_query_plan(
        ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
        output_root=output_root,
        caller_profile=CallerProfile.HOST_MANUAL,
    )
    if not validation.ok or not validation.bound_plan_id:
        raise CapabilityGap(f"N1E host-augmented plan failed validation: {validation.issues}")
    confirmation = host_confirm_bound_plan(
        validation.bound_plan_id,
        reviewer=source_label,
        output_root=output_root,
    )
    cache_before = execution_cache_status(
        {
            "bound_plan_id": validation.bound_plan_id,
            "execution_authorization_id": confirmation.execution_authorization_id,
            "result_limit": N1E_RESULT_LIMIT,
        },
        output_root=output_root,
    )
    executed = cached_execute_query_plan(
        ExecuteQueryPlanRequest(
            bound_plan_id=validation.bound_plan_id,
            execution_authorization_id=confirmation.execution_authorization_id,
            result_limit=N1E_RESULT_LIMIT,
        ),
        output_root=output_root,
    )
    execution = executed["execution"]
    if not execution.get("results"):
        raise CapabilityGap("N1E host execution produced no results for the frozen hero question.")
    first_result_id = str(execution["results"][0]["result_id"])
    inspection = inspect_result(
        InspectResultRequest(execution_id=execution["execution_id"], result_id=first_result_id),
        output_root=output_root,
    )
    replay = retrieve_replay_window(
        ReplayWindowRequest(execution_id=execution["execution_id"], result_id=first_result_id),
        output_root=output_root,
    )
    return {
        "submit": submitted.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "confirmation": confirmation.model_dump(mode="json"),
        "cache_before": cache_before,
        "execution": execution,
        "cache_after_execute": executed["cache"],
        "inspection": inspection.model_dump(mode="json"),
        "replay_window": replay.model_dump(mode="json"),
        "draft_record": read_handle("draft-plans", submitted.draft_plan_id, output_root=output_root),
        "bound_record": read_handle("bound-plans", validation.bound_plan_id, output_root=output_root),
        "execution_record": read_handle("executions", execution["execution_id"], output_root=output_root),
        "replay_record": read_handle("replay-windows", replay.replay_window_id, output_root=output_root),
    }


def n1e_job_root(output_root: Path) -> Path:
    return output_root / "n1e"


def n1e_job_dir(output_root: Path, job_id: str) -> Path:
    return n1e_job_root(output_root) / "jobs" / job_id


def n1e_status_path(output_root: Path, job_id: str) -> Path:
    return n1e_job_dir(output_root, job_id) / "status.json"


def n1e_bundle_path(output_root: Path, job_id: str) -> Path:
    return n1e_job_dir(output_root, job_id) / "n1e-origin-bundle.json"


def n1e_latest_path(output_root: Path) -> Path:
    return n1e_job_root(output_root) / "latest.json"


def write_n1e_status(output_root: Path, job_id: str, payload: dict[str, Any]) -> None:
    status = {"schema_version": "n1e.job_status.v1", "job_id": job_id, "updated_at": utc_now_iso(), **payload}
    write_json(n1e_status_path(output_root, job_id), status)
    write_json(n1e_latest_path(output_root), {"job_id": job_id, "status": status.get("status"), "updated_at": status["updated_at"]})


def read_n1e_status(output_root: Path, job_id: str | None = None) -> dict[str, Any]:
    selected = job_id
    if not selected and n1e_latest_path(output_root).exists():
        selected = str(read_json(n1e_latest_path(output_root)).get("job_id") or "")
    if not selected:
        return error_response("N1E_JOB_NOT_FOUND", "No N1E runner job has been started.")
    path = n1e_status_path(output_root, selected)
    if not path.exists():
        return error_response("N1E_JOB_NOT_FOUND", "N1E runner job was not found.")
    return ok(read_json(path))


def run_n1e_origin_bundle(job_id: str, *, output_root: Path) -> None:
    job_dir = n1e_job_dir(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    source_label = "n1e_origin_refresh"
    try:
        from tqe.verification.n1c import HERO_QUESTION
        from tqe.verification.n1d import ENTRY_BEFORE_OPEN_ANALYSIS, entry_mode_audit, runtime_hashes

        write_n1e_status(output_root, job_id, {"status": "running", "stage": "probing_hermes"})
        hermes = shutil.which("hermes")
        if not hermes:
            raise CapabilityGap("Hermes executable is not available in the deploy runtime.")
        surface = hermes_tool_surface(hermes)
        if not surface["safe"]:
            raise CapabilityGap(f"Unsafe Hermes tool surface: {surface}")

        prompt = hermes_interpret_prompt(HERO_QUESTION)
        started_at = newest_hermes_session_started_at()
        write_n1e_status(output_root, job_id, {"status": "running", "stage": "compiling_with_hermes"})
        completed = run_hermes_invocation(
            hermes,
            [
                "interpret",
                "--provider",
                HERMES_PROVIDER,
                "--model",
                HERMES_MODEL,
                "--toolset",
                HERMES_TOOLSET,
                "--prompt",
                prompt,
            ],
            timeout=HERMES_TIMEOUT_SECONDS,
        )
        session = newest_hermes_session_after(started_at)
        invocation = parse_invocation_json(completed.stdout)
        final = parse_final_json(str(invocation.get("stdout") or ""))
        if completed.returncode != 0 or not invocation.get("ok") or not final:
            raise CapabilityGap("Hermes did not return a valid structured N1E interpretation.")

        interpretation = hermes_final_to_interpretation(HERO_QUESTION, final, session)
        if interpretation.get("status") != "PLAN_INTERPRETED":
            raise CapabilityGap(f"Hermes did not return an executable plan: {interpretation.get('status')}")
        if interpretation.get("provenance_source") != "HERMES_NOVEL_COMPOSITION":
            raise CapabilityGap(
                f"Hermes did not produce novel-composition provenance: {interpretation.get('provenance_source')}"
            )
        draft_plan_id = str(final.get("draft_plan_id") or interpretation.get("draft_plan_id") or "")
        if not draft_plan_id:
            raise CapabilityGap("Hermes final decision did not include draft_plan_id.")
        hermes_draft_record = read_handle("draft-plans", draft_plan_id, output_root=HERMES_WORKSHOP_ROOT)
        hermes_draft_document = hermes_draft_record.get("document")
        if not isinstance(hermes_draft_document, dict):
            raise CapabilityGap("Hermes draft handle did not contain a plan document.")

        host_augmented_document = add_n1e_entry_mode_evidence(hermes_draft_document)
        write_n1e_status(output_root, job_id, {"status": "running", "stage": "executing_host_authority_pipeline"})
        records = run_host_authority_pipeline(
            host_augmented_document,
            output_root=output_root,
            source_label=source_label,
        )
        audit = entry_mode_audit(records["execution_record"])
        session_trace = export_hermes_session_trace(
            str(session.get("id")) if session else None,
            invocation=invocation,
            final_decision=final,
        )
        bundle = {
            "schema_version": "n1e.origin_bundle.v1",
            "status": "exported",
            "generated_at": utc_now_iso(),
            "job_id": job_id,
            "hero_question": {"text": HERO_QUESTION, "sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest()},
            "compile_contract": {
                "provider": HERMES_PROVIDER,
                "model": HERMES_MODEL,
                "toolset": HERMES_TOOLSET,
                "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
                "tool_surface": surface,
                "hermes_python": path_state(hermes_python_executable(hermes)),
                "hermes_executable": path_state(hermes),
            },
            "source": {
                "repo_commit": runtime_commit_identifier(),
                "runtime_hashes": runtime_hashes(),
                "output_root": cloud_safe_path(output_root),
                "hermes_workshop_root": cloud_safe_path(HERMES_WORKSHOP_ROOT),
            },
            "hermes_origin": {
                "session_id": str(session.get("id")) if session else None,
                "final_decision": final,
                "interpretation": interpretation,
                "draft_plan_id": draft_plan_id,
                "draft_plan_hash": hermes_draft_record.get("draft_plan_hash"),
                "draft_document": hermes_draft_document,
                "session_trace": session_trace,
                "ordered_tool_call_trace_sha256": stable_json_sha256(session_trace["ordered_tool_calls"]),
                "raw_hermes_decision_sha256": stable_json_sha256(session_trace["raw_model_output"]),
            },
            "host_augmentation": {
                "allowed_added_aliases": ["destination_entry_mode", "destination_time_to_entry_seconds"],
                "augmented_document": host_augmented_document,
                "augmented_document_sha256": stable_json_sha256(host_augmented_document),
                "source_label": source_label,
            },
            "host_pipeline": {
                "submit": records["submit"],
                "validation": records["validation"],
                "confirmation": records["confirmation"],
                "cache_before": records["cache_before"],
                "execution": records["execution"],
                "cache_after_execute": records["cache_after_execute"],
                "inspection": records["inspection"],
                "replay_window": records["replay_window"],
            },
            "artifact_records": {
                "draft_record": records["draft_record"],
                "bound_record": records["bound_record"],
                "execution_record": records["execution_record"],
                "replay_record": records["replay_record"],
            },
            "entry_mode_audit": audit,
            "entry_before_open_analysis": ENTRY_BEFORE_OPEN_ANALYSIS,
        }
        write_json(n1e_bundle_path(output_root, job_id), bundle)
        write_n1e_status(
            output_root,
            job_id,
            {
                "status": "succeeded",
                "stage": "bundle_exported",
                "bundle_sha256": file_sha256(n1e_bundle_path(output_root, job_id)),
                "session_id": bundle["hermes_origin"]["session_id"],
                "bound_plan_hash": records["validation"].get("bound_plan_hash"),
                "execution_id": records["execution"].get("execution_id"),
            },
        )
    except Exception as exc:  # noqa: BLE001 - this diagnostic job must preserve failure details.
        write_n1e_status(
            output_root,
            job_id,
            {
                "status": "failed",
                "stage": "failed",
                "error_type": type(exc).__name__,
                "message": short_text(str(exc), 1000),
            },
        )


def recover_latest_n1e_failure_bundle(*, output_root: Path) -> dict[str, Any]:
    from tqe.verification.n1c import HERO_QUESTION
    from tqe.verification.n1d import runtime_hashes

    session = newest_hermes_session_after(0.0)
    if not session:
        raise CapabilityGap("No Hermes session is available to recover.")
    session_id = str(session["id"])
    trace = export_hermes_session_trace(session_id, invocation={}, final_decision={})
    raw = trace.get("raw_model_output") if isinstance(trace, dict) else {}
    final_text = str(raw.get("final_assistant_content") or raw.get("invocation_stdout") or "")
    final_decision = parse_final_json(final_text)
    trace = export_hermes_session_trace(session_id, invocation={"stdout": final_text}, final_decision=final_decision)
    job_id = "n1e_recovered_" + session_id.replace("/", "_").replace(":", "_")[-24:]
    bundle = {
        "schema_version": "n1e.origin_bundle.v1",
        "status": "failed_compile_recovered",
        "generated_at": utc_now_iso(),
        "job_id": job_id,
        "hero_question": {"text": HERO_QUESTION, "sha256": sha256(HERO_QUESTION.encode("utf-8")).hexdigest()},
        "compile_contract": {
            "provider": HERMES_PROVIDER,
            "model": HERMES_MODEL,
            "toolset": HERMES_TOOLSET,
            "prompt_sha256": sha256(hermes_interpret_prompt(HERO_QUESTION).encode("utf-8")).hexdigest(),
        },
        "source": {
            "repo_commit": runtime_commit_identifier(),
            "runtime_hashes": runtime_hashes(),
            "output_root": cloud_safe_path(output_root),
            "hermes_workshop_root": cloud_safe_path(HERMES_WORKSHOP_ROOT),
        },
        "hermes_origin": {
            "session_id": session_id,
            "final_decision": final_decision,
            "session_trace": trace,
            "ordered_tool_call_trace_sha256": stable_json_sha256(trace["ordered_tool_calls"]),
            "raw_hermes_decision_sha256": stable_json_sha256(trace["raw_model_output"]),
        },
        "blocking_reason": "Hermes returned clarification/capability-gap/no-plan, so no host execution was performed.",
    }
    write_json(n1e_bundle_path(output_root, job_id), bundle)
    write_n1e_status(
        output_root,
        job_id,
        {
            "status": "failed",
            "stage": "recovered_failure_bundle",
            "bundle_sha256": file_sha256(n1e_bundle_path(output_root, job_id)),
            "session_id": session_id,
            "message": "Recovered latest Hermes session as a failed N1E origin bundle.",
        },
    )
    return {"job_id": job_id, "bundle_sha256": file_sha256(n1e_bundle_path(output_root, job_id))}


def n1f_job_root(output_root: Path) -> Path:
    return output_root / "n1f"


def n1f_job_dir(output_root: Path, job_id: str) -> Path:
    return n1f_job_root(output_root) / "jobs" / job_id


def n1f_status_path(output_root: Path, job_id: str) -> Path:
    return n1f_job_dir(output_root, job_id) / "status.json"


def n1f_bundle_path(output_root: Path, job_id: str) -> Path:
    return n1f_job_dir(output_root, job_id) / "n1f-origin-bundle.json"


def n1f_latest_path(output_root: Path) -> Path:
    return n1f_job_root(output_root) / "latest.json"


def write_n1f_status(output_root: Path, job_id: str, payload: dict[str, Any]) -> None:
    status = {"schema_version": "n1f.job_status.v1", "job_id": job_id, "updated_at": utc_now_iso(), **payload}
    write_json(n1f_status_path(output_root, job_id), status)
    write_json(n1f_latest_path(output_root), {"job_id": job_id, "status": status.get("status"), "updated_at": status["updated_at"]})


def read_n1f_status(output_root: Path, job_id: str | None = None) -> dict[str, Any]:
    selected = job_id
    if not selected and n1f_latest_path(output_root).exists():
        selected = str(read_json(n1f_latest_path(output_root)).get("job_id") or "")
    if not selected:
        return error_response("N1F_JOB_NOT_FOUND", "No N1F runner job has been started.")
    path = n1f_status_path(output_root, selected)
    if not path.exists():
        return error_response("N1F_JOB_NOT_FOUND", "N1F runner job was not found.")
    return ok(read_json(path))


def n1f_clarified_query(hero_question: str) -> str:
    return "\n".join(
        [
            hero_question,
            "",
            "Clarification answer for invocation binding only, not tactical semantics:",
            f"match_ids: {json.dumps(N1F_CLARIFICATION_ANSWER['match_ids'], separators=(',', ':'))}",
            f"periods: {json.dumps(N1F_CLARIFICATION_ANSWER['periods'], separators=(',', ':'))}",
            f"perspective_team_role: {json.dumps(N1F_CLARIFICATION_ANSWER['perspective_team_role'])}",
        ]
    )


def committed_n1e_origin_chain() -> dict[str, Any] | None:
    path = REPO_ROOT / "delivery/n1d/n1e-origin-bundle.json"
    if not path.exists():
        return None
    bundle = read_json(path)
    hermes = bundle.get("hermes_origin") if isinstance(bundle.get("hermes_origin"), dict) else {}
    trace = hermes.get("session_trace") if isinstance(hermes.get("session_trace"), dict) else {}
    return {
        "bundle_path": "delivery/n1d/n1e-origin-bundle.json",
        "bundle_sha256": file_sha256(path),
        "job_id": bundle.get("job_id"),
        "session_id": hermes.get("session_id"),
        "first_turn_decision": hermes.get("final_decision"),
        "ordered_tool_calls": trace.get("ordered_tool_calls") if isinstance(trace.get("ordered_tool_calls"), list) else [],
        "ordered_tool_call_trace_sha256": hermes.get("ordered_tool_call_trace_sha256"),
        "raw_hermes_decision_sha256": hermes.get("raw_hermes_decision_sha256"),
    }


def n1f_base_bundle(
    *,
    job_id: str,
    status: str,
    output_root: Path,
    hero_question: str,
    clarified_query: str,
    prompt: str,
    surface: dict[str, Any],
    session: dict[str, Any] | None,
    invocation: dict[str, Any],
    final_decision: dict[str, Any],
) -> dict[str, Any]:
    from tqe.verification.n1d import runtime_hashes

    session_trace = export_hermes_session_trace(
        str(session.get("id")) if session else None,
        invocation=invocation,
        final_decision=final_decision,
    )
    return {
        "schema_version": "n1f.origin_bundle.v1",
        "status": status,
        "generated_at": utc_now_iso(),
        "job_id": job_id,
        "hero_question": {"text": hero_question, "sha256": sha256(hero_question.encode("utf-8")).hexdigest()},
        "first_turn_origin": committed_n1e_origin_chain(),
        "clarification_answer": {
            "kind": "invocation_binding",
            "answer": N1F_CLARIFICATION_ANSWER,
            "answer_sha256": stable_json_sha256(N1F_CLARIFICATION_ANSWER),
            "not_tactical_semantics": True,
        },
        "second_turn_request": {
            "text": clarified_query,
            "sha256": sha256(clarified_query.encode("utf-8")).hexdigest(),
        },
        "compile_contract": {
            "provider": HERMES_PROVIDER,
            "model": HERMES_MODEL,
            "toolset": HERMES_TOOLSET,
            "prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
            "tool_surface": surface,
        },
        "source": {
            "repo_commit": runtime_commit_identifier(),
            "runtime_hashes": runtime_hashes(),
            "output_root": cloud_safe_path(output_root),
            "hermes_workshop_root": cloud_safe_path(HERMES_WORKSHOP_ROOT),
        },
        "hermes_origin": {
            "session_id": str(session.get("id")) if session else None,
            "final_decision": final_decision,
            "session_trace": session_trace,
            "ordered_tool_call_trace_sha256": stable_json_sha256(session_trace["ordered_tool_calls"]),
            "raw_hermes_decision_sha256": stable_json_sha256(session_trace["raw_model_output"]),
        },
    }


def write_failed_n1f_bundle(
    *,
    output_root: Path,
    job_id: str,
    bundle: dict[str, Any],
    reason: str,
    stage: str,
) -> None:
    payload = {**bundle, "status": "failed_compile", "blocking_reason": reason}
    write_json(n1f_bundle_path(output_root, job_id), payload)
    write_n1f_status(
        output_root,
        job_id,
        {
            "status": "failed",
            "stage": stage,
            "bundle_sha256": file_sha256(n1f_bundle_path(output_root, job_id)),
            "session_id": payload.get("hermes_origin", {}).get("session_id"),
            "message": reason,
        },
    )


def n1f_trace_draft_plan_id(bundle: dict[str, Any]) -> str:
    trace = bundle.get("hermes_origin", {}).get("session_trace", {})
    calls = trace.get("ordered_tool_calls") if isinstance(trace, dict) else None
    if not isinstance(calls, list):
        return ""
    for call in reversed(calls):
        if not isinstance(call, dict):
            continue
        if str(call.get("name") or "").removeprefix("functions.") != "mcp_priori_tactical_validate_query_plan":
            continue
        arguments = call.get("arguments")
        if isinstance(arguments, dict) and arguments.get("draft_plan_id"):
            return str(arguments["draft_plan_id"]).strip()
    return ""


def n1f_trace_submitted_plan_document(bundle: dict[str, Any]) -> dict[str, Any] | None:
    trace = bundle.get("hermes_origin", {}).get("session_trace", {})
    calls = trace.get("ordered_tool_calls") if isinstance(trace, dict) else None
    if not isinstance(calls, list):
        return None
    for call in reversed(calls):
        if not isinstance(call, dict):
            continue
        if str(call.get("name") or "").removeprefix("functions.") != "mcp_priori_tactical_submit_query_plan":
            continue
        arguments = call.get("arguments")
        document = arguments.get("plan_document") if isinstance(arguments, dict) else None
        if isinstance(document, dict):
            return document
    return None


def attach_n1f_hermes_draft_if_present(bundle: dict[str, Any], final_decision: dict[str, Any]) -> None:
    draft_plan_id = str(final_decision.get("draft_plan_id") or "").strip() or n1f_trace_draft_plan_id(bundle)
    if not draft_plan_id:
        return
    try:
        hermes_draft_record = read_handle("draft-plans", draft_plan_id, output_root=HERMES_WORKSHOP_ROOT)
    except Exception as exc:  # noqa: BLE001 - diagnostic bundle should preserve absence rather than fail.
        submitted_document = n1f_trace_submitted_plan_document(bundle)
        if submitted_document is not None:
            hermes_origin = bundle.setdefault("hermes_origin", {})
            hermes_origin["draft_plan_id"] = draft_plan_id
            hermes_origin["draft_plan_hash"] = stable_json_sha256(submitted_document)
            hermes_origin["draft_document"] = submitted_document
            hermes_origin["draft_hash_source"] = "submitted_tool_arguments"
        bundle.setdefault("hermes_origin", {})["draft_lookup_error"] = {
            "draft_plan_id": draft_plan_id,
            "error_type": type(exc).__name__,
            "message": short_text(str(exc), 500),
        }
        return
    hermes_origin = bundle.setdefault("hermes_origin", {})
    hermes_origin["draft_plan_id"] = draft_plan_id
    hermes_origin["draft_plan_hash"] = hermes_draft_record.get("draft_plan_hash")
    document = hermes_draft_record.get("document")
    if isinstance(document, dict):
        hermes_origin["draft_document"] = document


def run_n1f_origin_bundle(job_id: str, *, output_root: Path) -> None:
    job_dir = n1f_job_dir(output_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    source_label = "n1f_scoped_origin_refresh"
    try:
        from tqe.verification.n1c import HERO_QUESTION
        from tqe.verification.n1d import ENTRY_BEFORE_OPEN_ANALYSIS, entry_mode_audit

        write_n1f_status(output_root, job_id, {"status": "running", "stage": "probing_hermes"})
        hermes = shutil.which("hermes")
        if not hermes:
            raise CapabilityGap("Hermes executable is not available in the deploy runtime.")
        surface = hermes_tool_surface(hermes)
        if not surface["safe"]:
            raise CapabilityGap(f"Unsafe Hermes tool surface: {surface}")

        clarified_query = n1f_clarified_query(HERO_QUESTION)
        prompt = hermes_interpret_prompt(clarified_query)
        started_at = newest_hermes_session_started_at()
        write_n1f_status(output_root, job_id, {"status": "running", "stage": "compiling_with_hermes_second_turn"})
        completed = run_hermes_invocation(
            hermes,
            [
                "interpret",
                "--provider",
                HERMES_PROVIDER,
                "--model",
                HERMES_MODEL,
                "--toolset",
                HERMES_TOOLSET,
                "--prompt",
                prompt,
            ],
            timeout=HERMES_TIMEOUT_SECONDS,
        )
        session = newest_hermes_session_after(started_at)
        invocation = parse_invocation_json(completed.stdout)
        final = parse_final_json(str(invocation.get("stdout") or ""))
        base_bundle = n1f_base_bundle(
            job_id=job_id,
            status="compiled",
            output_root=output_root,
            hero_question=HERO_QUESTION,
            clarified_query=clarified_query,
            prompt=prompt,
            surface=surface,
            session=session,
            invocation=invocation,
            final_decision=final,
        )
        if completed.returncode != 0 or not invocation.get("ok") or not final:
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=base_bundle,
                reason="Hermes did not return a valid structured N1F interpretation.",
                stage="invalid_structured_interpretation",
            )
            return

        interpretation = hermes_final_to_interpretation(clarified_query, final, session)
        base_bundle["hermes_origin"]["interpretation"] = interpretation
        if interpretation.get("status") != "PLAN_INTERPRETED":
            attach_n1f_hermes_draft_if_present(base_bundle, final)
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=base_bundle,
                reason=f"Hermes did not return an executable plan: {interpretation.get('status')}",
                stage="non_plan_outcome",
            )
            return
        if interpretation.get("provenance_source") != "HERMES_NOVEL_COMPOSITION":
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=base_bundle,
                reason=f"Hermes did not produce novel-composition provenance: {interpretation.get('provenance_source')}",
                stage="non_novel_outcome",
            )
            return

        draft_plan_id = str(final.get("draft_plan_id") or interpretation.get("draft_plan_id") or "")
        if not draft_plan_id:
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=base_bundle,
                reason="Hermes final decision did not include draft_plan_id.",
                stage="missing_draft_plan_id",
            )
            return
        hermes_draft_record = read_handle("draft-plans", draft_plan_id, output_root=HERMES_WORKSHOP_ROOT)
        hermes_draft_document = hermes_draft_record.get("document")
        if not isinstance(hermes_draft_document, dict):
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=base_bundle,
                reason="Hermes draft handle did not contain a plan document.",
                stage="missing_draft_document",
            )
            return

        host_augmented_document = add_n1e_entry_mode_evidence(hermes_draft_document)
        write_n1f_status(output_root, job_id, {"status": "running", "stage": "executing_host_authority_pipeline"})
        records = run_host_authority_pipeline(
            host_augmented_document,
            output_root=output_root,
            source_label=source_label,
        )
        audit = entry_mode_audit(records["execution_record"])
        bundle = {
            **base_bundle,
            "status": "exported",
            "hermes_origin": {
                **base_bundle["hermes_origin"],
                "draft_plan_id": draft_plan_id,
                "draft_plan_hash": hermes_draft_record.get("draft_plan_hash"),
                "draft_document": hermes_draft_document,
            },
            "host_augmentation": {
                "allowed_added_aliases": ["destination_entry_mode", "destination_time_to_entry_seconds"],
                "augmented_document": host_augmented_document,
                "augmented_document_sha256": stable_json_sha256(host_augmented_document),
                "source_label": source_label,
            },
            "host_pipeline": {
                "submit": records["submit"],
                "validation": records["validation"],
                "confirmation": records["confirmation"],
                "cache_before": records["cache_before"],
                "execution": records["execution"],
                "cache_after_execute": records["cache_after_execute"],
                "inspection": records["inspection"],
                "replay_window": records["replay_window"],
            },
            "artifact_records": {
                "draft_record": records["draft_record"],
                "bound_record": records["bound_record"],
                "execution_record": records["execution_record"],
                "replay_record": records["replay_record"],
            },
            "entry_mode_audit": audit,
            "entry_before_open_analysis": ENTRY_BEFORE_OPEN_ANALYSIS,
        }
        write_json(n1f_bundle_path(output_root, job_id), bundle)
        write_n1f_status(
            output_root,
            job_id,
            {
                "status": "succeeded",
                "stage": "bundle_exported",
                "bundle_sha256": file_sha256(n1f_bundle_path(output_root, job_id)),
                "session_id": bundle["hermes_origin"]["session_id"],
                "bound_plan_hash": records["validation"].get("bound_plan_hash"),
                "execution_id": records["execution"].get("execution_id"),
            },
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic job must preserve failure details.
        write_n1f_status(
            output_root,
            job_id,
            {
                "status": "failed",
                "stage": "failed",
                "error_type": type(exc).__name__,
                "message": short_text(str(exc), 1000),
            },
        )


def interpret_request(payload: dict[str, Any], *, output_root: Path = DEFAULT_WORKSHOP_ROOT) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    mode = str(payload.get("mode") or "manual")
    clarifications = [str(item) for item in payload.get("clarifications") or [] if str(item).strip()]
    selected_recipe_id = payload.get("selected_recipe_id")
    preset_id = payload.get("preset_id")
    if mode == "model":
        if not hermes_enabled():
            return hermes_unavailable(query, fallback_reason="hermes_disabled")
        return hermes_interpret_request(query)

    text = normalized(query)
    gaps = unsupported_gaps(text)
    if gaps:
        return ok(
            {
                "status": "CAPABILITY_GAP",
                "provenance_source": "CAPABILITY_GAP",
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
                "provenance_source": "DETERMINISTIC_REPAIR",
                "query": query,
                "source": "manual_host_interpreter",
                "repair_applied": True,
                "fallback_reason": "support_language_requires_clarification",
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
                "provenance_source": "DETERMINISTIC_REPAIR",
                "query": query,
                "source": "manual_host_interpreter",
                "repair_applied": True,
                "fallback_reason": "recipe_selection_required",
                "clarification_questions": [
                    "Select the approved block-shift recipe or the experimental corridor preset.",
                ],
                "clarification_codes": ["RECIPE_SELECTION"],
            }
        )

    plan_document = load_plan_from_path(path)
    state = "APPROVED" if path == APPROVED_PLAN_PATH else "EXPERIMENTAL"
    provenance_source = "REVIEWED_RECIPE" if state == "APPROVED" else "MANUAL_PRESET"
    return ok(
        {
            "status": "PLAN_INTERPRETED",
            "provenance_source": provenance_source,
            "query": query,
            "source": "manual_host_interpreter",
            "recipe_id": str(plan_document.get("recipe", {}).get("recipe_id") or ""),
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
        "runtime_version": "workbench_beta0_execution_cache_v2",
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
    base = cache_root(output_root).resolve()
    path = (base / f"{cache_key}.json").resolve()
    if base not in path.parents:
        raise CapabilityGap("Execution cache path escapes storage root.")
    return path


def cache_root(output_root: Path) -> Path:
    return CACHE_ROOT if CACHE_ROOT is not None else output_root / "execution-cache"


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


def readiness_report(*, static_root: Path, output_root: Path) -> dict[str, Any]:
    checks = [
        readiness_check(
            "frontend.index",
            (static_root / "index.html").exists(),
            {"path": cloud_safe_path(static_root / "index.html")},
        ),
        readiness_check(
            "runtime_root.writable",
            directory_writable(output_root),
            {"path": cloud_safe_path(output_root)},
        ),
        readiness_check(
            "cache_root.writable",
            directory_writable(cache_root(output_root)),
            {"path": cloud_safe_path(cache_root(output_root))},
        ),
        *dataset_readiness_checks(),
        *knowledge_pack_readiness_checks(),
        *recipe_readiness_checks(),
    ]
    return {
        "status": "READY" if all(item["ok"] for item in checks) else "NOT_READY",
        "checks": checks,
    }


def readiness_check(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(passed), "details": details or {}}


def directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def dataset_readiness_checks() -> list[dict[str, Any]]:
    checks = [
        readiness_check(
            "dataset.root.exists",
            DEFAULT_CANONICAL_ROOT.exists(),
            {"path": cloud_safe_path(DEFAULT_CANONICAL_ROOT)},
        )
    ]
    manifest = read_deploy_manifest(DATA_MANIFEST_PATH)
    required_paths = manifest.get("required_paths") if isinstance(manifest, dict) else None
    if isinstance(required_paths, list):
        missing = [
            str(path)
            for path in required_paths
            if not (DEFAULT_CANONICAL_ROOT / str(path)).exists()
        ]
        checks.append(
            readiness_check(
                "dataset.required_paths.present",
                not missing,
                {"missing": missing[:20], "required_count": len(required_paths)},
            )
        )
    else:
        required = [
            "matches.parquet",
            "players.parquet",
            "teams.parquet",
            "orientation.parquet",
        ]
        missing = [path for path in required if not (DEFAULT_CANONICAL_ROOT / path).exists()]
        checks.append(readiness_check("dataset.core_tables.present", not missing, {"missing": missing}))
    required_raw = [
        "J03WOY/tracking.xml",
        "J03WPY/tracking.xml",
        "J03WQQ/tracking.xml",
        "J03WR9/tracking.xml",
    ]
    missing_raw = [path for path in required_raw if not (DEFAULT_RAW_ROOT / path).exists()]
    checks.append(
        readiness_check(
            "dataset.raw_tracking.present",
            not missing_raw,
            {"missing": missing_raw, "path": cloud_safe_path(DEFAULT_RAW_ROOT)},
        )
    )
    return checks


def knowledge_pack_readiness_checks() -> list[dict[str, Any]]:
    exists = KNOWLEDGE_PACK_PATH.exists()
    checks = [
        readiness_check(
            "knowledge_pack.exists",
            exists,
            {"path": cloud_safe_path(KNOWLEDGE_PACK_PATH)},
        )
    ]
    if exists and EXPECTED_KNOWLEDGE_PACK_SHA256:
        actual = file_sha256(KNOWLEDGE_PACK_PATH)
        checks.append(
            readiness_check(
                "knowledge_pack.sha256",
                actual == EXPECTED_KNOWLEDGE_PACK_SHA256,
                {"actual": actual, "expected": EXPECTED_KNOWLEDGE_PACK_SHA256},
            )
        )
    return checks


def recipe_readiness_checks() -> list[dict[str, Any]]:
    checks = []
    for recipe_id in ("ball_side_block_shift_v1", "possession_corridor_availability_v1"):
        try:
            plan_for_recipe(recipe_id)
            checks.append(readiness_check(f"recipe.{recipe_id}.loadable", True, {}))
        except Exception as exc:  # noqa: BLE001
            checks.append(readiness_check(f"recipe.{recipe_id}.loadable", False, {"error": type(exc).__name__}))
    return checks


def prewarm_execution_cache(*, output_root: Path, recipe_ids: tuple[str, ...], result_limit: int) -> None:
    for recipe_id in recipe_ids:
        started_at = time.monotonic()
        print(f"Prewarming execution cache for {recipe_id}...", flush=True)
        submitted = submit_query_plan(
            SubmitQueryPlanRequest(
                plan_document=host_owned_plan_document(plan_for_recipe(recipe_id)),
                source_label="workbench_alpha_prewarm",
            ),
            output_root=output_root,
            caller_profile=CallerProfile.HOST_MANUAL,
        )
        validation = validate_query_plan(
            ValidateQueryPlanRequest(draft_plan_id=submitted.draft_plan_id),
            output_root=output_root,
            caller_profile=CallerProfile.HOST_MANUAL,
        )
        confirmation = host_confirm_bound_plan(
            validation.bound_plan_id,
            reviewer="workbench_alpha_prewarm",
            output_root=output_root,
        )
        executed = cached_execute_query_plan(
            ExecuteQueryPlanRequest(
                bound_plan_id=validation.bound_plan_id,
                execution_authorization_id=confirmation.execution_authorization_id,
                result_limit=result_limit,
            ),
            output_root=output_root,
        )
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        print(
            "Prewarmed execution cache for "
            f"{recipe_id}: cache_status={executed['cache']['cache_status']} "
            f"results={executed['execution']['total_result_count']} elapsed_ms={elapsed_ms}",
            flush=True,
        )


def read_deploy_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def cloud_safe_path(path: Path) -> str:
    resolved = str(path)
    if resolved.startswith("/Users/"):
        return "<local-dev-path>"
    return resolved


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

    def send_demo_auth_required(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("WWW-Authenticate", 'Basic realm="Manual Tactical Workbench Alpha"')
            body = json_response(
                error_response(
                    "DEMO_ACCESS_REQUIRED",
                    "Demo access token is required.",
                )
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = (
            "<!doctype html><title>Manual Tactical Workbench Alpha</title>"
            "<body><h1>Manual Tactical Workbench Alpha</h1>"
            "<p>Demo access token is required.</p></body>"
        ).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("WWW-Authenticate", 'Basic realm="Manual Tactical Workbench Alpha"')
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

    def demo_access_allowed(self, parsed: Any) -> bool:
        if not DEMO_ACCESS_TOKEN:
            return True
        query_token = (parse_qs(parsed.query).get("access_token") or [""])[0]
        if DEMO_ACCESS_QUERY_TOKEN_ENABLED and query_token and query_token == DEMO_ACCESS_TOKEN:
            return True
        cookie = self.headers.get("Cookie", "")
        if any(part.strip() == f"demo_access_token={DEMO_ACCESS_TOKEN}" for part in cookie.split(";")):
            return True
        if self.headers.get("X-Demo-Access-Token", "") == DEMO_ACCESS_TOKEN:
            return True
        authorization = self.headers.get("Authorization", "")
        if authorization == f"Bearer {DEMO_ACCESS_TOKEN}":
            return True
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization.removeprefix("Basic ").strip()).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return False
            _username, separator, password = decoded.partition(":")
            return bool(separator) and password == DEMO_ACCESS_TOKEN
        return False

    def n1e_access_allowed(self) -> bool:
        if not N1E_RUNNER_ENABLED or not N1E_RUN_TOKEN:
            return False
        authorization = self.headers.get("Authorization", "")
        if authorization == f"Bearer {N1E_RUN_TOKEN}":
            return True
        return self.headers.get("X-N1E-Run-Token", "") == N1E_RUN_TOKEN

    def send_n1e_forbidden(self) -> None:
        self.send_json(
            error_response(
                "N1E_RUNNER_UNAVAILABLE",
                "N1E runner is disabled or the runner token is invalid.",
            ),
            HTTPStatus.FORBIDDEN,
        )

    def handle_n1e_get(self, parsed: Any) -> None:
        if not self.n1e_access_allowed():
            self.send_n1e_forbidden()
            return
        query = parse_qs(parsed.query)
        job_id = (query.get("job_id") or [""])[0] or None
        if parsed.path == "/api/n1e/status":
            self.send_json(read_n1e_status(self.server.output_root, job_id))
            return
        if parsed.path == "/api/n1e/bundle":
            status = read_n1e_status(self.server.output_root, job_id)
            selected_job_id = status.get("job_id") if status.get("ok") else None
            if not selected_job_id:
                self.send_json(status, HTTPStatus.NOT_FOUND)
                return
            path = n1e_bundle_path(self.server.output_root, str(selected_job_id))
            if not path.exists():
                self.send_json(error_response("N1E_BUNDLE_NOT_FOUND", "N1E origin bundle is not available."), HTTPStatus.NOT_FOUND)
                return
            self.send_json(read_json(path))
            return
        self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)

    def handle_n1e_post(self, parsed: Any) -> None:
        if not self.n1e_access_allowed():
            self.send_n1e_forbidden()
            return
        if parsed.path == "/api/n1e/recover-latest":
            self.send_json(ok(recover_latest_n1e_failure_bundle(output_root=self.server.output_root)))
            return
        if parsed.path != "/api/n1e/run":
            self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
            return
        job_id = "n1e_" + uuid.uuid4().hex[:16]
        write_n1e_status(self.server.output_root, job_id, {"status": "queued", "stage": "queued"})
        thread = threading.Thread(
            target=run_n1e_origin_bundle,
            kwargs={"job_id": job_id, "output_root": self.server.output_root},
            name=f"n1e-runner-{job_id}",
            daemon=True,
        )
        with N1E_JOB_THREADS_LOCK:
            N1E_JOB_THREADS[job_id] = thread
        thread.start()
        self.send_json(ok({"job_id": job_id, "status": "queued"}), HTTPStatus.ACCEPTED)

    def handle_n1f_get(self, parsed: Any) -> None:
        if not self.n1e_access_allowed():
            self.send_n1e_forbidden()
            return
        query = parse_qs(parsed.query)
        job_id = (query.get("job_id") or [""])[0] or None
        if parsed.path == "/api/n1f/status":
            self.send_json(read_n1f_status(self.server.output_root, job_id))
            return
        if parsed.path == "/api/n1f/bundle":
            status = read_n1f_status(self.server.output_root, job_id)
            selected_job_id = status.get("job_id") if status.get("ok") else None
            if not selected_job_id:
                self.send_json(status, HTTPStatus.NOT_FOUND)
                return
            path = n1f_bundle_path(self.server.output_root, str(selected_job_id))
            if not path.exists():
                self.send_json(error_response("N1F_BUNDLE_NOT_FOUND", "N1F origin bundle is not available."), HTTPStatus.NOT_FOUND)
                return
            self.send_json(read_json(path))
            return
        self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)

    def handle_n1f_post(self, parsed: Any) -> None:
        if not self.n1e_access_allowed():
            self.send_n1e_forbidden()
            return
        if parsed.path != "/api/n1f/run":
            self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
            return
        job_id = "n1f_" + uuid.uuid4().hex[:16]
        write_n1f_status(self.server.output_root, job_id, {"status": "queued", "stage": "queued"})
        thread = threading.Thread(
            target=run_n1f_origin_bundle,
            kwargs={"job_id": job_id, "output_root": self.server.output_root},
            name=f"n1f-runner-{job_id}",
            daemon=True,
        )
        with N1E_JOB_THREADS_LOCK:
            N1E_JOB_THREADS[job_id] = thread
        thread.start()
        self.send_json(ok({"job_id": job_id, "status": "queued"}), HTTPStatus.ACCEPTED)

    def set_demo_cookie_if_needed(self, parsed: Any) -> None:
        if not DEMO_ACCESS_TOKEN:
            return
        query_token = (parse_qs(parsed.query).get("access_token") or [""])[0]
        if DEMO_ACCESS_QUERY_TOKEN_ENABLED and query_token == DEMO_ACCESS_TOKEN:
            self.send_header("Set-Cookie", f"demo_access_token={DEMO_ACCESS_TOKEN}; Path=/; HttpOnly; SameSite=Lax")

    def redirect_with_demo_cookie(self, parsed: Any) -> bool:
        if not DEMO_ACCESS_TOKEN:
            return False
        query_token = (parse_qs(parsed.query).get("access_token") or [""])[0]
        if not DEMO_ACCESS_QUERY_TOKEN_ENABLED or query_token != DEMO_ACCESS_TOKEN:
            return False
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", parsed.path or "/")
        self.set_demo_cookie_if_needed(parsed)
        self.end_headers()
        return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_json(ok({"service": "workbench_alpha_host", "status": "ALIVE"}))
            return
        if parsed.path == "/readyz":
            report = readiness_report(static_root=self.server.static_root, output_root=self.server.output_root)
            status = HTTPStatus.OK if report["status"] == "READY" else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_json(ok(report), status)
            return
        if parsed.path.startswith("/api/n1e/"):
            self.handle_n1e_get(parsed)
            return
        if parsed.path.startswith("/api/n1f/"):
            self.handle_n1f_get(parsed)
            return
        if self.redirect_with_demo_cookie(parsed):
            return
        if not self.demo_access_allowed(parsed):
            self.send_demo_auth_required()
            return
        if parsed.path == "/api/health":
            self.send_json(ok({"service": "workbench_alpha_host", "mcp_adapter": False}))
            return
        if parsed.path == "/api/bootstrap":
            self.send_json(self.bootstrap())
            return
        if parsed.path == "/api/matches":
            self.send_json(validate_public_response("MatchLibraryResponse", match_library()))
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
        if parsed.path.startswith("/api/n1e/"):
            self.handle_n1e_post(parsed)
            return
        if parsed.path.startswith("/api/n1f/"):
            self.handle_n1f_post(parsed)
            return
        if not self.demo_access_allowed(parsed):
            self.send_demo_auth_required()
            return
        try:
            payload = self.read_body()
            if parsed.path == "/api/interpret":
                self.send_json(
                    validate_public_response(
                        "InterpretResponse",
                        interpret_request(payload, output_root=self.server.output_root),
                    )
                )
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
                    "status": "HERMES_CONFIGURED" if hermes_enabled() and shutil.which("hermes") is not None else "MODEL_UNAVAILABLE",
                    "message": (
                        "Hermes is configured; each interpretation is probed and validated at request time."
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
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--static-root", type=Path, default=DEFAULT_STATIC_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_WORKSHOP_ROOT)
    args = parser.parse_args()
    if WORKBENCH_PREWARM_EXECUTION_CACHE:
        prewarm_execution_cache(
            output_root=args.output_root,
            recipe_ids=WORKBENCH_PREWARM_RECIPE_IDS,
            result_limit=WORKBENCH_PREWARM_RESULT_LIMIT,
        )
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
