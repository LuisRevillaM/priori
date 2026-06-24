"""M1.2 bounded workshop tools.

This module is intentionally deterministic and local. Hermes can later become a
client of this surface, but S0/S1 keep every operation usable without an agent.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tqe.runtime.binder import (
    HOST_RUNTIME_PARAMETER_DEFAULTS,
    BindError,
    bind_document,
    bind_document_from_path,
)
from tqe.runtime.catalog import default_catalog
from tqe.runtime.executor import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_RAW_ROOT,
    FRAME_RATE_HZ,
    GENERIC_EXECUTION_PROFILE,
    LEGACY_M1_PARITY_PROFILE,
    TacticalQueryExecutor,
    execute_legacy_m1_plan_from_path,
    execute_plan_from_path,
    execution_result_rows,
)
from tqe.runtime.ir import (
    BoundCatalogNode,
    BoundPredicateNode,
    ClassificationMode,
    ExecutionMode,
    ExecutionStatus,
    EvaluationTarget,
    NodeKind,
    PayloadType,
    PlanStatus,
    QueryExecution,
    TacticalQueryDocument,
    Unit,
    UnknownEvidencePolicy,
    model_payload,
    stable_hash,
)

HERMES_S2_TOOL_NAMES = [
    "list_capabilities",
    "search_recipes",
    "describe_capability",
    "submit_query_plan",
    "validate_query_plan",
    "execute_query_plan",
    "inspect_result",
    "inspect_non_match",
    "retrieve_replay_window",
]
HERMES_S2I_MCP_TOOL_NAMES = [
    "list_capabilities",
    "search_recipes",
    "describe_capability",
    "submit_query_plan",
    "validate_query_plan",
    "inspect_result",
    "inspect_non_match",
    "retrieve_replay_window",
]
MANUAL_ONLY_TOOL_NAMES = [
    "compare_query_versions",
    "record_feedback",
    "save_experimental_recipe",
]
APPROVED_TOOL_NAMES = HERMES_S2_TOOL_NAMES + MANUAL_ONLY_TOOL_NAMES
FORBIDDEN_SURFACES = [
    "arbitrary_python",
    "sql",
    "filesystem_editing",
    "primitive_mutation",
    "raw_match_dump",
    "result_row_mutation",
    "threshold_auto_tuning",
]
SAFE_ANCHOR_RELATIVE_OPERATORS = {"exists", "count_at_least"}
SAFE_ANCHOR_RELATIVE_OUTPUT = "anchor_evaluations"
DEFAULT_WORKSHOP_ROOT = Path(os.environ.get("TQE_RUNTIME_ROOT", "artifacts/m1.2/workshop"))
CAPABILITY_CONTEXT_PATH = Path("generated/capability-context.json")
TRUSTED_M1_RECIPE_ID = "ball_side_block_shift_v1"
TRUSTED_M1_RECIPE_VERSION = "1.0.0"
RECIPE_PLAN_PATHS = [
    Path("config/query-plans/ball_side_block_shift.ir.v1.json"),
    Path("config/query-plans/possession_corridor_availability.experimental.v1.json"),
    Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json"),
    Path("config/query-plans/high_bypass_completed_pass.experimental.v1.json"),
    Path("config/query-plans/line_break_support_response.experimental.v1.json"),
]
NON_AUTHORABLE_CATALOG_REFS = {
    "outcome_classification",
    "relation_destination_entry_classification",
    "shift_persistence",
    "wide_channel_dwell",
}
DESTINATION_ENTRY_AGENT_PATH = {
    "path_id": "possession_corridor_destination_entry_v1",
    "purpose": (
        "Agent-authorable generic composition for possession-start progressive "
        "corridors followed by ball entry into the relation destination region."
    ),
    "node_sequence": [
        "possession_segment.anchors",
        "geometric_progressive_corridor_from_anchor_set.episodes",
        "relation_destination_entry.entry_status",
        "eq PASS predicate",
        "classification/result evidence",
    ],
    "required_catalog_refs": [
        "possession_segment",
        "geometric_progressive_corridor_from_anchor_set",
        "relation_destination_entry",
    ],
    "classification_predicate": {
        "input": {"source_node_id": "destination_entry", "output_name": "entry_status"},
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
    },
    "recommended_evidence": [
        "destination_entry_status",
        "destination_entry_mode",
        "destination_time_to_entry_seconds",
    ],
    "forbidden_catalog_refs": ["relation_destination_entry_classification"],
    "claims_boundary": (
        "Measures geometric ball entry into a relation destination region only; "
        "no pass probability, optimality, intent, causation, or missed-opportunity claim."
    ),
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeedbackLabel(StrEnum):
    MATCHES_INTENT = "MATCHES_INTENT"
    NEAR_MATCH = "NEAR_MATCH"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    KNOWN_MISS = "KNOWN_MISS"
    UNUSABLE_DATA = "UNUSABLE_DATA"


class CallerProfile(StrEnum):
    HERMES_S2 = "HERMES_S2"
    HERMES_S2I_MCP = "HERMES_S2I_MCP"
    HOST_MANUAL = "HOST_MANUAL"


HANDLE_PATTERNS = {
    "draft-plans": re.compile(r"^draft_[0-9a-f]{16}$"),
    "bound-plans": re.compile(r"^bound_[0-9a-f]{16}$"),
    "executions": re.compile(r"^exec_[0-9a-f]{16}$"),
    "replay-windows": re.compile(r"^replay_[0-9a-f]{16}$"),
    "recipes": re.compile(r"^recipe_[0-9a-f]{16}$"),
    "authorizations": re.compile(r"^auth_[0-9a-f]{16}$"),
}


class HostConfirmationResponse(StrictModel):
    ok: bool
    bound_plan_id: str
    execution_authorization_id: str


class ResolvedEvaluationTarget(StrictModel):
    original_target: EvaluationTarget
    match_id: str
    period: str
    canonical_frame_id: int
    resolved_match_time_ms: int
    absolute_frame_time_ms: int
    resolution_distance_frames: int
    resolution_distance_ms: int

    def as_executor_target(self) -> EvaluationTarget:
        return EvaluationTarget(
            target_id=self.original_target.target_id,
            match_id=self.match_id,
            period=self.period,  # type: ignore[arg-type]
            approximate_time_ms=self.absolute_frame_time_ms,
            search_radius_ms=self.original_target.search_radius_ms,
        )


class ToolSpec(StrictModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    unavailable_surfaces: list[str]
    exposure: Literal["hermes_s2", "manual_only"]


class CapabilityContext(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    milestone: Literal["M1.2"] = "M1.2"
    generated_at: str
    tools: list[ToolSpec]
    primitives: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    operators: list[dict[str, Any]]
    authoring_contracts: dict[str, Any]
    recipe_states: list[str]
    evidence_fields: dict[str, list[str]]
    safe_operator_source_rules: dict[str, Any]
    default_complexity_limits: dict[str, Any]
    host_owned_complexity_ceilings: dict[str, Any]
    limitations: list[str]
    forbidden_surfaces: list[str]


class ToolErrorResponse(StrictModel):
    ok: Literal[False] = False
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolDispatchRequest(StrictModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolDispatchResponse(StrictModel):
    ok: bool
    tool_name: str
    response: dict[str, Any]


class ListCapabilitiesRequest(StrictModel):
    pass


class DescribeCapabilityRequest(StrictModel):
    capability_name: str = Field(min_length=1)


class DescribeCapabilityResponse(StrictModel):
    ok: bool
    capability: dict[str, Any]


class SearchRecipesRequest(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    states: list[Literal["APPROVED", "USER_SAVED", "EXPERIMENTAL", "DEPRECATED"]] = Field(
        default_factory=lambda: ["APPROVED", "EXPERIMENTAL"],
        min_length=1,
    )
    limit: int = Field(default=5, ge=1, le=20)


class RecipeSearchResult(StrictModel):
    recipe_id: str
    recipe_version: str
    state: Literal["APPROVED", "USER_SAVED", "EXPERIMENTAL", "DEPRECATED"]
    display_name: str
    description: str
    output_classifications: list[str]
    allowed_claims: list[str]
    disallowed_claims: list[str]
    limitations: list[str]
    parameters: list[dict[str, Any]]
    score: int
    matched_fields: list[str]


class SearchRecipesResponse(StrictModel):
    ok: bool
    query: str
    recipes: list[RecipeSearchResult]


class SubmitQueryPlanRequest(StrictModel):
    plan_document: TacticalQueryDocument
    source_label: str = Field(default="manual", min_length=1, max_length=80)


class SubmitQueryPlanResponse(StrictModel):
    ok: bool
    draft_plan_id: str
    draft_plan_hash: str
    recipe_id: str
    recipe_version: str
    plan_status: str


class ValidateQueryPlanRequest(StrictModel):
    draft_plan_id: str


class ValidateQueryPlanResponse(StrictModel):
    ok: bool
    draft_plan_id: str
    bound_plan_id: str | None = None
    plan_id: str | None = None
    recipe_id: str | None = None
    plan_status: str | None = None
    bound_plan_hash: str | None = None
    execution_profile: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteQueryPlanRequest(StrictModel):
    bound_plan_id: str = Field(pattern=r"^bound_[0-9a-f]{16}$")
    execution_authorization_id: str = Field(pattern=r"^auth_[0-9a-f]{16}$")
    result_limit: int = Field(default=25, ge=1, le=100)


class ExecuteQueryPlanResponse(StrictModel):
    ok: bool
    execution_id: str
    execution_status: str
    execution_complete: bool
    requested_evidence_failure_count: int
    requested_evidence_failures: list[dict[str, Any]] = Field(default_factory=list)
    bound_plan_id: str
    plan_id: str
    plan_status: str
    compatibility_profile: str
    draft_plan_hash: str
    total_result_count: int
    returned_result_count: int
    results: list[dict[str, Any]]
    trace_count: int
    bound_plan_hash: str


class InspectResultRequest(StrictModel):
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{16}$")
    result_id: str


class InspectResultResponse(StrictModel):
    ok: bool
    execution_id: str
    result: dict[str, Any]
    predicate_traces: list[dict[str, Any]]
    requested_evidence: dict[str, Any]


class InspectNonMatchRequest(StrictModel):
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{16}$")
    target: EvaluationTarget


class InspectNonMatchResponse(StrictModel):
    ok: bool
    execution_id: str
    inspection: dict[str, Any]


class ReplayWindowRequest(StrictModel):
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{16}$")
    result_id: str | None = None
    target: EvaluationTarget | None = None
    padding_seconds: float = Field(default=2.0, ge=0.2, le=8.0)

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ReplayWindowRequest":
        if (self.result_id is None) == (self.target is None):
            raise ValueError("provide exactly one of result_id or target")
        return self


class ReplayWindowResponse(StrictModel):
    ok: bool
    execution_id: str
    replay_window_id: str
    match_id: str
    period: str
    start_frame_id: int
    end_frame_id: int
    anchor_frame_id: int
    frame_count: int
    entity_observation_count: int
    source_kind: Literal["result", "target"]


class RecordFeedbackRequest(StrictModel):
    execution_id: str = Field(pattern=r"^exec_[0-9a-f]{16}$")
    label: FeedbackLabel
    reviewer: str
    reason_code: str
    result_id: str | None = None
    target: EvaluationTarget | None = None
    note: str | None = None

    @model_validator(mode="after")
    def exactly_one_feedback_subject(self) -> "RecordFeedbackRequest":
        if (self.result_id is None) == (self.target is None):
            raise ValueError("provide exactly one of result_id or target")
        return self


class RecordFeedbackResponse(StrictModel):
    ok: bool
    execution_id: str
    feedback_id: str
    path: str


class SaveExperimentalRecipeRequest(StrictModel):
    draft_plan_id: str = Field(pattern=r"^draft_[0-9a-f]{16}$")
    creator: str
    parent_version: str | None = None
    note: str | None = None


class SaveExperimentalRecipeResponse(StrictModel):
    ok: bool
    recipe_version_id: str
    path: str
    query_hash: str


class CompareQueryVersionsRequest(StrictModel):
    before_recipe_version_id: str = Field(pattern=r"^recipe_[0-9a-f]{16}$")
    after_recipe_version_id: str = Field(pattern=r"^recipe_[0-9a-f]{16}$")


class CompareQueryVersionsResponse(StrictModel):
    ok: bool
    before_hash: str
    after_hash: str
    same: bool
    semantic_changes: list[dict[str, Any]]


class CapabilityGap(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def handle_path(kind: str, handle_id: str, *, output_root: Path = DEFAULT_WORKSHOP_ROOT) -> Path:
    pattern = HANDLE_PATTERNS.get(kind)
    if pattern is None:
        raise CapabilityGap(f"Unsupported handle kind: {kind}")
    if pattern.fullmatch(handle_id) is None:
        raise CapabilityGap(f"Invalid {kind} handle: {handle_id}")
    base = (output_root / "handles" / kind).resolve()
    path = (base / f"{handle_id}.json").resolve()
    if base not in path.parents:
        raise CapabilityGap(f"Handle path escapes storage root: {handle_id}")
    return path


def write_handle(
    kind: str,
    handle_id: str,
    payload: dict[str, Any],
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> None:
    path = handle_path(kind, handle_id, output_root=output_root)
    if path.exists():
        existing = read_json(path)
        if canonical_identity(existing) == canonical_identity(payload):
            return
        if (
            kind == "executions"
            and existing.get("execution_id") == payload.get("execution_id") == handle_id
            and existing.get("bound_plan_id") == payload.get("bound_plan_id")
            and existing.get("bound_plan_hash") == payload.get("bound_plan_hash")
        ):
            write_json(path, payload)
            return
        raise CapabilityGap(f"{kind} handle collision: {handle_id}")
    write_json(path, payload)


def canonical_identity(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: canonical_identity(value)
            for key, value in payload.items()
            if key not in {"created_at", "saved_at", "recorded_at", "generated_at", "timing_ms", "source_label"}
        }
    if isinstance(payload, list):
        return [canonical_identity(item) for item in payload]
    return payload


def read_handle(
    kind: str,
    handle_id: str,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> dict[str, Any]:
    path = handle_path(kind, handle_id, output_root=output_root)
    if not path.exists():
        raise CapabilityGap(f"Unknown {kind} handle: {handle_id}")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise CapabilityGap(f"Invalid {kind} handle payload: {handle_id}")
    return payload


def submit_query_plan(
    request: SubmitQueryPlanRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> SubmitQueryPlanResponse:
    if is_model_caller(caller_profile) and request.plan_document.draft_plan.status != PlanStatus.EXPERIMENTAL:
        raise CapabilityGap("Hermes-authored query documents must be EXPERIMENTAL")
    document_payload = model_payload(request.plan_document)
    draft_hash = stable_hash(document_payload)
    draft_plan_id = f"draft_{draft_hash[:16]}"
    write_handle(
        "draft-plans",
        draft_plan_id,
        {
            "schema_version": "1.0",
            "created_at": utc_now_iso(),
            "source_label": request.source_label,
            "draft_plan_id": draft_plan_id,
            "draft_plan_hash": draft_hash,
            "document": document_payload,
        },
        output_root=output_root,
    )
    return SubmitQueryPlanResponse(
        ok=True,
        draft_plan_id=draft_plan_id,
        draft_plan_hash=draft_hash,
        recipe_id=request.plan_document.recipe.recipe_id,
        recipe_version=request.plan_document.recipe.recipe_version,
        plan_status=request.plan_document.draft_plan.status.value,
    )


def is_model_caller(caller_profile: CallerProfile) -> bool:
    return caller_profile in {CallerProfile.HERMES_S2, CallerProfile.HERMES_S2I_MCP}


def visible_tool_names(caller_profile: CallerProfile) -> list[str]:
    if caller_profile == CallerProfile.HERMES_S2:
        return HERMES_S2_TOOL_NAMES
    if caller_profile == CallerProfile.HERMES_S2I_MCP:
        return HERMES_S2I_MCP_TOOL_NAMES
    return APPROVED_TOOL_NAMES


def _typed_value_contract(payload_type: str, unit: str = "none", value: Any = "<value>") -> dict[str, Any]:
    return {"payload_type": payload_type, "unit": unit, "value": value}


def _parameter_ref_contract(parameter_name: str = "<declared_recipe_parameter_name>") -> dict[str, str]:
    return {"kind": "parameter", "name": parameter_name}


def _signal_ref_contract(
    source_node_id: str = "<source_node_id>",
    output_name: str = "<registered_output_name>",
) -> dict[str, str]:
    return {"source_node_id": source_node_id, "output_name": output_name}


def _catalog_entry_contract(entry: Any) -> dict[str, Any]:
    """Return the generated authoring contract for one registered catalog entry."""

    return {
        "kind": entry.kind.value if hasattr(entry.kind, "value") else entry.kind,
        "registered_catalog_ref": entry.name,
        "version": entry.version,
        "node_schema": {
            "kind": entry.kind.value if hasattr(entry.kind, "value") else entry.kind,
            "node_id": "<agent_chosen_lower_snake_id>",
            "catalog_ref": entry.name,
            "version": entry.version,
            "inputs": {
                input_ref.name: _signal_ref_contract()
                for input_ref in entry.inputs
            },
            "parameters": {
                parameter.name: {
                    "accepted_forms": [
                        _typed_value_contract(
                            parameter.payload_type.value
                            if hasattr(parameter.payload_type, "value")
                            else str(parameter.payload_type),
                            parameter.unit.value if hasattr(parameter.unit, "value") else str(parameter.unit),
                        ),
                        _parameter_ref_contract(),
                    ],
                    "definition": parameter.model_dump(mode="json", exclude_none=True),
                }
                for parameter in entry.parameters
            },
        },
        "required_inputs": [item.model_dump(mode="json") for item in entry.inputs],
        "outputs": [item.model_dump(mode="json") for item in entry.outputs],
        "valid_output_names": [output.name for output in entry.outputs],
        "valid_parameter_names": [parameter.name for parameter in entry.parameters],
        "limitations": list(entry.limitations),
    }


def _operator_contract(operator: Any) -> dict[str, Any]:
    payload = operator.model_dump(mode="json", exclude_none=True)
    payload["predicate_node_schema"] = {
        "kind": "predicate",
        "node_id": "<agent_chosen_lower_snake_id>",
        "input": _signal_ref_contract(),
        "operator": {"name": operator.name, "version": operator.version},
    }
    if operator.compare_required:
        payload["predicate_node_schema"]["compare"] = {
            "accepted_payload_types": [
                item.value if hasattr(item, "value") else str(item)
                for item in operator.compare_payload_types
            ],
            "schema": _typed_value_contract("<matching_payload_type>", "<matching_unit_or_none>"),
        }
    if operator.duration_required:
        payload["predicate_node_schema"]["duration"] = _typed_value_contract("number", "second")
    if operator.name in SAFE_ANCHOR_RELATIVE_OPERATORS:
        payload["agent_visible_source_rule"] = {
            "allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT,
            "rejected_sources": [
                "raw boolean EpisodeSet",
                "raw RelationEpisodeSet",
                "generic collection counts not indexed by anchor_id",
            ],
        }
    return payload


def _catalog_entry_by_name(catalog: Any, name: str) -> Any:
    for collection in (catalog.primitives, catalog.relations):
        for entry in collection:
            if entry.name == name:
                return entry
    raise KeyError(name)


def _operator_by_name(catalog: Any, name: str) -> Any:
    for operator in catalog.operators:
        if operator.name == name:
            return operator
    raise KeyError(name)


def typed_query_plan_authoring_contract(catalog: Any) -> dict[str, Any]:
    """Generated schema guidance for model-authored TacticalQueryDocument payloads."""

    del catalog
    return {
        "name": "typed_query_plan",
        "source": "tqe.runtime.ir",
        "plan_document_shape": ["schema_version", "recipe", "default_invocation", "draft_plan"],
        "recipe_contract": {
            "required_fields": [
                "schema_version",
                "recipe_id",
                "recipe_version",
                "display_name",
                "description",
                "parameters",
                "default_unknown_evidence_policy",
                "output_classifications",
            ],
            "parameter_rule": (
                "default_invocation.parameters may only contain names declared in recipe.parameters "
                "or host-owned runtime globals. Catalog node parameters must use exact catalog "
                "parameter names and may be inline TypedValue objects or ParameterRef objects whose "
                "name appears in recipe.parameters."
            ),
        },
        "default_invocation_contract": {
            "execution_mode_values": [item.value for item in ExecutionMode],
            "scope_fields": ["match_ids", "periods", "perspective_team_role"],
            "parameters_rule": "Do not put undeclared names here; use recipe.parameters + ParameterRef or inline node TypedValue.",
        },
        "draft_plan_contract": {
            "status_values": [item.value for item in PlanStatus],
            "hermes_status": PlanStatus.EXPERIMENTAL.value,
            "unknown_evidence_policy_values": [item.value for item in UnknownEvidencePolicy],
            "classification_mode_values": [item.value for item in ClassificationMode],
            "anchor_source_schema": _signal_ref_contract(),
            "classification_rule_schema": {
                "label": "UPPER_SNAKE_CASE",
                "predicate_ids": ["<predicate_node_id>"],
                "description": "<human-readable result label explanation>",
            },
            "requested_evidence_schema": {
                "source": _signal_ref_contract(),
                "field": "<registered_evidence_field_on_source_output>",
                "alias": "<optional_lower_snake_alias>",
                "required": True,
            },
        },
        "draft_catalog_node_schema": {
            "kind": ["primitive", "relation"],
            "node_id": "lower_snake_case",
            "catalog_ref": "<exact registered catalog_ref>",
            "version": "<exact registered version>",
            "inputs": {"<registered_input_name>": _signal_ref_contract()},
            "parameters": {
                "<registered_parameter_name>": [
                    _typed_value_contract("<payload_type>", "<unit>"),
                    _parameter_ref_contract(),
                ]
            },
        },
        "draft_predicate_node_schema": {
            "kind": "predicate",
            "node_id": "lower_snake_case",
            "input": _signal_ref_contract(),
            "operator": {"name": "<exact registered_operator_name>", "version": "<exact registered_version>"},
            "compare": _typed_value_contract("<required_when_operator_requires_compare>", "<unit>"),
            "duration": _typed_value_contract("number", "second"),
        },
        "typed_value_schema": {
            "payload_type_values": [item.value for item in PayloadType],
            "unit_values": [item.value for item in Unit],
            "shape": _typed_value_contract("<payload_type>", "<unit>"),
        },
        "parameter_ref_schema": _parameter_ref_contract(),
        "signal_ref_schema": _signal_ref_contract(),
        "host_runtime_globals": [
            parameter.model_dump(mode="json", exclude_none=True)
            for parameter in HOST_RUNTIME_PARAMETER_DEFAULTS.values()
        ],
    }


def plan_node_authoring_contract(catalog: Any) -> dict[str, Any]:
    authorable_refs = [
        entry.name
        for collection in (catalog.primitives, catalog.relations)
        for entry in collection
        if entry.name not in NON_AUTHORABLE_CATALOG_REFS
    ]
    return {
        "name": "plan_nodes",
        "authorable_catalog_refs": sorted(authorable_refs),
        "trusted_recipe_only_catalog_refs_omitted": sorted(NON_AUTHORABLE_CATALOG_REFS),
        "operators": {
            operator.name: _operator_contract(operator)
            for operator in catalog.operators
        },
        "catalog_nodes": {
            entry.name: _catalog_entry_contract(entry)
            for collection in (catalog.primitives, catalog.relations)
            for entry in collection
            if entry.name not in NON_AUTHORABLE_CATALOG_REFS
        },
    }


def possession_corridor_destination_entry_authoring_contract(catalog: Any) -> dict[str, Any]:
    possession = _catalog_entry_by_name(catalog, "possession_segment")
    corridor = _catalog_entry_by_name(catalog, "geometric_progressive_corridor_from_anchor_set")
    destination = _catalog_entry_by_name(catalog, "relation_destination_entry")
    exists_operator = _operator_by_name(catalog, "exists")
    eq_operator = _operator_by_name(catalog, "eq")
    return {
        **DESTINATION_ENTRY_AGENT_PATH,
        "required_catalog_refs": [possession.name, corridor.name, destination.name],
        "required_operators": [exists_operator.name, eq_operator.name],
        "registered_node_contracts": {
            possession.name: _catalog_entry_contract(possession),
            corridor.name: _catalog_entry_contract(corridor),
            destination.name: _catalog_entry_contract(destination),
        },
        "registered_operator_contracts": {
            exists_operator.name: _operator_contract(exists_operator),
            eq_operator.name: _operator_contract(eq_operator),
        },
        "required_wiring": [
            {
                "from": {"source_node_id": "possession", "output_name": "anchors"},
                "to": {"target_node_id": "progressive_corridor", "input_name": "anchors"},
            },
            {
                "from": {"source_node_id": "progressive_corridor", "output_name": "anchor_evaluations"},
                "to": {"target_node_id": "has_progressive_corridor", "input": True, "operator": "exists"},
            },
            {
                "from": {"source_node_id": "progressive_corridor", "output_name": "episodes"},
                "to": {"target_node_id": "destination_entry", "input_name": "relation_episodes"},
            },
            {
                "from": {"source_node_id": "destination_entry", "output_name": "entry_status"},
                "to": {
                    "target_node_id": "destination_region_entered",
                    "input": True,
                    "operator": "eq",
                    "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
                },
            },
        ],
        "anchor_source": {"source_node_id": "possession", "output_name": "anchors"},
        "classification_rule_contract": {
            "predicate_ids_must_include": ["has_progressive_corridor", "destination_region_entered"],
            "label_contract": "UPPER_SNAKE_CASE",
        },
        "valid_requested_evidence_sources": {
            "progressive_corridor.episodes": _catalog_entry_contract(corridor)["outputs"][0],
            "destination_entry.entry_status": _catalog_entry_contract(destination)["outputs"][0],
        },
        "required_safety_rules": [
            "Use geometric_progressive_corridor_from_anchor_set.episodes for relation_destination_entry.relation_episodes.",
            "Use geometric_progressive_corridor_from_anchor_set.anchor_evaluations for exists.",
            "Use relation_destination_entry.entry_status with eq PASS for destination-region entry.",
            "Do not invent operators or catalog refs.",
            "Do not use relation_destination_entry_classification in agent-authored plans.",
        ],
    }


def generated_authoring_contracts(catalog: Any) -> dict[str, Any]:
    typed_contract = typed_query_plan_authoring_contract(catalog)
    nodes_contract = plan_node_authoring_contract(catalog)
    destination_contract = possession_corridor_destination_entry_authoring_contract(catalog)
    return {
        "typed_query_plan": typed_contract,
        "query_plan_schema": typed_contract,
        "plan_nodes": nodes_contract,
        "possession_corridor_destination_entry": destination_contract,
        "possession_corridor_destination_entry_v1": destination_contract,
    }


def list_capabilities(caller_profile: CallerProfile = CallerProfile.HERMES_S2) -> CapabilityContext:
    catalog = default_catalog()
    evidence_fields: dict[str, list[str]] = {}
    primitives = []
    for entry in catalog.primitives:
        primitives.append(catalog_entry_summary(entry))
        evidence_fields[entry.name] = sorted(entry.evidence_fields)
    relations = []
    for entry in catalog.relations:
        relations.append(catalog_entry_summary(entry))
        evidence_fields[entry.name] = sorted(entry.evidence_fields)

    operators = []
    for operator in catalog.operators:
        operators.append(_operator_contract(operator))

    tool_names = visible_tool_names(caller_profile)
    authoring_contracts = generated_authoring_contracts(catalog)
    return CapabilityContext(
        generated_at="reproducible_from_source_hashes",
        tools=[tool_spec(name) for name in tool_names],
        primitives=primitives,
        relations=relations,
        operators=operators,
        authoring_contracts=authoring_contracts,
        recipe_states=["APPROVED", "USER_SAVED", "EXPERIMENTAL", "DEPRECATED"],
        evidence_fields=evidence_fields,
        safe_operator_source_rules={
            "exists": {"allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT},
            "count_at_least": {"allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT},
            "possession_corridor_destination_entry": authoring_contracts[
                "possession_corridor_destination_entry"
            ],
        },
        default_complexity_limits=catalog.default_complexity_limits.model_dump(mode="json"),
        host_owned_complexity_ceilings=catalog.default_complexity_limits.model_dump(mode="json"),
        limitations=[
            "Hermes receives this bounded context, not raw match dumps or primitive code.",
            "exists/count_at_least are agent-visible only on anchor_evaluations.",
            "For destination-region ball entry after possession-start corridors, Hermes must use relation_destination_entry.entry_status with eq PASS; relation_destination_entry_classification is trusted-recipe-only.",
            "legacy_m1_parity is allowed only for the frozen approved M1 recipe.",
            "Unsupported concepts must be returned as capability gaps.",
        ],
        forbidden_surfaces=FORBIDDEN_SURFACES,
    )


def write_capability_context(path: Path = CAPABILITY_CONTEXT_PATH) -> CapabilityContext:
    context = list_capabilities(CallerProfile.HERMES_S2)
    write_json(path, context.model_dump(mode="json"))
    return context


def describe_capability(
    capability_name: str,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> dict[str, Any]:
    context = list_capabilities(caller_profile)
    authoring_contract = context.authoring_contracts.get(capability_name)
    if authoring_contract is not None:
        return {"kind": "authoring_contract", **authoring_contract}
    for collection_name in ("tools", "primitives", "relations", "operators"):
        collection = getattr(context, collection_name)
        for item in collection:
            payload = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            if payload.get("name") == capability_name:
                return {"kind": collection_name[:-1], **payload}
    for path in RECIPE_PLAN_PATHS:
        document = read_json(path)
        recipe = document["recipe"]
        if recipe.get("recipe_id") == capability_name:
            return {
                "kind": "recipe",
                **recipe_summary_from_document(document),
                "authoring_contract": recipe_authoring_contract(document),
            }
    raise CapabilityGap(f"Unsupported capability: {capability_name}")


def describe_capability_tool(
    request: DescribeCapabilityRequest,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> DescribeCapabilityResponse:
    return DescribeCapabilityResponse(
        ok=True,
        capability=describe_capability(request.capability_name, caller_profile),
    )


def search_recipes(
    request: SearchRecipesRequest,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> SearchRecipesResponse:
    del caller_profile
    query_terms = normalized_search_terms(request.query)
    requested_states = set(request.states)
    results: list[RecipeSearchResult] = []
    for recipe in recipe_summaries():
        if recipe["state"] not in requested_states:
            continue
        score, matched_fields = score_recipe_match(recipe, query_terms)
        if score <= 0:
            continue
        results.append(
            RecipeSearchResult(
                recipe_id=recipe["recipe_id"],
                recipe_version=recipe["recipe_version"],
                state=recipe["state"],
                display_name=recipe["display_name"],
                description=recipe["description"],
                output_classifications=recipe["output_classifications"],
                allowed_claims=recipe["allowed_claims"],
                disallowed_claims=recipe["disallowed_claims"],
                limitations=recipe["limitations"],
                parameters=recipe["parameters"],
                score=score,
                matched_fields=matched_fields,
            )
        )
    results.sort(key=lambda item: (-item.score, item.recipe_id))
    return SearchRecipesResponse(ok=True, query=request.query, recipes=results[: request.limit])


def recipe_summaries() -> list[dict[str, Any]]:
    summaries = []
    for path in RECIPE_PLAN_PATHS:
        document = read_json(path)
        summaries.append(recipe_summary_from_document(document))
    return summaries


def recipe_summary_from_document(document: dict[str, Any]) -> dict[str, Any]:
    recipe = document["recipe"]
    state = "APPROVED" if recipe["recipe_id"] == TRUSTED_M1_RECIPE_ID else "EXPERIMENTAL"
    return {
        "recipe_id": recipe["recipe_id"],
        "recipe_version": recipe["recipe_version"],
        "state": state,
        "display_name": recipe["display_name"],
        "description": recipe["description"],
        "output_classifications": recipe.get("output_classifications", []),
        "allowed_claims": recipe.get("allowed_claims", []),
        "disallowed_claims": recipe.get("disallowed_claims", []),
        "limitations": recipe.get("limitations", []),
        "parameters": recipe.get("parameters", []),
    }


def recipe_authoring_contract(document: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded schema contract for authoring a recipe-shaped plan.

    This is intentionally declarative. It exposes names, refs, and safe wiring
    already present in the recipe document, but no runtime calculation logic,
    raw data, or execution authority.
    """

    draft_plan = document["draft_plan"]
    default_invocation = document["default_invocation"]
    non_authorable_node_ids = {
        str(node.get("node_id"))
        for node in draft_plan.get("nodes", [])
        if node.get("catalog_ref") in NON_AUTHORABLE_CATALOG_REFS
    }

    def references_non_authorable_node(node: dict[str, Any]) -> bool:
        ref = node.get("input")
        if isinstance(ref, dict) and str(ref.get("source_node_id")) in non_authorable_node_ids:
            return True
        for ref in (node.get("inputs") or {}).values():
            if isinstance(ref, dict) and str(ref.get("source_node_id")) in non_authorable_node_ids:
                return True
        return False

    def evidence_references_non_authorable_node(request: dict[str, Any]) -> bool:
        source = request.get("source") if isinstance(request, dict) else None
        return isinstance(source, dict) and str(source.get("source_node_id")) in non_authorable_node_ids

    return {
        "plan_document_shape": ["schema_version", "recipe", "default_invocation", "draft_plan"],
        "default_invocation_contract": {
            "match_ids": default_invocation.get("match_ids", []),
            "periods": default_invocation.get("periods", []),
            "perspective_team_role": default_invocation.get("perspective_team_role"),
            "execution_mode": "execute",
            "validation_contract": "validate_query_plan binds and checks the plan but never executes it.",
            "max_results_ceiling": default_invocation.get("max_results"),
        },
        "draft_plan_defaults": {
            "recipe_id": draft_plan.get("recipe_id"),
            "recipe_version": draft_plan.get("recipe_version"),
            "status": draft_plan.get("status"),
            "unknown_evidence_policy": draft_plan.get("unknown_evidence_policy"),
            "classification_mode": draft_plan.get("classification_mode"),
            "anchor_source": draft_plan.get("anchor_source"),
            "complexity_limits": draft_plan.get("complexity_limits"),
        },
        "authorable_nodes": [
            {
                "kind": node.get("kind"),
                "catalog_ref": node.get("catalog_ref"),
                "version": node.get("version"),
                "required_inputs": node.get("inputs", {}),
                "parameters": node.get("parameters", {}),
            }
            for node in draft_plan.get("nodes", [])
            if node.get("kind") in {"primitive", "relation"}
            and node.get("catalog_ref") not in NON_AUTHORABLE_CATALOG_REFS
            and not references_non_authorable_node(node)
        ],
        "trusted_recipe_only_catalog_refs_omitted": sorted(
            {
                str(node.get("catalog_ref"))
                for node in draft_plan.get("nodes", [])
                if node.get("catalog_ref") in NON_AUTHORABLE_CATALOG_REFS
            }
        ),
        "required_predicates": [
            {
                "input": node.get("input"),
                "operator": node.get("operator"),
                "compare": node.get("compare"),
                "duration": node.get("duration"),
            }
            for node in draft_plan.get("nodes", [])
            if node.get("kind") == "predicate"
            and not references_non_authorable_node(node)
        ],
        "classification_rules": draft_plan.get("classification_rules", []),
        "requested_evidence": [
            request
            for request in draft_plan.get("requested_evidence", [])
            if not evidence_references_non_authorable_node(request)
        ],
        "safe_generic_composition_hints": {
            "destination_entry_after_possession_corridor": DESTINATION_ENTRY_AGENT_PATH,
        },
        "constraints": [
            "The authored plan must keep status=experimental for Hermes.",
            "Keep default_invocation.execution_mode=execute; host confirmation still controls whether execution may happen.",
            "exists/count_at_least may only consume anchor_evaluations.",
            "Use relation_destination_entry.entry_status with eq PASS for agent-authored destination-region entry checks.",
            "Do not use trusted recipe wrappers such as relation_destination_entry_classification in agent-authored plans.",
            "Do not request raw match dumps, primitive mutation, confirmation, or execution.",
        ],
    }


