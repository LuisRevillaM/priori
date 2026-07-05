"""Tri-state ordered anchor sequence operator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tqe.runtime.ir import (
    Cardinality,
    CompositionOperatorSignature,
    EntityScope,
    MissingDataSemantics,
    OperatorInputDefinition,
    OperatorOutputDeclaration,
    ParameterDefinition,
    PayloadType,
    TemporalContainer,
    TypedValue,
    Unit,
    stable_hash,
)
from tqe.runtime.values import FrameSignal, RuntimeValue, canonical_anchor_record_id


TRI_STATE_VALUES = ("PASS", "FAIL", "UNKNOWN")
MATCH_POLICY_VALUES = ("first", "all")
OVERLAP_POLICY_VALUES = ("allow_overlaps", "non_overlapping")
WINDOW_BOUNDARY_VALUES = ("exclusive_start_inclusive_end",)
POSSESSION_CONTINUITY_SOURCE_VALUES = ("stage_fields", "observed_possession_stream")
CHAIN_EVIDENCE_FIELDS = [
    "chain_id",
    "chain_status",
    "chain_reason",
    "chain_length",
    "stage_count",
    "match_policy",
    "overlap_policy",
    "window_boundary_policy",
    "frame_rate_hz",
    "same_team_perspective_required",
    "same_possession_required",
    "possession_continuity_source",
    "same_player_required",
    "constraint_opt_out_reason",
    "team_role_field",
    "team_role",
    "match_id",
    "period",
    "perspective_team_role",
    "anchor_id",
    "anchor_frame_id",
    "start_frame_id",
    "end_frame_id",
    "stage_1_anchor_id",
    "stage_1_frame_id",
    "stage_1_start_frame_id",
    "stage_1_end_frame_id",
    "stage_1_status",
    "stage_1_status_field",
    "stage_1_frame_field",
    "stage_1_team_role",
    "stage_1_possession_id",
    "stage_1_player_id",
    "stage_1_record_hash",
    "stage_1_source_node_id",
    "stage_1_source_output_name",
    "stage_2_anchor_id",
    "stage_2_frame_id",
    "stage_2_start_frame_id",
    "stage_2_end_frame_id",
    "stage_2_status",
    "stage_2_status_field",
    "stage_2_frame_field",
    "stage_2_team_role",
    "stage_2_possession_id",
    "stage_2_player_id",
    "stage_2_record_hash",
    "stage_2_source_node_id",
    "stage_2_source_output_name",
    "stage_2_window_start_frame_id",
    "stage_2_window_end_frame_id",
    "stage_2_window_seconds",
    "stage_2_window_truncated",
    "stage_2_candidate_count",
    "stage_2_unknown_candidate_count",
    "stage_2_minimum_numeric_field",
    "stage_2_minimum_numeric_value",
    "stage_3_anchor_id",
    "stage_3_frame_id",
    "stage_3_start_frame_id",
    "stage_3_end_frame_id",
    "stage_3_status",
    "stage_3_status_field",
    "stage_3_frame_field",
    "stage_3_team_role",
    "stage_3_possession_id",
    "stage_3_player_id",
    "stage_3_record_hash",
    "stage_3_source_node_id",
    "stage_3_source_output_name",
    "stage_3_window_start_frame_id",
    "stage_3_window_end_frame_id",
    "stage_3_window_seconds",
    "stage_3_window_truncated",
    "stage_3_candidate_count",
    "stage_3_unknown_candidate_count",
    "witness_stage_count",
    "source_node_id",
    "source_output_name",
    "source_record_count",
    "source_records",
]


def _stage_parameter(name: str, *, required: bool = True, default: str = "none") -> ParameterDefinition:
    return ParameterDefinition(
        name=name,
        payload_type=PayloadType.ENUM,
        required=required,
        default=None if required else TypedValue(payload_type=PayloadType.ENUM, value=default),
        description=f"Declared sequence stage parameter {name}.",
    )


SEQUENCE_PATTERN_SIGNATURE = CompositionOperatorSignature(
    name="sequence_pattern",
    version="0.1.0",
    purpose=(
        "Build tri-state ordered anchor chains across declared stage outputs, "
        "preserving UNKNOWN when successor windows are unobserved or only UNKNOWN candidates match."
    ),
    inputs=[
        OperatorInputDefinition(
            name="stage_1",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="stage_2",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="stage_3",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="chain_records",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=CHAIN_EVIDENCE_FIELDS,
        ),
        OperatorOutputDeclaration(
            name="chain_status",
            temporal_type=TemporalContainer.FRAME_SIGNAL,
            payload_type=PayloadType.ENUM,
            cardinality=Cardinality.SINGLE,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=CHAIN_EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="stage_count",
            payload_type=PayloadType.NUMBER,
            unit=Unit.COUNT,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, value=3, unit=Unit.COUNT),
            minimum=3,
            description="R2-4 sequence_pattern supports exactly three declared stages.",
        ),
        ParameterDefinition(
            name="match_policy",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(MATCH_POLICY_VALUES),
            description="Whether each stage advances by the first matching successor or all successors.",
        ),
        ParameterDefinition(
            name="overlap_policy",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(OVERLAP_POLICY_VALUES),
            description="Whether successor records may be reused by multiple emitted chains.",
        ),
        ParameterDefinition(
            name="window_boundary_policy",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="exclusive_start_inclusive_end"),
            allowed_values=list(WINDOW_BOUNDARY_VALUES),
            description="Successor window is open at the predecessor frame and closed at the declared end frame.",
        ),
        ParameterDefinition(
            name="frame_rate_hz",
            payload_type=PayloadType.NUMBER,
            unit=Unit.HERTZ,
            required=True,
            minimum=0.001,
            description="Frame rate used to convert declared stage windows from seconds to frames.",
        ),
        ParameterDefinition(
            name="stage_2_window_seconds",
            payload_type=PayloadType.NUMBER,
            unit=Unit.SECOND,
            required=True,
            minimum=0.0,
            description="Maximum time from stage 1 reference frame to stage 2 anchor frame.",
        ),
        ParameterDefinition(
            name="stage_3_window_seconds",
            payload_type=PayloadType.NUMBER,
            unit=Unit.SECOND,
            required=True,
            minimum=0.0,
            description="Maximum time from stage 2 reference frame to stage 3 anchor frame.",
        ),
        _stage_parameter("stage_1_status_field"),
        _stage_parameter("stage_2_status_field"),
        _stage_parameter("stage_3_status_field"),
        _stage_parameter("stage_1_frame_field"),
        _stage_parameter("stage_2_frame_field"),
        _stage_parameter("stage_3_frame_field"),
        _stage_parameter("stage_1_end_frame_field", required=False),
        _stage_parameter("stage_2_end_frame_field", required=False),
        _stage_parameter("stage_3_end_frame_field", required=False),
        _stage_parameter("stage_1_team_role_field"),
        _stage_parameter("stage_2_team_role_field"),
        _stage_parameter("stage_3_team_role_field"),
        _stage_parameter("stage_1_possession_id_field", required=False),
        _stage_parameter("stage_2_possession_id_field", required=False),
        _stage_parameter("stage_3_possession_id_field", required=False),
        _stage_parameter("stage_1_player_id_field", required=False),
        _stage_parameter("stage_2_player_id_field", required=False),
        _stage_parameter("stage_3_player_id_field", required=False),
        _stage_parameter("stage_2_minimum_numeric_field", required=False),
        ParameterDefinition(
            name="stage_2_minimum_numeric_value",
            payload_type=PayloadType.NUMBER,
            unit=Unit.NONE,
            required=False,
            default=TypedValue(payload_type=PayloadType.NUMBER, value=0.0, unit=Unit.NONE),
            description="Minimum numeric threshold for stage 2 when a field is declared.",
        ),
        ParameterDefinition(
            name="same_team_perspective_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=True),
            description="Require all stage witnesses to share the declared team role.",
        ),
        ParameterDefinition(
            name="same_possession_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Require all stage witnesses to share declared possession identity fields.",
        ),
        ParameterDefinition(
            name="possession_continuity_source",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="stage_fields"),
            allowed_values=list(POSSESSION_CONTINUITY_SOURCE_VALUES),
            description="Source for same-possession continuity when stage fields do not expose a possession id.",
        ),
        ParameterDefinition(
            name="same_player_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=False),
            description="Require all stage witnesses to share declared player identity fields.",
        ),
        ParameterDefinition(
            name="constraint_opt_out_reason",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Required when same-team perspective is explicitly disabled.",
        ),
        ParameterDefinition(
            name="team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="team_role"),
            description="Canonical team-role field echoed for aggregate/rate grouping.",
        ),
    ],
    coverage_propagation_rule_id="sequence_successor_unknown_preserved",
    witness_rule_id="sequence_stage_witnesses",
    limitations=[
        "R2-4 supports three-stage chains; variable-length authoring is future work.",
        "Window start is exclusive and window end is inclusive.",
        "A fully observed empty successor window is FAIL; truncated windows and UNKNOWN-status candidates are UNKNOWN.",
    ],
)


@dataclass(frozen=True)
class StageSpec:
    index: int
    status_field: str
    frame_field: str
    end_frame_field: str
    team_role_field: str
    possession_id_field: str
    player_id_field: str


@dataclass(frozen=True)
class SequenceConfig:
    match_policy: str
    overlap_policy: str
    window_boundary_policy: str
    frame_rate_hz: float
    stage_2_window_seconds: float
    stage_3_window_seconds: float
    same_team_perspective_required: bool
    same_possession_required: bool
    possession_continuity_source: str
    same_player_required: bool
    constraint_opt_out_reason: str
    team_role_field: str
    stage_2_minimum_numeric_field: str
    stage_2_minimum_numeric_value: float
    stage_specs: tuple[StageSpec, StageSpec, StageSpec]


def execute_sequence_pattern(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    config = _sequence_config(parameters)
    if config.window_boundary_policy != "exclusive_start_inclusive_end":
        raise ValueError("sequence_pattern supports exclusive_start_inclusive_end windows only")
    stage_records = {
        index: _sorted_records(_runtime_records(inputs.get(f"stage_{index}")), config.stage_specs[index - 1])
        for index in (1, 2, 3)
    }
    observed_frames = _observed_frames(state, stage_records)
    period_end_frame = max(observed_frames) if observed_frames else 0
    used_successors: dict[int, set[str]] = {2: set(), 3: set()}
    chain_records: list[dict[str, Any]] = []
    source_refs = {
        index: node.inputs[f"stage_{index}"]
        for index in (1, 2, 3)
        if f"stage_{index}" in getattr(node, "inputs", {})
    }

    for seed in stage_records[1]:
        seed_status = _tri_state(seed, config.stage_specs[0].status_field)
        if seed_status != "PASS":
            chain_records.append(
                _chain_record(
                    state=state,
                    config=config,
                    source_refs=source_refs,
                    witnesses=[seed],
                    terminal_stage=1,
                    chain_status="UNKNOWN" if seed_status == "UNKNOWN" else "FAIL",
                    chain_reason=f"stage_1_{seed_status.lower()}",
                    windows={},
                )
            )
            continue
        partials = [([seed], {})]
        terminal_records: list[dict[str, Any]] = []
        for next_stage in (2, 3):
            next_partials: list[tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]] = []
            for witnesses, windows in partials:
                predecessor = witnesses[-1]
                predecessor_spec = config.stage_specs[next_stage - 2]
                reference_frame = _reference_frame(predecessor, predecessor_spec)
                window_seconds = config.stage_2_window_seconds if next_stage == 2 else config.stage_3_window_seconds
                window_end = reference_frame + int(round(window_seconds * config.frame_rate_hz))
                window = {
                    "window_start_frame_id": reference_frame + 1,
                    "window_end_frame_id": window_end,
                    "window_seconds": window_seconds,
                    "window_truncated": not _window_fully_observed(
                        observed_frames=observed_frames,
                        start_frame=reference_frame + 1,
                        end_frame=window_end,
                        period_end_frame=period_end_frame,
                    ),
                    "candidate_count": 0,
                    "unknown_candidate_count": 0,
                }
                candidates = _stage_candidates(
                    records=stage_records[next_stage],
                    state=state,
                    config=config,
                    witnesses=witnesses,
                    stage_index=next_stage,
                    reference_frame=reference_frame,
                    window_end=window_end,
                    used_successors=used_successors[next_stage],
                )
                window["candidate_count"] = len(candidates)
                pass_candidates = [record for record in candidates if _tri_state(record, config.stage_specs[next_stage - 1].status_field) == "PASS"]
                unknown_candidates = [record for record in candidates if _tri_state(record, config.stage_specs[next_stage - 1].status_field) == "UNKNOWN"]
                window["unknown_candidate_count"] = len(unknown_candidates)
                if pass_candidates:
                    selected = pass_candidates[:1] if config.match_policy == "first" else pass_candidates
                    for candidate in selected:
                        successor_key = _record_identity(candidate)
                        if config.overlap_policy == "non_overlapping":
                            used_successors[next_stage].add(successor_key)
                        next_partials.append(([*witnesses, candidate], {**windows, next_stage: window}))
                    continue
                if unknown_candidates:
                    terminal_records.append(
                        _chain_record(
                            state=state,
                            config=config,
                            source_refs=source_refs,
                            witnesses=[*witnesses, unknown_candidates[0]],
                            terminal_stage=next_stage,
                            chain_status="UNKNOWN",
                            chain_reason=f"stage_{next_stage}_unknown_candidate",
                            windows={**windows, next_stage: window},
                        )
                    )
                    continue
                terminal_records.append(
                    _chain_record(
                        state=state,
                        config=config,
                        source_refs=source_refs,
                        witnesses=witnesses,
                        terminal_stage=next_stage,
                        chain_status="UNKNOWN" if window["window_truncated"] else "FAIL",
                        chain_reason=(
                            f"stage_{next_stage}_window_truncated"
                            if window["window_truncated"]
                            else f"stage_{next_stage}_fully_observed_empty_window"
                        ),
                        windows={**windows, next_stage: window},
                    )
                )
            partials = next_partials
            if not partials:
                break
        for witnesses, windows in partials:
            terminal_records.append(
                _chain_record(
                    state=state,
                    config=config,
                    source_refs=source_refs,
                    witnesses=witnesses,
                    terminal_stage=3,
                    chain_status="PASS",
                    chain_reason="all_stages_pass",
                    windows=windows,
                )
            )
        chain_records.extend(terminal_records)

    chain_records.sort(
        key=lambda record: (
            str(record.get("match_id") or ""),
            str(record.get("period") or ""),
            str(record.get("team_role") or ""),
            int(record.get("anchor_frame_id") or 0),
            str(record.get("chain_id") or ""),
        )
    )
    frame_ids = [int(record["anchor_frame_id"]) for record in chain_records]
    status_values = [
        None if str(record["chain_status"]) == "UNKNOWN" else str(record["chain_status"])
        for record in chain_records
    ]
    state.signals[node.node_id] = {
        "chain_records": chain_records,
        "chain_records_records": chain_records,
        "chain_status": FrameSignal(
            frame_ids=frame_ids,
            values=status_values,
            unknown_mask=[value is None for value in status_values],
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        "chain_status_records": chain_records,
    }


def _sequence_config(parameters: dict[str, TypedValue]) -> SequenceConfig:
    stage_count = int(round(_number(parameters, "stage_count", 3)))
    if stage_count != 3:
        raise ValueError("sequence_pattern R2-4 supports exactly three stages")
    if not _boolean(parameters, "same_team_perspective_required", True) and _enum(parameters, "constraint_opt_out_reason", "none") == "none":
        raise ValueError("sequence_pattern same-team opt-out requires constraint_opt_out_reason")
    specs = tuple(
        StageSpec(
            index=index,
            status_field=_enum(parameters, f"stage_{index}_status_field"),
            frame_field=_enum(parameters, f"stage_{index}_frame_field"),
            end_frame_field=_enum(parameters, f"stage_{index}_end_frame_field", "none"),
            team_role_field=_enum(parameters, f"stage_{index}_team_role_field"),
            possession_id_field=_enum(parameters, f"stage_{index}_possession_id_field", "none"),
            player_id_field=_enum(parameters, f"stage_{index}_player_id_field", "none"),
        )
        for index in (1, 2, 3)
    )
    return SequenceConfig(
        match_policy=_enum(parameters, "match_policy"),
        overlap_policy=_enum(parameters, "overlap_policy"),
        window_boundary_policy=_enum(parameters, "window_boundary_policy", "exclusive_start_inclusive_end"),
        frame_rate_hz=_number(parameters, "frame_rate_hz"),
        stage_2_window_seconds=_number(parameters, "stage_2_window_seconds"),
        stage_3_window_seconds=_number(parameters, "stage_3_window_seconds"),
        same_team_perspective_required=_boolean(parameters, "same_team_perspective_required", True),
        same_possession_required=_boolean(parameters, "same_possession_required", False),
        possession_continuity_source=_enum(parameters, "possession_continuity_source", "stage_fields"),
        same_player_required=_boolean(parameters, "same_player_required", False),
        constraint_opt_out_reason=_enum(parameters, "constraint_opt_out_reason", "none"),
        team_role_field=_enum(parameters, "team_role_field", "team_role"),
        stage_2_minimum_numeric_field=_enum(parameters, "stage_2_minimum_numeric_field", "none"),
        stage_2_minimum_numeric_value=_number(parameters, "stage_2_minimum_numeric_value", 0.0),
        stage_specs=specs,  # type: ignore[arg-type]
    )


def _runtime_records(value: RuntimeValue | None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if value.records:
        return [record for record in value.records if isinstance(record, dict)]
    if isinstance(value.value, list):
        return [record for record in value.value if isinstance(record, dict)]
    return []


def _sorted_records(records: list[dict[str, Any]], spec: StageSpec) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: (_frame(record, spec.frame_field), _record_identity(record)))


def _stage_candidates(
    *,
    records: list[dict[str, Any]],
    state: Any,
    config: SequenceConfig,
    witnesses: list[dict[str, Any]],
    stage_index: int,
    reference_frame: int,
    window_end: int,
    used_successors: set[str],
) -> list[dict[str, Any]]:
    spec = config.stage_specs[stage_index - 1]
    result = []
    for record in records:
        frame = _frame(record, spec.frame_field)
        if frame <= reference_frame or frame > window_end:
            continue
        if config.overlap_policy == "non_overlapping" and _record_identity(record) in used_successors:
            continue
        if stage_index == 2 and not _minimum_numeric_satisfied(record, config):
            continue
        if not _continuity_satisfied(witnesses[0], record, state=state, config=config, stage_index=stage_index):
            continue
        result.append(record)
    return sorted(result, key=lambda item: (_frame(item, spec.frame_field), _record_identity(item)))


def _continuity_satisfied(
    first: dict[str, Any],
    candidate: dict[str, Any],
    *,
    state: Any,
    config: SequenceConfig,
    stage_index: int,
) -> bool:
    first_spec = config.stage_specs[0]
    candidate_spec = config.stage_specs[stage_index - 1]
    if config.same_team_perspective_required and _field(first, first_spec.team_role_field) != _field(candidate, candidate_spec.team_role_field):
        return False
    if config.same_possession_required:
        first_possession = _possession_identity(first, first_spec, state=state, config=config)
        candidate_possession = _possession_identity(candidate, candidate_spec, state=state, config=config)
        if first_possession is None or candidate_possession is None:
            return False
        if first_possession != candidate_possession:
            return False
    if config.same_player_required:
        if first_spec.player_id_field == "none" or candidate_spec.player_id_field == "none":
            return False
        if _field(first, first_spec.player_id_field) != _field(candidate, candidate_spec.player_id_field):
            return False
    return True


def _possession_identity(
    record: dict[str, Any],
    spec: StageSpec,
    *,
    state: Any,
    config: SequenceConfig,
) -> str | None:
    declared = _field(record, spec.possession_id_field)
    if declared is not None:
        return declared
    if config.possession_continuity_source != "observed_possession_stream":
        return None
    team_role = _field(record, spec.team_role_field)
    if team_role is None:
        return None
    return _state_possession_identity(state, frame_id=_frame(record, spec.frame_field), team_role=team_role)


def _state_possession_identity(state: Any, *, frame_id: int, team_role: str) -> str | None:
    raw_frame_ids = getattr(state, "frame_ids", None)
    raw_possession_role = getattr(state, "possession_role", None)
    raw_ball_alive = getattr(state, "ball_alive", None)
    frame_ids = [] if raw_frame_ids is None else list(raw_frame_ids)
    possession_role = [] if raw_possession_role is None else list(raw_possession_role)
    ball_alive = [] if raw_ball_alive is None else list(raw_ball_alive)
    if not frame_ids or not possession_role or len(frame_ids) != len(possession_role):
        return None
    try:
        index = next(idx for idx, value in enumerate(frame_ids) if int(value) == int(frame_id))
    except StopIteration:
        return None
    if str(possession_role[index]) != str(team_role):
        return None
    if ball_alive and not bool(ball_alive[index]):
        return None
    start = index
    while start > 0 and str(possession_role[start - 1]) == str(team_role):
        if ball_alive and not bool(ball_alive[start - 1]):
            break
        start -= 1
    match_id = str(getattr(state, "match_id", ""))
    period = str(getattr(state, "period", ""))
    return f"possession:{match_id}:{period}:{team_role}:{int(frame_ids[start])}"


def _minimum_numeric_satisfied(record: dict[str, Any], config: SequenceConfig) -> bool:
    field = config.stage_2_minimum_numeric_field
    if field == "none":
        return True
    raw = record.get(field)
    try:
        return float(raw) >= float(config.stage_2_minimum_numeric_value)
    except (TypeError, ValueError):
        return False


def _window_fully_observed(
    *,
    observed_frames: set[int],
    start_frame: int,
    end_frame: int,
    period_end_frame: int,
) -> bool:
    if end_frame < start_frame:
        return True
    if end_frame > period_end_frame:
        return False
    if not observed_frames:
        return False
    return all(frame in observed_frames for frame in range(start_frame, end_frame + 1))


def _observed_frames(state: Any, stage_records: dict[int, list[dict[str, Any]]]) -> set[int]:
    frame_ids = getattr(state, "frame_ids", None)
    if frame_ids is not None:
        return {int(frame) for frame in frame_ids}
    frames: set[int] = set()
    for records in stage_records.values():
        for record in records:
            for key in (
                "anchor_frame_id",
                "start_frame_id",
                "end_frame_id",
                "transition_frame_id",
                "carry_start_frame_id",
                "carry_end_frame_id",
                "controlled_reception_frame_id",
            ):
                if key in record and record[key] is not None:
                    frames.add(int(record[key]))
    return frames


def _chain_record(
    *,
    state: Any,
    config: SequenceConfig,
    source_refs: dict[int, Any],
    witnesses: list[dict[str, Any]],
    terminal_stage: int,
    chain_status: str,
    chain_reason: str,
    windows: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    del terminal_stage
    first = witnesses[0]
    first_spec = config.stage_specs[0]
    team_role = _field(first, first_spec.team_role_field)
    end_frame = _frame(witnesses[-1], config.stage_specs[len(witnesses) - 1].frame_field)
    if len(witnesses) == 3:
        end_frame = _reference_frame(witnesses[-1], config.stage_specs[2])
    payload: dict[str, Any] = {
        "match_id": str(getattr(state, "match_id", first.get("match_id", ""))),
        "period": str(getattr(state, "period", first.get("period", ""))),
        "perspective_team_role": str(getattr(state, "perspective_team_role", first.get("perspective_team_role", team_role))),
        "team_role": team_role,
        "entity_refs": [team_role] if team_role is not None else [],
        "anchor_frame_id": _frame(first, first_spec.frame_field),
        "start_frame_id": _frame(first, first_spec.frame_field),
        "end_frame_id": end_frame,
        "chain_status": chain_status,
        "chain_reason": chain_reason,
        "chain_length": len(witnesses),
        "stage_count": 3,
        "match_policy": config.match_policy,
        "overlap_policy": config.overlap_policy,
        "window_boundary_policy": config.window_boundary_policy,
        "frame_rate_hz": config.frame_rate_hz,
        "same_team_perspective_required": config.same_team_perspective_required,
        "same_possession_required": config.same_possession_required,
        "possession_continuity_source": config.possession_continuity_source,
        "same_player_required": config.same_player_required,
        "constraint_opt_out_reason": config.constraint_opt_out_reason,
        "team_role_field": config.team_role_field,
        "witness_stage_count": len(witnesses),
        "source_node_id": getattr(source_refs.get(1), "source_node_id", None),
        "source_output_name": getattr(source_refs.get(1), "output_name", None),
        "source_record_count": len(witnesses),
        "source_records": witnesses,
    }
    for index in (1, 2, 3):
        spec = config.stage_specs[index - 1]
        witness = witnesses[index - 1] if len(witnesses) >= index else None
        source_ref = source_refs.get(index)
        _add_stage_witness(payload, index=index, spec=spec, witness=witness, source_ref=source_ref)
        if index in (2, 3):
            window = windows.get(index, {})
            payload[f"stage_{index}_window_start_frame_id"] = window.get("window_start_frame_id")
            payload[f"stage_{index}_window_end_frame_id"] = window.get("window_end_frame_id")
            payload[f"stage_{index}_window_seconds"] = window.get("window_seconds")
            payload[f"stage_{index}_window_truncated"] = bool(window.get("window_truncated", False))
            payload[f"stage_{index}_candidate_count"] = int(window.get("candidate_count", 0))
            payload[f"stage_{index}_unknown_candidate_count"] = int(window.get("unknown_candidate_count", 0))
    payload["stage_2_minimum_numeric_field"] = config.stage_2_minimum_numeric_field
    payload["stage_2_minimum_numeric_value"] = config.stage_2_minimum_numeric_value
    payload["chain_id"] = stable_hash(
        {
            "operator": "sequence_pattern",
            "match_id": payload["match_id"],
            "period": payload["period"],
            "status": chain_status,
            "reason": chain_reason,
            "witness_ids": [payload.get(f"stage_{index}_anchor_id") for index in (1, 2, 3)],
            "windows": windows,
        }
    )[:16]
    payload["anchor_id"] = canonical_anchor_record_id(payload)
    return payload


def _add_stage_witness(
    payload: dict[str, Any],
    *,
    index: int,
    spec: StageSpec,
    witness: dict[str, Any] | None,
    source_ref: Any,
) -> None:
    prefix = f"stage_{index}"
    payload[f"{prefix}_status_field"] = spec.status_field
    payload[f"{prefix}_frame_field"] = spec.frame_field
    payload[f"{prefix}_source_node_id"] = getattr(source_ref, "source_node_id", None)
    payload[f"{prefix}_source_output_name"] = getattr(source_ref, "output_name", None)
    if witness is None:
        payload[f"{prefix}_anchor_id"] = None
        payload[f"{prefix}_frame_id"] = None
        payload[f"{prefix}_start_frame_id"] = None
        payload[f"{prefix}_end_frame_id"] = None
        payload[f"{prefix}_status"] = None
        payload[f"{prefix}_team_role"] = None
        payload[f"{prefix}_possession_id"] = None
        payload[f"{prefix}_player_id"] = None
        payload[f"{prefix}_record_hash"] = None
        return
    payload[f"{prefix}_anchor_id"] = str(witness.get("anchor_id") or _record_identity(witness))
    payload[f"{prefix}_frame_id"] = _frame(witness, spec.frame_field)
    payload[f"{prefix}_start_frame_id"] = _optional_frame(witness, "start_frame_id") or _optional_frame(witness, spec.frame_field)
    payload[f"{prefix}_end_frame_id"] = _reference_frame(witness, spec)
    payload[f"{prefix}_status"] = _tri_state(witness, spec.status_field)
    payload[f"{prefix}_team_role"] = _field(witness, spec.team_role_field)
    payload[f"{prefix}_possession_id"] = _field(witness, spec.possession_id_field)
    payload[f"{prefix}_player_id"] = _field(witness, spec.player_id_field)
    payload[f"{prefix}_record_hash"] = stable_hash(witness)


def _reference_frame(record: dict[str, Any], spec: StageSpec) -> int:
    if spec.end_frame_field != "none" and record.get(spec.end_frame_field) is not None:
        return int(record[spec.end_frame_field])
    return _frame(record, spec.frame_field)


def _frame(record: dict[str, Any], field: str) -> int:
    value = record.get(field)
    if value is None:
        value = record.get("anchor_frame_id")
    return int(value)


def _optional_frame(record: dict[str, Any], field: str) -> int | None:
    value = record.get(field)
    return None if value is None else int(value)


def _tri_state(record: dict[str, Any], field: str) -> str:
    raw = record.get(field)
    status = "UNKNOWN" if raw is None else str(raw)
    if status not in set(TRI_STATE_VALUES):
        raise ValueError(f"sequence_pattern status field {field} must be PASS/FAIL/UNKNOWN")
    return status


def _field(record: dict[str, Any], field: str) -> str | None:
    if field == "none":
        return None
    value = record.get(field)
    return None if value is None else str(value)


def _record_identity(record: dict[str, Any]) -> str:
    return str(record.get("anchor_id") or record.get("chain_id") or stable_hash(record)[:16])


def _enum(parameters: dict[str, TypedValue], name: str, default: str | None = None) -> str:
    value = parameters.get(name)
    if value is None:
        if default is None:
            raise ValueError(f"sequence_pattern missing parameter {name}")
        return default
    return str(value.value)


def _number(parameters: dict[str, TypedValue], name: str, default: float | None = None) -> float:
    value = parameters.get(name)
    if value is None:
        if default is None:
            raise ValueError(f"sequence_pattern missing parameter {name}")
        return float(default)
    return float(value.value)


def _boolean(parameters: dict[str, TypedValue], name: str, default: bool) -> bool:
    value = parameters.get(name)
    if value is None:
        return bool(default)
    return bool(value.value)
