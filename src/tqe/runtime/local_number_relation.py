"""Pure observed local-number relation evaluation.

This module counts observed players from two declared sides inside a declared
radius around a reference point at one frame. It does not infer pressure,
tactical role, support quality, player intention, line-break causation, pass
optimality, or pass probability.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

Status = str
FrameId = int | str | None
PositionInput = tuple[float, ...] | list[float] | Mapping[str, Any]

_EPSILON = 1e-9


class LocalNumberStatus(str, Enum):
    PASS = PASS
    FAIL = FAIL
    UNKNOWN = UNKNOWN


class LocalNumberReason(str, Enum):
    REQUIREMENT_SATISFIED = "local_number_requirement_satisfied"
    REQUIREMENT_NOT_MET = "local_number_requirement_not_met"
    INVALID_CONFIG = "invalid_local_number_config"
    EVALUATION_FRAME_MISSING = "evaluation_frame_missing"
    INVALID_FRAME = "invalid_frame"
    REFERENCE_POINT_MISSING = "reference_point_missing"
    REFERENCE_POINT_INVALID = "reference_point_invalid"
    PLAYER_POSITIONS_MISSING = "player_positions_missing"
    INVALID_PLAYER_IDS = "invalid_player_ids"
    PLAYER_ON_BOTH_SIDES = "player_present_on_both_sides"
    MISSING_PLAYER_EVIDENCE = "missing_player_evidence"
    INVALID_PLAYER_COORDINATES = "invalid_player_coordinates"
    DUPLICATE_PLAYER_POSITION_RECORDS = "duplicate_player_position_records"


@dataclass(frozen=True)
class LocalNumberConfig:
    radius_m: float = 10.0
    minimum_difference: int = 1
    minimum_perspective_players: int = 0
    maximum_defending_players: int | None = None


@dataclass(frozen=True)
class LocalNumberConfigEvidence:
    radius_m: float | None
    minimum_difference: int | None
    minimum_perspective_players: int | None
    maximum_defending_players: int | None
    boundary_policy: str
    invalid_config_fields: tuple[str, ...]


@dataclass(frozen=True)
class LocalNumberPlayerEvidence:
    player_id: str
    side: str
    frame_id: FrameId
    x_m: float | None
    y_m: float | None
    distance_to_reference_m: float | None
    in_region: bool | None
    reason: str | None


@dataclass(frozen=True)
class LocalNumberEvaluation:
    status: Status
    reason: str
    anchor_id: str | None
    anchor_frame_id: FrameId
    evaluation_frame_id: FrameId
    reference_point: dict[str, float] | None
    radius_m: float | None
    minimum_difference: int | None
    minimum_perspective_players: int | None
    maximum_defending_players: int | None
    perspective_player_ids: tuple[str, ...]
    defending_player_ids: tuple[str, ...]
    perspective_count: int | None
    defending_count: int | None
    local_number_difference: int | None
    evaluated_perspective_player_ids: tuple[str, ...]
    evaluated_defending_player_ids: tuple[str, ...]
    missing_perspective_player_ids: tuple[str, ...]
    missing_defending_player_ids: tuple[str, ...]
    invalid_perspective_player_ids: tuple[str, ...]
    invalid_defending_player_ids: tuple[str, ...]
    duplicate_perspective_player_ids: tuple[str, ...]
    duplicate_defending_player_ids: tuple[str, ...]
    invalid_coordinate_player_ids: tuple[str, ...]
    perspective_in_region_player_ids: tuple[str, ...]
    defending_in_region_player_ids: tuple[str, ...]
    per_player_evidence: tuple[LocalNumberPlayerEvidence, ...]
    coverage_status: str
    config_evidence: LocalNumberConfigEvidence

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _Point:
    x_m: float
    y_m: float


@dataclass(frozen=True)
class _PositionRecord:
    index: int
    side: str
    player_id: str | None
    frame_id: FrameId
    x_m: float | None
    y_m: float | None
    invalid_player_id: str | None
    frame_invalid: bool
    coordinate_invalid: bool


@dataclass(frozen=True)
class _ResolvedConfig:
    radius_m: float | None
    minimum_difference: int | None
    minimum_perspective_players: int | None
    maximum_defending_players: int | None
    invalid_config_fields: tuple[str, ...]


def evaluate_local_number_relation(
    *,
    anchor: Mapping[str, object] | None = None,
    anchor_id: str | None = None,
    anchor_frame_id: object | None = None,
    evaluation_frame_id: object | None = None,
    reference_point: PositionInput | None = None,
    perspective_positions: Sequence[object] | None = None,
    defending_positions: Sequence[object] | None = None,
    perspective_player_ids: Sequence[object] | None = None,
    defending_player_ids: Sequence[object] | None = None,
    config: LocalNumberConfig = LocalNumberConfig(),
    radius_m: object | None = None,
    minimum_difference: object | None = None,
    minimum_perspective_players: object | None = None,
    maximum_defending_players: object | None = None,
) -> LocalNumberEvaluation:
    """Evaluate an observed local-number relation."""

    if anchor is not None:
        if anchor_id is None:
            anchor_id = _string_or_none(_first_field(anchor, "anchor_id", "id", "action_id"))
        if anchor_frame_id is None:
            anchor_frame_id = _first_field(anchor, "anchor_frame_id", "frame_id", "frame")
        if evaluation_frame_id is None:
            evaluation_frame_id = _first_field(anchor, "evaluation_frame_id", "anchor_frame_id", "frame_id", "frame")

    normalized_anchor_frame_id, anchor_frame_invalid = _normalize_frame_id(anchor_frame_id)
    normalized_evaluation_frame_id, evaluation_frame_invalid = _normalize_frame_id(evaluation_frame_id)
    resolved_config = _resolve_config(
        config=config,
        radius_m=radius_m,
        minimum_difference=minimum_difference,
        minimum_perspective_players=minimum_perspective_players,
        maximum_defending_players=maximum_defending_players,
    )
    config_evidence = LocalNumberConfigEvidence(
        radius_m=resolved_config.radius_m,
        minimum_difference=resolved_config.minimum_difference,
        minimum_perspective_players=resolved_config.minimum_perspective_players,
        maximum_defending_players=resolved_config.maximum_defending_players,
        boundary_policy="radius_boundary_inclusive",
        invalid_config_fields=resolved_config.invalid_config_fields,
    )

    reference, reference_reason = _coerce_point(reference_point)
    perspective_records = _parse_position_records(perspective_positions or (), "perspective")
    defending_records = _parse_position_records(defending_positions or (), "defending")
    perspective_ids, invalid_perspective_ids = _resolve_side_player_ids(
        perspective_records,
        perspective_player_ids,
        "perspective_player_ids",
    )
    defending_ids, invalid_defending_ids = _resolve_side_player_ids(
        defending_records,
        defending_player_ids,
        "defending_player_ids",
    )

    empty_base = {
        "anchor_id": anchor_id,
        "anchor_frame_id": normalized_anchor_frame_id,
        "evaluation_frame_id": normalized_evaluation_frame_id,
        "reference_point": None if reference is None else {"x_m": reference.x_m, "y_m": reference.y_m},
        "radius_m": resolved_config.radius_m,
        "minimum_difference": resolved_config.minimum_difference,
        "minimum_perspective_players": resolved_config.minimum_perspective_players,
        "maximum_defending_players": resolved_config.maximum_defending_players,
        "perspective_player_ids": perspective_ids,
        "defending_player_ids": defending_ids,
        "perspective_count": None,
        "defending_count": None,
        "local_number_difference": None,
        "evaluated_perspective_player_ids": (),
        "evaluated_defending_player_ids": (),
        "missing_perspective_player_ids": (),
        "missing_defending_player_ids": (),
        "invalid_perspective_player_ids": invalid_perspective_ids,
        "invalid_defending_player_ids": invalid_defending_ids,
        "duplicate_perspective_player_ids": (),
        "duplicate_defending_player_ids": (),
        "invalid_coordinate_player_ids": (),
        "perspective_in_region_player_ids": (),
        "defending_in_region_player_ids": (),
        "per_player_evidence": (),
        "config_evidence": config_evidence,
    }

    if resolved_config.invalid_config_fields:
        return _evaluation(UNKNOWN, LocalNumberReason.INVALID_CONFIG.value, {**empty_base, "coverage_status": UNKNOWN})
    if evaluation_frame_invalid or anchor_frame_invalid:
        return _evaluation(UNKNOWN, LocalNumberReason.INVALID_FRAME.value, {**empty_base, "coverage_status": UNKNOWN})
    if normalized_evaluation_frame_id is None:
        return _evaluation(
            UNKNOWN,
            LocalNumberReason.EVALUATION_FRAME_MISSING.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )
    if reference_reason is not None:
        return _evaluation(UNKNOWN, reference_reason, {**empty_base, "coverage_status": UNKNOWN})
    if perspective_positions is None or defending_positions is None:
        return _evaluation(
            UNKNOWN,
            LocalNumberReason.PLAYER_POSITIONS_MISSING.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )
    if invalid_perspective_ids or invalid_defending_ids:
        return _evaluation(
            UNKNOWN,
            LocalNumberReason.INVALID_PLAYER_IDS.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )
    if set(perspective_ids) & set(defending_ids):
        # A player declared on both sides is contradictory side-membership
        # evidence; counting it twice would fabricate a numerical advantage.
        return _evaluation(
            UNKNOWN,
            LocalNumberReason.PLAYER_ON_BOTH_SIDES.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )

    selected_perspective = _selected_records(perspective_records, perspective_ids, normalized_evaluation_frame_id)
    selected_defending = _selected_records(defending_records, defending_ids, normalized_evaluation_frame_id)
    if not selected_perspective and not selected_defending:
        return _evaluation(
            UNKNOWN,
            LocalNumberReason.PLAYER_POSITIONS_MISSING.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )

    missing_perspective_ids = _sorted_tuple(set(perspective_ids) - {record.player_id for record in selected_perspective if record.player_id})
    missing_defending_ids = _sorted_tuple(set(defending_ids) - {record.player_id for record in selected_defending if record.player_id})
    duplicate_perspective_ids = _duplicate_ids(selected_perspective)
    duplicate_defending_ids = _duplicate_ids(selected_defending)
    invalid_coordinate_ids = _sorted_tuple(
        record.player_id
        for record in (*selected_perspective, *selected_defending)
        if record.player_id is not None and record.coordinate_invalid
    )

    per_player = tuple(
        sorted(
            (
                *[
                    _player_evidence(record, reference, resolved_config.radius_m or 0.0)
                    for record in selected_perspective
                    if record.player_id is not None
                ],
                *[
                    _player_evidence(record, reference, resolved_config.radius_m or 0.0)
                    for record in selected_defending
                    if record.player_id is not None
                ],
            ),
            key=lambda item: (item.side, _stable_sort_key(item.player_id)),
        )
    )
    perspective_in_region = _sorted_tuple(
        item.player_id for item in per_player if item.side == "perspective" and item.in_region is True
    )
    defending_in_region = _sorted_tuple(
        item.player_id for item in per_player if item.side == "defending" and item.in_region is True
    )
    perspective_count = len(perspective_in_region)
    defending_count = len(defending_in_region)
    difference = perspective_count - defending_count
    result_base = {
        **empty_base,
        "perspective_count": perspective_count,
        "defending_count": defending_count,
        "local_number_difference": difference,
        "evaluated_perspective_player_ids": _sorted_tuple(
            record.player_id for record in selected_perspective if record.player_id is not None
        ),
        "evaluated_defending_player_ids": _sorted_tuple(
            record.player_id for record in selected_defending if record.player_id is not None
        ),
        "missing_perspective_player_ids": missing_perspective_ids,
        "missing_defending_player_ids": missing_defending_ids,
        "duplicate_perspective_player_ids": duplicate_perspective_ids,
        "duplicate_defending_player_ids": duplicate_defending_ids,
        "invalid_coordinate_player_ids": invalid_coordinate_ids,
        "perspective_in_region_player_ids": perspective_in_region,
        "defending_in_region_player_ids": defending_in_region,
        "per_player_evidence": per_player,
    }
    if (
        missing_perspective_ids
        or missing_defending_ids
        or duplicate_perspective_ids
        or duplicate_defending_ids
        or invalid_coordinate_ids
    ):
        reason = (
            LocalNumberReason.MISSING_PLAYER_EVIDENCE.value
            if missing_perspective_ids or missing_defending_ids
            else LocalNumberReason.DUPLICATE_PLAYER_POSITION_RECORDS.value
            if duplicate_perspective_ids or duplicate_defending_ids
            else LocalNumberReason.INVALID_PLAYER_COORDINATES.value
        )
        return _evaluation(UNKNOWN, reason, {**result_base, "coverage_status": UNKNOWN})

    maximum_defending = resolved_config.maximum_defending_players
    requirement_satisfied = (
        difference >= int(resolved_config.minimum_difference or 0)
        and perspective_count >= int(resolved_config.minimum_perspective_players or 0)
        and (maximum_defending is None or defending_count <= maximum_defending)
    )
    if requirement_satisfied:
        return _evaluation(
            PASS,
            LocalNumberReason.REQUIREMENT_SATISFIED.value,
            {**result_base, "coverage_status": "COMPLETE"},
        )
    return _evaluation(
        FAIL,
        LocalNumberReason.REQUIREMENT_NOT_MET.value,
        {**result_base, "coverage_status": "COMPLETE"},
    )


def _evaluation(status: Status, reason: str, values: Mapping[str, object]) -> LocalNumberEvaluation:
    return LocalNumberEvaluation(
        status=status,
        reason=reason,
        anchor_id=_string_or_none(values.get("anchor_id")),
        anchor_frame_id=values.get("anchor_frame_id"),
        evaluation_frame_id=values.get("evaluation_frame_id"),
        reference_point=values.get("reference_point") if isinstance(values.get("reference_point"), dict) else None,
        radius_m=values.get("radius_m") if isinstance(values.get("radius_m"), float | int) else None,
        minimum_difference=values.get("minimum_difference") if isinstance(values.get("minimum_difference"), int) else None,
        minimum_perspective_players=values.get("minimum_perspective_players")
        if isinstance(values.get("minimum_perspective_players"), int)
        else None,
        maximum_defending_players=values.get("maximum_defending_players")
        if isinstance(values.get("maximum_defending_players"), int)
        else None,
        perspective_player_ids=tuple(values.get("perspective_player_ids") or ()),
        defending_player_ids=tuple(values.get("defending_player_ids") or ()),
        perspective_count=values.get("perspective_count") if isinstance(values.get("perspective_count"), int) else None,
        defending_count=values.get("defending_count") if isinstance(values.get("defending_count"), int) else None,
        local_number_difference=values.get("local_number_difference")
        if isinstance(values.get("local_number_difference"), int)
        else None,
        evaluated_perspective_player_ids=tuple(values.get("evaluated_perspective_player_ids") or ()),
        evaluated_defending_player_ids=tuple(values.get("evaluated_defending_player_ids") or ()),
        missing_perspective_player_ids=tuple(values.get("missing_perspective_player_ids") or ()),
        missing_defending_player_ids=tuple(values.get("missing_defending_player_ids") or ()),
        invalid_perspective_player_ids=tuple(values.get("invalid_perspective_player_ids") or ()),
        invalid_defending_player_ids=tuple(values.get("invalid_defending_player_ids") or ()),
        duplicate_perspective_player_ids=tuple(values.get("duplicate_perspective_player_ids") or ()),
        duplicate_defending_player_ids=tuple(values.get("duplicate_defending_player_ids") or ()),
        invalid_coordinate_player_ids=tuple(values.get("invalid_coordinate_player_ids") or ()),
        perspective_in_region_player_ids=tuple(values.get("perspective_in_region_player_ids") or ()),
        defending_in_region_player_ids=tuple(values.get("defending_in_region_player_ids") or ()),
        per_player_evidence=tuple(values.get("per_player_evidence") or ()),
        coverage_status=str(values.get("coverage_status") or UNKNOWN),
        config_evidence=values["config_evidence"],  # type: ignore[arg-type]
    )


def _resolve_config(
    *,
    config: LocalNumberConfig,
    radius_m: object | None,
    minimum_difference: object | None,
    minimum_perspective_players: object | None,
    maximum_defending_players: object | None,
) -> _ResolvedConfig:
    invalid: list[str] = []
    radius = _optional_float(config.radius_m if radius_m is None else radius_m)
    min_diff = _optional_int(config.minimum_difference if minimum_difference is None else minimum_difference)
    min_perspective = _optional_int(
        config.minimum_perspective_players
        if minimum_perspective_players is None
        else minimum_perspective_players
    )
    max_defending = _optional_int(
        config.maximum_defending_players
        if maximum_defending_players is None
        else maximum_defending_players
    )
    if radius is None or radius <= 0:
        invalid.append("radius_m")
    if min_diff is None:
        invalid.append("minimum_difference")
    if min_perspective is None or min_perspective < 0:
        invalid.append("minimum_perspective_players")
    if max_defending is not None and max_defending < 0:
        invalid.append("maximum_defending_players")
    return _ResolvedConfig(
        radius_m=radius,
        minimum_difference=min_diff,
        minimum_perspective_players=min_perspective,
        maximum_defending_players=max_defending,
        invalid_config_fields=tuple(invalid),
    )


def _parse_position_records(records: Sequence[object], side: str) -> tuple[_PositionRecord, ...]:
    parsed: list[_PositionRecord] = []
    for index, record in enumerate(records):
        player_id, player_invalid = _coerce_player_id(
            _first_field(record, "player_id", "entity_id"),
            fallback=f"{side}[{index}]",
        )
        frame_id, frame_invalid = _normalize_frame_id(_first_field(record, "frame_id", "frame"))
        x_m, x_invalid = _required_float(_first_field(record, "x_m", "x"))
        y_m, y_invalid = _required_float(_first_field(record, "y_m", "y"))
        parsed.append(
            _PositionRecord(
                index=index,
                side=side,
                player_id=None if player_invalid else player_id,
                frame_id=frame_id,
                x_m=x_m,
                y_m=y_m,
                invalid_player_id=player_id if player_invalid else None,
                frame_invalid=frame_invalid,
                coordinate_invalid=x_invalid or y_invalid,
            )
        )
    return tuple(parsed)


def _resolve_side_player_ids(
    records: Sequence[_PositionRecord],
    explicit_ids: Sequence[object] | None,
    label: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if explicit_ids is not None:
        return _normalize_player_id_sequence(explicit_ids, label=label)
    invalid_ids = tuple(record.invalid_player_id for record in records if record.invalid_player_id)
    ids = tuple(record.player_id for record in records if record.player_id is not None)
    return _sorted_tuple(ids), _sorted_tuple(invalid_ids)


def _selected_records(
    records: Sequence[_PositionRecord],
    player_ids: Sequence[str],
    evaluation_frame_id: FrameId,
) -> tuple[_PositionRecord, ...]:
    player_id_set = set(player_ids)
    return tuple(
        sorted(
            (
                record
                for record in records
                if record.player_id in player_id_set
                and not record.frame_invalid
                and record.frame_id == evaluation_frame_id
            ),
            key=lambda item: (_stable_sort_key(item.player_id), item.index),
        )
    )


def _duplicate_ids(records: Sequence[_PositionRecord]) -> tuple[str, ...]:
    counts: dict[tuple[str | None, FrameId], int] = {}
    for record in records:
        counts[(record.player_id, record.frame_id)] = counts.get((record.player_id, record.frame_id), 0) + 1
    return _sorted_tuple(player_id for (player_id, _frame_id), count in counts.items() if player_id is not None and count > 1)


def _player_evidence(record: _PositionRecord, reference: _Point, radius_m: float) -> LocalNumberPlayerEvidence:
    if record.coordinate_invalid or record.x_m is None or record.y_m is None:
        return LocalNumberPlayerEvidence(
            player_id=str(record.player_id),
            side=record.side,
            frame_id=record.frame_id,
            x_m=record.x_m,
            y_m=record.y_m,
            distance_to_reference_m=None,
            in_region=None,
            reason=LocalNumberReason.INVALID_PLAYER_COORDINATES.value,
        )
    distance = hypot(record.x_m - reference.x_m, record.y_m - reference.y_m)
    in_region = distance <= radius_m + _EPSILON
    return LocalNumberPlayerEvidence(
        player_id=str(record.player_id),
        side=record.side,
        frame_id=record.frame_id,
        x_m=record.x_m,
        y_m=record.y_m,
        distance_to_reference_m=distance,
        in_region=in_region,
        reason=None,
    )


def _coerce_point(value: PositionInput | None) -> tuple[_Point | None, str | None]:
    if value is None:
        return None, LocalNumberReason.REFERENCE_POINT_MISSING.value
    x_value = _first_field(value, "x_m", "x", 0)
    y_value = _first_field(value, "y_m", "y", 1)
    x_m, x_invalid = _required_float(x_value)
    y_m, y_invalid = _required_float(y_value)
    if x_invalid or y_invalid or x_m is None or y_m is None:
        return None, LocalNumberReason.REFERENCE_POINT_INVALID.value
    return _Point(x_m=x_m, y_m=y_m), None


def _normalize_player_id_sequence(values: Sequence[object], *, label: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ids: list[str] = []
    invalid: list[str] = []
    for index, value in enumerate(values):
        player_id, is_invalid = _coerce_player_id(value, fallback=f"{label}[{index}]")
        if is_invalid:
            invalid.append(player_id)
        else:
            ids.append(player_id)
    return _sorted_tuple(ids), _sorted_tuple(invalid)


def _coerce_player_id(value: object, *, fallback: str) -> tuple[str, bool]:
    if value is None:
        return f"{fallback}:missing_player_id", True
    text = str(value).strip()
    if not text:
        return f"{fallback}:missing_player_id", True
    return text, False


def _normalize_frame_id(value: object | None) -> tuple[FrameId, bool]:
    if value is None or isinstance(value, bool):
        return None, value is not None
    if isinstance(value, int):
        return value, False
    if isinstance(value, float):
        if isfinite(value) and value.is_integer():
            return int(value), False
        return None, True
    text = str(value).strip()
    if not text:
        return None, True
    try:
        return int(text), False
    except ValueError:
        return text, False


def _optional_float(value: object | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if isfinite(number) else None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if isfinite(number) else None


def _required_float(value: object | None) -> tuple[float | None, bool]:
    number = _optional_float(value)
    return number, number is None


def _optional_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if isfinite(value) and value.is_integer():
            return int(value)
        return None
    try:
        parsed = float(str(value).strip())
    except ValueError:
        return None
    if not isfinite(parsed) or not parsed.is_integer():
        return None
    return int(parsed)


def _first_field(value: object, *keys: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in keys:
            if isinstance(key, int):
                continue
            if key in value:
                return value[key]
        return None
    if isinstance(value, tuple | list):
        for key in keys:
            if isinstance(key, int) and 0 <= key < len(value):
                return value[key]
        return None
    for key in keys:
        if isinstance(key, str) and hasattr(value, key):
            return getattr(value, key)
    return None


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _sorted_tuple(values: Sequence[object] | set[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value is not None}, key=_stable_sort_key))


def _stable_sort_key(value: object) -> tuple[str, str]:
    text = str(value)
    return (text.casefold(), text)