def normalized_search_terms(query: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9_]+", " ", query.lower())
    return [term for term in normalized.split() if len(term) >= 3]


def score_recipe_match(recipe: dict[str, Any], query_terms: list[str]) -> tuple[int, list[str]]:
    field_texts = {
        "recipe_id": recipe["recipe_id"],
        "display_name": recipe["display_name"],
        "description": recipe["description"],
        "output_classifications": " ".join(recipe["output_classifications"]),
        "claims": " ".join(recipe["allowed_claims"] + recipe["disallowed_claims"]),
        "parameters": " ".join(
            f"{parameter.get('name', '')} {parameter.get('description', '')}"
            for parameter in recipe["parameters"]
        ),
    }
    score = 0
    matched_fields: list[str] = []
    for field, text in field_texts.items():
        normalized = re.sub(r"[^a-z0-9_]+", " ", text.lower())
        field_score = sum(1 for term in query_terms if term in normalized)
        if field_score:
            score += field_score
            matched_fields.append(field)
    return score, matched_fields


def validate_query_plan(
    request: ValidateQueryPlanRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> ValidateQueryPlanResponse:
    try:
        draft_record = read_handle("draft-plans", request.draft_plan_id, output_root=output_root)
        document = TacticalQueryDocument.model_validate(draft_record["document"])
        bound = bind_document(document)
        validate_safe_agent_plan(bound, caller_profile=caller_profile)
        profile = default_profile_for_bound_plan(bound)
        bound_plan_id = f"bound_{bound.bound_plan_hash[:16]}"
        bound_payload = {
                "schema_version": "1.0",
                "created_at": utc_now_iso(),
                "draft_plan_id": request.draft_plan_id,
                "draft_plan_hash": draft_record["draft_plan_hash"],
                "bound_plan_id": bound_plan_id,
                "bound_plan_hash": bound.bound_plan_hash,
                "execution_profile": profile,
                "document": draft_record["document"],
                "bound_plan": model_payload(bound),
                "confirmed": False,
            }
        bound_path = handle_path("bound-plans", bound_plan_id, output_root=output_root)
        if bound_path.exists():
            existing = read_handle("bound-plans", bound_plan_id, output_root=output_root)
            if existing.get("bound_plan_hash") != bound.bound_plan_hash:
                raise CapabilityGap(f"bound plan handle collision: {bound_plan_id}")
        else:
            write_handle("bound-plans", bound_plan_id, bound_payload, output_root=output_root)
        return ValidateQueryPlanResponse(
            ok=True,
            draft_plan_id=request.draft_plan_id,
            bound_plan_id=bound_plan_id,
            plan_id=bound.plan_id,
            recipe_id=bound.recipe_id,
            plan_status=bound.plan_status.value,
            bound_plan_hash=bound.bound_plan_hash,
            execution_profile=profile,
        )
    except BindError as exc:
        return ValidateQueryPlanResponse(
            ok=False,
            draft_plan_id=request.draft_plan_id,
            issues=[issue.model_dump(mode="json") for issue in exc.issues],
        )
    except Exception as exc:
        return ValidateQueryPlanResponse(
            ok=False,
            draft_plan_id=request.draft_plan_id,
            issues=[{"code": type(exc).__name__, "message": str(exc), "path": request.draft_plan_id}],
        )


def host_confirm_bound_plan(
    bound_plan_id: str,
    *,
    reviewer: str = "controller",
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> HostConfirmationResponse:
    bound_record = read_handle("bound-plans", bound_plan_id, output_root=output_root)
    auth_id = f"auth_{stable_hash({'bound_plan_id': bound_plan_id, 'reviewer': reviewer, 'bound_plan_hash': bound_record['bound_plan_hash']})[:16]}"
    write_handle(
        "authorizations",
        auth_id,
        {
            "schema_version": "1.0",
            "created_at": utc_now_iso(),
            "bound_plan_id": bound_plan_id,
            "bound_plan_hash": bound_record["bound_plan_hash"],
            "reviewer": reviewer,
            "confirmation_source": "host_manual",
        },
        output_root=output_root,
    )
    return HostConfirmationResponse(
        ok=True,
        bound_plan_id=bound_plan_id,
        execution_authorization_id=auth_id,
    )


def execute_query_plan(
    request: ExecuteQueryPlanRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> ExecuteQueryPlanResponse:
    bound_record = read_handle("bound-plans", request.bound_plan_id, output_root=output_root)
    auth_record = read_handle("authorizations", request.execution_authorization_id, output_root=output_root)
    if auth_record.get("bound_plan_id") != request.bound_plan_id:
        raise CapabilityGap("execution authorization does not match bound_plan_id")
    if auth_record.get("bound_plan_hash") != bound_record.get("bound_plan_hash"):
        raise CapabilityGap("execution authorization does not match bound_plan_hash")
    document = TacticalQueryDocument.model_validate(bound_record["document"])
    bound = bind_document(document)
    validate_safe_agent_plan(bound, caller_profile=CallerProfile.HOST_MANUAL)
    profile = str(bound_record["execution_profile"])
    execution = executor_for_profile(profile).execute(bound)
    rows = execution_result_rows(execution)
    returned = rows[: request.result_limit]
    execution_id = f"exec_{execution.execution_id}"
    execution_record = execution_record_payload(
        bound_record=bound_record,
        execution=execution,
        rows=rows,
        profile=profile,
        execution_id=execution_id,
    )
    write_handle("executions", execution_id, execution_record, output_root=output_root)
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    evidence_failures = execution.provenance.get("requested_evidence_failures")
    return ExecuteQueryPlanResponse(
        ok=True,
        execution_id=execution_id,
        execution_status=execution.status.value,
        execution_complete=execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
        requested_evidence_failure_count=evidence_failure_count,
        requested_evidence_failures=evidence_failures if isinstance(evidence_failures, list) else [],
        bound_plan_id=request.bound_plan_id,
        plan_id=bound.plan_id,
        plan_status=bound.plan_status.value,
        compatibility_profile=str(execution.provenance.get("compatibility_profile")),
        draft_plan_hash=str(bound_record["draft_plan_hash"]),
        total_result_count=len(rows),
        returned_result_count=len(returned),
        results=[rank_result(row, rank=index + 1) for index, row in enumerate(returned)],
        trace_count=len(execution.predicate_traces),
        bound_plan_hash=bound.bound_plan_hash,
    )


def inspect_result(
    request: InspectResultRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> InspectResultResponse:
    execution_record = read_handle("executions", request.execution_id, output_root=output_root)
    rows = execution_record["rows"]
    result = next((row for row in rows if str(row["result_id"]) == request.result_id), None)
    if result is None:
        raise CapabilityGap(f"Unknown result_id for plan execution: {request.result_id}")
    traces = [
        trace
        for trace in execution_record["predicate_traces"]
        if str(trace.get("source_evidence", {}).get("result_id")) == request.result_id
    ]
    requested_evidence = result.get("requested_evidence")
    return InspectResultResponse(
        ok=True,
        execution_id=request.execution_id,
        result=result,
        predicate_traces=traces,
        requested_evidence=requested_evidence if isinstance(requested_evidence, dict) else {},
    )


def inspect_non_match(
    request: InspectNonMatchRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> InspectNonMatchResponse:
    execution_record = read_handle("executions", request.execution_id, output_root=output_root)
    document = TacticalQueryDocument.model_validate(execution_record["document"])
    bound = bind_document(document)
    validate_safe_agent_plan(bound, caller_profile=CallerProfile.HOST_MANUAL)
    resolved = resolve_evaluation_target(request.target)
    inspection = executor_for_profile(str(execution_record["compatibility_profile"])).evaluate_target(
        bound,
        resolved.as_executor_target(),
    )
    inspection["resolved_target"] = resolved.model_dump(mode="json")
    return InspectNonMatchResponse(ok=True, execution_id=request.execution_id, inspection=inspection)


def retrieve_replay_window(
    request: ReplayWindowRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> ReplayWindowResponse:
    execution_record = read_handle("executions", request.execution_id, output_root=output_root)
    if request.result_id is not None:
        inspection = inspect_result(
            InspectResultRequest(
                execution_id=request.execution_id,
                result_id=request.result_id,
            ),
            output_root=output_root,
        )
        row = inspection.result
        match_id = str(row["match_id"])
        period = str(row["period"])
        anchor_frame_id = int(row["anchor_frame_id"])
        source_id = request.result_id
        source_kind: Literal["result", "target"] = "result"
    else:
        assert request.target is not None
        resolved = resolve_evaluation_target(request.target)
        match_id = resolved.match_id
        period = resolved.period
        anchor_frame_id = resolved.canonical_frame_id
        source_id = request.target.target_id
        source_kind = "target"

    replay_window_id = "replay_" + stable_hash(
        {
            "execution_id": request.execution_id,
            "source_id": source_id,
            "match_id": match_id,
            "period": period,
            "anchor_frame_id": anchor_frame_id,
            "padding_seconds": request.padding_seconds,
        }
    )[:16]
    replay = replay_window_from_canonical(
        replay_window_id=replay_window_id,
        plan_path=Path(f"handle://{execution_record['bound_plan_id']}"),
        source_id=source_id,
        source_kind=source_kind,
        match_id=match_id,
        period=period,
        anchor_frame_id=anchor_frame_id,
        padding_seconds=request.padding_seconds,
    )
    if not replay["frames"]:
        raise CapabilityGap("NO_REPLAY_WINDOW: requested target produced no canonical replay frames")
    artifact_path = output_root / "replay-windows" / f"{replay_window_id}.json"
    if artifact_path.exists():
        existing_replay = read_json(artifact_path)
        if canonical_identity(existing_replay) != canonical_identity(replay):
            raise CapabilityGap(f"replay artifact collision: {replay_window_id}")
    else:
        write_json(artifact_path, replay)
    write_handle(
        "replay-windows",
        replay_window_id,
        {
            "schema_version": "1.0",
            "created_at": utc_now_iso(),
            "replay_window_id": replay_window_id,
            "execution_id": request.execution_id,
            "source_kind": source_kind,
            "source_id": source_id,
            "match_id": match_id,
            "period": period,
            "start_frame_id": int(replay["start_frame_id"]),
            "end_frame_id": int(replay["end_frame_id"]),
            "anchor_frame_id": anchor_frame_id,
            "frame_count": len(replay["frames"]),
            "artifact_path": str(artifact_path),
        },
        output_root=output_root,
    )
    return ReplayWindowResponse(
        ok=True,
        execution_id=request.execution_id,
        replay_window_id=replay_window_id,
        match_id=match_id,
        period=period,
        start_frame_id=int(replay["start_frame_id"]),
        end_frame_id=int(replay["end_frame_id"]),
        anchor_frame_id=anchor_frame_id,
        frame_count=len(replay["frames"]),
        entity_observation_count=sum(len(frame["entities"]) for frame in replay["frames"]),
        source_kind=source_kind,
    )


def record_feedback(
    request: RecordFeedbackRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> RecordFeedbackResponse:
    execution_record = read_handle("executions", request.execution_id, output_root=output_root)
    if request.result_id is not None:
        if not any(str(row["result_id"]) == request.result_id for row in execution_record["rows"]):
            raise CapabilityGap(f"result_id {request.result_id} does not belong to execution {request.execution_id}")
    payload = {
        "schema_version": "1.0",
        "recorded_at": utc_now_iso(),
        **request.model_dump(mode="json", exclude_none=True),
    }
    feedback_id = stable_hash(payload)[:16]
    record = {"feedback_id": feedback_id, **payload}
    path = output_root / "feedback-records.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return RecordFeedbackResponse(ok=True, execution_id=request.execution_id, feedback_id=feedback_id, path=str(path))


def save_experimental_recipe(
    request: SaveExperimentalRecipeRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> SaveExperimentalRecipeResponse:
    draft_record = read_handle("draft-plans", request.draft_plan_id, output_root=output_root)
    document = TacticalQueryDocument.model_validate(draft_record["document"])
    bound = bind_document(document)
    validate_safe_agent_plan(bound, caller_profile=CallerProfile.HOST_MANUAL)
    if document.draft_plan.status != PlanStatus.EXPERIMENTAL:
        raise CapabilityGap("save_experimental_recipe only accepts experimental draft plans")
    query_hash = stable_hash(model_payload(document))
    payload = {
        "schema_version": "1.0",
        "saved_at": utc_now_iso(),
        "state": "EXPERIMENTAL",
        "creator": request.creator,
        "parent_version": request.parent_version,
        "note": request.note,
        "draft_plan_id": request.draft_plan_id,
        "query_hash": query_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "document": model_payload(document),
    }
    recipe_version_id = f"recipe_{query_hash[:16]}"
    path = output_root / "recipes" / f"{recipe_version_id}.json"
    if path.exists():
        existing = read_json(path)
        if existing.get("query_hash") != query_hash:
            raise RuntimeError(f"Immutable recipe path collision at {path}")
    else:
        write_json(path, payload)
    write_handle("recipes", recipe_version_id, payload, output_root=output_root)
    return SaveExperimentalRecipeResponse(
        ok=True,
        recipe_version_id=recipe_version_id,
        path=str(path),
        query_hash=query_hash,
    )


def compare_query_versions(request: CompareQueryVersionsRequest) -> CompareQueryVersionsResponse:
    before = read_handle("recipes", request.before_recipe_version_id)
    after = read_handle("recipes", request.after_recipe_version_id)
    before_hash = stable_hash(before)
    after_hash = stable_hash(after)
    changes: list[dict[str, Any]] = []
    for pointer in (
        "/recipe/display_name",
        "/draft_plan/nodes",
        "/draft_plan/classification_rules",
        "/draft_plan/requested_evidence",
        "/default_invocation/parameters",
    ):
        before_value = value_at_pointer(before, pointer)
        after_value = value_at_pointer(after, pointer)
        if before_value != after_value:
            changes.append({"pointer": pointer, "before": before_value, "after": after_value})
    return CompareQueryVersionsResponse(
        ok=True,
        before_hash=before_hash,
        after_hash=after_hash,
        same=before_hash == after_hash,
        semantic_changes=changes,
    )


def validate_safe_agent_plan(
    bound: Any,
    *,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> None:
    trusted_m1 = is_trusted_m1_bound_plan(bound)
    if is_model_caller(caller_profile) and bound.plan_status != PlanStatus.EXPERIMENTAL:
        raise CapabilityGap("Hermes-authored query documents must be EXPERIMENTAL")
    if is_model_caller(caller_profile) and bound.execution_mode != ExecutionMode.EXECUTE:
        raise CapabilityGap("Hermes-authored query documents must keep execution_mode=execute; validation does not execute")
    if bound.plan_status == PlanStatus.APPROVED and not trusted_m1:
        raise CapabilityGap("Approved recipes must be loaded from trusted host records")
    for node in bound.nodes:
        if isinstance(node, BoundCatalogNode) and not trusted_m1:
            if node.catalog_ref in NON_AUTHORABLE_CATALOG_REFS:
                raise CapabilityGap(f"{node.catalog_ref} is not agent-authorable")
        if not isinstance(node, BoundPredicateNode):
            continue
        if node.operator.name in SAFE_ANCHOR_RELATIVE_OPERATORS:
            if node.input.output_name != SAFE_ANCHOR_RELATIVE_OUTPUT:
                raise CapabilityGap(
                    f"{node.operator.name} is agent-visible only for "
                    f"{SAFE_ANCHOR_RELATIVE_OUTPUT}; got "
                    f"{node.input.source_node_id}.{node.input.output_name}"
                )


def default_profile_for_bound_plan(bound_plan: Any) -> str:
    if is_trusted_m1_bound_plan(bound_plan):
        return LEGACY_M1_PARITY_PROFILE
    return GENERIC_EXECUTION_PROFILE


def is_trusted_m1_bound_plan(bound_plan: Any) -> bool:
    if bound_plan.plan_status != PlanStatus.APPROVED:
        return False
    if bound_plan.recipe_id != TRUSTED_M1_RECIPE_ID or bound_plan.recipe_version != TRUSTED_M1_RECIPE_VERSION:
        return False
    try:
        trusted = bind_document_from_path(Path("config/query-plans/ball_side_block_shift.ir.v1.json"))
    except Exception:
        return False
    semantic_fields = (
        "plan_hash",
        "max_results",
        "execution_mode",
        "unknown_evidence_policy",
        "classification_mode",
        "classification_rules",
        "anchor_source",
        "requested_evidence",
        "complexity_limits",
        "resolved_parameters",
        "nodes",
    )
    return all(stable_hash(getattr(bound_plan, field)) == stable_hash(getattr(trusted, field)) for field in semantic_fields)


def execution_record_payload(
    *,
    bound_record: dict[str, Any],
    execution: QueryExecution,
    rows: list[dict[str, Any]],
    profile: str,
    execution_id: str,
) -> dict[str, Any]:
    traces = [trace.model_dump(mode="json", exclude_none=True) for trace in execution.predicate_traces]
    document = bound_record["document"]
    scope = selected_scope_from_document(document)
    enriched_rows = [result_row_with_context(row) for row in rows]
    evidence_failure_count = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    evidence_failures = execution.provenance.get("requested_evidence_failures")
    return {
        "schema_version": "1.0",
        "created_at": utc_now_iso(),
        "execution_id": execution_id,
        "execution_status": execution.status.value,
        "execution_complete": execution.status == ExecutionStatus.PASS and evidence_failure_count == 0,
        "requested_evidence_failure_count": evidence_failure_count,
        "requested_evidence_failures": evidence_failures if isinstance(evidence_failures, list) else [],
        "draft_plan_id": bound_record["draft_plan_id"],
        "draft_plan_hash": bound_record["draft_plan_hash"],
        "bound_plan_id": bound_record["bound_plan_id"],
        "bound_plan_hash": bound_record["bound_plan_hash"],
        "compatibility_profile": profile,
        "dataset_identity": {
            "canonical_root": str(DEFAULT_CANONICAL_ROOT),
            "raw_root": str(DEFAULT_RAW_ROOT),
        },
        "scope": scope,
        "document": document,
        "execution": execution.model_dump(mode="json", exclude_none=True),
        "rows": enriched_rows,
        "result_ids": [str(row["result_id"]) for row in enriched_rows],
        "predicate_traces": traces,
    }


def validate_profile_allowed(plan_status: PlanStatus, profile: str) -> None:
    if profile == LEGACY_M1_PARITY_PROFILE and plan_status != PlanStatus.APPROVED:
        raise CapabilityGap("legacy_m1_parity is restricted to the frozen approved M1 recipe")


def executor_for_profile(profile: str) -> TacticalQueryExecutor:
    return TacticalQueryExecutor(
        canonical_root=DEFAULT_CANONICAL_ROOT,
        raw_root=DEFAULT_RAW_ROOT,
        compatibility_profile=profile,
    )


def catalog_entry_summary(entry: Any) -> dict[str, Any]:
    agent_authorable = entry.name not in NON_AUTHORABLE_CATALOG_REFS
    payload = {
        "name": entry.name,
        "version": entry.version,
        "kind": entry.kind.value if hasattr(entry.kind, "value") else entry.kind,
        "purpose": entry.purpose,
        "agent_authorable": agent_authorable,
        "inputs": [item.model_dump(mode="json") for item in entry.inputs],
        "outputs": [output.model_dump(mode="json") for output in entry.outputs],
        "parameters": [parameter.model_dump(mode="json", exclude_none=True) for parameter in entry.parameters],
        "limitations": entry.limitations,
        "evidence_fields": entry.evidence_fields,
    }
    if entry.name == "relation_destination_entry":
        payload["agent_authoring"] = {
            "safe_generic_path": DESTINATION_ENTRY_AGENT_PATH,
            "output_to_classify": "entry_status",
            "required_operator": "eq",
            "required_compare_value": "PASS",
        }
    elif entry.name == "relation_destination_entry_classification":
        payload["trusted_recipe_wrapper"] = True
        payload["agent_authoring"] = {
            "allowed": False,
            "use_instead": "relation_destination_entry",
            "reason": "Recipe-specific wrapper; agent-authored plans must use the generic entry_status path.",
        }
    return payload


def tool_spec(name: str) -> ToolSpec:
    descriptions = {
        "list_capabilities": "Return the Hermes-safe capability context.",
        "search_recipes": "Search approved and experimental recipe summaries without exposing files or raw data.",
        "describe_capability": "Describe one exposed tool, primitive, relation, operator, or generated typed-plan authoring contract.",
        "submit_query_plan": "Store a typed query document and return an opaque draft_plan_id.",
        "validate_query_plan": "Bind and boundary-check a submitted typed query plan.",
        "execute_query_plan": "Execute a validated plan through the deterministic runtime.",
        "inspect_result": "Return predicate traces and requested evidence for a result.",
        "inspect_non_match": "Evaluate a known timestamp target against a bound plan.",
        "retrieve_replay_window": "Materialize a bounded coordinate replay JSON artifact.",
        "compare_query_versions": "Compute deterministic semantic diffs for two query documents.",
        "record_feedback": "Append immutable analyst feedback for a result or known target.",
        "save_experimental_recipe": "Save a content-addressed experimental recipe version.",
    }
    request_models: dict[str, type[BaseModel]] = {
        "list_capabilities": ListCapabilitiesRequest,
        "search_recipes": SearchRecipesRequest,
        "describe_capability": DescribeCapabilityRequest,
        "submit_query_plan": SubmitQueryPlanRequest,
        "validate_query_plan": ValidateQueryPlanRequest,
        "execute_query_plan": ExecuteQueryPlanRequest,
        "inspect_result": InspectResultRequest,
        "inspect_non_match": InspectNonMatchRequest,
        "retrieve_replay_window": ReplayWindowRequest,
        "compare_query_versions": CompareQueryVersionsRequest,
        "record_feedback": RecordFeedbackRequest,
        "save_experimental_recipe": SaveExperimentalRecipeRequest,
    }
    response_models: dict[str, type[BaseModel]] = {
        "list_capabilities": CapabilityContext,
        "search_recipes": SearchRecipesResponse,
        "describe_capability": DescribeCapabilityResponse,
        "submit_query_plan": SubmitQueryPlanResponse,
        "validate_query_plan": ValidateQueryPlanResponse,
        "execute_query_plan": ExecuteQueryPlanResponse,
        "inspect_result": InspectResultResponse,
        "inspect_non_match": InspectNonMatchResponse,
        "retrieve_replay_window": ReplayWindowResponse,
        "compare_query_versions": CompareQueryVersionsResponse,
        "record_feedback": RecordFeedbackResponse,
        "save_experimental_recipe": SaveExperimentalRecipeResponse,
    }
    return ToolSpec(
        name=name,
        description=descriptions[name],
        input_schema=request_models[name].model_json_schema(),
        output_schema={
            "oneOf": [
                response_models[name].model_json_schema(),
                ToolErrorResponse.model_json_schema(),
            ]
        },
        unavailable_surfaces=FORBIDDEN_SURFACES,
        exposure="hermes_s2" if name in HERMES_S2_TOOL_NAMES else "manual_only",
    )


def dispatch_tool(
    request: ToolDispatchRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> ToolDispatchResponse:
    try:
        if is_model_caller(caller_profile) and request.tool_name not in visible_tool_names(caller_profile):
            raise CapabilityGap(f"{request.tool_name} is not available to {caller_profile.value}")
        if request.tool_name == "list_capabilities":
            ListCapabilitiesRequest.model_validate(request.arguments)
            response = list_capabilities(caller_profile)
        elif request.tool_name == "search_recipes":
            response = search_recipes(
                SearchRecipesRequest.model_validate(request.arguments),
                caller_profile,
            )
        elif request.tool_name == "describe_capability":
            response = describe_capability_tool(
                DescribeCapabilityRequest.model_validate(request.arguments),
                caller_profile,
            )
        elif request.tool_name == "submit_query_plan":
            response = submit_query_plan(
                SubmitQueryPlanRequest.model_validate(request.arguments),
                output_root=output_root,
                caller_profile=caller_profile,
            )
        elif request.tool_name == "validate_query_plan":
            response = validate_query_plan(
                ValidateQueryPlanRequest.model_validate(request.arguments),
                output_root=output_root,
                caller_profile=caller_profile,
            )
        elif request.tool_name == "execute_query_plan":
            response = execute_query_plan(
                ExecuteQueryPlanRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "inspect_result":
            response = inspect_result(
                InspectResultRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "inspect_non_match":
            response = inspect_non_match(
                InspectNonMatchRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "retrieve_replay_window":
            response = retrieve_replay_window(
                ReplayWindowRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "record_feedback":
            response = record_feedback(
                RecordFeedbackRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "save_experimental_recipe":
            response = save_experimental_recipe(
                SaveExperimentalRecipeRequest.model_validate(request.arguments),
                output_root=output_root,
            )
        elif request.tool_name == "compare_query_versions":
            response = compare_query_versions(CompareQueryVersionsRequest.model_validate(request.arguments))
        else:
            raise CapabilityGap(f"Unsupported tool: {request.tool_name}")
        return ToolDispatchResponse(
            ok=True,
            tool_name=request.tool_name,
            response=response.model_dump(mode="json") if isinstance(response, BaseModel) else response,
        )
    except Exception as exc:
        return ToolDispatchResponse(
            ok=False,
            tool_name=request.tool_name,
            response=ToolErrorResponse(
                error_code=stable_tool_error_code(exc),
                message=str(exc),
                details={"exception_type": type(exc).__name__},
            ).model_dump(mode="json"),
        )


def stable_tool_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, CapabilityGap):
        if "unknown" in message and "handle" in message:
            return "UNKNOWN_HANDLE"
        if "no_replay_window" in message:
            return "NO_REPLAY_WINDOW"
        if "authorization" in message or "confirmed" in message:
            return "EXECUTION_NOT_CONFIRMED"
        return "CAPABILITY_GAP"
    if isinstance(exc, BindError):
        return "PLAN_VALIDATION_FAILED"
    if type(exc).__name__ == "ValidationError":
        return "REQUEST_SCHEMA_INVALID"
    return "INTERNAL_ERROR"


def dispatch_model_visible(
    request: ToolDispatchRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> dict[str, Any]:
    dispatch = dispatch_tool(request, output_root=output_root, caller_profile=caller_profile)
    payload = dispatch.response
    validate_model_visible_payload(
        tool_name=request.tool_name,
        payload=payload,
        caller_profile=caller_profile,
    )
    return payload


def validate_model_visible_payload(
    *,
    tool_name: str,
    payload: dict[str, Any],
    caller_profile: CallerProfile = CallerProfile.HERMES_S2,
) -> None:
    context = list_capabilities(caller_profile)
    tool = next((item for item in context.tools if item.name == tool_name), None)
    if tool is None:
        if payload.get("ok") is False:
            ToolErrorResponse.model_validate(payload)
            return
        raise CapabilityGap(f"{tool_name} is not visible to {caller_profile.value}")
    model = response_model_for_tool(tool_name)
    try:
        model.model_validate(payload)
    except Exception:
        ToolErrorResponse.model_validate(payload)


def response_model_for_tool(tool_name: str) -> type[BaseModel]:
    response_models: dict[str, type[BaseModel]] = {
        "list_capabilities": CapabilityContext,
        "search_recipes": SearchRecipesResponse,
        "describe_capability": DescribeCapabilityResponse,
        "submit_query_plan": SubmitQueryPlanResponse,
        "validate_query_plan": ValidateQueryPlanResponse,
        "execute_query_plan": ExecuteQueryPlanResponse,
        "inspect_result": InspectResultResponse,
        "inspect_non_match": InspectNonMatchResponse,
        "retrieve_replay_window": ReplayWindowResponse,
        "compare_query_versions": CompareQueryVersionsResponse,
        "record_feedback": RecordFeedbackResponse,
        "save_experimental_recipe": SaveExperimentalRecipeResponse,
    }
    return response_models[tool_name]


def rank_result(row: dict[str, Any], *, rank: int) -> dict[str, Any]:
    row = result_row_with_context(row)
    match_id = str(row["match_id"])
    period = str(row["period"])
    anchor_frame_id = int(row["anchor_frame_id"])
    return {
        "rank": rank,
        "result_id": str(row["result_id"]),
        "classification": str(row["classification"]),
        "match_id": match_id,
        "period": period,
        "anchor_frame_id": anchor_frame_id,
        "match_time_ms": canonical_match_time_ms(match_id, period, anchor_frame_id),
        "requested_evidence": row.get("requested_evidence", {}),
    }


def result_row_with_context(row: dict[str, Any]) -> dict[str, Any]:
    next_row = dict(row)
    match_id = str(next_row["match_id"])
    period = str(next_row["period"])
    anchor_frame_id = int(next_row["anchor_frame_id"])
    next_row["match_time_ms"] = canonical_match_time_ms(match_id, period, anchor_frame_id)
    return next_row


def selected_scope_from_document(document: dict[str, Any]) -> dict[str, Any]:
    invocation = document.get("default_invocation") if isinstance(document, dict) else {}
    if not isinstance(invocation, dict):
        invocation = {}
    return {
        "match_ids": invocation.get("match_ids"),
        "periods": invocation.get("periods"),
        "perspective_team_role": invocation.get("perspective_team_role"),
    }


@lru_cache(maxsize=128)
def canonical_frame_time_lookup(match_id: str, period: str) -> dict[int, int]:
    frame_path = DEFAULT_CANONICAL_ROOT / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
    frames_table = pq.ParquetFile(frame_path).read(columns=["frame_id"]).to_pandas()
    frame_ids = sorted(int(item) for item in frames_table.frame_id.tolist())
    if not frame_ids:
        return {}
    first_frame = frame_ids[0]
    return {
        frame_id: int(round((frame_id - first_frame) / FRAME_RATE_HZ * 1000))
        for frame_id in frame_ids
    }


def canonical_match_time_ms(match_id: str, period: str, frame_id: int) -> int | None:
    try:
        return canonical_frame_time_lookup(match_id, period).get(frame_id)
    except Exception:  # noqa: BLE001 - result ranking should not mask the original execution result.
        return None


def resolve_evaluation_target(target: EvaluationTarget) -> ResolvedEvaluationTarget:
    frame_path = DEFAULT_CANONICAL_ROOT / "frames" / f"match_id={target.match_id}" / f"period={target.period}.parquet"
    frames_table = pq.ParquetFile(frame_path).read(columns=["frame_id"]).to_pandas()
    frame_ids = sorted(int(item) for item in frames_table.frame_id.tolist())
    if not frame_ids:
        raise CapabilityGap(f"NO_REPLAY_WINDOW: no canonical frames for {target.match_id} {target.period}")
    first_frame = frame_ids[0]
    nominal = first_frame + int(round(target.approximate_time_ms / 1000.0 * FRAME_RATE_HZ))
    canonical_frame_id = min(frame_ids, key=lambda item: abs(item - nominal))
    resolution_distance_frames = abs(canonical_frame_id - nominal)
    return ResolvedEvaluationTarget(
        original_target=target,
        match_id=target.match_id,
        period=target.period,
        canonical_frame_id=canonical_frame_id,
        resolved_match_time_ms=int(round((canonical_frame_id - first_frame) / FRAME_RATE_HZ * 1000)),
        absolute_frame_time_ms=int(round(canonical_frame_id / FRAME_RATE_HZ * 1000)),
        resolution_distance_frames=resolution_distance_frames,
        resolution_distance_ms=int(round(resolution_distance_frames / FRAME_RATE_HZ * 1000)),
    )


def canonical_frame_for_target(target: EvaluationTarget) -> int:
    return resolve_evaluation_target(target).canonical_frame_id


def replay_artifact_path(
    replay_window_id: str,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> Path:
    handle_path("replay-windows", replay_window_id, output_root=output_root)
    return output_root / "replay-windows" / f"{replay_window_id}.json"


def replay_window_from_canonical(
    *,
    replay_window_id: str,
    plan_path: Path,
    source_id: str,
    source_kind: str,
    match_id: str,
    period: str,
    anchor_frame_id: int,
    padding_seconds: float,
) -> dict[str, Any]:
    frame_path = DEFAULT_CANONICAL_ROOT / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
    position_path = DEFAULT_CANONICAL_ROOT / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
    matches_path = DEFAULT_CANONICAL_ROOT / "matches.parquet"
    frames_table = pq.ParquetFile(frame_path).read().to_pandas()
    positions_table = pq.ParquetFile(position_path).read().to_pandas()
    matches = {
        str(row["match_id"]): row
        for row in pq.ParquetFile(matches_path).read().to_pylist()
    }
    padding_frames = int(round(padding_seconds * FRAME_RATE_HZ))
    min_frame = int(frames_table.frame_id.min())
    max_frame = int(frames_table.frame_id.max())
    start_frame_id = max(min_frame, anchor_frame_id - padding_frames)
    end_frame_id = min(max_frame, anchor_frame_id + padding_frames)
    frame_rows = frames_table[
        (frames_table.frame_id >= start_frame_id) & (frames_table.frame_id <= end_frame_id)
    ].sort_values("frame_id")
    position_rows = positions_table[
        (positions_table.frame_id >= start_frame_id)
        & (positions_table.frame_id <= end_frame_id)
    ].sort_values(["frame_id", "team_role", "entity_type", "entity_id"])
    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in position_rows.itertuples(index=False):
        positions_by_frame.setdefault(int(row.frame_id), []).append(
            {
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "entity_id": str(row.entity_id),
                "entity_type": str(row.entity_type),
                "x_m": round(float(row.x_m), 3),
                "y_m": round(float(row.y_m), 3),
            }
        )
    match = matches.get(match_id, {})
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "replay_window_id": replay_window_id,
        "source_kind": source_kind,
        "source_id": source_id,
        "plan_path": str(plan_path),
        "match_id": match_id,
        "period": period,
        "frame_rate_hz": FRAME_RATE_HZ,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "anchor_frame_id": anchor_frame_id,
        "pitch": {
            "length_m": float(match.get("pitch_length_m", 105.0)),
            "width_m": float(match.get("pitch_width_m", 68.0)),
            "coordinate_contract": "centered_metres",
        },
        "canonical_sources": {
            "frames": str(frame_path),
            "positions": str(position_path),
        },
        "frames": [
            {
                "frame_id": int(row.frame_id),
                "timestamp_utc": str(row.timestamp_utc),
                "entities": positions_by_frame.get(int(row.frame_id), []),
            }
            for row in frame_rows.itertuples(index=False)
        ],
    }


def value_at_pointer(payload: Any, pointer: str) -> Any:
    current = payload
    for part in pointer.strip("/").split("/"):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def write_manual_workshop_artifacts(
    *,
    output_root: Path,
    data: dict[str, Any],
) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    data_path = output_root / "manual-workshop-data.json"
    js_path = output_root / "manual-workshop-data.js"
    html_path = output_root / "index.html"
    write_json(data_path, data)
    js_path.write_text(
        "window.M12_WORKSHOP_DATA = "
        + json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + ";\n",
        encoding="utf-8",
    )
    html_path.write_text(manual_workshop_html(), encoding="utf-8")
    return {"data_json": str(data_path), "data_js": str(js_path), "html": str(html_path)}


def manual_workshop_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>M1.2 Manual Tactical Query Workshop</title>
<style>
body{margin:0;font-family:Arial,sans-serif;background:#f7f7f4;color:#171717}
main{display:grid;grid-template-columns:420px 1fr;height:100vh}
aside{border-right:1px solid #c9c9c2;padding:14px;overflow:auto;background:#fff}
section{padding:14px;overflow:auto}
textarea{width:100%;height:260px;font:12px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace}
button{margin:3px;padding:6px 9px;border:1px solid #888;background:#fff;cursor:pointer}
button.active{background:#171717;color:#fff}
canvas{width:100%;max-width:920px;aspect-ratio:105/68;border:1px solid #aaa;background:#4f8f55}
pre{white-space:pre-wrap;background:#fff;border:1px solid #ddd;padding:8px;max-height:260px;overflow:auto}
.row{border-bottom:1px solid #ddd;padding:7px 0}
</style>
</head>
<body>
<main>
<aside>
<h1>M1.2 Workshop</h1>
<label>Typed plan JSON</label>
<textarea id="plan"></textarea>
<h2>Results</h2>
<div id="results"></div>
<h2>Feedback labels</h2>
<pre id="feedback"></pre>
</aside>
<section>
<canvas id="pitch" width="1050" height="680"></canvas>
<p id="frame"></p>
<button id="prev">Prev</button><button id="play">Play</button><button id="next">Next</button>
<h2>Predicate trace</h2>
<pre id="trace"></pre>
<h2>Known timestamp inspection</h2>
<pre id="nonmatch"></pre>
</section>
</main>
<script src="manual-workshop-data.js"></script>
<script>
const data = window.M12_WORKSHOP_DATA;
let selected = data.runs[0].results[0];
let frameIndex = 0;
let timer = null;
const ctx = document.getElementById("pitch").getContext("2d");
document.getElementById("plan").value = JSON.stringify(data.runs[0].plan_document, null, 2);
document.getElementById("feedback").textContent = data.feedback_labels.join("\\n");
document.getElementById("nonmatch").textContent = JSON.stringify(data.non_match_inspection, null, 2);
function renderResults(){
  const root=document.getElementById("results"); root.innerHTML="";
  data.runs.flatMap(run => run.results.map(result => ({run,result}))).forEach(({run,result})=>{
    const b=document.createElement("button");
    b.className=result.result_id===selected.result_id?"active":"";
    b.textContent=`${run.recipe_state} #${result.rank} ${result.classification}`;
    b.onclick=()=>{selected=result;frameIndex=0;renderAll();};
    const row=document.createElement("div"); row.className="row"; row.appendChild(b); root.appendChild(row);
  });
}
function xy(x,y,pitch){return [(x+pitch.length_m/2)/pitch.length_m*1050,(pitch.width_m/2-y)/pitch.width_m*680];}
function renderPitch(){
  const replay=selected.replay;
  const frames=replay.frames || [];
  const frame=frames[Math.min(frameIndex, Math.max(0, frames.length-1))] || {entities:[]};
  ctx.clearRect(0,0,1050,680);
  ctx.fillStyle="#4f8f55"; ctx.fillRect(0,0,1050,680);
  ctx.strokeStyle="#fff"; ctx.lineWidth=3; ctx.strokeRect(20,20,1010,640);
  ctx.beginPath(); ctx.moveTo(525,20); ctx.lineTo(525,660); ctx.stroke();
  for (const e of frame.entities){
    const p=xy(e.x_m,e.y_m,replay.pitch);
    ctx.beginPath(); ctx.arc(p[0],p[1],e.entity_type==="ball"?5:9,0,Math.PI*2);
    ctx.fillStyle=e.entity_type==="ball"?"#f4f4f4":(e.team_role==="home"?"#1f5fbf":"#c43a31");
    ctx.fill();
  }
  document.getElementById("frame").textContent =
    `${selected.result_id} | ${replay.replay_window_id} | frame ${frame.frame_id || "-"} | ${frameIndex+1}/${frames.length}`;
}
function renderAll(){
  renderResults(); renderPitch();
  document.getElementById("trace").textContent = JSON.stringify(selected.predicate_traces, null, 2);
}
document.getElementById("prev").onclick=()=>{frameIndex=Math.max(0,frameIndex-1);renderPitch();};
document.getElementById("next").onclick=()=>{frameIndex=Math.min((selected.replay.frames||[]).length-1,frameIndex+1);renderPitch();};
document.getElementById("play").onclick=()=>{
  if(timer){clearInterval(timer); timer=null; return;}
  timer=setInterval(()=>{frameIndex=(frameIndex+1)%Math.max(1,(selected.replay.frames||[]).length);renderPitch();},120);
};
renderAll();
</script>
</body>
</html>
"""
