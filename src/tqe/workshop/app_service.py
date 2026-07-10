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
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
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

from tqe.data.team_branding import team_branding_for
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
    replay_window_from_canonical,
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
HIGH_BYPASS_PLAN_PATH = Path("config/query-plans/high_bypass_completed_pass.experimental.v1.json")
LINE_BREAK_SUPPORT_RESPONSE_PLAN_PATH = Path("config/query-plans/line_break_support_response.experimental.v1.json")
FILM_ROOM_R2_4_PLAN_PATH = Path("delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_v0.json")
FILM_ROOM_R2_4_TABLE_PATH = Path("delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_table.json")
FILM_ROOM_R2_2_PLAN_PATH = Path("delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json")
FILM_ROOM_R2_2_TABLE_PATH = Path("delivery/packets/r2-2-flagship/fragile_retention_rate_table.json")
FILM_ROOM_COUNTERATTACK_QUESTION = (
    "After a regain, how often does the team progress the ball by carry and keep it with a controlled pass?"
)
FILM_ROOM_FRAGILE_RETENTION_QUESTION = "When a team faces the fragile condition, how often is possession retained?"
MOMENT_ZERO_PAYLOAD_PATH = Path("apps/workbench-alpha/src/generated/moment-zero.json")
MOMENT_LINE_BREAK_SUPPORTED_PAYLOAD_PATH = Path("apps/workbench-alpha/src/generated/moment-line-break-supported.json")
MOMENT_HIGH_BYPASS_PAYLOAD_PATH = Path("apps/workbench-alpha/src/generated/moment-high-bypass.json")
MOMENT_ZERO_CATALOG_PATH = Path("apps/workbench-alpha/src/generated/moment-zero-catalog.json")
MOMENT_LINE_BREAK_SUPPORTED_CATALOG_PATH = Path("apps/workbench-alpha/src/generated/moment-line-break-supported-catalog.json")
MOMENT_HIGH_BYPASS_CATALOG_PATH = Path("apps/workbench-alpha/src/generated/moment-high-bypass-catalog.json")
DEFAULT_STATIC_ROOT = Path("apps/workbench-alpha/dist")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/Users/luisrevilla/.hermes-priori"))
HERMES_DB = HERMES_HOME / "state.db"
HERMES_WORKSHOP_ROOT = Path(
    os.environ.get("WORKBENCH_HERMES_WORKSHOP_ROOT")
    or os.environ.get("TQE_WORKSHOP_OUTPUT_ROOT")
    or os.environ.get("TQE_RUNTIME_ROOT")
    or "artifacts/m1.2/workshop"
)
HERMES_PROVIDER = os.environ.get("WORKBENCH_HERMES_PROVIDER", "openai-codex")
HERMES_MODEL = os.environ.get("WORKBENCH_HERMES_MODEL", "gpt-5.5")
HERMES_TOOLSET = os.environ.get("WORKBENCH_HERMES_TOOLSET", "mcp-priori_tactical")
HERMES_TIMEOUT_SECONDS = int(os.environ.get("WORKBENCH_HERMES_TIMEOUT_SECONDS", "240"))
N1E_RUNNER_ENABLED = os.environ.get("ENABLE_N1E_RUNNER", "").strip() == "1"
N1E_RUN_TOKEN = os.environ.get("N1E_RUN_TOKEN", "").strip()
N1E_RESULT_LIMIT = int(os.environ.get("N1E_RESULT_LIMIT", "25"))
DEMO_ACCESS_TOKEN = os.environ.get("DEMO_ACCESS_TOKEN", "").strip()
DEMO_ACCESS_QUERY_TOKEN_ENABLED = os.environ.get("DEMO_ACCESS_QUERY_TOKEN_ENABLED", "").strip() == "1"
TQE_PUBLIC_MODE = os.environ.get("TQE_PUBLIC_MODE", "").strip() == "1"
TQE_PUBLIC_ASK_TIMEOUT_SECONDS = float(os.environ.get("TQE_PUBLIC_ASK_TIMEOUT_SECONDS", "120"))
WORKBENCH_PREWARM_EXECUTION_CACHE = os.environ.get("WORKBENCH_PREWARM_EXECUTION_CACHE", "").strip() == "1"
WORKBENCH_PREWARM_RESULT_LIMIT = int(os.environ.get("WORKBENCH_PREWARM_RESULT_LIMIT", "3"))
WORKBENCH_PREWARM_FILM_ROOM = os.environ.get("WORKBENCH_PREWARM_FILM_ROOM", "1").strip() != "0"
WORKBENCH_FILM_ROOM_RESULT_LIMIT = int(os.environ.get("WORKBENCH_FILM_ROOM_RESULT_LIMIT", "25"))
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
FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA = "film_room.descriptor_index.v1"
FILM_ROOM_HYDRATION_SCHEMA = "film_room.chain_hydration.v1"
FILM_ROOM_DESCRIPTOR_FRAGMENT_DIR = "film-room-descriptor-fragments"
FILM_ROOM_HYDRATION_DIR = "film-room-hydration"
FILM_ROOM_DESCRIPTOR_INDEX_FILE = "film-room-descriptor-index.json"
N1D_ATTESTATION_PATH = Path("delivery/n1d/n1d1-attestation.json")
N1D_MANIFEST_PATH = Path("delivery/n1d/n1d-canonical-freeze-manifest.json")
N1D_ORIGIN_BUNDLE_PATH = Path("delivery/n1d/n1f-origin-bundle.json")
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
FILM_ROOM_PREWARMED_RESPONSES: dict[str, dict[str, Any]] = {}
FILM_ROOM_PREWARM_RECORDS: list[dict[str, Any]] = []
FILM_ROOM_PREWARM_LOCK = threading.Lock()
FILM_ROOM_PREWARM_STATE: dict[str, Any] = {
    "state": "warming",
    "started_at": None,
    "completed_at": None,
    "items": [],
    "last_error": None,
}
FILM_ROOM_REPLAY_INDEX: dict[str, dict[str, Any]] = {}
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
    preset_id: Literal[
        "approved_block_shift",
        "experimental_corridor",
        "experimental_high_bypass",
        "experimental_line_break_support_response",
    ]
    label: str
    recipe: RecipeCardResponse
    plan_hash: str


class CapabilitySummaryResponse(WorkbenchResponseModel):
    primitive_count: int
    relation_count: int
    operator_count: int
    tools: list[str]
    execute_tool_description: dict[str, Any]


class TeamBrandResponse(WorkbenchResponseModel):
    team_id: str | None = None
    team_name: str
    short_name: str
    abbreviation: str
    logo_url: str | None = None
    logo_source: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class MatchSummaryResponse(WorkbenchResponseModel):
    match_id: str
    match_title: str
    home_team: str
    away_team: str
    home_team_brand: TeamBrandResponse
    away_team_brand: TeamBrandResponse
    result: str | None = None
    match_day: str | None = None
    kickoff_time_utc: str | None = None


class MatchLibraryResponse(WorkbenchResponseModel):
    ok: Literal[True]
    perspective_team: str
    perspective_team_brand: TeamBrandResponse
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
    "HERMES_EXPERIMENTAL_UNVERIFIED",
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


CoachInterpretStatus = Literal[
    "moment_found",
    "no_moments_found",
    "clarification_required",
    "understood_but_not_expressible",
]


class CoachMomentResponse(WorkbenchResponseModel):
    moment_id: str
    result_count: int
    replay_payload: dict[str, Any] | None = None
    evidence_fields: list[str]


class CoachInterpretResponse(WorkbenchResponseModel):
    ok: Literal[True]
    status: CoachInterpretStatus
    query: str
    display_answer: str
    suggestions: list[str] = Field(default_factory=list)
    match_scope: dict[str, Any] = Field(default_factory=dict)
    meaning_definition: str | None = None
    interpretation_rules: list[str] = Field(default_factory=list)
    contract_hash: str | None = None
    plan_hash: str | None = None
    result_count: int = 0
    moments: list[CoachMomentResponse] = Field(default_factory=list)
    gap: dict[str, Any] | None = None
    audit: dict[str, Any] = Field(default_factory=dict)


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


FilmRoomSourceKind = Literal[
    "result",
    "target",
    "chain_record",
    "certified_table_partition",
]


class ReplayPayloadResponse(WorkbenchResponseModel):
    schema_version: str
    replay_window_id: str
    source_kind: FilmRoomSourceKind
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
    overlays: dict[str, Any] = Field(default_factory=dict)


class FilmRoomIntervalMetricResponse(WorkbenchResponseModel):
    label: str
    observed: float
    lower: float
    upper: float
    unknown_count: int
    source: dict[str, Any]


class FilmRoomMomentResponse(WorkbenchResponseModel):
    result_id: str
    source_kind: FilmRoomSourceKind
    classification: str
    match_id: str
    period: str
    anchor_frame_id: int
    start_frame_id: int | None = None
    end_frame_id: int | None = None
    match_time_ms: int | None = None
    requested_evidence: dict[str, Any]
    replay_window_id: str | None = None
    replay_start_frame_id: int | None = None
    replay_end_frame_id: int | None = None
    evidence_row: dict[str, Any] | None = None
    unknown_reason: str | None = None
    chain_status: str | None = None
    chain_reason: str | None = None
    evidence_overlay: dict[str, Any] = Field(default_factory=dict)


class FilmRoomExecutionRecordResponse(WorkbenchResponseModel):
    role: str
    submit: dict[str, Any]
    validation: dict[str, Any]
    confirmation: dict[str, Any]
    cache_before: dict[str, Any]
    execution: dict[str, Any]
    runtime_evidence_sources: list[dict[str, Any]] = Field(default_factory=list)
    cache_after_execute: dict[str, Any]
    draft_record: dict[str, Any]
    bound_record: dict[str, Any]


class FilmRoomProvenanceResponse(WorkbenchResponseModel):
    plan_hash: str
    synthesized_document_hash: str
    expression_hash: str | None = None
    certified_table_path: str | None = None
    certified_table_hash: str | None = None
    certified_plan_path: str | None = None
    certified_period_records_hash: str | None = None
    bound_plan_hashes: dict[str, str]
    replay_window_id: str | None = None
    canonical_sources: dict[str, str]
    runtime_commit: str | None = None
    tree: str | None = None


class FilmRoomAnswerResponse(WorkbenchResponseModel):
    status: Literal["answer_ready"]
    compiled_chips: list[str]
    document: dict[str, Any]
    certified_evidence_rows: list[dict[str, Any]]
    runtime_evidence_rows: list[dict[str, Any]]
    evidence_rows_kind: Literal["certified", "runtime"]
    interval_metric: FilmRoomIntervalMetricResponse | None = None
    moments: list[FilmRoomMomentResponse]
    moment_total_count: int
    visible_moment_count: int
    replay: ReplayPayloadResponse | None = None
    executions: list[FilmRoomExecutionRecordResponse]
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    provenance: FilmRoomProvenanceResponse


class FilmRoomAskResponse(WorkbenchResponseModel):
    ok: Literal[True]
    outcome: Literal["expression", "clarification_required", "understood_but_not_expressible", "unsupported_modality"]
    request_text: str
    provider: str
    model: str
    latency_ms: int
    latency_breakdown_ms: dict[str, int]
    hermes: dict[str, Any]
    answer: FilmRoomAnswerResponse | None = None
    clarification: dict[str, Any] | None = None
    refusal: dict[str, Any] | None = None


class FilmRoomBootstrapResponse(WorkbenchResponseModel):
    ok: Literal[True]
    state: Literal["ready", "warming"]
    provider: str
    model: str
    billing_surface: str
    flagship_plan_hashes: dict[str, str | None]
    prewarm_records: list[dict[str, Any]]
    warming: dict[str, Any] | None = None
    prewarmed_response: dict[str, Any] | None = None
    answer: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None


class FilmRoomReplayFrameResponse(WorkbenchResponseModel):
    ok: Literal[True]
    replay_window_id: str
    frame_id: int
    frame_sha256: str
    canonical_sources: dict[str, str]
    frame: ReplayFrameResponse


class FilmRoomReplayWindowResponse(WorkbenchResponseModel):
    ok: Literal[True]
    replay_window_id: str
    replay: ReplayPayloadResponse


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
    "CoachInterpretResponse": CoachInterpretResponse,
    "PlanResponse": PlanResponse,
    "InterpretResponse": InterpretResponse,
    "SubmitValidateResponse": SubmitValidateResponseEnvelope,
    "ConfirmationResponse": ConfirmationResponseEnvelope,
    "ExecutionResponse": ExecutionResponseEnvelope,
    "ExecutionProgressResponse": ExecutionProgressResponse,
    "FilmRoomBootstrapResponse": FilmRoomBootstrapResponse,
    "FilmRoomAskResponse": FilmRoomAskResponse,
    "FilmRoomReplayFrameResponse": FilmRoomReplayFrameResponse,
    "FilmRoomReplayWindowResponse": FilmRoomReplayWindowResponse,
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

COACH_COMPILER_LOCK = threading.Lock()
COACH_SEARCH_EXECUTOR: Any = None
COACH_RESPONSE_CACHE: dict[str, dict[str, Any]] = {}
COACH_ALLOWED_EXCLUDED_REFS = {"relation_destination_entry_classification", "outcome_classification"}
COACH_MATCH_IDS = tuple(
    match_id.strip()
    for match_id in os.environ.get(
        "TQE_COACH_MATCH_IDS",
        "J03WOH,J03WOY,J03WPY,J03WQQ,J03WR9,J03WMX,J03WN1",
    ).split(",")
    if match_id.strip()
)
COACH_MATCH_SCOPE = {
    "match_ids": list(COACH_MATCH_IDS),
    "periods": ["firstHalf", "secondHalf"],
    "perspective_team_role": "home",
}
COACH_SUGGESTIONS = [
    "Show line breaks with underneath support",
    "Show line breaks with no underneath outlet",
    "Show high-bypass passes",
    "Show line breaks with two underneath outlets",
    "Show expected pass completion",
    "Show dangerous attacks",
]
COACH_DISPLAY_TEMPLATES = {
    "moment_found.line_break_no_underneath_support": "Line broken. The outlet space stays empty.",
    "moment_found.line_break_with_underneath_outlet": "Line broken. Support arrives underneath.",
    "moment_found.high_bypass_completed_pass": "Passes bypassed multiple opponents with control after reception.",
    "no_moments_found.line_break_no_underneath_support": "Across these matches, that clean-control line-break moment did not appear.",
    "no_moments_found.line_break_with_two_underneath_outlets": "Across these matches, no clean-control line break had two underneath outlets.",
    "no_moments_found.line_break_with_underneath_outlet": "Across these matches, that clean-control supported line-break moment did not appear.",
    "no_moments_found.high_bypass_completed_pass": "Across these matches, no clean-control pass bypassed five opponents.",
    "no_moments_found.progressive_carry_under_pressure": "Across these matches, no carry progressed forward under defender pressure.",
    "no_moments_found.give_and_go_sequence": "Across these matches, no give-and-go sequence appeared.",
    "no_moments_found.onward_two_pass_sequence": "Across these matches, no onward two-pass sequence appeared.",
    "no_moments_found.default": "Across these matches, that observed moment did not appear.",
    "clarification_required.tactical_meaning_underspecified": "Pick the observable part of the attack you want to see.",
    "clarification_required.request_not_recognized": "Name the action, players, and moment you want to see.",
    "understood_but_not_expressible.unsupported_modality": "This view stays with observed moments.",
    "understood_but_not_expressible.no_replay_surface": "I can show line-break moments in this preview.",
    "understood_but_not_expressible.default": "I can show observed moments from the current vocabulary.",
}
COACH_TEMPLATE_PROHIBITED_TERMS = {
    "best",
    "better",
    "caused",
    "caught out",
    "cleanly",
    "dangerous",
    "decided",
    "effective",
    "good",
    "intent",
    "optimal",
    "planned",
    "should",
    "smart",
    "worked",
}
COACH_PRODUCT_CLAIM_REQUIREMENTS = {
    "line_break_no_underneath_support": {
        "claim_id": "observed_line_break_without_underneath_outlet_with_clean_control",
        "requirements": [
            {"path": "moment.requested_evidence.line_break_status", "equals": "PASS"},
            {"path": "moment.requested_evidence.support_arrival_status", "equals": "FAIL"},
            {"path": "moment.support_region.support_arrival_status", "equals": "FAIL"},
            {"path": "moment.clean_control_retention.mode", "equals": "tracking_clean_team_control_after_reception_v0"},
            {"path": "moment.clean_control_retention.status", "equals": "PASS"},
        ],
    },
    "line_break_with_underneath_outlet": {
        "claim_id": "observed_line_break_with_underneath_outlet_with_clean_control",
        "requirements": [
            {"path": "moment.requested_evidence.line_break_status", "equals": "PASS"},
            {"path": "moment.requested_evidence.support_arrival_status", "equals": "PASS"},
            {"path": "moment.support_region.support_arrival_status", "equals": "PASS"},
            {"path": "moment.clean_control_retention.mode", "equals": "tracking_clean_team_control_after_reception_v0"},
            {"path": "moment.clean_control_retention.status", "equals": "PASS"},
        ],
    },
    "high_bypass_completed_pass": {
        "claim_id": "observed_high_bypass_pass_with_clean_control_after_reception",
        "requirements": [
            {"path": "moment.requested_evidence.evaluation_status", "equals": "PASS"},
            {"path": "moment.opponents_bypassed_count", "gte": 5},
            {"path": "moment.clean_control_retention.mode", "equals": "tracking_clean_team_control_after_reception_v0"},
            {"path": "moment.clean_control_retention.status", "equals": "PASS"},
        ],
    },
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
    "DEMO_TOKEN_REQUIRED": "Demo token is required for public live asks.",
    "ASKS_DISABLED": "Live asks are disabled in this environment.",
    "MODEL_OUTPUT_TRUNCATED": "The model answer was cut off before it produced complete JSON.",
    "UNKNOWN_HANDLE": "Requested handle is unavailable.",
    "NO_REPLAY_WINDOW": "No replay window is available for that request.",
    "EXECUTION_NOT_CONFIRMED": "Execution requires host-generated confirmation authorization.",
    "CAPABILITY_GAP": "Requested capability is unavailable through this API.",
    "PLAN_NOT_FOUND": "Requested plan was not found.",
    "INTERNAL_ERROR": "Internal host service error.",
}


