"""M1.2 bounded workshop tools.

This module is intentionally deterministic and local. Hermes can later become a
client of this surface, but S0/S1 keep every operation usable without an agent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field

from tqe.runtime.binder import BindError, bind_document_from_path
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
    BoundPredicateNode,
    EvaluationTarget,
    NodeKind,
    PlanStatus,
    TacticalQueryDocument,
    model_payload,
    stable_hash,
)

APPROVED_TOOL_NAMES = [
    "list_capabilities",
    "describe_capability",
    "validate_query_plan",
    "execute_query_plan",
    "inspect_result",
    "inspect_non_match",
    "retrieve_replay_window",
    "compare_query_versions",
    "record_feedback",
    "save_experimental_recipe",
]
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
DEFAULT_WORKSHOP_ROOT = Path("artifacts/m1.2/workshop")
CAPABILITY_CONTEXT_PATH = Path("generated/capability-context.json")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeedbackLabel(StrEnum):
    MATCHES_INTENT = "MATCHES_INTENT"
    NEAR_MATCH = "NEAR_MATCH"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    KNOWN_MISS = "KNOWN_MISS"
    UNUSABLE_DATA = "UNUSABLE_DATA"


class ToolSpec(StrictModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    unavailable_surfaces: list[str]


class CapabilityContext(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    milestone: Literal["M1.2"] = "M1.2"
    generated_at: str
    tools: list[ToolSpec]
    primitives: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    operators: list[dict[str, Any]]
    recipe_states: list[str]
    evidence_fields: dict[str, list[str]]
    safe_operator_source_rules: dict[str, Any]
    default_complexity_limits: dict[str, Any]
    host_owned_complexity_ceilings: dict[str, Any]
    limitations: list[str]
    forbidden_surfaces: list[str]


class ValidateQueryPlanRequest(StrictModel):
    plan_path: str


class ValidateQueryPlanResponse(StrictModel):
    ok: bool
    plan_path: str
    plan_id: str | None = None
    plan_status: str | None = None
    bound_plan_hash: str | None = None
    compatibility_profile: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteQueryPlanRequest(StrictModel):
    plan_path: str
    compatibility_profile: Literal["generic", "legacy_m1_parity"] = GENERIC_EXECUTION_PROFILE
    result_limit: int = Field(default=25, ge=1, le=100)


class ExecuteQueryPlanResponse(StrictModel):
    ok: bool
    plan_path: str
    execution_id: str
    plan_id: str
    plan_status: str
    compatibility_profile: str
    total_result_count: int
    returned_result_count: int
    results: list[dict[str, Any]]
    trace_count: int
    bound_plan_hash: str


class InspectResultRequest(StrictModel):
    plan_path: str
    result_id: str
    compatibility_profile: Literal["generic", "legacy_m1_parity"] = GENERIC_EXECUTION_PROFILE


class InspectResultResponse(StrictModel):
    ok: bool
    result: dict[str, Any]
    predicate_traces: list[dict[str, Any]]
    requested_evidence: dict[str, Any]


class InspectNonMatchRequest(StrictModel):
    plan_path: str
    target: EvaluationTarget
    compatibility_profile: Literal["generic", "legacy_m1_parity"] = GENERIC_EXECUTION_PROFILE


class InspectNonMatchResponse(StrictModel):
    ok: bool
    inspection: dict[str, Any]


class ReplayWindowRequest(StrictModel):
    plan_path: str
    compatibility_profile: Literal["generic", "legacy_m1_parity"] = GENERIC_EXECUTION_PROFILE
    result_id: str | None = None
    target: EvaluationTarget | None = None
    padding_seconds: float = Field(default=2.0, ge=0.2, le=8.0)


class ReplayWindowResponse(StrictModel):
    ok: bool
    replay_window_id: str
    artifact_path: str
    match_id: str
    period: str
    start_frame_id: int
    end_frame_id: int
    anchor_frame_id: int
    frame_count: int
    entity_observation_count: int
    source_kind: Literal["result", "target"]


class RecordFeedbackRequest(StrictModel):
    query_version: str
    label: FeedbackLabel
    reviewer: str
    reason_code: str
    result_id: str | None = None
    target: EvaluationTarget | None = None
    note: str | None = None


class RecordFeedbackResponse(StrictModel):
    ok: bool
    feedback_id: str
    path: str


class SaveExperimentalRecipeRequest(StrictModel):
    plan_path: str
    creator: str
    parent_version: str | None = None
    note: str | None = None


class SaveExperimentalRecipeResponse(StrictModel):
    ok: bool
    recipe_version_id: str
    path: str
    query_hash: str


class CompareQueryVersionsRequest(StrictModel):
    before_path: str
    after_path: str


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


def list_capabilities() -> CapabilityContext:
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
        payload = operator.model_dump(mode="json", exclude_none=True)
        if operator.name in SAFE_ANCHOR_RELATIVE_OPERATORS:
            payload["agent_visible_source_rule"] = {
                "allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT,
                "rejected_sources": [
                    "raw boolean EpisodeSet",
                    "raw RelationEpisodeSet",
                    "generic collection counts not indexed by anchor_id",
                ],
            }
        operators.append(payload)

    return CapabilityContext(
        generated_at=utc_now_iso(),
        tools=[tool_spec(name) for name in APPROVED_TOOL_NAMES],
        primitives=primitives,
        relations=relations,
        operators=operators,
        recipe_states=["APPROVED", "USER_SAVED", "EXPERIMENTAL", "DEPRECATED"],
        evidence_fields=evidence_fields,
        safe_operator_source_rules={
            "exists": {"allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT},
            "count_at_least": {"allowed_output_name": SAFE_ANCHOR_RELATIVE_OUTPUT},
        },
        default_complexity_limits=catalog.default_complexity_limits.model_dump(mode="json"),
        host_owned_complexity_ceilings=catalog.default_complexity_limits.model_dump(mode="json"),
        limitations=[
            "Hermes receives this bounded context, not raw match dumps or primitive code.",
            "exists/count_at_least are agent-visible only on anchor_evaluations.",
            "legacy_m1_parity is allowed only for the frozen approved M1 recipe.",
            "Unsupported concepts must be returned as capability gaps.",
        ],
        forbidden_surfaces=FORBIDDEN_SURFACES,
    )


def write_capability_context(path: Path = CAPABILITY_CONTEXT_PATH) -> CapabilityContext:
    context = list_capabilities()
    write_json(path, context.model_dump(mode="json"))
    return context


def describe_capability(capability_name: str) -> dict[str, Any]:
    context = list_capabilities()
    for collection_name in ("tools", "primitives", "relations", "operators"):
        collection = getattr(context, collection_name)
        for item in collection:
            payload = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            if payload.get("name") == capability_name:
                return {"kind": collection_name[:-1], **payload}
    raise CapabilityGap(f"Unsupported capability: {capability_name}")


def validate_query_plan(request: ValidateQueryPlanRequest) -> ValidateQueryPlanResponse:
    plan_path = Path(request.plan_path)
    try:
        bound = bind_document_from_path(plan_path)
        validate_safe_agent_plan(bound)
        profile = default_profile_for_plan(bound.plan_status)
        return ValidateQueryPlanResponse(
            ok=True,
            plan_path=str(plan_path),
            plan_id=bound.plan_id,
            plan_status=bound.plan_status.value,
            bound_plan_hash=bound.bound_plan_hash,
            compatibility_profile=profile,
        )
    except BindError as exc:
        return ValidateQueryPlanResponse(
            ok=False,
            plan_path=str(plan_path),
            issues=[issue.model_dump(mode="json") for issue in exc.issues],
        )
    except Exception as exc:
        return ValidateQueryPlanResponse(
            ok=False,
            plan_path=str(plan_path),
            issues=[{"code": type(exc).__name__, "message": str(exc), "path": str(plan_path)}],
        )


def execute_query_plan(request: ExecuteQueryPlanRequest) -> ExecuteQueryPlanResponse:
    bound = bind_document_from_path(Path(request.plan_path))
    validate_safe_agent_plan(bound)
    validate_profile_allowed(bound.plan_status, request.compatibility_profile)
    if request.compatibility_profile == LEGACY_M1_PARITY_PROFILE:
        bound, execution = execute_legacy_m1_plan_from_path(Path(request.plan_path))
    else:
        bound, execution = execute_plan_from_path(Path(request.plan_path))
    rows = execution_result_rows(execution)
    returned = rows[: request.result_limit]
    return ExecuteQueryPlanResponse(
        ok=True,
        plan_path=request.plan_path,
        execution_id=execution.execution_id,
        plan_id=bound.plan_id,
        plan_status=bound.plan_status.value,
        compatibility_profile=str(execution.provenance.get("compatibility_profile")),
        total_result_count=len(rows),
        returned_result_count=len(returned),
        results=[rank_result(row, rank=index + 1) for index, row in enumerate(returned)],
        trace_count=len(execution.predicate_traces),
        bound_plan_hash=bound.bound_plan_hash,
    )


def inspect_result(request: InspectResultRequest) -> InspectResultResponse:
    bound = bind_document_from_path(Path(request.plan_path))
    validate_safe_agent_plan(bound)
    validate_profile_allowed(bound.plan_status, request.compatibility_profile)
    execution = executor_for_profile(request.compatibility_profile).execute(bound)
    rows = execution_result_rows(execution)
    result = next((row for row in rows if str(row["result_id"]) == request.result_id), None)
    if result is None:
        raise CapabilityGap(f"Unknown result_id for plan execution: {request.result_id}")
    traces = [
        trace.model_dump(mode="json", exclude_none=True)
        for trace in execution.predicate_traces
        if str(trace.source_evidence.get("result_id")) == request.result_id
    ]
    requested_evidence = result.get("requested_evidence")
    return InspectResultResponse(
        ok=True,
        result=result,
        predicate_traces=traces,
        requested_evidence=requested_evidence if isinstance(requested_evidence, dict) else {},
    )


def inspect_non_match(request: InspectNonMatchRequest) -> InspectNonMatchResponse:
    bound = bind_document_from_path(Path(request.plan_path))
    validate_safe_agent_plan(bound)
    validate_profile_allowed(bound.plan_status, request.compatibility_profile)
    inspection = executor_for_profile(request.compatibility_profile).evaluate_target(
        bound,
        request.target,
    )
    return InspectNonMatchResponse(ok=True, inspection=inspection)


def retrieve_replay_window(
    request: ReplayWindowRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> ReplayWindowResponse:
    if (request.result_id is None) == (request.target is None):
        raise CapabilityGap("Provide exactly one of result_id or target")
    if request.result_id is not None:
        inspection = inspect_result(
            InspectResultRequest(
                plan_path=request.plan_path,
                result_id=request.result_id,
                compatibility_profile=request.compatibility_profile,
            )
        )
        row = inspection.result
        match_id = str(row["match_id"])
        period = str(row["period"])
        anchor_frame_id = int(row["anchor_frame_id"])
        source_id = request.result_id
        source_kind: Literal["result", "target"] = "result"
    else:
        assert request.target is not None
        match_id = request.target.match_id
        period = request.target.period
        anchor_frame_id = int(round(request.target.approximate_time_ms / 1000.0 * FRAME_RATE_HZ))
        source_id = request.target.target_id
        source_kind = "target"

    replay_window_id = stable_hash(
        {
            "plan_path": request.plan_path,
            "profile": request.compatibility_profile,
            "source_id": source_id,
            "match_id": match_id,
            "period": period,
            "anchor_frame_id": anchor_frame_id,
            "padding_seconds": request.padding_seconds,
        }
    )[:16]
    replay = replay_window_from_canonical(
        replay_window_id=replay_window_id,
        plan_path=Path(request.plan_path),
        source_id=source_id,
        source_kind=source_kind,
        match_id=match_id,
        period=period,
        anchor_frame_id=anchor_frame_id,
        padding_seconds=request.padding_seconds,
    )
    artifact_path = output_root / "replay-windows" / f"{replay_window_id}.json"
    write_json(artifact_path, replay)
    return ReplayWindowResponse(
        ok=True,
        replay_window_id=replay_window_id,
        artifact_path=str(artifact_path),
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
    return RecordFeedbackResponse(ok=True, feedback_id=feedback_id, path=str(path))


def save_experimental_recipe(
    request: SaveExperimentalRecipeRequest,
    *,
    output_root: Path = DEFAULT_WORKSHOP_ROOT,
) -> SaveExperimentalRecipeResponse:
    document = TacticalQueryDocument.model_validate_json(Path(request.plan_path).read_text(encoding="utf-8"))
    query_hash = stable_hash(model_payload(document))
    payload = {
        "schema_version": "1.0",
        "saved_at": utc_now_iso(),
        "state": "EXPERIMENTAL",
        "creator": request.creator,
        "parent_version": request.parent_version,
        "note": request.note,
        "plan_path": request.plan_path,
        "query_hash": query_hash,
        "document": model_payload(document),
    }
    recipe_version_id = query_hash[:16]
    path = output_root / "recipes" / f"{recipe_version_id}.json"
    if path.exists():
        existing = read_json(path)
        if existing.get("query_hash") != query_hash:
            raise RuntimeError(f"Immutable recipe path collision at {path}")
    else:
        write_json(path, payload)
    return SaveExperimentalRecipeResponse(
        ok=True,
        recipe_version_id=recipe_version_id,
        path=str(path),
        query_hash=query_hash,
    )


def compare_query_versions(request: CompareQueryVersionsRequest) -> CompareQueryVersionsResponse:
    before = read_json(Path(request.before_path))
    after = read_json(Path(request.after_path))
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


def validate_safe_agent_plan(bound: Any) -> None:
    for node in bound.nodes:
        if not isinstance(node, BoundPredicateNode):
            continue
        if node.operator.name in SAFE_ANCHOR_RELATIVE_OPERATORS:
            if node.input.output_name != SAFE_ANCHOR_RELATIVE_OUTPUT:
                raise CapabilityGap(
                    f"{node.operator.name} is agent-visible only for "
                    f"{SAFE_ANCHOR_RELATIVE_OUTPUT}; got "
                    f"{node.input.source_node_id}.{node.input.output_name}"
                )


def default_profile_for_plan(plan_status: PlanStatus) -> str:
    return LEGACY_M1_PARITY_PROFILE if plan_status == PlanStatus.APPROVED else GENERIC_EXECUTION_PROFILE


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
    return {
        "name": entry.name,
        "version": entry.version,
        "kind": entry.kind.value if hasattr(entry.kind, "value") else entry.kind,
        "purpose": entry.purpose,
        "outputs": [output.model_dump(mode="json") for output in entry.outputs],
        "parameters": [parameter.model_dump(mode="json", exclude_none=True) for parameter in entry.parameters],
        "limitations": entry.limitations,
        "evidence_fields": entry.evidence_fields,
    }


def tool_spec(name: str) -> ToolSpec:
    descriptions = {
        "list_capabilities": "Return the Hermes-safe capability context.",
        "describe_capability": "Describe one exposed tool, primitive, relation, or operator.",
        "validate_query_plan": "Bind and boundary-check a typed query plan.",
        "execute_query_plan": "Execute a validated plan through the deterministic runtime.",
        "inspect_result": "Return predicate traces and requested evidence for a result.",
        "inspect_non_match": "Evaluate a known timestamp target against a bound plan.",
        "retrieve_replay_window": "Materialize a bounded coordinate replay JSON artifact.",
        "compare_query_versions": "Compute deterministic semantic diffs for two query documents.",
        "record_feedback": "Append immutable analyst feedback for a result or known target.",
        "save_experimental_recipe": "Save a content-addressed experimental recipe version.",
    }
    return ToolSpec(
        name=name,
        description=descriptions[name],
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object", "additionalProperties": False},
        unavailable_surfaces=FORBIDDEN_SURFACES,
    )


def rank_result(row: dict[str, Any], *, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "result_id": str(row["result_id"]),
        "classification": str(row["classification"]),
        "match_id": str(row["match_id"]),
        "period": str(row["period"]),
        "anchor_frame_id": int(row["anchor_frame_id"]),
        "requested_evidence": row.get("requested_evidence", {}),
    }


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
    `${selected.result_id} | frame ${frame.frame_id || "-"} | ${frameIndex+1}/${frames.length} | ${replay.artifact_path}`;
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
