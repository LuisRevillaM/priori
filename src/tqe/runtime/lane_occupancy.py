"""Pure lateral lane-occupancy evaluation.

This module classifies selected player position records into declared lateral
pitch lanes. It does not infer player intention, support quality, tactical
optimality, defensive-line breaks, or role semantics.

The default model uses centered football pitch coordinates over a 68m width:
``y_m=-34`` is the left touchline and ``y_m=34`` is the right touchline. Lane
boundaries are lower-inclusive and upper-exclusive except the final lane, which
includes the right touchline.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

LEFT_WIDE = "LEFT_WIDE"
LEFT_HALF_SPACE = "LEFT_HALF_SPACE"
CENTRAL = "CENTRAL"
RIGHT_HALF_SPACE = "RIGHT_HALF_SPACE"
RIGHT_WIDE = "RIGHT_WIDE"

DEFAULT_PITCH_WIDTH_M = 68.0
DEFAULT_LANE_IDS = (LEFT_WIDE, LEFT_HALF_SPACE, CENTRAL, RIGHT_HALF_SPACE, RIGHT_WIDE)

Status = str
FrameId = int | str | None


class LaneOccupancyStatus(str, Enum):
    PASS = PASS
    FAIL = FAIL
    UNKNOWN = UNKNOWN


class LaneOccupancyReason(str, Enum):
    OCCUPANCY_CLASSIFIED = "lane_occupancy_classified"
    REQUIREMENT_SATISFIED = "lane_requirement_satisfied"
    REQUIREMENT_NOT_MET = "lane_requirement_not_met"
    PLAYER_POSITIONS_MISSING = "player_positions_missing"
    NO_TARGET_PLAYERS = "no_target_players"
    TARGET_PLAYER_IDS_CONFLICT = "target_player_ids_conflict"
    INVALID_TARGET_PLAYER_IDS = "invalid_target_player_ids"
    UNKNOWN_REQUIRED_LANE_IDS = "unknown_required_lane_ids"
    INVALID_REQUIRED_LANE_COUNTS = "invalid_required_lane_counts"
    INVALID_REQUIRED_OCCUPIED_LANE_COUNT = "invalid_required_occupied_lane_count"
    LANE_DEFINITION_INVALID = "lane_definition_invalid"
    MISSING_TARGET_PLAYER_EVIDENCE = "missing_target_player_evidence"
    INVALID_PLAYER_IDS = "invalid_player_ids"
    INVALID_PLAYER_COORDINATES = "invalid_player_coordinates"
    DUPLICATE_PLAYER_POSITION_RECORDS = "duplicate_player_position_records"
    PLAYER_OUTSIDE_DEFINED_LANES = "player_outside_defined_lanes"


@dataclass(frozen=True)
class LaneDefinition:
    lane_id: str
    min_y_m: float
    max_y_m: float
    includes_min_y: bool
    includes_max_y: bool
    ordinal: int


@dataclass(frozen=True)
class LaneOccupancyConfig:
    pitch_width_m: float = DEFAULT_PITCH_WIDTH_M
    lane_definitions: tuple[LaneDefinition, ...] | None = None
    coordinate_system: str = "centered_pitch_y_negative_left_positive_right"


@dataclass(frozen=True)
class PlayerLaneAssignment:
    player_id: str
    lane_id: str
    frame_id: FrameId
    x_m: float
    y_m: float
    team_role: str | None


@dataclass(frozen=True)
class FrameLaneCounts:
    frame_id: FrameId
    occupied_lanes: tuple[str, ...]
    lane_counts: dict[str, int]


@dataclass(frozen=True)
class LaneOccupancyEvaluation:
    status: Status
    reason: str | None
    anchor_id: str | None
    anchor_frame_id: FrameId
    frame_ids: tuple[FrameId, ...]
    occupied_lanes: tuple[str, ...]
    lane_counts: dict[str, int]
    frame_lane_counts: tuple[FrameLaneCounts, ...]
    player_assignments: tuple[PlayerLaneAssignment, ...]
    target_player_ids: tuple[str, ...]
    evaluated_player_ids: tuple[str, ...]
    missing_player_ids: tuple[str, ...]
    invalid_player_ids: tuple[str, ...]
    invalid_coordinate_player_ids: tuple[str, ...]
    duplicate_player_ids: tuple[str, ...]
    outside_lane_player_ids: tuple[str, ...]
    unknown_lane_ids: tuple[str, ...]
    required_lane_ids: tuple[str, ...]
    required_lane_counts: dict[str, int]
    required_occupied_lane_count: int | None
    selected_record_count: int
    evaluated_record_count: int
    invalid_record_count: int
    coverage_status: str
    lane_definitions: tuple[LaneDefinition, ...]
    pitch_width_m: float | None
    coordinate_system: str
    boundary_policy: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _PlayerRecord:
    index: int
    player_id: str
    frame_id: FrameId
    x_m: float | None
    y_m: float | None
    team_role: str | None
    coordinate_invalid: bool


def evaluate_lane_occupancy(
    *,
    player_positions: Sequence[object] | None,
    target_player_ids: Sequence[object] | None = None,
    expected_player_ids: Sequence[object] | None = None,
    required_lane_ids: Sequence[object] | None = None,
    required_lane_counts: Mapping[object, object] | None = None,
    required_occupied_lane_count: object | None = None,
    anchor_id: str | None = None,
    anchor_frame_id: FrameId = None,
    frame_id: FrameId = None,
    frame_ids: Sequence[object] | None = None,
    config: LaneOccupancyConfig = LaneOccupancyConfig(),
) -> LaneOccupancyEvaluation:
    """Classify selected player records into lateral pitch lanes.

    ``target_player_ids`` and ``expected_player_ids`` are aliases. When neither
    is supplied, all valid supplied player records in the selected frame scope
    are evaluated. Requirements are evaluated against aggregate selected
    records; multi-frame callers should inspect ``frame_lane_counts`` when they
    need per-frame evidence.
    """

    lane_definitions, lane_reason = _resolve_lane_definitions(config)
    lane_order = {definition.lane_id: definition.ordinal for definition in lane_definitions}
    requested_frame_ids = _resolve_frame_filter(frame_id=frame_id, frame_ids=frame_ids)
    resolved_anchor_frame_id = anchor_frame_id if anchor_frame_id is not None else _single_frame_id(requested_frame_ids)

    target_ids, invalid_target_ids, target_reason = _resolve_target_ids(
        target_player_ids=target_player_ids,
        expected_player_ids=expected_player_ids,
    )
    normalized_required_lane_ids = _normalize_lane_id_sequence(required_lane_ids)
    normalized_required_lane_counts, invalid_count_lanes = _normalize_required_lane_counts(required_lane_counts)
    normalized_required_occupied_lane_count = _normalize_required_occupied_lane_count(required_occupied_lane_count)

    raw_records = list(player_positions or ())
    selected_raw_records = [
        (index, record)
        for index, record in enumerate(raw_records)
        if _record_in_frame_scope(record, requested_frame_ids)
    ]
    invalid_record_ids: list[str] = []
    records: list[_PlayerRecord] = []
    for index, record in selected_raw_records:
        player_id, player_id_invalid = _coerce_player_id(
            _first_field(record, "player_id", "entity_id"),
            fallback=f"record[{index}]",
        )
        if player_id_invalid:
            invalid_record_ids.append(player_id)
            continue
        x_m, x_invalid = _required_float(_first_field(record, "x_m", "x"))
        y_m, y_invalid = _required_float(_first_field(record, "y_m", "y"))
        records.append(
            _PlayerRecord(
                index=index,
                player_id=player_id,
                frame_id=_frame_id_from_record(record),
                x_m=x_m,
                y_m=y_m,
                team_role=_string_or_none(_first_field(record, "team_role")),
                coordinate_invalid=x_invalid or y_invalid,
            )
        )

    supplied_ids = tuple(sorted({record.player_id for record in records}, key=_stable_sort_key))
    if target_ids is None:
        selected_target_ids = supplied_ids
        all_supplied_players_selected = True
    else:
        selected_target_ids = target_ids
        all_supplied_players_selected = False

    selected_records = [record for record in records if record.player_id in set(selected_target_ids)]
    selected_record_count = len(selected_records)
    duplicate_player_ids = _duplicate_player_ids(selected_records)
    missing_player_ids = tuple(
        sorted(set(selected_target_ids) - {record.player_id for record in selected_records}, key=_stable_sort_key)
    )

    invalid_coordinate_player_ids = tuple(
        sorted({record.player_id for record in selected_records if record.coordinate_invalid}, key=_stable_sort_key)
    )
    duplicate_keys = _duplicate_keys(selected_records)
    classifiable_records = [
        record
        for record in selected_records
        if not record.coordinate_invalid and (record.frame_id, record.player_id) not in duplicate_keys
    ]

    assignments: list[PlayerLaneAssignment] = []
    outside_lane_player_ids: list[str] = []
    for record in classifiable_records:
        lane_id = _lane_id_for_y(record.y_m, lane_definitions) if record.y_m is not None else None
        if lane_id is None:
            outside_lane_player_ids.append(record.player_id)
            continue
        assignments.append(
            PlayerLaneAssignment(
                player_id=record.player_id,
                lane_id=lane_id,
                frame_id=record.frame_id,
                x_m=float(record.x_m),
                y_m=float(record.y_m),
                team_role=record.team_role,
            )
        )

    assignments_tuple = tuple(
        sorted(assignments, key=lambda item: (_stable_sort_key(item.frame_id), _stable_sort_key(item.player_id)))
    )
    lane_counts = _lane_counts(assignments_tuple, lane_definitions)
    occupied_lanes = tuple(definition.lane_id for definition in lane_definitions if lane_counts[definition.lane_id] > 0)
    frame_lane_counts = _frame_lane_counts(assignments_tuple, lane_definitions, requested_frame_ids)
    evaluated_player_ids = tuple(sorted({item.player_id for item in assignments_tuple}, key=_stable_sort_key))

    known_lane_ids = set(lane_order)
    unknown_lane_ids = tuple(
        sorted(
            (set(normalized_required_lane_ids) | set(normalized_required_lane_counts)) - known_lane_ids,
            key=_stable_sort_key,
        )
    )

    invalid_player_ids = tuple(
        sorted(
            set(invalid_target_ids) | (set(invalid_record_ids) if all_supplied_players_selected else set()),
            key=_stable_sort_key,
        )
    )
    outside_lane_player_ids_tuple = tuple(sorted(set(outside_lane_player_ids), key=_stable_sort_key))
    invalid_record_count = (
        len(invalid_record_ids)
        + len(invalid_coordinate_player_ids)
        + len(duplicate_player_ids)
        + len(outside_lane_player_ids_tuple)
    )

    base = {
        "anchor_id": anchor_id,
        "anchor_frame_id": resolved_anchor_frame_id,
        "frame_ids": _result_frame_ids(records=records, requested_frame_ids=requested_frame_ids),
        "occupied_lanes": occupied_lanes,
        "lane_counts": lane_counts,
        "frame_lane_counts": frame_lane_counts,
        "player_assignments": assignments_tuple,
        "target_player_ids": selected_target_ids,
        "evaluated_player_ids": evaluated_player_ids,
        "missing_player_ids": missing_player_ids,
        "invalid_player_ids": invalid_player_ids,
        "invalid_coordinate_player_ids": invalid_coordinate_player_ids,
        "duplicate_player_ids": duplicate_player_ids,
        "outside_lane_player_ids": outside_lane_player_ids_tuple,
        "unknown_lane_ids": unknown_lane_ids,
        "required_lane_ids": normalized_required_lane_ids,
        "required_lane_counts": _ordered_lane_count_requirements(normalized_required_lane_counts, lane_definitions),
        "required_occupied_lane_count": normalized_required_occupied_lane_count,
        "selected_record_count": selected_record_count,
        "evaluated_record_count": len(assignments_tuple),
        "invalid_record_count": invalid_record_count,
        "lane_definitions": lane_definitions,
        "pitch_width_m": _pitch_width_or_none(config.pitch_width_m),
        "coordinate_system": str(config.coordinate_system),
        "boundary_policy": "min_y_inclusive_max_y_exclusive_except_final_lane",
    }

    if lane_reason is not None:
        return _evaluation(UNKNOWN, lane_reason, {**base, "coverage_status": UNKNOWN})
    if player_positions is None or len(raw_records) == 0:
        return _evaluation(UNKNOWN, LaneOccupancyReason.PLAYER_POSITIONS_MISSING.value, {**base, "coverage_status": UNKNOWN})
    if target_reason is not None:
        return _evaluation(UNKNOWN, target_reason, {**base, "coverage_status": UNKNOWN})
    if normalized_required_occupied_lane_count is None and required_occupied_lane_count is not None:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.INVALID_REQUIRED_OCCUPIED_LANE_COUNT.value,
            {**base, "coverage_status": UNKNOWN},
        )
    if invalid_count_lanes:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.INVALID_REQUIRED_LANE_COUNTS.value,
            {**base, "coverage_status": UNKNOWN},
        )
    if unknown_lane_ids:
        return _evaluation(UNKNOWN, LaneOccupancyReason.UNKNOWN_REQUIRED_LANE_IDS.value, {**base, "coverage_status": UNKNOWN})
    if not selected_target_ids:
        return _evaluation(UNKNOWN, LaneOccupancyReason.NO_TARGET_PLAYERS.value, {**base, "coverage_status": UNKNOWN})
    if invalid_player_ids:
        return _evaluation(UNKNOWN, LaneOccupancyReason.INVALID_PLAYER_IDS.value, {**base, "coverage_status": UNKNOWN})
    if missing_player_ids:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.MISSING_TARGET_PLAYER_EVIDENCE.value,
            {**base, "coverage_status": UNKNOWN},
        )
    if invalid_coordinate_player_ids:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.INVALID_PLAYER_COORDINATES.value,
            {**base, "coverage_status": UNKNOWN},
        )
    if duplicate_player_ids:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.DUPLICATE_PLAYER_POSITION_RECORDS.value,
            {**base, "coverage_status": UNKNOWN},
        )
    if outside_lane_player_ids_tuple:
        return _evaluation(
            UNKNOWN,
            LaneOccupancyReason.PLAYER_OUTSIDE_DEFINED_LANES.value,
            {**base, "coverage_status": UNKNOWN},
        )

    requirement_declared = bool(
        normalized_required_lane_ids
        or normalized_required_lane_counts
        or normalized_required_occupied_lane_count is not None
    )
    requirement_met = _requirements_met(
        lane_counts=lane_counts,
        required_lane_ids=normalized_required_lane_ids,
        required_lane_counts=normalized_required_lane_counts,
        required_occupied_lane_count=normalized_required_occupied_lane_count,
    )
    if requirement_declared and not requirement_met:
        return _evaluation(FAIL, LaneOccupancyReason.REQUIREMENT_NOT_MET.value, {**base, "coverage_status": "COMPLETE"})
    reason = (
        LaneOccupancyReason.REQUIREMENT_SATISFIED.value
        if requirement_declared
        else LaneOccupancyReason.OCCUPANCY_CLASSIFIED.value
    )
    return _evaluation(PASS, reason, {**base, "coverage_status": "COMPLETE"})


def default_lane_definitions(pitch_width_m: float = DEFAULT_PITCH_WIDTH_M) -> tuple[LaneDefinition, ...]:
    """Return the default equal-width five-lane model for a centered pitch."""

    half_width = float(pitch_width_m) / 2.0
    lane_width = float(pitch_width_m) / len(DEFAULT_LANE_IDS)
    definitions: list[LaneDefinition] = []
    for ordinal, lane_id in enumerate(DEFAULT_LANE_IDS):
        min_y = round(-half_width + ordinal * lane_width, 10)
        max_y = round(-half_width + (ordinal + 1) * lane_width, 10)
        definitions.append(
            LaneDefinition(
                lane_id=lane_id,
                min_y_m=min_y,
                max_y_m=max_y,
                includes_min_y=True,
                includes_max_y=ordinal == len(DEFAULT_LANE_IDS) - 1,
                ordinal=ordinal,
            )
        )
    return tuple(definitions)


def _resolve_lane_definitions(config: LaneOccupancyConfig) -> tuple[tuple[LaneDefinition, ...], str | None]:
    if config.lane_definitions is None:
        pitch_width, pitch_reason = _optional_positive_float(config.pitch_width_m)
        if pitch_reason is not None:
            return (), LaneOccupancyReason.LANE_DEFINITION_INVALID.value
        lane_definitions = default_lane_definitions(pitch_width)
    else:
        lane_definitions = tuple(config.lane_definitions)

    if not lane_definitions:
        return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    lane_ids = [definition.lane_id for definition in lane_definitions]
    if len(set(lane_ids)) != len(lane_ids):
        return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    for definition in lane_definitions:
        if not str(definition.lane_id):
            return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
        if not _finite_number(definition.min_y_m) or not _finite_number(definition.max_y_m):
            return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
        if float(definition.min_y_m) >= float(definition.max_y_m):
            return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
        if not isinstance(definition.includes_min_y, bool) or not isinstance(definition.includes_max_y, bool):
            return lane_definitions, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    return tuple(sorted(lane_definitions, key=lambda item: item.ordinal)), None


def _resolve_target_ids(
    *,
    target_player_ids: Sequence[object] | None,
    expected_player_ids: Sequence[object] | None,
) -> tuple[tuple[str, ...] | None, tuple[str, ...], str | None]:
    if target_player_ids is not None and expected_player_ids is not None:
        target = _normalize_player_id_sequence(target_player_ids)
        expected = _normalize_player_id_sequence(expected_player_ids)
        if target[0] != expected[0]:
            return target[0], tuple(sorted(set(target[1]) | set(expected[1]), key=_stable_sort_key)), (
                LaneOccupancyReason.TARGET_PLAYER_IDS_CONFLICT.value
            )
        invalid = tuple(sorted(set(target[1]) | set(expected[1]), key=_stable_sort_key))
        return target[0], invalid, LaneOccupancyReason.INVALID_TARGET_PLAYER_IDS.value if invalid else None
    if target_player_ids is not None:
        ids, invalid = _normalize_player_id_sequence(target_player_ids)
        return ids, invalid, LaneOccupancyReason.INVALID_TARGET_PLAYER_IDS.value if invalid else None
    if expected_player_ids is not None:
        ids, invalid = _normalize_player_id_sequence(expected_player_ids)
        return ids, invalid, LaneOccupancyReason.INVALID_TARGET_PLAYER_IDS.value if invalid else None
    return None, (), None


def _normalize_player_id_sequence(values: Sequence[object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized: list[str] = []
    invalid: list[str] = []
    for index, value in enumerate(values):
        player_id, is_invalid = _coerce_player_id(value, fallback=f"target_player_ids[{index}]")
        if is_invalid:
            invalid.append(player_id)
        else:
            normalized.append(player_id)
    return tuple(sorted(set(normalized), key=_stable_sort_key)), tuple(sorted(set(invalid), key=_stable_sort_key))


def _normalize_lane_id_sequence(values: Sequence[object] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(sorted({str(value) for value in values if value is not None and str(value)}, key=_stable_sort_key))


def _normalize_required_lane_counts(values: Mapping[object, object] | None) -> tuple[dict[str, int], tuple[str, ...]]:
    if values is None:
        return {}, ()
    normalized: dict[str, int] = {}
    invalid_lane_ids: list[str] = []
    for lane_id, raw_count in values.items():
        lane_id_string = str(lane_id)
        count = _non_negative_int(raw_count)
        if not lane_id_string or count is None:
            invalid_lane_ids.append(lane_id_string or "<missing_lane_id>")
        else:
            normalized[lane_id_string] = count
    return dict(sorted(normalized.items(), key=lambda item: _stable_sort_key(item[0]))), tuple(
        sorted(invalid_lane_ids, key=_stable_sort_key)
    )


def _normalize_required_occupied_lane_count(value: object | None) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value)


def _requirements_met(
    *,
    lane_counts: Mapping[str, int],
    required_lane_ids: tuple[str, ...],
    required_lane_counts: Mapping[str, int],
    required_occupied_lane_count: int | None,
) -> bool:
    for lane_id in required_lane_ids:
        if int(lane_counts.get(lane_id, 0)) < 1:
            return False
    for lane_id, count in required_lane_counts.items():
        if int(lane_counts.get(lane_id, 0)) < int(count):
            return False
    if required_occupied_lane_count is not None:
        occupied_count = sum(1 for count in lane_counts.values() if int(count) > 0)
        if occupied_count < required_occupied_lane_count:
            return False
    return True


def _lane_id_for_y(y_m: float | None, lane_definitions: tuple[LaneDefinition, ...]) -> str | None:
    if y_m is None:
        return None
    y_value = float(y_m)
    for definition in lane_definitions:
        above_min = y_value >= definition.min_y_m if definition.includes_min_y else y_value > definition.min_y_m
        below_max = y_value <= definition.max_y_m if definition.includes_max_y else y_value < definition.max_y_m
        if above_min and below_max:
            return definition.lane_id
    return None


def _lane_counts(
    assignments: tuple[PlayerLaneAssignment, ...],
    lane_definitions: tuple[LaneDefinition, ...],
) -> dict[str, int]:
    counts = Counter(item.lane_id for item in assignments)
    return {definition.lane_id: int(counts.get(definition.lane_id, 0)) for definition in lane_definitions}


def _frame_lane_counts(
    assignments: tuple[PlayerLaneAssignment, ...],
    lane_definitions: tuple[LaneDefinition, ...],
    requested_frame_ids: tuple[FrameId, ...] | None,
) -> tuple[FrameLaneCounts, ...]:
    if requested_frame_ids is None:
        frame_ids = tuple(sorted({item.frame_id for item in assignments}, key=_stable_sort_key))
    else:
        frame_ids = requested_frame_ids
    result: list[FrameLaneCounts] = []
    for frame_id in frame_ids:
        frame_assignments = tuple(item for item in assignments if item.frame_id == frame_id)
        counts = _lane_counts(frame_assignments, lane_definitions)
        occupied = tuple(definition.lane_id for definition in lane_definitions if counts[definition.lane_id] > 0)
        result.append(FrameLaneCounts(frame_id=frame_id, occupied_lanes=occupied, lane_counts=counts))
    return tuple(result)


def _ordered_lane_count_requirements(
    required_lane_counts: Mapping[str, int],
    lane_definitions: tuple[LaneDefinition, ...],
) -> dict[str, int]:
    ordered: dict[str, int] = {}
    for definition in lane_definitions:
        if definition.lane_id in required_lane_counts:
            ordered[definition.lane_id] = int(required_lane_counts[definition.lane_id])
    for lane_id in sorted(set(required_lane_counts) - set(ordered), key=_stable_sort_key):
        ordered[lane_id] = int(required_lane_counts[lane_id])
    return ordered


def _duplicate_player_ids(records: Sequence[_PlayerRecord]) -> tuple[str, ...]:
    counts = Counter((record.frame_id, record.player_id) for record in records)
    return tuple(sorted({player_id for (_, player_id), count in counts.items() if count > 1}, key=_stable_sort_key))


def _duplicate_keys(records: Sequence[_PlayerRecord]) -> set[tuple[FrameId, str]]:
    counts = Counter((record.frame_id, record.player_id) for record in records)
    return {key for key, count in counts.items() if count > 1}


def _result_frame_ids(
    *,
    records: Sequence[_PlayerRecord],
    requested_frame_ids: tuple[FrameId, ...] | None,
) -> tuple[FrameId, ...]:
    if requested_frame_ids is not None:
        return requested_frame_ids
    return tuple(sorted({record.frame_id for record in records}, key=_stable_sort_key))


def _resolve_frame_filter(*, frame_id: FrameId, frame_ids: Sequence[object] | None) -> tuple[FrameId, ...] | None:
    if frame_ids is None and frame_id is None:
        return None
    values = list(frame_ids or ())
    if frame_id is not None:
        values.append(frame_id)
    return tuple(sorted(set(_normalize_frame_id(value) for value in values), key=_stable_sort_key))


def _record_in_frame_scope(record: object, frame_ids: tuple[FrameId, ...] | None) -> bool:
    if frame_ids is None:
        return True
    return _frame_id_from_record(record) in set(frame_ids)


def _frame_id_from_record(record: object) -> FrameId:
    return _normalize_frame_id(_first_field(record, "frame_id", "anchor_frame_id"))


def _normalize_frame_id(value: object | None) -> FrameId:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | str):
        return value
    return str(value)


def _single_frame_id(frame_ids: tuple[FrameId, ...] | None) -> FrameId:
    if frame_ids is None or len(frame_ids) != 1:
        return None
    return frame_ids[0]


def _coerce_player_id(value: object | None, *, fallback: str) -> tuple[str, bool]:
    if value is None or isinstance(value, bool):
        return f"{fallback}:invalid_player_id", True
    player_id = str(value).strip()
    if not player_id:
        return f"{fallback}:invalid_player_id", True
    return player_id, False


def _required_float(value: object | None) -> tuple[float | None, bool]:
    if value is None or isinstance(value, bool):
        return None, True
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None, True
    if not isfinite(result):
        return None, True
    return result, False


def _optional_positive_float(value: object | None) -> tuple[float, str | None]:
    if value is None or isinstance(value, bool):
        return 0.0, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    if not isfinite(result) or result <= 0.0:
        return 0.0, LaneOccupancyReason.LANE_DEFINITION_INVALID.value
    return result, None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not isfinite(value) or not value.is_integer():
            return None
        result = int(value)
        return result if result >= 0 else None
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if result < 0:
        return None
    return result


def _pitch_width_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(result):
        return None
    return result


def _finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _first_field(value: object | None, *field_names: str) -> object | None:
    for field_name in field_names:
        field_value = _extract_field(value, field_name)
        if field_value is not None:
            return field_value
    return None


def _extract_field(value: object | None, field_name: str) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _stable_sort_key(value: object) -> tuple[str, str]:
    if value is None:
        return ("0", "")
    return (type(value).__name__, str(value))


def _evaluation(status: str, reason: str | None, base: Mapping[str, Any]) -> LaneOccupancyEvaluation:
    return LaneOccupancyEvaluation(status=status, reason=reason, **base)