class RequestSchemaError(ValueError):
    """Raised only while decoding or validating an inbound request payload."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def request_schema_error(exc: Exception, *, expected: str) -> RequestSchemaError:
    return RequestSchemaError(str(exc), details={"expected": expected, "reason": str(exc)})


def require_request_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RequestSchemaError(
            "request body must be a JSON object",
            details={"expected": "JSON object request body"},
        )
    return value


def validate_request(factory: Any, *, expected: str) -> Any:
    try:
        return factory()
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise request_schema_error(exc, expected=expected) from exc


def validate_film_room_ask_payload(payload: dict[str, Any]) -> None:
    def parse() -> None:
        text = str(payload.get("text") or payload.get("query") or "").strip()
        if not text:
            raise ValueError("text must be non-empty")
        film_room_compile_context(payload)

    validate_request(parse, expected='JSON object with non-empty "text" and optional "context"')


def validate_film_room_replay_window_payload(payload: dict[str, Any]) -> None:
    def parse() -> None:
        replay_window_id = str(payload.get("replay_window_id") or "").strip()
        if not replay_window_id:
            raise ValueError("replay_window_id must be non-empty")

    validate_request(parse, expected='JSON object with non-empty "replay_window_id"')


def validate_film_room_replay_frame_payload(payload: dict[str, Any]) -> None:
    def parse() -> None:
        replay_window_id = str(payload.get("replay_window_id") or "").strip()
        if not replay_window_id:
            raise ValueError("replay_window_id must be non-empty")
        int(payload.get("frame_id"))

    validate_request(parse, expected='JSON object with "replay_window_id" and integer "frame_id"')


def log_internal_error(exc: Exception, *, path: str) -> str:
    correlation_id = f"err_{uuid.uuid4().hex[:12]}"
    payload = {
        "event": "workbench_internal_error",
        "correlation_id": correlation_id,
        "path": path,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)
    return correlation_id


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
    if recipe_id == "high_bypass_completed_pass_v1":
        return read_json(HIGH_BYPASS_PLAN_PATH)
    if recipe_id == "line_break_support_response_v1":
        return read_json(LINE_BREAK_SUPPORT_RESPONSE_PLAN_PATH)
    raise ValueError(f"Unsupported recipe_id: {recipe_id}")


def plan_path_for_preset(preset_id: str | None, selected_recipe_id: str | None) -> Path | None:
    key = (preset_id or selected_recipe_id or "").strip()
    if key in {"approved_block_shift", "ball_side_block_shift_v1"}:
        return APPROVED_PLAN_PATH
    if key in {"experimental_corridor", "possession_corridor_availability_v1"}:
        return CORRIDOR_PLAN_PATH
    if key in {"experimental_high_bypass", "high_bypass_completed_pass_v1"}:
        return HIGH_BYPASS_PLAN_PATH
    if key in {"experimental_line_break_support_response", "line_break_support_response_v1"}:
        return LINE_BREAK_SUPPORT_RESPONSE_PLAN_PATH
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
    teams_by_match_role = canonical_team_records_by_match_role()
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
                home_record = teams_by_match_role.get((match_id, "home"), {})
                away_record = teams_by_match_role.get((match_id, "away"), {})
                home_name = clean_optional_string(home_record.get("team_name")) or (home_team if separator else "Fortuna Düsseldorf")
                away_name = clean_optional_string(away_record.get("team_name")) or (away_team if separator else title)
                rows.append(
                    {
                        "match_id": match_id,
                        "match_title": title,
                        "home_team": home_name,
                        "away_team": away_name,
                        "home_team_brand": team_brand_payload(home_record, fallback_name=home_name),
                        "away_team_brand": team_brand_payload(away_record, fallback_name=away_name),
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
                "home_team_brand": team_brand_payload({"team_id": "DFL-CLU-00000P", "team_name": "Fortuna Düsseldorf"}),
                "away_team_brand": team_brand_payload({"team_name": match_id}),
                "result": None,
                "match_day": None,
                "kickoff_time_utc": None,
            }
            for match_id in manifest_ids
        ]
    order = {match_id: index for index, match_id in enumerate(manifest_ids)}
    rows.sort(key=lambda item: order.get(str(item["match_id"]), len(order)))
    perspective_brand = team_brand_payload({"team_id": "DFL-CLU-00000P", "team_name": "Fortuna Düsseldorf"})
    return ok(
        {
            "perspective_team": "Fortuna Düsseldorf",
            "perspective_team_brand": perspective_brand,
            "default_match_ids": manifest_ids or [str(item["match_id"]) for item in rows],
            "matches": rows,
        }
    )


def canonical_team_records_by_match_role() -> dict[tuple[str, str], dict[str, Any]]:
    teams_path = DEFAULT_CANONICAL_ROOT / "teams.parquet"
    if not teams_path.exists():
        return {}
    try:
        import pandas as pd

        frame = pd.read_parquet(teams_path)
    except Exception:  # noqa: BLE001 - logos are display metadata; never break query execution.
        return {}
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for record in frame.to_dict(orient="records"):
        match_id = clean_optional_string(record.get("match_id"))
        team_role = clean_optional_string(record.get("team_role"))
        if match_id and team_role:
            records[(match_id, team_role)] = record
    return records


def team_brand_payload(record: dict[str, Any], *, fallback_name: str | None = None) -> dict[str, Any]:
    team_id = clean_optional_string(record.get("team_id"))
    team_name = clean_optional_string(record.get("team_name")) or fallback_name or "Unknown team"
    branding = team_branding_for(team_id, team_name)
    return {
        "team_id": team_id or (branding.team_id if branding else None),
        "team_name": team_name,
        "short_name": clean_optional_string(record.get("team_short_name"))
        or (branding.short_name if branding else short_team_name(team_name)),
        "abbreviation": clean_optional_string(record.get("team_abbreviation"))
        or (branding.abbreviation if branding else team_initials(team_name)),
        "logo_url": clean_optional_string(record.get("logo_url")) or (branding.logo_url if branding else None),
        "logo_source": clean_optional_string(record.get("logo_source")) or (branding.logo_source if branding else None),
        "primary_color": clean_optional_string(record.get("primary_color")) or (branding.primary_color if branding else None),
        "secondary_color": clean_optional_string(record.get("secondary_color")) or (branding.secondary_color if branding else None),
    }


def clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null"}:
        return None
    return text


def short_team_name(value: str) -> str:
    return (
        value.replace("F.C. ", "")
        .replace("1. FC ", "")
        .replace("FC ", "")
        .replace(" 1848", "")
        .strip()
        or value
    )


def team_initials(value: str) -> str:
    parts = [part for part in value.replace(".", " ").split() if part]
    return "".join(part[0].upper() for part in parts[:3]) or "?"


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
    if candidate.recipe.recipe_id == "possession_corridor_destination_entry_v1" and not attested_scope_matches(plan_document):
        raise CapabilityGap("Attested Hermes novel-composition proof is locked to its frozen match, period, perspective, and result-limit scope")
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


def coach_template(key: str) -> str:
    value = COACH_DISPLAY_TEMPLATES[key]
    lowered = value.casefold()
    forbidden = sorted(term for term in COACH_TEMPLATE_PROHIBITED_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered))
    if forbidden:
        raise ValueError(f"Coach display template {key!r} contains prohibited terms: {forbidden}")
    return value


def coach_product_claim_gate(kind: str, replay_payload: dict[str, Any]) -> dict[str, Any]:
    spec = COACH_PRODUCT_CLAIM_REQUIREMENTS.get(kind)
    if spec is None:
        return {
            "passed": False,
            "kind": kind,
            "claim_id": None,
            "failures": [{"path": "kind", "reason": "claim_requirements_missing"}],
        }
    failures = []
    for requirement in spec["requirements"]:
        path = str(requirement["path"])
        value = dotted_get(replay_payload, path)
        if "equals" in requirement and value != requirement["equals"]:
            failures.append({"path": path, "expected": requirement["equals"], "actual": value})
        if "gte" in requirement:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                failures.append({"path": path, "expected_gte": requirement["gte"], "actual": value})
                continue
            if numeric < float(requirement["gte"]):
                failures.append({"path": path, "expected_gte": requirement["gte"], "actual": value})
    return {
        "passed": not failures,
        "kind": kind,
        "claim_id": spec["claim_id"],
        "failures": failures,
    }


def dotted_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def coach_search_executor() -> Any:
    global COACH_SEARCH_EXECUTOR
    if COACH_SEARCH_EXECUTOR is None:
        from scripts.coverage_map.compiler_search_reachability import TacticalQueryExecutor

        COACH_SEARCH_EXECUTOR = TacticalQueryExecutor(canonical_root=DEFAULT_CANONICAL_ROOT, raw_root=DEFAULT_RAW_ROOT)
    return COACH_SEARCH_EXECUTOR


def coach_interpret_request(payload: dict[str, Any], *, output_root: Path = DEFAULT_WORKSHOP_ROOT) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        return coach_clarification_response(
            query=query,
            display_answer=coach_template("clarification_required.request_not_recognized"),
            clarification_codes=["REQUEST_EMPTY"],
            clarification_questions=["Ask for an observable football moment."],
        )

    from scripts.coverage_map.semantic_contract_scl0 import generate_contract_from_meaning
    from scripts.coverage_map.semantic_nl_interpreter_scl0 import CLARIFICATION_REQUIRED, MEANING_DEFINITION, interpret_request as scl_nl_interpret
    from scripts.coverage_map import compiler_search_reachability as search

    meaning = scl_nl_interpret(query)
    meaning_payload = meaning.as_dict()
    if meaning.status == CLARIFICATION_REQUIRED:
        code = (meaning.clarification_codes or ("REQUEST_NOT_RECOGNIZED",))[0]
        template_key = (
            "clarification_required.tactical_meaning_underspecified"
            if code == "TACTICAL_MEANING_UNDERSPECIFIED"
            else "clarification_required.request_not_recognized"
        )
        return coach_clarification_response(
            query=query,
            display_answer=coach_template(template_key),
            clarification_codes=list(meaning.clarification_codes),
            clarification_questions=list(meaning.clarification_questions),
            audit={"pipeline": "scl_nl_to_search.v0", "meaning": meaning_payload},
        )
    if meaning.status != MEANING_DEFINITION or not meaning.meaning_definition:
        return coach_cant_yet_response(
            query=query,
            display_answer=coach_template("understood_but_not_expressible.default"),
            meaning_definition=meaning.meaning_definition,
            interpretation_rules=list(meaning.interpretation_rules),
            gap={"kind": "nl_understood_but_not_expressible", "message": "The request did not produce an executable meaning definition."},
            audit={"pipeline": "scl_nl_to_search.v0", "meaning": meaning_payload},
        )

    contract, traces = generate_contract_from_meaning(meaning.meaning_definition)
    contract_hash = stable_hash(contract)
    if coach_preview_runtime_family_without_surface(contract):
        return coach_cant_yet_response(
            query=query,
            display_answer=coach_template("understood_but_not_expressible.no_replay_surface"),
            meaning_definition=meaning.meaning_definition,
            interpretation_rules=list(meaning.interpretation_rules),
            contract_hash=contract_hash,
            gap={
                "kind": "preview_surface_missing",
                "message": "The request is understood, but this public coach preview only executes the line-break support family.",
            },
            audit={
                "pipeline": "scl_nl_to_scl_contract_to_search.v0",
                "meaning": meaning_payload,
                "trace_count": len(traces),
                "evidence_fields": contract.get("required_evidence", []),
                "cache_status": "SKIPPED_PREVIEW_SURFACE",
            },
        )
    cached_response = COACH_RESPONSE_CACHE.get(contract_hash)
    if cached_response is not None:
        response = deepcopy(cached_response)
        response["query"] = query
        response.setdefault("audit", {})["cache_status"] = "HIT"
        return response
    target_id = f"coach_{contract_hash[:12]}"
    target = {
        "target_id": target_id,
        "concept": target_id,
        "target_contract": contract,
    }
    row = {"concept": target_id, "classification": "coach_prompt"}

    with COACH_COMPILER_LOCK:
        old_plan_dir = search.PLAN_DIR
        old_match_ids = search.MATCH_IDS
        search.PLAN_DIR = output_root / "coach-compiler" / "plans"
        search.MATCH_IDS = list(COACH_MATCH_IDS)
        search.PLAN_DIR.mkdir(parents=True, exist_ok=True)
        try:
            catalog = search.CatalogIndex(excluded_refs=COACH_ALLOWED_EXCLUDED_REFS)
            result = search.evaluate_target(
                target=target,
                row=row,
                catalog=catalog,
                executor=coach_search_executor(),
            )
        finally:
            search.PLAN_DIR = old_plan_dir
            search.MATCH_IDS = old_match_ids

    audit = {
        "pipeline": "scl_nl_to_scl_contract_to_search.v0",
        "meaning": meaning_payload,
        "trace_count": len(traces),
        "evidence_fields": contract.get("required_evidence", []),
        "providers_used": result.get("providers_used", []),
        "rules_used": result.get("rules_used", []),
        "failure_taxonomy": result.get("failure_taxonomy"),
        "search_budget_label": result.get("search_budget_label"),
        "requested_evidence_failure_count": result.get("requested_evidence_failure_count"),
        "cache_status": "MISS",
    }

    if result.get("result") == "compiler_reachable":
        result_count = int(result.get("result_count") or 0)
        plan_hash = clean_optional_string(result.get("document_hash"))
        visual_kind = coach_visual_moment_kind(contract)
        if result_count <= 0:
            no_moments_kind = coach_no_moments_kind(contract)
            response = ok(
                {
                    "status": "no_moments_found",
                    "query": query,
                    "display_answer": coach_template(f"no_moments_found.{no_moments_kind}"),
                    "suggestions": COACH_SUGGESTIONS,
                    "match_scope": COACH_MATCH_SCOPE,
                    "meaning_definition": meaning.meaning_definition,
                    "interpretation_rules": list(meaning.interpretation_rules),
                    "contract_hash": contract_hash,
                    "plan_hash": plan_hash,
                    "result_count": 0,
                    "moments": [],
                    "gap": None,
                    "audit": audit,
                }
            )
            COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
            return response
        if visual_kind is None:
            response = coach_cant_yet_response(
                query=query,
                display_answer=coach_template("understood_but_not_expressible.no_replay_surface"),
                meaning_definition=meaning.meaning_definition,
                interpretation_rules=list(meaning.interpretation_rules),
                contract_hash=contract_hash,
                gap={
                    "kind": "replay_surface_missing",
                    "message": "The compiler found observed moments, but this coach preview has no claim-bounded replay renderer for that contract yet.",
                    "result_count": result_count,
                    "plan_hash": plan_hash,
                },
                audit=audit,
            )
            COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
            return response
        catalog_replay_payloads = coach_moment_payloads(visual_kind)
        surface_replay_payloads = coach_surface_moment_payloads(visual_kind, catalog_replay_payloads)
        surface_result_count = len(surface_replay_payloads)
        audit["compiler_result_count"] = result_count
        audit["surface_filter"] = {
            "kind": "clean_control_after_reception",
            "mode": "tracking_clean_team_control_after_reception_v0",
            "catalog_payload_count": len(catalog_replay_payloads),
            "surface_result_count": surface_result_count,
        }
        if surface_result_count <= 0:
            no_moments_kind = coach_no_moments_kind(contract)
            response = ok(
                {
                    "status": "no_moments_found",
                    "query": query,
                    "display_answer": coach_template(f"no_moments_found.{no_moments_kind}"),
                    "suggestions": COACH_SUGGESTIONS,
                    "match_scope": COACH_MATCH_SCOPE,
                    "meaning_definition": meaning.meaning_definition,
                    "interpretation_rules": list(meaning.interpretation_rules),
                    "contract_hash": contract_hash,
                    "plan_hash": plan_hash,
                    "result_count": 0,
                    "moments": [],
                    "gap": None,
                    "audit": audit,
                }
            )
            COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
            return response
        replay_payloads = surface_replay_payloads
        product_claim_gates = [
            coach_product_claim_gate(visual_kind, replay_payload)
            for replay_payload in replay_payloads
        ]
        product_claim_gate = {
            "passed": bool(product_claim_gates) and all(gate["passed"] for gate in product_claim_gates),
            "kind": visual_kind,
            "claim_id": product_claim_gates[0]["claim_id"] if product_claim_gates else None,
            "payload_count": len(replay_payloads),
            "catalog_payload_count": len(catalog_replay_payloads),
            "expected_result_count": surface_result_count,
            "compiler_result_count": result_count,
            "returned_count_matches_result_count": len(replay_payloads) == surface_result_count,
            "catalog_count_matches_result_count": len(surface_replay_payloads) == surface_result_count,
            "failures": [
                {"payload_index": index, "failures": gate["failures"]}
                for index, gate in enumerate(product_claim_gates)
                if not gate["passed"]
            ],
        }
        audit["product_claim_gate"] = product_claim_gate
        if not product_claim_gate["passed"]:
            response = coach_cant_yet_response(
                query=query,
                display_answer=coach_template("understood_but_not_expressible.no_replay_surface"),
                meaning_definition=meaning.meaning_definition,
                interpretation_rules=list(meaning.interpretation_rules),
                contract_hash=contract_hash,
                gap={
                    "kind": "product_claim_unbacked",
                    "message": "The compiler found observed moments, but the representative replay does not back the full coach-facing product claim.",
                    "claim_gate": product_claim_gate,
                    "result_count": surface_result_count,
                    "compiler_result_count": result_count,
                    "plan_hash": plan_hash,
                },
                audit=audit,
            )
            COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
            return response
        response_moments = [
            {
                "moment_id": visual_kind,
                "result_count": surface_result_count,
                "replay_payload": replay_payload,
                "evidence_fields": list(contract.get("required_evidence", [])),
            }
            for replay_payload in replay_payloads
        ]
        response = ok(
            {
                "status": "moment_found",
                "query": query,
                "display_answer": coach_template(f"moment_found.{visual_kind}"),
                "suggestions": COACH_SUGGESTIONS,
                "match_scope": COACH_MATCH_SCOPE,
                "meaning_definition": meaning.meaning_definition,
                "interpretation_rules": list(meaning.interpretation_rules),
                "contract_hash": contract_hash,
                "plan_hash": plan_hash,
                "result_count": surface_result_count,
                "moments": response_moments,
                "gap": None,
                "audit": audit,
            }
        )
        COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
        return response

    failure_taxonomy = str(result.get("failure_taxonomy") or "not_compiler_reachable")
    template_key = (
        "understood_but_not_expressible.unsupported_modality"
        if failure_taxonomy == "unsupported_modality"
        else "understood_but_not_expressible.default"
    )
    response = coach_cant_yet_response(
        query=query,
        display_answer=coach_template(template_key),
        meaning_definition=meaning.meaning_definition,
        interpretation_rules=list(meaning.interpretation_rules),
        contract_hash=contract_hash,
        gap={
            "kind": failure_taxonomy,
            "message": str(result.get("message") or "The current compiler could not produce an executable observed moment."),
            "details": result.get("failure_details") or {},
        },
        audit=audit,
    )
    COACH_RESPONSE_CACHE[contract_hash] = deepcopy(response)
    return response


def coach_catalog_response(kind: str) -> dict[str, Any]:
    kind = str(kind or "").strip()
    if kind not in {
        "line_break_no_underneath_support",
        "line_break_with_underneath_outlet",
        "high_bypass_completed_pass",
    }:
        return error_response("UNKNOWN_COACH_CATALOG_KIND", f"Unknown coach catalog kind: {kind}", details={"kind": kind})

    catalog_replay_payloads = coach_moment_payloads(kind)
    surface_replay_payloads = coach_surface_moment_payloads(kind, catalog_replay_payloads)
    surface_result_count = len(surface_replay_payloads)
    if surface_result_count <= 0:
        return ok(
            {
                "status": "no_moments_found",
                "query": "",
                "display_answer": coach_template(f"no_moments_found.{kind}"),
                "suggestions": COACH_SUGGESTIONS,
                "match_scope": COACH_MATCH_SCOPE,
                "meaning_definition": None,
                "interpretation_rules": [],
                "contract_hash": None,
                "plan_hash": None,
                "result_count": 0,
                "moments": [],
                "gap": None,
                "audit": {
                    "pipeline": "precomputed_clean_control_catalog.v0",
                    "catalog_payload_count": len(catalog_replay_payloads),
                    "surface_filter": {
                        "kind": "clean_control_after_reception",
                        "mode": "tracking_clean_team_control_after_reception_v0",
                        "surface_result_count": 0,
                    },
                },
            }
        )

    product_claim_gates = [coach_product_claim_gate(kind, replay_payload) for replay_payload in surface_replay_payloads]
    if not all(gate["passed"] for gate in product_claim_gates):
        return coach_cant_yet_response(
            query="",
            display_answer=coach_template("understood_but_not_expressible.no_replay_surface"),
            meaning_definition=None,
            interpretation_rules=[],
            gap={
                "kind": "product_claim_unbacked",
                "message": "The precomputed catalog contains a replay that does not back the full coach-facing product claim.",
                "failures": [
                    {"payload_index": index, "failures": gate["failures"]}
                    for index, gate in enumerate(product_claim_gates)
                    if not gate["passed"]
                ],
            },
            audit={
                "pipeline": "precomputed_clean_control_catalog.v0",
                "catalog_payload_count": len(catalog_replay_payloads),
                "surface_result_count": surface_result_count,
            },
        )

    return ok(
        {
            "status": "moment_found",
            "query": "",
            "display_answer": coach_template(f"moment_found.{kind}"),
            "suggestions": COACH_SUGGESTIONS,
            "match_scope": COACH_MATCH_SCOPE,
            "meaning_definition": None,
            "interpretation_rules": [],
            "contract_hash": None,
            "plan_hash": None,
            "result_count": surface_result_count,
            "moments": [
                {
                    "moment_id": kind,
                    "result_count": surface_result_count,
                    "replay_payload": replay_payload,
                    "evidence_fields": [],
                }
                for replay_payload in surface_replay_payloads
            ],
            "gap": None,
            "audit": {
                "pipeline": "precomputed_clean_control_catalog.v0",
                "catalog_payload_count": len(catalog_replay_payloads),
                "surface_filter": {
                    "kind": "clean_control_after_reception",
                    "mode": "tracking_clean_team_control_after_reception_v0",
                    "surface_result_count": surface_result_count,
                },
            },
        }
    )


def coach_clarification_response(
    *,
    query: str,
    display_answer: str,
    clarification_codes: list[str],
    clarification_questions: list[str],
    audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ok(
        {
            "status": "clarification_required",
            "query": query,
            "display_answer": display_answer,
            "suggestions": COACH_SUGGESTIONS,
            "match_scope": COACH_MATCH_SCOPE,
            "meaning_definition": None,
            "interpretation_rules": [],
            "contract_hash": None,
            "plan_hash": None,
            "result_count": 0,
            "moments": [],
            "gap": {
                "kind": "clarification_required",
                "codes": clarification_codes,
                "questions": clarification_questions,
            },
            "audit": audit or {},
        }
    )


def coach_cant_yet_response(
    *,
    query: str,
    display_answer: str,
    meaning_definition: str | None,
    interpretation_rules: list[str],
    gap: dict[str, Any],
    audit: dict[str, Any] | None = None,
    contract_hash: str | None = None,
) -> dict[str, Any]:
    return ok(
        {
            "status": "understood_but_not_expressible",
            "query": query,
            "display_answer": display_answer,
            "suggestions": COACH_SUGGESTIONS,
            "match_scope": COACH_MATCH_SCOPE,
            "meaning_definition": meaning_definition,
            "interpretation_rules": interpretation_rules,
            "contract_hash": contract_hash,
            "plan_hash": None,
            "result_count": 0,
            "moments": [],
            "gap": gap,
            "audit": audit or {},
        }
    )


def coach_visual_moment_kind(contract: dict[str, Any]) -> str | None:
    if coach_contract_matches_line_break_no_underneath_support(contract):
        return "line_break_no_underneath_support"
    if coach_contract_matches_line_break_with_underneath_support(contract):
        return "line_break_with_underneath_outlet"
    if coach_contract_matches_high_bypass_completed_pass(contract):
        return "high_bypass_completed_pass"
    return None


def coach_no_moments_kind(contract: dict[str, Any]) -> str:
    required = set(str(field) for field in contract.get("required_evidence", []))
    status_values = coach_status_values(contract)
    constraints = [item for item in contract.get("composition_constraints", []) if isinstance(item, dict)]
    if coach_contract_matches_line_break_no_underneath_support(contract):
        return "line_break_no_underneath_support"
    if coach_contract_matches_line_break_with_underneath_support(contract):
        if coach_support_minimum_players(contract) >= 2:
            return "line_break_with_two_underneath_outlets"
        return "line_break_with_underneath_outlet"
    if coach_contract_matches_high_bypass_completed_pass(contract):
        return "high_bypass_completed_pass"
    if (
        {"carry_status", "pressure_status", "carry_forward_progression_m"}.issubset(required)
        and status_values.get("carry_status") == "PASS"
        and status_values.get("pressure_status") == "PASS"
    ):
        return "progressive_carry_under_pressure"
    if "pass_chain_status" in required and status_values.get("pass_chain_status") == "PASS":
        if any(item.get("kind") == "same_player_return" for item in constraints):
            return "give_and_go_sequence"
        return "onward_two_pass_sequence"
    return "default"


def coach_contract_matches_line_break_no_underneath_support(contract: dict[str, Any]) -> bool:
    required = set(str(field) for field in contract.get("required_evidence", []))
    status_values = coach_status_values(contract)
    return (
        {"line_break_status", "support_arrival_status", "support_region_mode", "supporting_player_ids"}.issubset(required)
        and status_values.get("line_break_status") == "PASS"
        and status_values.get("support_arrival_status") == "FAIL"
    )


def coach_contract_matches_line_break_with_underneath_support(contract: dict[str, Any]) -> bool:
    required = set(str(field) for field in contract.get("required_evidence", []))
    status_values = coach_status_values(contract)
    return (
        {"line_break_status", "support_arrival_status", "support_region_mode", "supporting_player_ids"}.issubset(required)
        and status_values.get("line_break_status") == "PASS"
        and status_values.get("support_arrival_status") == "PASS"
    )


def coach_contract_matches_high_bypass_completed_pass(contract: dict[str, Any]) -> bool:
    required = set(str(field) for field in contract.get("required_evidence", []))
    status_values = coach_status_values(contract)
    return (
        {
            "pass_episode_id",
            "passer_id",
            "receiver_id",
            "release_frame_id",
            "reception_frame_id",
            "release_ball_point",
            "reception_ball_point",
            "forward_progression_m",
            "opponents_bypassed_count",
            "bypassed_player_ids",
            "evaluation_status",
        }.issubset(required)
        and status_values.get("evaluation_status") == "PASS"
        and coach_threshold_at_least(contract, "forward_progression_m", 8.0)
        and coach_threshold_at_least(contract, "opponents_bypassed_count", 5.0)
    )


def coach_contract_matches_line_break_support_family(contract: dict[str, Any]) -> bool:
    return coach_contract_matches_line_break_no_underneath_support(contract) or coach_contract_matches_line_break_with_underneath_support(contract)


def coach_preview_runtime_family_without_surface(contract: dict[str, Any]) -> bool:
    if coach_contract_matches_line_break_support_family(contract):
        return False
    required = set(str(field) for field in contract.get("required_evidence", []))
    public_preview_deferred_fields = {
        "carry_status",
        "pressure_status",
        "pass_chain_status",
        "team_press_status",
        "cover_shadow_status",
        "marking_status",
        "off_ball_run_status",
        "space_region_status",
        "acceleration_status",
        "deceleration_status",
    }
    return bool(required & public_preview_deferred_fields)


def coach_support_minimum_players(contract: dict[str, Any]) -> int:
    for item in contract.get("composition_constraints", []):
        if isinstance(item, dict) and item.get("kind") == "relation_on_anchor" and "minimum_supporting_players" in item:
            try:
                return int(item["minimum_supporting_players"])
            except (TypeError, ValueError):
                return 1
    return 1


def coach_status_values(contract: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("field")): str(item.get("required_value"))
        for item in contract.get("status_semantics", [])
        if isinstance(item, dict) and "required_value" in item
    }


def coach_threshold_at_least(contract: dict[str, Any], field_name: str, threshold: float) -> bool:
    for item in contract.get("status_semantics", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("field")) != field_name or str(item.get("operator")) != "gte":
            continue
        try:
            return float(item.get("threshold")) >= threshold
        except (TypeError, ValueError):
            return False
    return False


def coach_moment_zero_payload() -> dict[str, Any]:
    return coach_moment_payload("line_break_no_underneath_support")


def coach_moment_payload(kind: str) -> dict[str, Any]:
    if kind == "line_break_with_underneath_outlet":
        payload_path = MOMENT_LINE_BREAK_SUPPORTED_PAYLOAD_PATH
    elif kind == "high_bypass_completed_pass":
        payload_path = MOMENT_HIGH_BYPASS_PAYLOAD_PATH
    else:
        payload_path = MOMENT_ZERO_PAYLOAD_PATH
    path = REPO_ROOT / payload_path
    if not path.exists():
        return {}
    return read_json(path)


def coach_moment_payloads(kind: str) -> list[dict[str, Any]]:
    if kind == "line_break_with_underneath_outlet":
        catalog_path = MOMENT_LINE_BREAK_SUPPORTED_CATALOG_PATH
    elif kind == "high_bypass_completed_pass":
        catalog_path = MOMENT_HIGH_BYPASS_CATALOG_PATH
    else:
        catalog_path = MOMENT_ZERO_CATALOG_PATH
    path = REPO_ROOT / catalog_path
    if path.exists():
        payload = read_json(path)
        moments = payload.get("moments") if isinstance(payload, dict) else None
        if isinstance(moments, list):
            return [moment for moment in moments if isinstance(moment, dict)]
    fallback = coach_moment_payload(kind)
    return [fallback] if fallback else []


def coach_surface_moment_payloads(kind: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if kind not in {
        "line_break_no_underneath_support",
        "line_break_with_underneath_outlet",
        "high_bypass_completed_pass",
    }:
        return payloads
    return [
        payload
        for payload in payloads
        if dotted_get(payload, "moment.clean_control_retention.mode") == "tracking_clean_team_control_after_reception_v0"
        and dotted_get(payload, "moment.clean_control_retention.status") == "PASS"
    ]


def needs_support_clarification(text: str, clarifications: list[str]) -> bool:
    if clarifications:
        return False
    if "support" not in text and "second runner" not in text and "teammate" not in text:
        return False
    return "corridor" not in text and "progressive lane" not in text and "passing lane" not in text


def infer_plan_path(query: str) -> Path | None:
    text = normalized(query)
    if (
        ("bypass" in text or "bypassed" in text or "behind" in text)
        and ("pass" in text or "completed" in text or "opponent" in text or "players" in text)
    ):
        return HIGH_BYPASS_PLAN_PATH
    if "line" in text and "support" in text and ("break" in text or "cross" in text):
        return LINE_BREAK_SUPPORT_RESPONSE_PLAN_PATH
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


def hermes_interpret_request(
    query: str,
    *,
    model_query: str | None = None,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> dict[str, Any]:
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
        surface = hermes_tool_surface(hermes, output_root=output_root)
        if not surface["safe"]:
            return hermes_unavailable(
                query,
                "Hermes did not expose the frozen priori_tactical-only tool surface. Manual mode remains available.",
                fallback_reason="unsafe_tool_surface",
            )
        started_at = newest_hermes_session_started_at()
        prompt_query = model_query or query
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
                hermes_interpret_prompt(prompt_query),
            ],
            timeout=HERMES_TIMEOUT_SECONDS,
            output_root=output_root,
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
        return hermes_final_to_interpretation(query, final, session, output_root=output_root)
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


def hermes_tool_surface(hermes: str, *, output_root: Path | None = None) -> dict[str, Any]:
    completed = run_hermes_invocation(hermes, ["probe", "--toolset", HERMES_TOOLSET], timeout=60, output_root=output_root)
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


def hermes_invocation_output_root(output_root: Path | None = None) -> Path:
    return (output_root or HERMES_WORKSHOP_ROOT).resolve()


def run_hermes_invocation(
    hermes: str,
    args: list[str],
    *,
    timeout: int,
    output_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    hermes_python = hermes_python_executable(hermes)
    workshop_output_root = hermes_invocation_output_root(output_root)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(HERMES_HOME)
    env.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
    env["TQE_WORKSHOP_OUTPUT_ROOT"] = str(workshop_output_root)
    env.setdefault("TQE_RUNTIME_ROOT", str(workshop_output_root))
    env.setdefault("WORKBENCH_HERMES_WORKSHOP_ROOT", str(workshop_output_root))
    env["PYTHONPATH"] = hermes_pythonpath(env.get("PYTHONPATH"))
    log_hermes_event(
        "subprocess_start",
        {
            "subcommand": args[0] if args else "",
            "python": path_state(hermes_python),
            "hermes": path_state(hermes),
            "cwd": path_state(str(REPO_ROOT)),
            "pythonpath_entries": len(env["PYTHONPATH"].split(os.pathsep)),
            "workshop_output_root": cloud_safe_path(workshop_output_root),
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
You are the Entrelíneas M1.2 Integrated Alpha tactical query interpreter.

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


def hermes_final_to_interpretation(
    query: str,
    final: dict[str, Any],
    session: dict[str, Any] | None,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
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
        bound_plan_hash = str(final.get("bound_plan_hash") or "") or None
        plan_document = hermes_bound_plan_document(bound_plan_id, output_root=output_root)
        if plan_document is None:
            return hermes_unavailable(query, "Hermes validated a draft but the host could not recover its bound plan handle.")
        provenance_source, attestation_details = hermes_draft_provenance(plan_document, bound_plan_hash)
        fallback_reason = None
        if provenance_source == "HERMES_EXPERIMENTAL_UNVERIFIED":
            failures = attestation_details.get("failures") if isinstance(attestation_details, dict) else None
            fallback_reason = "attestation_not_verified" + (f":{','.join(failures)}" if failures else "")
        return ok(
            {
                **base,
                "status": "PLAN_INTERPRETED",
                "provenance_source": provenance_source,
                "recipe_id": str(plan_document.get("recipe", {}).get("recipe_id") or ""),
                "recipe": recipe_card(plan_document, "EXPERIMENTAL"),
                "plan_document": plan_document,
                "plan_hash": stable_hash(plan_document),
                "draft_plan_hash": stable_hash(plan_document),
                "fallback_reason": fallback_reason,
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
    if recipe_id in {
        "ball_side_block_shift_v1",
        "possession_corridor_availability_v1",
        "high_bypass_completed_pass_v1",
        "line_break_support_response_v1",
    }:
        return "HERMES_RECIPE_SELECTION"
    return "HERMES_EXPERIMENTAL_UNVERIFIED"


def read_committed_json(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def attested_invocation_scope() -> dict[str, Any]:
    bundle = read_committed_json(N1D_ORIGIN_BUNDLE_PATH)
    document = bundle.get("host_augmentation", {}).get("augmented_document") if isinstance(bundle.get("host_augmentation"), dict) else None
    invocation = document.get("default_invocation") if isinstance(document, dict) else None
    if not isinstance(invocation, dict):
        return {}
    return {
        "match_ids": list(invocation.get("match_ids") or []),
        "periods": list(invocation.get("periods") or []),
        "perspective_team_role": invocation.get("perspective_team_role"),
        "max_results": invocation.get("max_results"),
    }


def is_attested_novel_recipe(plan_document: dict[str, Any]) -> bool:
    recipe = plan_document.get("recipe") if isinstance(plan_document, dict) else None
    return isinstance(recipe, dict) and recipe.get("recipe_id") == "possession_corridor_destination_entry_v1"


def attested_scope_matches(plan_document: dict[str, Any]) -> bool:
    invocation = plan_document.get("default_invocation") if isinstance(plan_document, dict) else None
    expected = attested_invocation_scope()
    if not isinstance(invocation, dict) or not expected:
        return False
    return (
        list(invocation.get("match_ids") or []) == expected["match_ids"]
        and list(invocation.get("periods") or []) == expected["periods"]
        and invocation.get("perspective_team_role") == expected["perspective_team_role"]
        and invocation.get("max_results") == expected["max_results"]
    )


def current_manifest_identity_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    pinned = manifest.get("pinned_identity") if isinstance(manifest.get("pinned_identity"), dict) else {}
    knowledge_pack = pinned.get("knowledge_pack") if isinstance(pinned.get("knowledge_pack"), dict) else {}
    expected_pack_sha = knowledge_pack.get("file_sha256")
    if expected_pack_sha and (not KNOWLEDGE_PACK_PATH.exists() or file_sha256(KNOWLEDGE_PACK_PATH) != expected_pack_sha):
        failures.append("knowledge_pack_sha256")
    data = pinned.get("data") if isinstance(pinned.get("data"), dict) else {}
    expected_manifest_sha = data.get("deploy_manifest_sha256")
    if expected_manifest_sha and (not DATA_MANIFEST_PATH.exists() or file_sha256(DATA_MANIFEST_PATH) != expected_manifest_sha):
        failures.append("deploy_manifest_sha256")
    source_files = manifest.get("source", {}).get("source_files") if isinstance(manifest.get("source"), dict) else {}
    if isinstance(source_files, dict):
        for name, identity in source_files.items():
            if not isinstance(identity, dict):
                failures.append(f"source_file.{name}")
                continue
            path = Path(str(identity.get("path") or ""))
            expected = str(identity.get("sha256") or "")
            if not expected or not path.exists() or file_sha256(path) != expected:
                failures.append(f"source_file.{name}")
    return failures


def verified_novel_attestation(plan_document: dict[str, Any], bound_plan_hash: str | None) -> dict[str, Any]:
    attestation = read_committed_json(N1D_ATTESTATION_PATH)
    manifest = read_committed_json(N1D_MANIFEST_PATH)
    origin_bundle = read_committed_json(N1D_ORIGIN_BUNDLE_PATH)
    failures: list[str] = []
    if attestation.get("status") != "VERIFIED":
        failures.append("attestation_status")
    if not bound_plan_hash or attestation.get("plan_hash") != bound_plan_hash:
        failures.append("plan_hash")
    if (
        attestation.get("freeze_manifest_sha256")
        and (not N1D_MANIFEST_PATH.exists() or file_sha256(N1D_MANIFEST_PATH) != attestation.get("freeze_manifest_sha256"))
    ):
        failures.append("freeze_manifest_sha256")
    elif not attestation.get("freeze_manifest_sha256"):
        failures.append("freeze_manifest_sha256_missing")
    origin = attestation.get("hermes_origin") if isinstance(attestation.get("hermes_origin"), dict) else {}
    expected_origin_path = str(N1D_ORIGIN_BUNDLE_PATH)
    if origin.get("origin_bundle_path") != expected_origin_path:
        failures.append("origin_bundle_path")
    if origin.get("origin_bundle_sha256") != stable_json_sha256(origin_bundle):
        failures.append("origin_bundle_sha256")
    try:
        from tqe.verification.n1a import structural_fingerprint

        fingerprint = structural_fingerprint(plan_document)
    except Exception:
        fingerprint = {}
        failures.append("structural_fingerprint")
    expected_fingerprint = (
        attestation.get("structural_novelty", {}).get("fingerprint_hash")
        if isinstance(attestation.get("structural_novelty"), dict)
        else None
    )
    if not expected_fingerprint or fingerprint.get("fingerprint_hash") != expected_fingerprint:
        failures.append("structural_fingerprint_hash")
    if not attested_scope_matches(plan_document):
        failures.append("attested_scope")
    failures.extend(current_manifest_identity_failures(manifest))
    return {
        "verified": not failures,
        "failures": sorted(set(failures)),
        "attestation_status": attestation.get("status"),
        "attested_plan_hash": attestation.get("plan_hash"),
        "structural_fingerprint_hash": fingerprint.get("fingerprint_hash"),
        "attested_structural_fingerprint_hash": expected_fingerprint,
    }


def hermes_draft_provenance(plan_document: dict[str, Any], bound_plan_hash: str | None) -> tuple[str, dict[str, Any]]:
    base_source = hermes_plan_provenance(plan_document)
    if base_source != "HERMES_EXPERIMENTAL_UNVERIFIED":
        return base_source, {"verified": False, "reason": "registered_recipe_selection"}
    if not is_attested_novel_recipe(plan_document):
        return "HERMES_EXPERIMENTAL_UNVERIFIED", {"verified": False, "failures": ["unattested_experimental_recipe"]}
    attestation = verified_novel_attestation(plan_document, bound_plan_hash)
    if attestation["verified"]:
        return "HERMES_NOVEL_COMPOSITION", attestation
    return "HERMES_EXPERIMENTAL_UNVERIFIED", attestation


def hermes_bound_plan_document(bound_plan_id: str, *, output_root: Path | None = None) -> dict[str, Any] | None:
    if not bound_plan_id:
        return None
    roots: list[Path] = []
    for candidate in (output_root, HERMES_WORKSHOP_ROOT, DEFAULT_WORKSHOP_ROOT):
        if candidate is not None and candidate not in roots:
            roots.append(candidate)
    for root in roots:
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


def int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def git_tree_identifier() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=REPO_ROOT,
        )
    except Exception:  # noqa: BLE001 - provenance metadata is useful but non-critical.
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


def film_room_compile_context(payload: dict[str, Any]) -> Any:
    from tqe.semantic_compiler.hermes_nl import HermesNLContext

    context_payload = payload.get("context")
    if isinstance(context_payload, dict) and context_payload:
        return HermesNLContext.model_validate(context_payload)
    return None


def film_room_ask_disabled_reason() -> dict[str, str] | None:
    if not hermes_enabled():
        return {
            "reason": "workbench_hermes_disabled",
            "message": "WORKBENCH_HERMES_ENABLED is not set to 1.",
        }
    hermes_path = shutil.which("hermes")
    if not hermes_path:
        return {
            "reason": "hermes_executable_missing",
            "message": "The Hermes executable is not available in this runtime.",
        }
    if HERMES_PROVIDER == "openai-codex" and not (HERMES_HOME / "auth.json").exists():
        return {
            "reason": "hermes_auth_missing",
            "message": f"Hermes auth was not found at {HERMES_HOME / 'auth.json'}.",
        }
    return None


def film_room_ask_request(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    from tqe.semantic_compiler.hermes_nl import (
        ClarificationRequiredOutcome,
        ExpressionOutcome,
        UnderstoodButNotExpressibleOutcome,
        UnsupportedModalityOutcome,
        compile_nl_request,
    )
    from scripts.coverage_map.compiler_search_reachability import SynthesisError
    from tqe.semantic_compiler.target_synthesis import synthesize_and_bind

    text = str(payload.get("text") or payload.get("query") or "").strip()
    if not text:
        raise ValueError("text must be non-empty")
    os.environ.setdefault("HERMES_HOME", str(HERMES_HOME))
    os.environ.setdefault("HERMES_SCP2_2_PROVIDER", HERMES_PROVIDER)
    os.environ.setdefault("HERMES_SCP2_2_MODEL", HERMES_MODEL)
    started_at = time.monotonic()
    hermes_started_at = time.monotonic()
    outcome = compile_nl_request(text, context=film_room_compile_context(payload))
    hermes_latency_ms = int((time.monotonic() - hermes_started_at) * 1000)
    hermes_payload = outcome.model_dump(mode="json")
    response: dict[str, Any] = {
        "ok": True,
        "outcome": hermes_payload["outcome"],
        "request_text": text,
        "provider": str(hermes_payload.get("transcript", {}).get("provider") or HERMES_PROVIDER),
        "model": str(hermes_payload.get("transcript", {}).get("model") or HERMES_MODEL),
        "latency_ms": int((time.monotonic() - started_at) * 1000),
        "latency_breakdown_ms": {
            "hermes": hermes_latency_ms,
            "synthesis": 0,
            "execution": 0,
            "total": int((time.monotonic() - started_at) * 1000),
        },
        "hermes": hermes_payload,
        "answer": None,
        "clarification": None,
        "refusal": None,
    }
    if isinstance(outcome, ClarificationRequiredOutcome):
        response["clarification"] = hermes_payload
        return validate_public_response("FilmRoomAskResponse", response)
    if isinstance(outcome, (UnderstoodButNotExpressibleOutcome, UnsupportedModalityOutcome)):
        response["refusal"] = hermes_payload
        return validate_public_response("FilmRoomAskResponse", response)
    if not isinstance(outcome, ExpressionOutcome):
        raise CapabilityGap(f"unsupported Hermes outcome: {type(outcome).__name__}")
    coverage_path = Path("generated/coverage-map.json")
    coverage_rows = read_json(coverage_path) if coverage_path.exists() else None
    synthesis_started_at = time.monotonic()
    try:
        synthesized = synthesize_and_bind(outcome.expression, coverage_rows=coverage_rows)
    except SynthesisError as exc:
        synthesis_latency_ms = int((time.monotonic() - synthesis_started_at) * 1000)
        response["outcome"] = "understood_but_not_expressible"
        response["refusal"] = {
            "outcome": "understood_but_not_expressible",
            "gap_code": "TARGET_SYNTHESIS_UNSATISFIED",
            "missing_capability": "registered_operator_composition",
            "message": "I understood the ask, but the current compiler cannot synthesize a registered operator composition for it.",
            "synthesis_error": {
                "taxonomy": exc.taxonomy,
                "message": exc.message,
                "details": exc.details,
            },
            "transcript": hermes_payload.get("transcript"),
        }
        response["latency_ms"] = int((time.monotonic() - started_at) * 1000)
        response["latency_breakdown_ms"] = {
            "hermes": hermes_latency_ms,
            "synthesis": synthesis_latency_ms,
            "execution": 0,
            "total": int(response["latency_ms"]),
        }
        return validate_public_response("FilmRoomAskResponse", response)
    synthesis_latency_ms = int((time.monotonic() - synthesis_started_at) * 1000)
    execution_started_at = time.monotonic()
    answer = film_room_answer_from_document(
        synthesized["document"],
        expression_payload=hermes_payload.get("expression_json") if isinstance(hermes_payload, dict) else None,
        expression_hash=outcome.document_hash,
        synthesized_document_hash=str(synthesized["document_hash"]),
        output_root=output_root,
    )
    execution_latency_ms = int((time.monotonic() - execution_started_at) * 1000)
    answer["compiled_chips"] = film_room_compiled_chips(hermes_payload.get("expression_json"), synthesized["document"])
    response["answer"] = answer
    response["latency_ms"] = int((time.monotonic() - started_at) * 1000)
    response["latency_breakdown_ms"] = {
        "hermes": hermes_latency_ms,
        "synthesis": synthesis_latency_ms,
        "execution": execution_latency_ms,
        "total": int(response["latency_ms"]),
    }
    return validate_public_response("FilmRoomAskResponse", response)


def public_film_room_ask_with_timeout(payload: dict[str, Any], *, output_root: Path) -> tuple[dict[str, Any], HTTPStatus]:
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result_queue.put(("response", film_room_ask_request(payload, output_root=output_root)))
        except Exception as exc:  # noqa: BLE001 - transported to request thread for typed rendering.
            result_queue.put(("exception", exc))

    worker = threading.Thread(target=run, name="public-film-room-ask", daemon=True)
    worker.start()
    try:
        kind, value = result_queue.get(timeout=TQE_PUBLIC_ASK_TIMEOUT_SECONDS)
    except queue.Empty:
        timeout = TimeoutError(f"public Film Room ask exceeded {TQE_PUBLIC_ASK_TIMEOUT_SECONDS:g}s")
        correlation_id = log_internal_error(timeout, path="/api/film-room/ask")
        return (
            error_response(
                "INTERNAL_ERROR",
                public_error_message("INTERNAL_ERROR"),
                details={
                    "correlation_id": correlation_id,
                    "reason": "public_ask_timeout",
                    "timeout_seconds": TQE_PUBLIC_ASK_TIMEOUT_SECONDS,
                },
            ),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    if kind == "response":
        return value, HTTPStatus.OK
    exc = value
    if type(exc).__name__ == "HermesNLAccessError":
        return (
            error_response(
                "ASKS_DISABLED",
                public_error_message("ASKS_DISABLED"),
                details={"reason": "hermes_access_error", "message": str(exc)},
            ),
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
    if isinstance(exc, CapabilityGap):
        code = stable_tool_error_code(exc)
        return error_response(code, public_error_message(code)), HTTPStatus.FORBIDDEN
    correlation_id = log_internal_error(exc, path="/api/film-room/ask")
    return (
        error_response(
            "INTERNAL_ERROR",
            public_error_message("INTERNAL_ERROR"),
            details={"correlation_id": correlation_id},
        ),
        HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def film_room_answer_from_document(
    document_payload: dict[str, Any],
    *,
    expression_payload: Any,
    expression_hash: str | None,
    synthesized_document_hash: str,
    output_root: Path,
) -> dict[str, Any]:
    plan_hash = stable_hash(document_payload)
    certified = film_room_certified_table_for_plan_hash(plan_hash)
    executions = film_room_execute_document(document_payload, output_root=output_root)
    selected_replay_window_id: str | None = None
    moments: list[dict[str, Any]] = []
    seen_moments: set[tuple[str, str, int, str]] = set()
    canonical_sources: dict[str, str] = {}
    raw_rate_evidence_rows: list[dict[str, Any]] = []
    for execution_record in executions:
        rows = execution_record["execution"].get("results")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            role = str(row.get("perspective_team_role") or execution_record["role"] or "")
            requested_evidence = row.get("requested_evidence") if isinstance(row.get("requested_evidence"), dict) else {}
            if requested_evidence:
                raw_rate_evidence_rows.append(deepcopy(requested_evidence))
            for chain_record in film_room_chain_population_records(requested_evidence, fallback=row):
                if not isinstance(chain_record, dict):
                    continue
                match_id = str(chain_record.get("match_id") or row.get("match_id") or "")
                period = str(chain_record.get("period") or row.get("period") or "")
                anchor_frame_id = int(chain_record.get("anchor_frame_id") or row.get("anchor_frame_id") or 0)
                source_kind = film_room_source_kind(chain_record, fallback=row)
                result_id = str(
                    chain_record.get("chain_id")
                    or chain_record.get("anchor_id")
                    or row.get("result_id")
                    or stable_hash(chain_record)[:16]
                )
                moment_key = (
                    match_id,
                    period,
                    anchor_frame_id,
                    result_id,
                )
                if moment_key in seen_moments:
                    continue
                seen_moments.add(moment_key)
                replay_meta = film_room_register_replay_window(
                    chain_record,
                    plan_hash=plan_hash,
                    fallback_result_id=str(row.get("result_id") or ""),
                    source_kind=source_kind,
                )
                if selected_replay_window_id is None and replay_meta["replay_window_id"]:
                    selected_replay_window_id = str(replay_meta["replay_window_id"])
                evidence_row = deepcopy(chain_record)
                moments.append(
                    {
                        "result_id": result_id,
                        "source_kind": source_kind,
                        "classification": str(row.get("classification") or chain_record.get("chain_status") or ""),
                        "match_id": match_id,
                        "period": period,
                        "anchor_frame_id": anchor_frame_id,
                        "start_frame_id": int_or_none(chain_record.get("start_frame_id")),
                        "end_frame_id": int_or_none(chain_record.get("end_frame_id")),
                        "match_time_ms": (
                            chain_record.get("match_time_ms")
                            if isinstance(chain_record.get("match_time_ms"), int)
                            else row.get("match_time_ms") if isinstance(row.get("match_time_ms"), int) else None
                        ),
                        "requested_evidence": deepcopy(chain_record),
                        "replay_window_id": replay_meta["replay_window_id"],
                        "replay_start_frame_id": replay_meta["replay_start_frame_id"],
                        "replay_end_frame_id": replay_meta["replay_end_frame_id"],
                        "evidence_row": evidence_row,
                        "unknown_reason": film_room_unknown_reason(evidence_row, row),
                        "chain_status": str(chain_record.get("chain_status")) if chain_record.get("chain_status") else None,
                        "chain_reason": str(chain_record.get("chain_reason")) if chain_record.get("chain_reason") else None,
                        "evidence_overlay": film_room_evidence_overlay(chain_record),
                    }
                )
    runtime_evidence_rows = [
        row
        for row in raw_rate_evidence_rows
        if isinstance(row, dict)
    ]
    runtime_rate_source_rows = film_room_runtime_rate_source_rows(executions)
    interval_metric = (
        film_room_interval_metric(certified.get("table") if certified else None)
        or film_room_interval_metric_from_evidence(runtime_rate_source_rows)
        or film_room_interval_metric_from_legacy_evidence(runtime_evidence_rows)
    )
    bound_plan_hashes = {
        str(record["role"]): str(record["execution"].get("bound_plan_hash") or record["bound_record"].get("bound_plan_hash"))
        for record in executions
    }
    answer = {
        "status": "answer_ready",
        "compiled_chips": film_room_compiled_chips(expression_payload, document_payload),
        "document": document_payload,
        "certified_evidence_rows": certified.get("table", {}).get("rows", []) if certified else [],
        "runtime_evidence_rows": runtime_evidence_rows,
        "evidence_rows_kind": "certified" if certified else "runtime",
        "interval_metric": interval_metric,
        "moments": moments,
        "moment_total_count": len(moments),
        "visible_moment_count": len(moments),
        # Replay payloads are deliberately lazy. The selected moment's window is
        # materialized only when /api/film-room/replay-window is requested.
        "replay": None,
        "executions": executions,
        "raw_evidence": {
            "rate_records": runtime_rate_source_rows or raw_rate_evidence_rows,
            "returned_rate_records": raw_rate_evidence_rows,
            "runtime_rate_source_rows": runtime_rate_source_rows,
            "certified_table": certified.get("table") if certified else None,
            "moment_source": "rate.source_records" if any("source_records" in row for row in raw_rate_evidence_rows) else "execution.results",
            "interval_source_contract": (
                "Film Room interval metrics use certified table totals when the document hash matches a committed table; "
                "otherwise they use execution.provenance.requested_evidence_sources rate_records summaries, not returned result order."
            ),
        },
        "provenance": {
            "plan_hash": plan_hash,
            "synthesized_document_hash": synthesized_document_hash,
            "expression_hash": expression_hash,
            "certified_table_path": str(certified["table_path"]) if certified else None,
            "certified_table_hash": certified["table_hash"] if certified else None,
            "certified_plan_path": str(certified["plan_path"]) if certified else None,
            "certified_period_records_hash": str(certified["table"].get("period_records_hash")) if certified else None,
            "bound_plan_hashes": bound_plan_hashes,
            "replay_window_id": selected_replay_window_id,
            "canonical_sources": canonical_sources,
            "runtime_commit": runtime_commit_identifier(),
            "tree": git_tree_identifier(),
        },
    }
    return FilmRoomAnswerResponse.model_validate(answer).model_dump(mode="json")


def film_room_execute_document(document_payload: dict[str, Any], *, output_root: Path) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    for role, document in film_room_role_documents(document_payload).items():
        plan_document = TacticalQueryDocument.model_validate(deepcopy(document))
        source_label = f"film_room_{role}"
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
            raise CapabilityGap(f"Film Room plan failed validation for {role}: {validation.issues}")
        confirmation = host_confirm_bound_plan(
            validation.bound_plan_id,
            reviewer="film_room",
            output_root=output_root,
        )
        execute_request = ExecuteQueryPlanRequest(
            bound_plan_id=validation.bound_plan_id,
            execution_authorization_id=confirmation.execution_authorization_id,
            result_limit=WORKBENCH_FILM_ROOM_RESULT_LIMIT,
        )
        cache_before = execution_cache_status(execute_request.model_dump(mode="json"), output_root=output_root)
        executed = cached_execute_query_plan(execute_request, output_root=output_root)
        execution_record = read_handle("executions", str(executed["execution"]["execution_id"]), output_root=output_root)
        provenance = execution_record.get("execution", {}).get("provenance", {})
        runtime_evidence_sources = (
            provenance.get("requested_evidence_sources")
            if isinstance(provenance, dict) and isinstance(provenance.get("requested_evidence_sources"), list)
            else []
        )
        executions.append(
            {
                "role": role,
                "submit": submitted.model_dump(mode="json"),
                "validation": validation.model_dump(mode="json"),
                "confirmation": confirmation.model_dump(mode="json"),
                "cache_before": cache_before,
                "execution": executed["execution"],
                "runtime_evidence_sources": runtime_evidence_sources,
                "cache_after_execute": executed["cache"],
                "draft_record": read_handle("draft-plans", submitted.draft_plan_id, output_root=output_root),
                "bound_record": read_handle("bound-plans", validation.bound_plan_id, output_root=output_root),
            }
        )
    return [FilmRoomExecutionRecordResponse.model_validate(item).model_dump(mode="json") for item in executions]


def film_room_role_documents(document_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if document_payload.get("schema_version") == "compiler_search_perspective_bundle.v1":
        documents = document_payload.get("documents")
        if not isinstance(documents, dict):
            raise CapabilityGap("Film Room perspective bundle is missing role documents.")
        return {str(role): deepcopy(document) for role, document in sorted(documents.items()) if isinstance(document, dict)}
    role = str(document_payload.get("default_invocation", {}).get("perspective_team_role") or "single")
    return {role: deepcopy(document_payload)}


def film_room_replay_for_result(*, execution_id: str, result_id: str, output_root: Path) -> dict[str, Any]:
    inspection = inspect_result(InspectResultRequest(execution_id=execution_id, result_id=result_id), output_root=output_root)
    replay_window = retrieve_replay_window(
        ReplayWindowRequest(execution_id=execution_id, result_id=result_id),
        output_root=output_root,
    )
    replay = replay_payload(replay_window.replay_window_id, output_root=output_root)
    return {
        "inspection": inspection.model_dump(mode="json"),
        "replay_window": replay_window.model_dump(mode="json"),
        "replay": replay,
    }


def film_room_chain_population_records(requested_evidence: dict[str, Any], *, fallback: dict[str, Any]) -> list[dict[str, Any]]:
    source_records = requested_evidence.get("source_records")
    if isinstance(source_records, list):
        records = [deepcopy(item) for item in source_records if isinstance(item, dict)]
        if records:
            return records
    return [deepcopy(fallback)]


def film_room_source_kind(record: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> Literal["result", "target", "chain_record"]:
    del fallback
    if record.get("chain_id") or record.get("chain_status") is not None:
        return "chain_record"
    if any(key.startswith("stage_") for key in record):
        return "chain_record"
    if record.get("target_id"):
        return "target"
    return "result"


def film_room_witness_frame_ids(record: dict[str, Any]) -> list[int]:
    frame_ids: list[int] = []
    for key, value in record.items():
        if not isinstance(value, int):
            continue
        if key == "anchor_frame_id" or key.endswith("_frame_id") or key.endswith("_start_frame_id") or key.endswith("_end_frame_id"):
            frame_ids.append(value)
    return sorted(set(frame_ids))


def film_room_register_replay_window(
    record: dict[str, Any],
    *,
    plan_hash: str,
    fallback_result_id: str,
    source_kind: FilmRoomSourceKind,
    plan_path: Path | None = None,
) -> dict[str, Any]:
    match_id = str(record.get("match_id") or "")
    period = str(record.get("period") or "")
    anchor_frame_id = int(record.get("anchor_frame_id") or 0)
    source_id = str(record.get("chain_id") or record.get("anchor_id") or fallback_result_id or stable_hash(record)[:16])
    witness_frames = film_room_witness_frame_ids(record)
    padding_frames = max(
        50,
        *[abs(frame_id - anchor_frame_id) + 25 for frame_id in witness_frames],
    )
    padding_seconds = padding_frames / 25.0
    replay_window_id = "replay_" + stable_hash(
        {
            "plan_hash": plan_hash,
            "source_id": source_id,
            "source_kind": source_kind,
            "match_id": match_id,
            "period": period,
            "anchor_frame_id": anchor_frame_id,
            "padding_seconds": padding_seconds,
        }
    )[:16]
    replay_start_frame_id = max(0, anchor_frame_id - padding_frames)
    replay_end_frame_id = anchor_frame_id + padding_frames
    FILM_ROOM_REPLAY_INDEX[replay_window_id] = {
        "replay_window_id": replay_window_id,
        "plan_hash": plan_hash,
        "plan_path": str(plan_path) if plan_path is not None else None,
        "source_id": source_id,
        "source_kind": source_kind,
        "match_id": match_id,
        "period": period,
        "anchor_frame_id": anchor_frame_id,
        "padding_seconds": padding_seconds,
    }
    return {
        "replay_window_id": replay_window_id,
        "replay_start_frame_id": replay_start_frame_id,
        "replay_end_frame_id": replay_end_frame_id,
    }


def ensure_film_room_replay_payload(replay_window_id: str, *, output_root: Path) -> dict[str, Any]:
    artifact = replay_artifact_path(replay_window_id, output_root=output_root)
    if artifact.exists():
        return replay_payload(replay_window_id, output_root=output_root)
    meta = FILM_ROOM_REPLAY_INDEX.get(replay_window_id)
    if not meta:
        raise CapabilityGap(f"Unknown Film Room replay window: {replay_window_id}")
    overlay: dict[str, Any] = {}
    hydration_relative = str(meta.get("hydration_path") or "")
    if hydration_relative:
        hydration_path = film_room_cache_path(output_root, hydration_relative)
        expected_sha = str(meta.get("hydration_sha256") or "")
        if not hydration_path.is_file() or not expected_sha or file_sha256(hydration_path) != expected_sha:
            raise CapabilityGap(f"Film Room hydration shard failed verification: {replay_window_id}")
        hydration = read_json(hydration_path)
        if (
            hydration.get("schema_version") != FILM_ROOM_HYDRATION_SCHEMA
            or hydration.get("replay_window_id") != replay_window_id
            or hydration.get("plan_hash") != meta.get("plan_hash")
            or not isinstance(hydration.get("chain_record"), dict)
        ):
            raise CapabilityGap(f"Film Room hydration shard provenance mismatch: {replay_window_id}")
        chain_record = hydration["chain_record"]
        overlay = film_room_evidence_overlay(chain_record)
        meta = {
            **meta,
            "source_id": str(hydration["source_id"]),
            "source_kind": "chain_record",
            "match_id": str(hydration["match_id"]),
            "period": str(hydration["period"]),
            "anchor_frame_id": int(hydration["anchor_frame_id"]),
            "padding_seconds": float(hydration["padding_seconds"]),
        }
    payload = replay_window_from_canonical(
        replay_window_id=replay_window_id,
        plan_path=Path(str(meta.get("plan_path") or f"film_room_plan_{meta['plan_hash']}")),
        source_id=str(meta["source_id"]),
        source_kind=str(meta["source_kind"]),
        match_id=str(meta["match_id"]),
        period=str(meta["period"]),
        anchor_frame_id=int(meta["anchor_frame_id"]),
        padding_seconds=float(meta["padding_seconds"]),
    )
    payload["overlays"] = {
        "stages": deepcopy(overlay.get("stage_labels") or []),
        "stage_labels": deepcopy(overlay.get("stage_labels") or []),
        "anchor_markers": deepcopy(overlay.get("anchor_markers") or []),
        "carry_trails": deepcopy(overlay.get("carry_trails") or []),
        "unknown": deepcopy(overlay.get("unknown") or {}),
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    write_json(artifact, payload)
    return sanitize_replay_payload(payload)


def film_room_replay_window_response(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    replay_window_id = str(payload.get("replay_window_id") or "").strip()
    replay = ensure_film_room_replay_payload(replay_window_id, output_root=output_root)
    response = {
        "ok": True,
        "replay_window_id": replay_window_id,
        "replay": replay,
    }
    return validate_public_response("FilmRoomReplayWindowResponse", response)


def film_room_evidence_overlay(record: dict[str, Any]) -> dict[str, Any]:
    stage_labels: list[dict[str, Any]] = []
    anchor_markers: list[dict[str, Any]] = []
    for index in (1, 2, 3):
        frame_id = int_or_none(record.get(f"stage_{index}_frame_id"))
        if frame_id is None:
            continue
        status = str(record.get(f"stage_{index}_status") or "UNKNOWN")
        player_id = record.get(f"stage_{index}_player_id")
        if index == 1:
            label = "regain"
        elif index == 2:
            distance = record.get("stage_2_minimum_numeric_value")
            label = f"carry >= {distance:g}m" if isinstance(distance, (int, float)) else "carry"
        else:
            label = "pass"
        stage_labels.append(
            {
                "stage": index,
                "label": label,
                "frame_id": frame_id,
                "status": status,
                "player_id": str(player_id) if player_id else None,
            }
        )
        anchor_markers.append(
            {
                "stage": index,
                "frame_id": frame_id,
                "status": status,
                "player_id": str(player_id) if player_id else None,
            }
        )
    if not stage_labels:
        anchor_frame_id = int_or_none(record.get("anchor_frame_id"))
        if anchor_frame_id is not None:
            status = str(
                record.get("chain_status")
                or record.get("rate_status")
                or record.get("classification")
                or "OBSERVED"
            )
            stage_labels.append(
                {
                    "stage": 0,
                    "label": "observed anchor",
                    "frame_id": anchor_frame_id,
                    "status": status,
                    "player_id": None,
                }
            )
            anchor_markers.append(
                {
                    "stage": 0,
                    "frame_id": anchor_frame_id,
                    "status": status,
                    "player_id": None,
                }
            )
    carry_trails = []
    stage_2_start = int_or_none(record.get("stage_2_start_frame_id") or record.get("stage_2_frame_id"))
    stage_2_end = int_or_none(record.get("stage_2_end_frame_id"))
    stage_2_player = record.get("stage_2_player_id")
    if stage_2_start is not None and stage_2_end is not None:
        carry_trails.append(
            {
                "start_frame_id": stage_2_start,
                "end_frame_id": stage_2_end,
                "player_id": str(stage_2_player) if stage_2_player else None,
                "status": str(record.get("stage_2_status") or "UNKNOWN"),
            }
        )
    unknown_reason = film_room_unknown_reason(record, record)
    return {
        "anchor_markers": anchor_markers,
        "carry_trails": carry_trails,
        "stage_labels": stage_labels,
        "unknown": {
            "is_unknown": str(record.get("chain_status") or "") == "UNKNOWN",
            "reason": unknown_reason,
        },
    }


def film_room_cache_path(output_root: Path, relative: str) -> Path:
    base = cache_root(output_root).resolve()
    path = (base / relative).resolve()
    if base not in path.parents:
        raise CapabilityGap("Film Room cache path escapes storage root.")
    return path


def write_film_room_cache_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def film_room_descriptor_evidence(record: dict[str, Any], *, role: str) -> dict[str, Any]:
    fields = (
        "chain_id",
        "anchor_id",
        "match_id",
        "period",
        "anchor_frame_id",
        "start_frame_id",
        "end_frame_id",
        "chain_status",
        "chain_reason",
        "stage_1_status",
        "stage_1_frame_id",
        "stage_1_player_id",
        "stage_2_status",
        "stage_2_frame_id",
        "stage_2_start_frame_id",
        "stage_2_end_frame_id",
        "stage_2_player_id",
        "stage_2_minimum_numeric_value",
        "stage_3_status",
        "stage_3_frame_id",
        "stage_3_player_id",
    )
    descriptor = {key: deepcopy(record[key]) for key in fields if key in record}
    descriptor["audit_role"] = role
    descriptor["descriptor_only"] = True
    return descriptor


def write_film_room_descriptor_fragment(
    *,
    key: str,
    role: str,
    plan_path: Path,
    executions: list[dict[str, Any]],
    output_root: Path,
) -> dict[str, Any]:
    """Write lightweight descriptors and one on-disk shard per chain record."""

    if len(executions) != 1 or str(executions[0].get("role")) != role:
        raise CapabilityGap(f"Descriptor generation expected one {role} execution.")
    document_payload = read_json(plan_path)
    plan_hash = stable_hash(document_payload)
    execution_record = executions[0]
    execution = execution_record.get("execution") if isinstance(execution_record.get("execution"), dict) else {}
    rows = execution.get("results") if isinstance(execution.get("results"), list) else []
    moments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        requested = row.get("requested_evidence") if isinstance(row.get("requested_evidence"), dict) else {}
        for chain_record in film_room_chain_population_records(requested, fallback=row):
            if not isinstance(chain_record, dict):
                continue
            source_kind = film_room_source_kind(chain_record, fallback=row)
            if source_kind != "chain_record":
                continue
            match_id = str(chain_record.get("match_id") or row.get("match_id") or "")
            period = str(chain_record.get("period") or row.get("period") or "")
            anchor_frame_id = int(chain_record.get("anchor_frame_id") or row.get("anchor_frame_id") or 0)
            result_id = str(
                chain_record.get("chain_id")
                or chain_record.get("anchor_id")
                or row.get("result_id")
                or stable_hash(chain_record)[:16]
            )
            replay_meta = film_room_register_replay_window(
                chain_record,
                plan_hash=plan_hash,
                plan_path=plan_path,
                fallback_result_id=str(row.get("result_id") or result_id),
                source_kind="chain_record",
            )
            replay_window_id = str(replay_meta["replay_window_id"])
            if replay_window_id in seen:
                continue
            seen.add(replay_window_id)
            replay_index = FILM_ROOM_REPLAY_INDEX[replay_window_id]
            hydration_relative = f"{FILM_ROOM_HYDRATION_DIR}/{replay_window_id}.json"
            hydration_payload = {
                "schema_version": FILM_ROOM_HYDRATION_SCHEMA,
                "replay_window_id": replay_window_id,
                "plan_hash": plan_hash,
                "plan_path": str(plan_path),
                "source_id": str(replay_index["source_id"]),
                "source_kind": "chain_record",
                "match_id": match_id,
                "period": period,
                "anchor_frame_id": anchor_frame_id,
                "padding_seconds": float(replay_index["padding_seconds"]),
                "chain_record": deepcopy(chain_record),
            }
            hydration_path = film_room_cache_path(output_root, hydration_relative)
            if hydration_path.exists():
                if read_json(hydration_path) != hydration_payload:
                    raise CapabilityGap(f"Conflicting Film Room hydration shard: {replay_window_id}")
            else:
                write_film_room_cache_json(hydration_path, hydration_payload)
            hydration_sha256 = file_sha256(hydration_path)
            evidence = film_room_descriptor_evidence(chain_record, role=role)
            overlay = film_room_evidence_overlay(chain_record)
            descriptor = FilmRoomMomentResponse.model_validate(
                {
                    "result_id": result_id,
                    "source_kind": "chain_record",
                    "classification": str(row.get("classification") or chain_record.get("chain_status") or ""),
                    "match_id": match_id,
                    "period": period,
                    "anchor_frame_id": anchor_frame_id,
                    "start_frame_id": int_or_none(chain_record.get("start_frame_id")),
                    "end_frame_id": int_or_none(chain_record.get("end_frame_id")),
                    "match_time_ms": (
                        chain_record.get("match_time_ms")
                        if isinstance(chain_record.get("match_time_ms"), int)
                        else row.get("match_time_ms") if isinstance(row.get("match_time_ms"), int) else None
                    ),
                    "requested_evidence": evidence,
                    "replay_window_id": replay_window_id,
                    "replay_start_frame_id": replay_meta["replay_start_frame_id"],
                    "replay_end_frame_id": replay_meta["replay_end_frame_id"],
                    "evidence_row": evidence,
                    "unknown_reason": film_room_unknown_reason(chain_record, row),
                    "chain_status": str(chain_record.get("chain_status")) if chain_record.get("chain_status") else None,
                    "chain_reason": str(chain_record.get("chain_reason")) if chain_record.get("chain_reason") else None,
                    "evidence_overlay": overlay,
                }
            ).model_dump(mode="json")
            moments.append(
                {
                    "descriptor": descriptor,
                    "hydration_path": hydration_relative,
                    "hydration_sha256": hydration_sha256,
                }
            )
    fragment = {
        "schema_version": FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA,
        "flagship_key": key,
        "role": role,
        "plan_hash": plan_hash,
        "plan_path": str(plan_path),
        "bound_plan_hash": str(execution.get("bound_plan_hash") or execution_record.get("bound_record", {}).get("bound_plan_hash") or ""),
        "execution_id": str(execution.get("execution_id") or ""),
        "cache_status": str(execution_record.get("cache_after_execute", {}).get("cache_status") or ""),
        "moments": moments,
    }
    fragment_path = film_room_cache_path(
        output_root,
        f"{FILM_ROOM_DESCRIPTOR_FRAGMENT_DIR}/{key}-{role}.json",
    )
    write_film_room_cache_json(fragment_path, fragment)
    return {
        "flagship_key": key,
        "role": role,
        "descriptor_count": len(moments),
        "fragment_path": str(fragment_path),
        "fragment_sha256": file_sha256(fragment_path),
    }


def build_film_room_descriptor_index(*, output_root: Path) -> dict[str, Any]:
    """Merge only small descriptor fragments; never open execution-cache payloads."""

    flagships: dict[str, Any] = {}
    for spec in film_room_flagship_specs():
        key = str(spec["key"])
        plan_path = Path(spec["plan_path"])
        document = read_json(plan_path)
        plan_hash = stable_hash(document)
        roles = sorted(film_room_role_documents(document))
        descriptors: list[dict[str, Any]] = []
        hydrations: dict[str, dict[str, str]] = {}
        bound_plan_hashes: dict[str, str] = {}
        fragment_hashes: dict[str, str] = {}
        for role in roles:
            fragment_path = film_room_cache_path(
                output_root,
                f"{FILM_ROOM_DESCRIPTOR_FRAGMENT_DIR}/{key}-{role}.json",
            )
            if not fragment_path.is_file():
                raise CapabilityGap(f"Film Room descriptor fragment is missing: {fragment_path}")
            fragment = read_json(fragment_path)
            if (
                fragment.get("schema_version") != FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA
                or fragment.get("flagship_key") != key
                or fragment.get("role") != role
                or fragment.get("plan_hash") != plan_hash
            ):
                raise CapabilityGap(f"Film Room descriptor fragment provenance mismatch: {fragment_path}")
            fragment_hashes[role] = file_sha256(fragment_path)
            bound_plan_hashes[role] = str(fragment.get("bound_plan_hash") or "")
            for item in fragment.get("moments") or []:
                if not isinstance(item, dict) or not isinstance(item.get("descriptor"), dict):
                    raise CapabilityGap(f"Malformed Film Room descriptor fragment: {fragment_path}")
                descriptor = FilmRoomMomentResponse.model_validate(item["descriptor"]).model_dump(mode="json")
                replay_window_id = str(descriptor.get("replay_window_id") or "")
                hydration_relative = str(item.get("hydration_path") or "")
                hydration_path = film_room_cache_path(output_root, hydration_relative)
                expected_sha = str(item.get("hydration_sha256") or "")
                if not replay_window_id or not hydration_path.is_file() or file_sha256(hydration_path) != expected_sha:
                    raise CapabilityGap(f"Film Room hydration shard failed verification: {replay_window_id}")
                if replay_window_id in hydrations:
                    continue
                descriptors.append(descriptor)
                hydrations[replay_window_id] = {
                    "path": hydration_relative,
                    "sha256": expected_sha,
                }
        flagships[key] = {
            "plan_hash": plan_hash,
            "plan_path": str(plan_path),
            "roles": roles,
            "bound_plan_hashes": bound_plan_hashes,
            "fragment_sha256": fragment_hashes,
            "descriptor_count": len(descriptors),
            "descriptors": descriptors,
            "hydrations": hydrations,
        }
    index = {
        "schema_version": FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA,
        "flagships": flagships,
    }
    write_film_room_cache_json(
        film_room_cache_path(output_root, FILM_ROOM_DESCRIPTOR_INDEX_FILE),
        index,
    )
    return index


def film_room_certified_table_for_plan_hash(plan_hash: str) -> dict[str, Any] | None:
    for table_path, plan_path in (
        (FILM_ROOM_R2_4_TABLE_PATH, FILM_ROOM_R2_4_PLAN_PATH),
        (FILM_ROOM_R2_2_TABLE_PATH, FILM_ROOM_R2_2_PLAN_PATH),
    ):
        if not table_path.exists() or not plan_path.exists():
            continue
        table = read_json(table_path)
        if str(table.get("plan_hash")) == plan_hash:
            return {
                "table": table,
                "table_path": table_path,
                "table_hash": file_sha256(table_path),
                "plan_path": plan_path,
            }
    return None


def film_room_certified_evidence_row(
    table: dict[str, Any] | None,
    *,
    role: str,
    match_id: str,
    period: str,
) -> dict[str, Any] | None:
    if not table:
        return None
    for row in table.get("rows", []):
        if not isinstance(row, dict):
            continue
        if str(row.get("audit_role")) != role or str(row.get("match_id")) != match_id:
            continue
        for period_record in row.get("periods", []):
            if isinstance(period_record, dict) and str(period_record.get("period")) == period:
                rate = period_record.get("rate")
                if isinstance(rate, dict):
                    return deepcopy(rate)
                aggregate = period_record.get("aggregate")
                if isinstance(aggregate, dict):
                    return deepcopy(aggregate)
        return deepcopy(row)
    return None


def film_room_unknown_reason(evidence_row: dict[str, Any] | None, row: dict[str, Any]) -> str | None:
    if evidence_row:
        chain_status = str(evidence_row.get("chain_status") or row.get("chain_status") or "")
        chain_reason = evidence_row.get("chain_reason") or row.get("chain_reason")
        if chain_status == "UNKNOWN" and chain_reason:
            return str(chain_reason)
        reason = evidence_row.get("constraint_opt_out_reason") or chain_reason
        if reason:
            return str(reason)
        unknown = evidence_row.get("unknown_count")
        if isinstance(unknown, int) and unknown > 0:
            return f"{unknown} UNKNOWN records remain in the certified evidence row."
    unknown_predicates = row.get("unknown_required_predicates")
    if isinstance(unknown_predicates, list) and unknown_predicates:
        return ", ".join(str(item) for item in unknown_predicates)
    return None


def film_room_runtime_rate_source_rows(executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for execution_record in executions:
        role = str(execution_record.get("role") or "")
        for source in execution_record.get("runtime_evidence_sources", []) or []:
            if not isinstance(source, dict):
                continue
            if str(source.get("output_name") or "") != "rate_records":
                continue
            for record in source.get("records", []) or []:
                if not isinstance(record, dict):
                    continue
                row = deepcopy(record)
                row.setdefault("audit_role", role)
                row.setdefault("match_id", source.get("match_id"))
                row.setdefault("period", source.get("period"))
                row.setdefault("perspective_team_role", source.get("perspective_team_role"))
                row["_runtime_source"] = {
                    "schema_version": source.get("schema_version"),
                    "source_node_id": source.get("source_node_id"),
                    "output_name": source.get("output_name"),
                    "record_count": source.get("record_count"),
                    "requested_aliases": source.get("requested_aliases"),
                }
                rows.append(row)
    return rows


def film_room_interval_metric(table: dict[str, Any] | None) -> dict[str, Any] | None:
    if not table:
        return None
    totals = table.get("totals") if isinstance(table.get("totals"), dict) else {}
    if all(key in totals for key in ("rate_observed", "rate_lower_bound", "rate_upper_bound", "unknown_count")):
        observed = totals["rate_observed"]
        lower = totals["rate_lower_bound"]
        upper = totals["rate_upper_bound"]
        unknown_count = totals["unknown_count"]
    elif all(key in totals for key in ("a_count", "b_count", "c_count", "d1_count", "d2_count")):
        a = int(totals["a_count"])
        b = int(totals["b_count"])
        c = int(totals["c_count"])
        d1 = int(totals["d1_count"])
        d2 = int(totals["d2_count"])
        observed_denominator = a + b
        bound_denominator = a + b + c + d1 + d2
        upper_denominator = a + b + c + d2
        observed = a / observed_denominator if observed_denominator > 0 else None
        lower = a / bound_denominator if bound_denominator > 0 else None
        upper = (a + c + d2) / upper_denominator if upper_denominator > 0 else None
        unknown_count = c + d1 + d2
    else:
        return None
    if not all(isinstance(value, (int, float)) for value in (observed, lower, upper)):
        return None
    return FilmRoomIntervalMetricResponse.model_validate(
        {
            "label": film_room_interval_label("certified", table=table),
            "observed": float(observed),
            "lower": float(lower),
            "upper": float(upper),
            "unknown_count": int(unknown_count),
            "source": {
                "evidence_kind": "certified",
                "plan_hash": str(table.get("plan_hash")),
                "period_records_hash": str(table.get("period_records_hash")),
                "denominator_status_field": film_room_declared_denominator_field(table=table),
                "denominator_label": film_room_declared_denominator_label(table=table),
                "population_expression": film_room_declared_population_expression(table=table),
                "a_count": int(totals.get("a_count") or 0),
                "b_count": int(totals.get("b_count") or 0),
                "c_count": int(totals.get("c_count") or 0),
                "d1_count": int(totals.get("d1_count") or 0),
                "d2_count": int(totals.get("d2_count") or 0),
                "e_count": int(totals.get("e_count") or 0),
                "population_count": int(totals.get("population_count") or 0),
            },
        }
    ).model_dump(mode="json")


def film_room_interval_metric_from_evidence(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    rate_rows = film_room_distinct_rate_rows(rows)
    if not rate_rows:
        return None
    totals = {
        name: sum(int(row.get(name) or 0) for row in rate_rows)
        for name in ("a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count")
    }
    counted = film_room_rate_interval_from_counts(totals)
    if counted is None:
        return None
    first = rate_rows[0]
    return FilmRoomIntervalMetricResponse.model_validate(
        {
            "label": film_room_interval_label("runtime", row=first),
            "observed": float(counted["observed"]),
            "lower": float(counted["lower"]),
            "upper": float(counted["upper"]),
            "unknown_count": int(counted["unknown_count"]),
            "source": {
                "evidence_kind": "runtime",
                "source": "execution_provenance_requested_evidence_sources",
                "partition_count": len(rate_rows),
                "denominator_status_field": film_room_declared_denominator_field(row=first),
                "denominator_label": film_room_declared_denominator_label(row=first),
                "population_expression": film_room_declared_population_expression(row=first),
                "a_count": totals["a_count"],
                "b_count": totals["b_count"],
                "c_count": totals["c_count"],
                "d1_count": totals["d1_count"],
                "d2_count": totals["d2_count"],
                "e_count": totals["e_count"],
                "population_count": sum(totals.values()),
            },
        }
    ).model_dump(mode="json")


def film_room_distinct_rate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    distinct: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for row in rows:
        if not film_room_has_rate_counts(row):
            continue
        key = (
            str(row.get("audit_role") or row.get("perspective_team_role") or ""),
            str(row.get("match_id") or ""),
            str(row.get("period") or ""),
            stable_hash(row.get("group_key") if isinstance(row.get("group_key"), dict) else {}),
            str(row.get("denominator_status_field") or ""),
            str(row.get("numerator_status_field") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        distinct.append(row)
    return distinct


def film_room_has_rate_counts(row: dict[str, Any]) -> bool:
    return all(isinstance(row.get(name), int) for name in ("a_count", "b_count", "c_count", "d1_count", "d2_count"))


def film_room_rate_count_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "a_count",
            "b_count",
            "c_count",
            "d1_count",
            "d2_count",
            "e_count",
            "group_key",
            "match_id",
            "period",
            "audit_role",
        )
    }


def film_room_interval_label(kind: Literal["certified", "runtime"], *, table: dict[str, Any] | None = None, row: dict[str, Any] | None = None) -> str:
    prefix = "CERTIFIED" if kind == "certified" else "RUNTIME EVIDENCE"
    return f"{prefix} interval ({film_room_declared_denominator_label(table=table, row=row)})"


def film_room_declared_denominator_field(*, table: dict[str, Any] | None = None, row: dict[str, Any] | None = None) -> str:
    if row and row.get("denominator_status_field"):
        return str(row["denominator_status_field"])
    if table:
        for item in table.get("rows", []) or []:
            if isinstance(item, dict) and item.get("denominator_status_field"):
                return str(item["denominator_status_field"])
    return ""


def film_room_declared_population_expression(*, table: dict[str, Any] | None = None, row: dict[str, Any] | None = None) -> str:
    if row and row.get("population_expression"):
        return str(row["population_expression"])
    if table:
        for item in table.get("rows", []) or []:
            if isinstance(item, dict) and item.get("population_expression"):
                return str(item["population_expression"])
    return ""


def film_room_declared_denominator_label(*, table: dict[str, Any] | None = None, row: dict[str, Any] | None = None) -> str:
    field = film_room_declared_denominator_field(table=table, row=row)
    population_expression = film_room_declared_population_expression(table=table, row=row)
    if field == "stage_1_status":
        return "per regain start"
    if population_expression:
        return f"per {population_expression}"
    if field:
        return f"per {field} PASS denominator"
    return "declared denominator"


def film_room_legacy_single_rate_interval(row: dict[str, Any]) -> dict[str, Any] | None:
    observed = row.get("observed")
    lower = row.get("lower_bound")
    upper = row.get("upper_bound")
    unknown = row.get("unknown_count")
    if not all(isinstance(value, (int, float)) for value in (observed, lower, upper, unknown)):
        return None
    return FilmRoomIntervalMetricResponse.model_validate(
        {
            "label": film_room_interval_label("runtime", row=row),
            "observed": float(observed),
            "lower": float(lower),
            "upper": float(upper),
            "unknown_count": int(unknown),
            "source": {
                "evidence_kind": "runtime",
                "source": "execution_requested_evidence",
                "match_id": str(row.get("match_id") or ""),
                "period": str(row.get("period") or ""),
                "rate_status": str(row.get("rate_status") or ""),
                "denominator_status_field": film_room_declared_denominator_field(row=row),
                "denominator_label": film_room_declared_denominator_label(row=row),
                "population_expression": film_room_declared_population_expression(row=row),
                "a_count": int(row.get("a_count") or 0),
                "b_count": int(row.get("b_count") or 0),
                "c_count": int(row.get("c_count") or 0),
                "d1_count": int(row.get("d1_count") or 0),
                "d2_count": int(row.get("d2_count") or 0),
                "e_count": int(row.get("e_count") or 0),
            },
        }
    ).model_dump(mode="json")


def film_room_interval_metric_from_legacy_evidence(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        counted = film_room_rate_interval_from_counts(row)
        if counted is not None:
            return film_room_interval_metric_from_evidence([row])
        legacy = film_room_legacy_single_rate_interval(row)
        if legacy is not None:
            return legacy
    return None


def film_room_rate_interval_from_counts(row: dict[str, Any]) -> dict[str, float | int] | None:
    count_names = ("a_count", "b_count", "c_count", "d1_count", "d2_count")
    if not all(isinstance(row.get(name), int) for name in count_names):
        return None
    a = int(row["a_count"])
    b = int(row["b_count"])
    c = int(row["c_count"])
    d1 = int(row["d1_count"])
    d2 = int(row["d2_count"])
    observed_denominator = a + b
    bound_denominator = a + b + c + d1 + d2
    upper_denominator = a + b + c + d2
    if observed_denominator <= 0 or bound_denominator <= 0:
        return None
    return {
        "observed": a / observed_denominator,
        "lower": a / bound_denominator,
        "upper": (a + c + d2) / upper_denominator if upper_denominator > 0 else 0.0,
        "unknown_count": c + d1 + d2,
    }


def film_room_compiled_chips(expression_payload: Any, document_payload: dict[str, Any]) -> list[str]:
    chips: list[str] = []
    if isinstance(expression_payload, dict):
        for item in expression_payload.get("operator_applications", []) or []:
            if isinstance(item, dict) and item.get("name"):
                chips.append(str(item["name"]))
    for document in film_room_role_documents(document_payload).values():
        for node in document.get("draft_plan", {}).get("nodes", []):
            if not isinstance(node, dict):
                continue
            if node.get("operator") and isinstance(node["operator"], dict):
                name = str(node["operator"].get("name") or node.get("node_id"))
            else:
                name = str(node.get("catalog_ref") or node.get("node_id") or "")
            if name and name not in chips:
                chips.append(name)
    return chips[:12]


def film_room_replay_frame_response(payload: dict[str, Any], *, output_root: Path) -> dict[str, Any]:
    replay_window_id = str(payload.get("replay_window_id") or "").strip()
    frame_id = int(payload.get("frame_id"))
    replay = ensure_film_room_replay_payload(replay_window_id, output_root=output_root)
    frame = next((item for item in replay.get("frames", []) if int(item.get("frame_id")) == frame_id), None)
    if not isinstance(frame, dict):
        raise CapabilityGap(f"frame {frame_id} is not available in {replay_window_id}")
    response = {
        "ok": True,
        "replay_window_id": replay_window_id,
        "frame_id": frame_id,
        "frame_sha256": stable_json_sha256(frame),
        "canonical_sources": public_canonical_sources(replay.get("canonical_sources")),
        "frame": frame,
    }
    return validate_public_response("FilmRoomReplayFrameResponse", response)


def film_room_flagship_specs() -> list[dict[str, Any]]:
    return [
        {
            "key": "fragile_retention",
            "question": FILM_ROOM_FRAGILE_RETENTION_QUESTION,
            "plan_path": FILM_ROOM_R2_2_PLAN_PATH,
            "table_path": FILM_ROOM_R2_2_TABLE_PATH,
        },
        {
            "key": "counterattack_sequence_rate",
            "question": FILM_ROOM_COUNTERATTACK_QUESTION,
            "plan_path": FILM_ROOM_R2_4_PLAN_PATH,
            "table_path": FILM_ROOM_R2_4_TABLE_PATH,
        },
    ]


def film_room_certified_table_moments(
    *,
    certified: dict[str, Any],
    plan_hash: str,
) -> list[dict[str, Any]]:
    """Build honest, replayable period records without executing the plan.

    The certified tables intentionally omit their source-record populations.
    Only table period records with a committed frame boundary can therefore be
    exposed as gallery moments. They remain labelled as table rate partitions,
    never as reconstructed chain records.
    """

    table = certified["table"]
    moments: list[dict[str, Any]] = []
    for row in table.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        audit_role = str(row.get("audit_role") or "")
        match_id = str(row.get("match_id") or "")
        for period_record in row.get("periods", []) or []:
            if not isinstance(period_record, dict):
                continue
            rate = period_record.get("rate")
            evidence = deepcopy(rate if isinstance(rate, dict) else period_record)
            period = str(period_record.get("period") or evidence.get("period") or "")
            anchor_frame_id = int_or_none(
                evidence.get("anchor_frame_id") or evidence.get("open_frame_id")
            )
            if not match_id or not period or anchor_frame_id is None:
                continue
            evidence.setdefault("audit_role", audit_role)
            evidence.setdefault("match_id", match_id)
            evidence.setdefault("period", period)
            unknown_count = evidence.get("unknown_count")
            if not isinstance(unknown_count, int) and all(
                isinstance(evidence.get(name), int) for name in ("c_count", "d1_count", "d2_count")
            ):
                unknown_count = sum(
                    int(evidence[name]) for name in ("c_count", "d1_count", "d2_count")
                )
                evidence["unknown_count"] = unknown_count
            result_id = "certified_" + stable_hash(
                {
                    "plan_hash": plan_hash,
                    "audit_role": audit_role,
                    "match_id": match_id,
                    "period": period,
                    "relation_id": evidence.get("relation_id"),
                }
            )[:16]
            replay_meta = film_room_register_replay_window(
                {
                    "match_id": match_id,
                    "period": period,
                    "anchor_frame_id": anchor_frame_id,
                },
                plan_hash=plan_hash,
                plan_path=Path(certified["plan_path"]),
                fallback_result_id=result_id,
                source_kind="certified_table_partition",
            )
            classification = "CERTIFIED_TABLE_RATE_PARTITION"
            overlay = film_room_evidence_overlay(
                {
                    "anchor_frame_id": anchor_frame_id,
                    "classification": classification,
                }
            )
            moments.append(
                {
                    "result_id": result_id,
                    "source_kind": "certified_table_partition",
                    "classification": classification,
                    "match_id": match_id,
                    "period": period,
                    "anchor_frame_id": anchor_frame_id,
                    "start_frame_id": int_or_none(evidence.get("open_frame_id")),
                    "end_frame_id": int_or_none(evidence.get("close_frame_id")),
                    "match_time_ms": None,
                    "requested_evidence": deepcopy(evidence),
                    "replay_window_id": replay_meta["replay_window_id"],
                    "replay_start_frame_id": replay_meta["replay_start_frame_id"],
                    "replay_end_frame_id": replay_meta["replay_end_frame_id"],
                    "evidence_row": deepcopy(evidence),
                    "unknown_reason": (
                        f"{unknown_count} UNKNOWN records remain in this certified table partition."
                        if isinstance(unknown_count, int) and unknown_count > 0
                        else None
                    ),
                    "chain_status": None,
                    "chain_reason": None,
                    "evidence_overlay": overlay,
                }
            )
    return moments


def film_room_answer_from_certified_table(
    document_payload: dict[str, Any],
    *,
    certified: dict[str, Any],
) -> dict[str, Any]:
    plan_hash = stable_hash(document_payload)
    table = certified["table"]
    if str(table.get("plan_hash") or "") != plan_hash:
        raise CapabilityGap("Committed Film Room plan does not match its certified table hash.")
    interval_metric = film_room_interval_metric(table)
    if interval_metric is None:
        raise CapabilityGap("Committed Film Room certified table has no interval metric.")
    moments = film_room_certified_table_moments(certified=certified, plan_hash=plan_hash)
    selected_replay_window_id = (
        str(moments[0]["replay_window_id"])
        if moments and moments[0].get("replay_window_id")
        else None
    )
    answer = {
        "status": "answer_ready",
        "compiled_chips": film_room_compiled_chips(None, document_payload),
        "document": document_payload,
        "certified_evidence_rows": deepcopy(table.get("rows", [])),
        "runtime_evidence_rows": [],
        "evidence_rows_kind": "certified",
        "interval_metric": interval_metric,
        "moments": moments,
        "moment_total_count": len(moments),
        "visible_moment_count": len(moments),
        "replay": None,
        "executions": [],
        "raw_evidence": {
            "rate_records": [],
            "returned_rate_records": [],
            "runtime_rate_source_rows": [],
            "certified_table": deepcopy(table),
            "moment_source": "certified_table.rows[].periods[].rate",
            "interval_source_contract": (
                "Film Room interval metrics and gallery records come from the committed certified "
                "table whose plan_hash matches the committed plan document. No plan execution ran."
            ),
        },
        "provenance": {
            "plan_hash": plan_hash,
            "synthesized_document_hash": plan_hash,
            "expression_hash": None,
            "certified_table_path": str(certified["table_path"]),
            "certified_table_hash": str(certified["table_hash"]),
            "certified_plan_path": str(certified["plan_path"]),
            "certified_period_records_hash": str(table.get("period_records_hash")),
            "bound_plan_hashes": {},
            "replay_window_id": selected_replay_window_id,
            "canonical_sources": {},
            "runtime_commit": runtime_commit_identifier(),
            "tree": git_tree_identifier(),
        },
    }
    return FilmRoomAnswerResponse.model_validate(answer).model_dump(mode="json")


def film_room_certified_prewarmed_response(
    *,
    key: str,
    question: str,
    plan_path: Path,
) -> dict[str, Any]:
    started_at = time.monotonic()
    document_payload = read_json(plan_path)
    plan_hash = stable_hash(document_payload)
    certified = film_room_certified_table_for_plan_hash(plan_hash)
    if certified is None:
        raise CapabilityGap(f"No committed certified table matches Film Room plan {plan_path}.")
    answer = film_room_answer_from_certified_table(document_payload, certified=certified)
    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    response = {
        "ok": True,
        "outcome": "expression",
        "request_text": question,
        "provider": "prewarmed_certified_table",
        "model": "not_invoked",
        "latency_ms": elapsed_ms,
        "latency_breakdown_ms": {
            "hermes": 0,
            "synthesis": 0,
            "execution": 0,
            "total": elapsed_ms,
        },
        "hermes": {
            "outcome": "expression",
            "source": "prewarmed_certified_table",
            "flagship_key": key,
            "execution_performed": False,
            "billing_surface": "none for committed certified-table bootstrap",
        },
        "answer": answer,
        "clarification": None,
        "refusal": None,
    }
    return validate_public_response("FilmRoomAskResponse", response)


def film_room_descriptor_prewarmed_response(
    *,
    key: str,
    question: str,
    plan_path: Path,
    index_entry: dict[str, Any],
) -> dict[str, Any]:
    """Upgrade the table answer from a lightweight, disk-backed descriptor index."""

    started_at = time.monotonic()
    response = film_room_certified_prewarmed_response(
        key=key,
        question=question,
        plan_path=plan_path,
    )
    answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
    plan_hash = stable_hash(read_json(plan_path))
    if index_entry.get("plan_hash") != plan_hash:
        raise CapabilityGap(f"Film Room descriptor index plan mismatch for {key}.")
    descriptors = [
        FilmRoomMomentResponse.model_validate(item).model_dump(mode="json")
        for item in index_entry.get("descriptors") or []
        if isinstance(item, dict)
    ]
    if not descriptors:
        raise CapabilityGap(f"Film Room descriptor index has no moments for {key}.")
    hydrations = index_entry.get("hydrations") if isinstance(index_entry.get("hydrations"), dict) else {}
    for descriptor in descriptors:
        replay_window_id = str(descriptor.get("replay_window_id") or "")
        hydration = hydrations.get(replay_window_id) if isinstance(hydrations.get(replay_window_id), dict) else {}
        if not hydration.get("path") or not hydration.get("sha256"):
            raise CapabilityGap(f"Film Room descriptor lacks hydration provenance: {replay_window_id}")
        anchor_frame_id = int(descriptor["anchor_frame_id"])
        start_frame_id = int(descriptor.get("replay_start_frame_id") or anchor_frame_id)
        end_frame_id = int(descriptor.get("replay_end_frame_id") or anchor_frame_id)
        padding_frames = max(50, anchor_frame_id - start_frame_id, end_frame_id - anchor_frame_id)
        FILM_ROOM_REPLAY_INDEX[replay_window_id] = {
            "replay_window_id": replay_window_id,
            "plan_hash": plan_hash,
            "plan_path": str(plan_path),
            "source_id": str(descriptor["result_id"]),
            "source_kind": "chain_record",
            "match_id": str(descriptor["match_id"]),
            "period": str(descriptor["period"]),
            "anchor_frame_id": anchor_frame_id,
            "padding_seconds": padding_frames / 25.0,
            "hydration_path": str(hydration["path"]),
            "hydration_sha256": str(hydration["sha256"]),
        }
    answer["moments"] = descriptors
    answer["moment_total_count"] = len(descriptors)
    answer["visible_moment_count"] = len(descriptors)
    answer["executions"] = []
    answer["replay"] = None
    answer["runtime_evidence_rows"] = []
    answer["evidence_rows_kind"] = "certified"
    answer["raw_evidence"] = {
        "descriptor_index": {
            "schema_version": FILM_ROOM_DESCRIPTOR_INDEX_SCHEMA,
            "descriptor_count": len(descriptors),
            "fragment_sha256": deepcopy(index_entry.get("fragment_sha256") or {}),
        },
        "moment_source": "disk_backed_chain_descriptor_index",
        "interval_source_contract": (
            "The interval remains the committed certified-table result; chain descriptors are loaded "
            "without opening full execution payloads and hydrate one replay window per request."
        ),
    }
    provenance = answer.get("provenance") if isinstance(answer.get("provenance"), dict) else {}
    provenance["bound_plan_hashes"] = deepcopy(index_entry.get("bound_plan_hashes") or {})
    provenance["replay_window_id"] = descriptors[0].get("replay_window_id")
    answer["provenance"] = provenance
    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    response.update(
        {
            "provider": "prewarmed_descriptor_index",
            "latency_ms": elapsed_ms,
            "latency_breakdown_ms": {
                "hermes": 0,
                "synthesis": 0,
                "execution": 0,
                "total": elapsed_ms,
            },
            "hermes": {
                "outcome": "expression",
                "source": "prewarmed_descriptor_index",
                "flagship_key": key,
                "execution_performed": False,
                "billing_surface": "none for disk-backed descriptor bootstrap",
            },
            "answer": FilmRoomAnswerResponse.model_validate(answer).model_dump(mode="json"),
        }
    )
    return validate_public_response("FilmRoomAskResponse", response)


def film_room_prewarmed_response(
    *,
    key: str,
    question: str,
    plan_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    started_at = time.monotonic()
    document_payload = read_json(plan_path)
    execution_started_at = time.monotonic()
    answer = film_room_answer_from_document(
        document_payload,
        expression_payload=None,
        expression_hash=None,
        synthesized_document_hash=stable_hash(document_payload),
        output_root=output_root,
    )
    execution_latency_ms = int((time.monotonic() - execution_started_at) * 1000)
    response = {
        "ok": True,
        "outcome": "expression",
        "request_text": question,
        "provider": "prewarmed_committed_plan",
        "model": "not_invoked",
        "latency_ms": int((time.monotonic() - started_at) * 1000),
        "latency_breakdown_ms": {
            "hermes": 0,
            "synthesis": 0,
            "execution": execution_latency_ms,
            "total": int((time.monotonic() - started_at) * 1000),
        },
        "hermes": {
            "outcome": "expression",
            "source": "prewarmed_committed_plan",
            "flagship_key": key,
            "billing_surface": "none for bootstrap render; live asks use ChatGPT subscription via openai-codex Hermes CLI",
        },
        "answer": answer,
        "clarification": None,
        "refusal": None,
    }
    return validate_public_response("FilmRoomAskResponse", response)


def utc_iso_seconds() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def film_room_flagship_plan_hashes() -> dict[str, str | None]:
    return {
        "fragile_retention": read_json(FILM_ROOM_R2_2_TABLE_PATH).get("plan_hash")
        if FILM_ROOM_R2_2_TABLE_PATH.exists()
        else None,
        "counterattack_sequence_rate": read_json(FILM_ROOM_R2_4_TABLE_PATH).get("plan_hash")
        if FILM_ROOM_R2_4_TABLE_PATH.exists()
        else None,
    }


def film_room_prewarm_warming_payload() -> dict[str, Any]:
    with FILM_ROOM_PREWARM_LOCK:
        state = deepcopy(FILM_ROOM_PREWARM_STATE)
        records = deepcopy(FILM_ROOM_PREWARM_RECORDS)
    if not state.get("started_at"):
        state["started_at"] = utc_iso_seconds()
    return {
        "state": "warming",
        "started_at": state.get("started_at"),
        "completed_at": state.get("completed_at"),
        "items": state.get("items") or [
            {
                "key": str(spec["key"]),
                "plan": str(spec["plan_path"]),
                "status": "queued",
            }
            for spec in film_room_flagship_specs()
        ],
        "prewarm_records": records,
        "last_error": state.get("last_error"),
    }


def film_room_bootstrap_response(*, output_root: Path) -> dict[str, Any]:
    with FILM_ROOM_PREWARM_LOCK:
        prewarmed = deepcopy(FILM_ROOM_PREWARMED_RESPONSES.get("counterattack_sequence_rate"))
        records = deepcopy(FILM_ROOM_PREWARM_RECORDS)
    state = "ready" if isinstance(prewarmed, dict) and isinstance(prewarmed.get("answer"), dict) else "warming"
    answer = prewarmed.get("answer") if isinstance(prewarmed, dict) else None
    provenance = answer.get("provenance") if isinstance(answer, dict) else None
    response = {
        "ok": True,
        "state": state,
        "provider": HERMES_PROVIDER,
        "model": HERMES_MODEL,
        "billing_surface": "ChatGPT subscription via openai-codex Hermes CLI",
        "flagship_plan_hashes": film_room_flagship_plan_hashes(),
        "prewarm_records": records,
        "warming": film_room_prewarm_warming_payload() if state == "warming" else None,
        "prewarmed_response": prewarmed,
        "answer": answer,
        "provenance": provenance,
    }
    return validate_public_response("FilmRoomBootstrapResponse", response)


def prewarm_film_room_flagships_from_certified_tables() -> None:
    """Install the cheap committed-table gallery without executing any plan."""

    started_at_iso = utc_iso_seconds()
    with FILM_ROOM_PREWARM_LOCK:
        FILM_ROOM_PREWARMED_RESPONSES.clear()
        FILM_ROOM_PREWARM_RECORDS.clear()
        FILM_ROOM_REPLAY_INDEX.clear()
        FILM_ROOM_PREWARM_STATE.update(
            {
                "state": "warming",
                "started_at": started_at_iso,
                "completed_at": None,
                "items": [
                    {
                        "key": str(spec["key"]),
                        "plan": str(spec["plan_path"]),
                        "table": str(spec["table_path"]),
                        "status": "queued",
                        "execution_status": "not_started",
                    }
                    for spec in film_room_flagship_specs()
                ],
                "last_error": None,
            }
        )
    errors: list[dict[str, str]] = []
    for spec in film_room_flagship_specs():
        plan_path = Path(spec["plan_path"])
        table_path = Path(spec["table_path"])
        if not plan_path.exists() or not table_path.exists():
            missing = plan_path if not plan_path.exists() else table_path
            error = {
                "error_type": "FileNotFoundError",
                "message": f"missing committed input: {missing}",
            }
            errors.append(error)
            with FILM_ROOM_PREWARM_LOCK:
                for item in FILM_ROOM_PREWARM_STATE["items"]:
                    if item.get("key") == str(spec["key"]):
                        item["status"] = "missing_committed_input"
            continue
        started_at = time.monotonic()
        print(f"Prewarming Film Room flagship from certified table {table_path}...", flush=True)
        with FILM_ROOM_PREWARM_LOCK:
            for item in FILM_ROOM_PREWARM_STATE["items"]:
                if item.get("key") == str(spec["key"]):
                    item["status"] = "running"
        try:
            response = film_room_certified_prewarmed_response(
                key=str(spec["key"]),
                question=str(spec["question"]),
                plan_path=plan_path,
            )
        except Exception as exc:  # noqa: BLE001 - committed-pair errors become honest warming.
            error = {"error_type": type(exc).__name__, "message": str(exc)}
            errors.append(error)
            with FILM_ROOM_PREWARM_LOCK:
                for item in FILM_ROOM_PREWARM_STATE["items"]:
                    if item.get("key") == str(spec["key"]):
                        item["status"] = "certified_table_error"
                        item["error"] = error
            continue
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        answer = response["answer"] if isinstance(response.get("answer"), dict) else {}
        record = {
            "key": str(spec["key"]),
            "plan": str(plan_path),
            "table": str(table_path),
            "prewarm_kind": "certified_table",
            "execution_performed": False,
            "elapsed_ms": elapsed_ms,
            "evidence_rows_kind": answer.get("evidence_rows_kind"),
            "moment_count": len(answer.get("moments", [])),
        }
        with FILM_ROOM_PREWARM_LOCK:
            FILM_ROOM_PREWARMED_RESPONSES[str(spec["key"])] = response
            FILM_ROOM_PREWARM_RECORDS.append(record)
            for item in FILM_ROOM_PREWARM_STATE["items"]:
                if item.get("key") == str(spec["key"]):
                    item["status"] = "certified_ready"
                    item["elapsed_ms"] = elapsed_ms
        print(
            f"Prewarmed Film Room flagship from certified table {table_path}: "
            f"moments={record['moment_count']} elapsed_ms={elapsed_ms}",
            flush=True,
        )
    with FILM_ROOM_PREWARM_LOCK:
        gallery_ready = isinstance(
            FILM_ROOM_PREWARMED_RESPONSES.get("counterattack_sequence_rate"), dict
        )
        FILM_ROOM_PREWARM_STATE.update(
            {
                "state": "ready" if gallery_ready else "warming",
                "completed_at": utc_iso_seconds(),
                "last_error": errors[-1] if errors else None,
            }
        )


def prewarm_film_room_flagships(*, output_root: Path) -> None:
    """Atomically upgrade table answers from disk-backed descriptors only."""

    with FILM_ROOM_PREWARM_LOCK:
        if not FILM_ROOM_PREWARM_STATE.get("items"):
            FILM_ROOM_PREWARM_STATE["items"] = [
                {
                    "key": str(spec["key"]),
                    "plan": str(spec["plan_path"]),
                    "table": str(spec["table_path"]),
                    "status": "not_loaded",
                    "execution_status": "queued",
                }
                for spec in film_room_flagship_specs()
            ]
        FILM_ROOM_PREWARM_STATE["execution_started_at"] = utc_iso_seconds()
    started_index = time.monotonic()
    descriptor_index = build_film_room_descriptor_index(output_root=output_root)
    index_elapsed_ms = int((time.monotonic() - started_index) * 1000)
    for spec in film_room_flagship_specs():
        plan_path = Path(spec["plan_path"])
        if not plan_path.exists():
            print(f"Film Room descriptor prewarm skipped missing plan: {plan_path}", flush=True)
            with FILM_ROOM_PREWARM_LOCK:
                for item in FILM_ROOM_PREWARM_STATE["items"]:
                    if item.get("key") == str(spec["key"]):
                        item["execution_status"] = "missing_plan"
            continue
        started_at = time.monotonic()
        print(f"Descriptor-prewarming Film Room flagship {plan_path}...", flush=True)
        with FILM_ROOM_PREWARM_LOCK:
            for item in FILM_ROOM_PREWARM_STATE["items"]:
                if item.get("key") == str(spec["key"]):
                    item["execution_status"] = "running"
        flagships = descriptor_index.get("flagships") if isinstance(descriptor_index.get("flagships"), dict) else {}
        index_entry = flagships.get(str(spec["key"])) if isinstance(flagships.get(str(spec["key"])), dict) else {}
        if not index_entry.get("descriptors"):
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            record = {
                "key": str(spec["key"]),
                "plan": str(plan_path),
                "prewarm_kind": "descriptor_index_upgrade",
                "execution_performed": False,
                "upgrade_applied": False,
                "elapsed_ms": elapsed_ms,
                "index_build_elapsed_ms": index_elapsed_ms,
                "descriptor_count": 0,
                "full_execution_cache_payloads_opened": 0,
                "reason": "no_chain_descriptors",
            }
            with FILM_ROOM_PREWARM_LOCK:
                FILM_ROOM_PREWARM_RECORDS.append(record)
                for item in FILM_ROOM_PREWARM_STATE["items"]:
                    if item.get("key") == str(spec["key"]):
                        item["execution_status"] = "no_chain_descriptors"
                        item["execution_elapsed_ms"] = elapsed_ms
            print(
                f"Descriptor-prewarmed Film Room flagship {plan_path}: "
                "descriptors=0 full_payloads_opened=0 upgrade_applied=False",
                flush=True,
            )
            continue
        response = film_room_descriptor_prewarmed_response(
            key=str(spec["key"]),
            question=str(spec["question"]),
            plan_path=plan_path,
            index_entry=index_entry,
        )
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        answer = response.get("answer") if isinstance(response.get("answer"), dict) else {}
        upgrade_servable = bool(answer.get("moments") and answer.get("interval_metric"))
        descriptor_count = len(answer.get("moments") or [])
        record = {
            "key": str(spec["key"]),
            "plan": str(plan_path),
            "prewarm_kind": "descriptor_index_upgrade",
            "execution_performed": False,
            "upgrade_applied": upgrade_servable,
            "elapsed_ms": elapsed_ms,
            "index_build_elapsed_ms": index_elapsed_ms,
            "descriptor_count": descriptor_count,
            "full_execution_cache_payloads_opened": 0,
        }
        with FILM_ROOM_PREWARM_LOCK:
            if upgrade_servable:
                FILM_ROOM_PREWARMED_RESPONSES[str(spec["key"])] = response
            FILM_ROOM_PREWARM_RECORDS.append(record)
            for item in FILM_ROOM_PREWARM_STATE["items"]:
                if item.get("key") == str(spec["key"]):
                    item["execution_status"] = (
                        "ready" if upgrade_servable else "completed_no_servable_upgrade"
                    )
                    item["execution_elapsed_ms"] = elapsed_ms
        print(
            f"Descriptor-prewarmed Film Room flagship {plan_path}: "
            f"descriptors={descriptor_count} full_payloads_opened=0 "
            f"upgrade_applied={upgrade_servable} elapsed_ms={elapsed_ms}",
            flush=True,
        )
    with FILM_ROOM_PREWARM_LOCK:
        gallery_ready = isinstance(
            FILM_ROOM_PREWARMED_RESPONSES.get("counterattack_sequence_rate"), dict
        )
        FILM_ROOM_PREWARM_STATE.update(
            {
                "state": "ready" if gallery_ready else "warming",
                "execution_completed_at": utc_iso_seconds(),
                "last_error": None,
            }
        )


def prewarm_film_room_flagships_safely(*, output_root: Path) -> None:
    try:
        prewarm_film_room_flagships(output_root=output_root)
        print("Film Room prewarm complete.", flush=True)
    except Exception as exc:  # noqa: BLE001 - background prewarm must not kill the bound service.
        print(
            json.dumps(
                {
                    "event": "film_room_prewarm_failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        with FILM_ROOM_PREWARM_LOCK:
            gallery_ready = isinstance(
                FILM_ROOM_PREWARMED_RESPONSES.get("counterattack_sequence_rate"), dict
            )
            FILM_ROOM_PREWARM_STATE.update(
                {
                    "state": "ready" if gallery_ready else "warming",
                    "last_error": {
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )


def start_film_room_prewarm_thread(*, output_root: Path) -> threading.Thread:
    with FILM_ROOM_PREWARM_LOCK:
        for item in FILM_ROOM_PREWARM_STATE.get("items", []):
            item["execution_status"] = "queued"
    thread = threading.Thread(
        target=prewarm_film_room_flagships_safely,
        kwargs={"output_root": output_root},
        name="film-room-prewarm",
        daemon=True,
    )
    thread.start()
    return thread


def initialize_film_room_prewarm(
    *,
    output_root: Path,
    execution_enabled: bool | None = None,
) -> threading.Thread | None:
    prewarm_film_room_flagships_from_certified_tables()
    should_execute = WORKBENCH_PREWARM_FILM_ROOM if execution_enabled is None else execution_enabled
    if should_execute:
        return start_film_room_prewarm_thread(output_root=output_root)
    with FILM_ROOM_PREWARM_LOCK:
        for item in FILM_ROOM_PREWARM_STATE.get("items", []):
            item["execution_status"] = "disabled"
    print(
        "Film Room execution prewarm disabled; certified-table gallery remains ready.",
        flush=True,
    )
    return None


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
        hermes_workshop_root = hermes_invocation_output_root(output_root)
        surface = hermes_tool_surface(hermes, output_root=hermes_workshop_root)
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
            output_root=hermes_workshop_root,
        )
        session = newest_hermes_session_after(started_at)
        invocation = parse_invocation_json(completed.stdout)
        final = parse_final_json(str(invocation.get("stdout") or ""))
        if completed.returncode != 0 or not invocation.get("ok") or not final:
            raise CapabilityGap("Hermes did not return a valid structured N1E interpretation.")

        interpretation = hermes_final_to_interpretation(HERO_QUESTION, final, session, output_root=hermes_workshop_root)
        if interpretation.get("status") != "PLAN_INTERPRETED":
            raise CapabilityGap(f"Hermes did not return an executable plan: {interpretation.get('status')}")
        if interpretation.get("provenance_source") != "HERMES_NOVEL_COMPOSITION":
            raise CapabilityGap(
                f"Hermes did not produce novel-composition provenance: {interpretation.get('provenance_source')}"
            )
        draft_plan_id = str(final.get("draft_plan_id") or interpretation.get("draft_plan_id") or "")
        if not draft_plan_id:
            raise CapabilityGap("Hermes final decision did not include draft_plan_id.")
        hermes_draft_record = read_handle("draft-plans", draft_plan_id, output_root=hermes_workshop_root)
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
                "hermes_workshop_root": cloud_safe_path(hermes_workshop_root),
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
            "hermes_workshop_root": cloud_safe_path(hermes_invocation_output_root(output_root)),
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


def is_attested_hero_question(query: str) -> bool:
    from tqe.verification.n1c import HERO_QUESTION

    return normalized(query) == normalized(HERO_QUESTION)


def product_model_query(query: str) -> str:
    if is_attested_hero_question(query):
        return n1f_clarified_query(query)
    return query


def attested_hero_interpretation(query: str) -> dict[str, Any]:
    bundle = read_committed_json(N1D_ORIGIN_BUNDLE_PATH)
    origin = bundle.get("hermes_origin") if isinstance(bundle.get("hermes_origin"), dict) else {}
    host_augmentation = bundle.get("host_augmentation") if isinstance(bundle.get("host_augmentation"), dict) else {}
    host_pipeline = bundle.get("host_pipeline") if isinstance(bundle.get("host_pipeline"), dict) else {}
    validation = host_pipeline.get("validation") if isinstance(host_pipeline.get("validation"), dict) else {}
    plan_document = host_augmentation.get("augmented_document")
    if not isinstance(plan_document, dict):
        return hermes_unavailable(
            query,
            "The verified Hermes composition artifact is unavailable. Manual recipes remain available.",
            fallback_reason="attested_origin_missing_plan",
        )
    provenance_source, attestation_details = hermes_draft_provenance(plan_document, str(validation.get("bound_plan_hash") or ""))
    fallback_reason = None
    if provenance_source != "HERMES_NOVEL_COMPOSITION":
        failures = attestation_details.get("failures") if isinstance(attestation_details, dict) else None
        fallback_reason = "attestation_not_verified" + (f":{','.join(failures)}" if failures else "")
    return ok(
        {
            "status": "PLAN_INTERPRETED",
            "provenance_source": provenance_source,
            "query": query,
            "message": "Loaded from the committed N1D.1 Hermes-origin attestation; scope is locked to the verified match, period, and perspective.",
            "source": "hermes_attested_origin_bundle",
            "agent_session_id": origin.get("session_id"),
            "model_session_id": origin.get("session_id"),
            "draft_plan_id": origin.get("draft_plan_id"),
            "draft_plan_hash": origin.get("draft_plan_hash"),
            "bound_plan_id": validation.get("bound_plan_id"),
            "bound_plan_hash": validation.get("bound_plan_hash"),
            "recipe_id": str(plan_document.get("recipe", {}).get("recipe_id") or ""),
            "recipe": recipe_card(plan_document, "EXPERIMENTAL"),
            "plan_document": plan_document,
            "plan_hash": stable_hash(plan_document),
            "manual_available": True,
            "repair_applied": False,
            "fallback_reason": fallback_reason,
        }
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


def n1f_trace_tool_response(bundle: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    trace = bundle.get("hermes_origin", {}).get("session_trace", {})
    responses = trace.get("tool_responses") if isinstance(trace, dict) else None
    if not isinstance(responses, list):
        return None
    expected = tool_name.removeprefix("functions.")
    for response in reversed(responses):
        if not isinstance(response, dict):
            continue
        actual = str(response.get("tool_name") or "").removeprefix("functions.")
        if actual != expected:
            continue
        content = response.get("content")
        if isinstance(content, dict):
            return content
    return None


def n1f_trace_submit_response_draft_plan_id(bundle: dict[str, Any]) -> str:
    content = n1f_trace_tool_response(bundle, "mcp_priori_tactical_submit_query_plan")
    if not isinstance(content, dict):
        return ""
    draft_plan_id = content.get("draft_plan_id")
    return str(draft_plan_id).strip() if draft_plan_id else ""


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


def recover_n1f_hermes_draft_record(
    draft_plan_id: str,
    bundle: dict[str, Any],
    *,
    output_root: Path,
    hermes_workshop_root: Path,
) -> dict[str, Any]:
    lookup_errors: list[dict[str, str]] = []
    roots: list[Path] = []
    for candidate in (hermes_workshop_root, output_root, HERMES_WORKSHOP_ROOT, DEFAULT_WORKSHOP_ROOT):
        if candidate not in roots:
            roots.append(candidate)
    for root in roots:
        try:
            record = read_handle("draft-plans", draft_plan_id, output_root=root)
        except Exception as exc:  # noqa: BLE001 - preserve all lookup attempts for origin diagnostics.
            lookup_errors.append(
                {
                    "root": cloud_safe_path(root),
                    "error_type": type(exc).__name__,
                    "message": short_text(str(exc), 300),
                }
            )
            continue
        record = dict(record)
        record["draft_record_source"] = "handle"
        record["draft_record_root"] = cloud_safe_path(root)
        return record

    submitted_document = n1f_trace_submitted_plan_document(bundle)
    if submitted_document is not None:
        submit_response = n1f_trace_tool_response(bundle, "mcp_priori_tactical_submit_query_plan") or {}
        draft_hash = str(submit_response.get("draft_plan_hash") or "").strip() or stable_hash(submitted_document)
        return {
            "schema_version": "1.0",
            "draft_plan_id": draft_plan_id,
            "draft_plan_hash": draft_hash,
            "document": submitted_document,
            "draft_record_source": "persisted_mcp_trace",
            "draft_document_source": "submit_query_plan.arguments.plan_document",
            "draft_hash_source": "submit_query_plan.response.draft_plan_hash"
            if submit_response.get("draft_plan_hash")
            else "recomputed_from_submit_query_plan.arguments.plan_document",
            "draft_lookup_errors": lookup_errors,
        }
    raise CapabilityGap(f"Unknown draft-plans handle: {draft_plan_id}")


def attach_n1f_hermes_draft_if_present(
    bundle: dict[str, Any],
    final_decision: dict[str, Any],
    *,
    output_root: Path,
    hermes_workshop_root: Path,
) -> None:
    draft_plan_id = (
        str(final_decision.get("draft_plan_id") or "").strip()
        or n1f_trace_draft_plan_id(bundle)
        or n1f_trace_submit_response_draft_plan_id(bundle)
    )
    if not draft_plan_id:
        return
    try:
        hermes_draft_record = recover_n1f_hermes_draft_record(
            draft_plan_id,
            bundle,
            output_root=output_root,
            hermes_workshop_root=hermes_workshop_root,
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic bundle should preserve absence rather than fail.
        bundle.setdefault("hermes_origin", {})["draft_lookup_error"] = {
            "draft_plan_id": draft_plan_id,
            "error_type": type(exc).__name__,
            "message": short_text(str(exc), 500),
        }
        return
    hermes_origin = bundle.setdefault("hermes_origin", {})
    hermes_origin["draft_plan_id"] = draft_plan_id
    hermes_origin["draft_plan_hash"] = hermes_draft_record.get("draft_plan_hash")
    hermes_origin["draft_record_source"] = hermes_draft_record.get("draft_record_source")
    if hermes_draft_record.get("draft_record_root"):
        hermes_origin["draft_record_root"] = hermes_draft_record.get("draft_record_root")
    if hermes_draft_record.get("draft_document_source"):
        hermes_origin["draft_document_source"] = hermes_draft_record.get("draft_document_source")
    if hermes_draft_record.get("draft_hash_source"):
        hermes_origin["draft_hash_source"] = hermes_draft_record.get("draft_hash_source")
    if hermes_draft_record.get("draft_lookup_errors"):
        hermes_origin["draft_lookup_errors"] = hermes_draft_record.get("draft_lookup_errors")
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
        hermes_workshop_root = hermes_invocation_output_root(output_root)
        surface = hermes_tool_surface(hermes, output_root=hermes_workshop_root)
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
            output_root=hermes_workshop_root,
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

        interpretation = hermes_final_to_interpretation(clarified_query, final, session, output_root=hermes_workshop_root)
        base_bundle["hermes_origin"]["interpretation"] = interpretation
        if interpretation.get("status") != "PLAN_INTERPRETED":
            attach_n1f_hermes_draft_if_present(
                base_bundle,
                final,
                output_root=output_root,
                hermes_workshop_root=hermes_workshop_root,
            )
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
        hermes_draft_record = recover_n1f_hermes_draft_record(
            draft_plan_id,
            base_bundle,
            output_root=output_root,
            hermes_workshop_root=hermes_workshop_root,
        )
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
        try:
            records = run_host_authority_pipeline(
                host_augmented_document,
                output_root=output_root,
                source_label=source_label,
            )
        except Exception as exc:  # noqa: BLE001 - preserve validated draft origin on host failures.
            failure_bundle = {
                **base_bundle,
                "hermes_origin": {
                    **base_bundle["hermes_origin"],
                    "draft_plan_id": draft_plan_id,
                    "draft_plan_hash": hermes_draft_record.get("draft_plan_hash"),
                    "draft_record_source": hermes_draft_record.get("draft_record_source"),
                    "draft_record_root": hermes_draft_record.get("draft_record_root"),
                    "draft_document_source": hermes_draft_record.get("draft_document_source"),
                    "draft_hash_source": hermes_draft_record.get("draft_hash_source"),
                    "draft_lookup_errors": hermes_draft_record.get("draft_lookup_errors"),
                    "draft_document": hermes_draft_document,
                },
                "host_augmentation": {
                    "allowed_added_aliases": ["destination_entry_mode", "destination_time_to_entry_seconds"],
                    "augmented_document": host_augmented_document,
                    "augmented_document_sha256": stable_json_sha256(host_augmented_document),
                    "source_label": source_label,
                },
                "host_pipeline_error": {
                    "error_type": type(exc).__name__,
                    "message": short_text(str(exc), 1000),
                },
            }
            write_failed_n1f_bundle(
                output_root=output_root,
                job_id=job_id,
                bundle=failure_bundle,
                reason=f"N1F host authority pipeline failed after Hermes validation: {type(exc).__name__}: {short_text(str(exc), 500)}",
                stage="host_authority_pipeline_failed",
            )
            return
        audit = entry_mode_audit(records["execution_record"])
        bundle = {
            **base_bundle,
            "status": "exported",
            "hermes_origin": {
                **base_bundle["hermes_origin"],
                "draft_plan_id": draft_plan_id,
                "draft_plan_hash": hermes_draft_record.get("draft_plan_hash"),
                "draft_record_source": hermes_draft_record.get("draft_record_source"),
                "draft_record_root": hermes_draft_record.get("draft_record_root"),
                "draft_document_source": hermes_draft_record.get("draft_document_source"),
                "draft_hash_source": hermes_draft_record.get("draft_hash_source"),
                "draft_lookup_errors": hermes_draft_record.get("draft_lookup_errors"),
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
        if is_attested_hero_question(query):
            return attested_hero_interpretation(query)
        return hermes_interpret_request(query, model_query=product_model_query(query), output_root=output_root)

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
                    "Select the approved block-shift recipe, the experimental corridor preset, or the high-bypass pass preset.",
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
        source_id = str(value)
        public[str(key)] = (
            source_id
            if source_id.startswith("canonical_source:")
            else f"canonical_source:{sha256(source_id.encode('utf-8')).hexdigest()[:16]}"
        )
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
        "runtime_version": "workbench_beta1c1_required_evidence_cache_v4",
        "execution_contract": "required_evidence_complete_v2_with_source_summaries",
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
    manifest_raw_paths = manifest.get("required_raw_paths") if isinstance(manifest, dict) else None
    required_raw = (
        [str(path) for path in manifest_raw_paths]
        if isinstance(manifest_raw_paths, list)
        else [
            "J03WOY/tracking.xml",
            "J03WPY/tracking.xml",
            "J03WQQ/tracking.xml",
            "J03WR9/tracking.xml",
        ]
    )
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
    for recipe_id in (
        "ball_side_block_shift_v1",
        "possession_corridor_availability_v1",
        "high_bypass_completed_pass_v1",
        "line_break_support_response_v1",
    ):
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

    def send_demo_token_required(self) -> None:
        self.send_json(
            error_response(
                "DEMO_TOKEN_REQUIRED",
                public_error_message("DEMO_TOKEN_REQUIRED"),
                details={
                    "public_mode": True,
                    "token_source": "demo_token body field, X-Demo-Access-Token header, Authorization bearer, or demo cookie",
                    "configured": bool(DEMO_ACCESS_TOKEN),
                },
            ),
            HTTPStatus.UNAUTHORIZED,
        )

    def send_asks_disabled(self, details: dict[str, Any]) -> None:
        self.send_json(
            error_response(
                "ASKS_DISABLED",
                public_error_message("ASKS_DISABLED"),
                details=details,
            ),
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

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

    def read_request_payload(self) -> dict[str, Any]:
        try:
            return require_request_payload(self.read_body())
        except (json.JSONDecodeError, UnicodeDecodeError, RequestSchemaError) as exc:
            if isinstance(exc, RequestSchemaError):
                raise
            raise request_schema_error(exc, expected="valid JSON object request body") from exc

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

    def public_film_room_ask_allowed(self, parsed: Any, payload: dict[str, Any]) -> bool:
        if not DEMO_ACCESS_TOKEN:
            return False
        if str(payload.get("demo_token") or "") == DEMO_ACCESS_TOKEN:
            return True
        return self.demo_access_allowed(parsed)

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
        if not TQE_PUBLIC_MODE and not self.demo_access_allowed(parsed):
            self.send_demo_auth_required()
            return
        if parsed.path == "/api/health":
            self.send_json(ok({"service": "workbench_alpha_host", "mcp_adapter": False}))
            return
        if parsed.path == "/api/bootstrap":
            self.send_json(self.bootstrap())
            return
        if parsed.path == "/api/film-room/bootstrap":
            self.send_json(film_room_bootstrap_response(output_root=self.server.output_root))
            return
        if parsed.path == "/api/film-room/replay-window":
            query = parse_qs(parsed.query)
            self.send_json(
                film_room_replay_window_response(
                    {"replay_window_id": (query.get("replay_window_id") or [""])[0]},
                    output_root=self.server.output_root,
                )
            )
            return
        if parsed.path == "/api/film-room/replay-frame":
            query = parse_qs(parsed.query)
            self.send_json(
                film_room_replay_frame_response(
                    {
                        "replay_window_id": (query.get("replay_window_id") or [""])[0],
                        "frame_id": (query.get("frame_id") or ["0"])[0],
                    },
                    output_root=self.server.output_root,
                )
            )
            return
        if parsed.path == "/api/matches":
            self.send_json(validate_public_response("MatchLibraryResponse", match_library()))
            return
        if parsed.path == "/api/coach/catalog":
            query = parse_qs(parsed.query)
            kind = (query.get("kind") or [""])[0]
            response = coach_catalog_response(kind)
            if response.get("ok") is False:
                self.send_json(response, HTTPStatus.NOT_FOUND)
            else:
                self.send_json(validate_public_response("CoachInterpretResponse", response))
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
        if not TQE_PUBLIC_MODE and not self.demo_access_allowed(parsed):
            self.send_demo_auth_required()
            return
        try:
            payload = self.read_request_payload()
        except RequestSchemaError as exc:
            self.send_json(
                error_response(
                    "REQUEST_SCHEMA_INVALID",
                    public_error_message("REQUEST_SCHEMA_INVALID"),
                    details=exc.details,
                ),
                HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            if parsed.path == "/api/coach/interpret":
                self.send_json(
                    validate_public_response(
                        "CoachInterpretResponse",
                        coach_interpret_request(payload, output_root=self.server.output_root),
                    )
                )
            elif parsed.path == "/api/interpret":
                self.send_json(
                    validate_public_response(
                        "InterpretResponse",
                        interpret_request(payload, output_root=self.server.output_root),
                    )
                )
            elif parsed.path == "/api/film-room/ask":
                if TQE_PUBLIC_MODE:
                    if not self.public_film_room_ask_allowed(parsed, payload):
                        self.send_demo_token_required()
                        return
                    disabled_reason = film_room_ask_disabled_reason()
                    if disabled_reason:
                        self.send_asks_disabled(disabled_reason)
                        return
                validate_film_room_ask_payload(payload)
                if TQE_PUBLIC_MODE:
                    response, status = public_film_room_ask_with_timeout(payload, output_root=self.server.output_root)
                    self.send_json(response, status)
                else:
                    self.send_json(film_room_ask_request(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/film-room/replay-window":
                validate_film_room_replay_window_payload(payload)
                self.send_json(film_room_replay_window_response(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/film-room/replay-frame":
                validate_film_room_replay_frame_payload(payload)
                self.send_json(film_room_replay_frame_response(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/execution-cache-status":
                validate_request(
                    lambda: ExecuteQueryPlanRequest.model_validate(payload),
                    expected='JSON object with "bound_plan_id" and "execution_authorization_id"',
                )
                self.send_json(execution_cache_status(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/submit-validate":
                plan_document_payload = validate_request(
                    lambda: payload["plan_document"],
                    expected='JSON object with "plan_document"',
                )
                plan_document = host_owned_plan_document(plan_document_payload)
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
                bound_plan_id = validate_request(
                    lambda: str(payload["bound_plan_id"]),
                    expected='JSON object with "bound_plan_id"',
                )
                confirmation: HostConfirmationResponse = host_confirm_bound_plan(
                    bound_plan_id,
                    reviewer=str(payload.get("reviewer") or "workbench_alpha_host"),
                    output_root=self.server.output_root,
                )
                self.send_json(ok({"confirmation": confirmation.model_dump(mode="json")}))
            elif parsed.path == "/api/execute":
                request = validate_request(
                    lambda: ExecuteQueryPlanRequest.model_validate(payload),
                    expected='JSON object with "bound_plan_id" and "execution_authorization_id"',
                )
                executed = cached_execute_query_plan(
                    request,
                    output_root=self.server.output_root,
                )
                self.send_json(validate_public_response("ExecutionResponse", ok(executed)))
            elif parsed.path == "/api/inspect-result":
                validate_request(
                    lambda: InspectResultRequest.model_validate(
                        {"execution_id": payload.get("execution_id"), "result_id": payload.get("result_id")}
                    ),
                    expected='JSON object with "execution_id" and "result_id"',
                )
                self.send_json(result_with_replay(payload, output_root=self.server.output_root))
            elif parsed.path == "/api/inspect-timestamp":
                validate_request(
                    lambda: InspectNonMatchRequest.model_validate(
                        {"execution_id": payload.get("execution_id"), "target": payload.get("target")}
                    ),
                    expected='JSON object with "execution_id" and "target"',
                )
                self.send_json(timestamp_inspection(payload, output_root=self.server.output_root))
            else:
                self.send_json(error_response("NOT_FOUND", f"Unknown endpoint: {parsed.path}"), HTTPStatus.NOT_FOUND)
        except RequestSchemaError as exc:
            self.send_json(
                error_response(
                    "REQUEST_SCHEMA_INVALID",
                    public_error_message("REQUEST_SCHEMA_INVALID"),
                    details=exc.details,
                ),
                HTTPStatus.BAD_REQUEST,
            )
        except CapabilityGap as exc:
            code = stable_tool_error_code(exc)
            self.send_json(
                error_response(code, public_error_message(code)),
                HTTPStatus.FORBIDDEN,
            )
        except Exception as exc:
            if TQE_PUBLIC_MODE and type(exc).__name__ == "HermesNLAccessError":
                self.send_asks_disabled(
                    {
                        "reason": "hermes_access_error",
                        "message": str(exc),
                    }
                )
                return
            correlation_id = log_internal_error(exc, path=parsed.path)
            self.send_json(
                error_response(
                    "INTERNAL_ERROR",
                    public_error_message("INTERNAL_ERROR"),
                    details={"correlation_id": correlation_id},
                ),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def bootstrap(self) -> dict[str, Any]:
        approved_plan = load_plan_from_path(APPROVED_PLAN_PATH)
        corridor_plan = load_plan_from_path(CORRIDOR_PLAN_PATH)
        high_bypass_plan = load_plan_from_path(HIGH_BYPASS_PLAN_PATH)
        line_break_support_response_plan = load_plan_from_path(LINE_BREAK_SUPPORT_RESPONSE_PLAN_PATH)
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
                    {
                        "preset_id": "experimental_high_bypass",
                        "label": "High-bypass pass",
                        "recipe": recipe_card(high_bypass_plan, "EXPERIMENTAL"),
                        "plan_hash": stable_hash(high_bypass_plan),
                    },
                    {
                        "preset_id": "experimental_line_break_support_response",
                        "label": "Line-break support response",
                        "recipe": recipe_card(line_break_support_response_plan, "EXPERIMENTAL"),
                        "plan_hash": stable_hash(line_break_support_response_plan),
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
    server = WorkbenchServer(
        (args.host, args.port),
        WorkbenchHandler,
        static_root=args.static_root,
        output_root=args.output_root,
    )
    if WORKBENCH_PREWARM_EXECUTION_CACHE:
        threading.Thread(
            target=prewarm_execution_cache,
            kwargs={
                "output_root": args.output_root,
                "recipe_ids": WORKBENCH_PREWARM_RECIPE_IDS,
                "result_limit": WORKBENCH_PREWARM_RESULT_LIMIT,
            },
            name="execution-cache-prewarm",
            daemon=True,
        ).start()
    initialize_film_room_prewarm(
        output_root=args.output_root,
        execution_enabled=WORKBENCH_PREWARM_FILM_ROOM,
    )
    print(f"Workbench Alpha host service: http://{args.host}:{args.port}")
    print(f"Static root: {args.static_root}")
    print(f"Output root: {args.output_root}")
    server.serve_forever()


if __name__ == "__main__":
    main()
