"""Pure geometric relative-position classification against an x line.

This module only compares an entity's x coordinate with a supplied line x
coordinate in attacking-direction-normalized space. It does not identify a
defensive line, infer a line break, or attach tactical meaning to the result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


AHEAD_OF_LINE = "AHEAD_OF_LINE"
BEHIND_LINE = "BEHIND_LINE"
LEVEL_WITH_LINE = "LEVEL_WITH_LINE"
UNKNOWN = "UNKNOWN"

Status = str


@dataclass(frozen=True)
class RelativePositionToLineConfig:
    buffer_m: float = 0.0


@dataclass(frozen=True)
class EntityPosition:
    x_m: float
    y_m: float | None = None


@dataclass(frozen=True)
class RelativePositionToLineEvaluation:
    status: Status
    reason: str | None
    entity_id: str | None
    anchor_frame_id: int | str | None
    attacking_direction: int | None
    line_x_m: float | None
    normalized_line_x_m: float | None
    entity_x_m: float | None
    entity_y_m: float | None
    normalized_entity_x_m: float | None
    signed_distance_to_line_m: float | None
    distance_to_line_m: float | None
    buffer_m: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PositionInput = EntityPosition | tuple[float, ...] | list[float] | Mapping[str, Any]


def evaluate_relative_position_to_line(
    *,
    entity_position: PositionInput | None,
    line_x_m: float | None = None,
    line_evaluation: object | None = None,
    attacking_direction: int | None = None,
    attack_x_sign: int | None = None,
    entity_id: str | None = None,
    anchor_frame_id: int | str | None = None,
    config: RelativePositionToLineConfig = RelativePositionToLineConfig(),
) -> RelativePositionToLineEvaluation:
    """Classify an entity relative to a line in normalized attacking coordinates."""

    _validate_config(config)
    line_direction = _extract_line_evaluation_field(line_evaluation, "attacking_direction")
    resolved_direction, direction_reason = _resolve_attacking_direction(
        attacking_direction=attacking_direction,
        line_attacking_direction=line_direction,
        attack_x_sign=attack_x_sign,
    )
    resolved_anchor_frame_id = (
        anchor_frame_id
        if anchor_frame_id is not None
        else _extract_line_evaluation_field(line_evaluation, "anchor_frame_id")
    )
    line_x, line_reason = _coerce_line_x(
        line_x_m=line_x_m,
        line_evaluation=line_evaluation,
    )
    entity, entity_reason = _coerce_entity_position(entity_position)

    normalized_line_x = None if line_x is None or resolved_direction is None else line_x * resolved_direction
    normalized_entity_x = (
        None if entity is None or resolved_direction is None else entity.x_m * resolved_direction
    )
    signed_distance = (
        None
        if normalized_line_x is None or normalized_entity_x is None
        else normalized_entity_x - normalized_line_x
    )
    distance = None if signed_distance is None else abs(signed_distance)

    if direction_reason is not None:
        return _evaluation(
            status=UNKNOWN,
            reason=direction_reason,
            entity_id=entity_id,
            anchor_frame_id=resolved_anchor_frame_id,
            attacking_direction=resolved_direction,
            line_x_m=line_x,
            normalized_line_x_m=normalized_line_x,
            entity=entity,
            normalized_entity_x_m=normalized_entity_x,
            signed_distance_to_line_m=signed_distance,
            distance_to_line_m=distance,
            config=config,
        )
    if line_reason is not None:
        return _evaluation(
            status=UNKNOWN,
            reason=line_reason,
            entity_id=entity_id,
            anchor_frame_id=resolved_anchor_frame_id,
            attacking_direction=resolved_direction,
            line_x_m=line_x,
            normalized_line_x_m=normalized_line_x,
            entity=entity,
            normalized_entity_x_m=normalized_entity_x,
            signed_distance_to_line_m=signed_distance,
            distance_to_line_m=distance,
            config=config,
        )
    if entity_reason is not None:
        return _evaluation(
            status=UNKNOWN,
            reason=entity_reason,
            entity_id=entity_id,
            anchor_frame_id=resolved_anchor_frame_id,
            attacking_direction=resolved_direction,
            line_x_m=line_x,
            normalized_line_x_m=normalized_line_x,
            entity=entity,
            normalized_entity_x_m=normalized_entity_x,
            signed_distance_to_line_m=signed_distance,
            distance_to_line_m=distance,
            config=config,
        )

    assert signed_distance is not None
    if signed_distance > config.buffer_m:
        status = AHEAD_OF_LINE
        reason = "entity_goalward_of_line"
    elif signed_distance < -config.buffer_m:
        status = BEHIND_LINE
        reason = "entity_behind_line"
    else:
        status = LEVEL_WITH_LINE
        reason = "entity_within_line_buffer"

    return _evaluation(
        status=status,
        reason=reason,
        entity_id=entity_id,
        anchor_frame_id=resolved_anchor_frame_id,
        attacking_direction=resolved_direction,
        line_x_m=line_x,
        normalized_line_x_m=normalized_line_x,
        entity=entity,
        normalized_entity_x_m=normalized_entity_x,
        signed_distance_to_line_m=signed_distance,
        distance_to_line_m=distance,
        config=config,
    )


def evaluate_relative_positions_to_line(
    *,
    entity_positions: Mapping[str, PositionInput | None],
    line_x_m: float | None = None,
    line_evaluation: object | None = None,
    attacking_direction: int | None = None,
    attack_x_sign: int | None = None,
    anchor_frame_id: int | str | None = None,
    config: RelativePositionToLineConfig = RelativePositionToLineConfig(),
) -> tuple[RelativePositionToLineEvaluation, ...]:
    """Classify a mapping of entities in deterministic entity-id order."""

    return tuple(
        evaluate_relative_position_to_line(
            entity_position=entity_positions[raw_entity_id],
            line_x_m=line_x_m,
            line_evaluation=line_evaluation,
            attacking_direction=attacking_direction,
            attack_x_sign=attack_x_sign,
            entity_id=str(raw_entity_id),
            anchor_frame_id=anchor_frame_id,
            config=config,
        )
        for raw_entity_id in sorted(entity_positions, key=str)
    )


def _validate_config(config: RelativePositionToLineConfig) -> None:
    if not isfinite(float(config.buffer_m)):
        raise ValueError("buffer_m must be finite")
    if config.buffer_m < 0:
        raise ValueError("buffer_m must be non-negative")


def _resolve_attacking_direction(
    *,
    attacking_direction: int | None,
    line_attacking_direction: object | None,
    attack_x_sign: int | None,
) -> tuple[int | None, str | None]:
    direction_values = [
        value
        for value in (attacking_direction, line_attacking_direction, attack_x_sign)
        if value is not None
    ]
    if not direction_values:
        return None, "attacking_direction_invalid"

    coerced_values: list[int] = []
    for value in direction_values:
        if isinstance(value, bool):
            return None, "attacking_direction_invalid"
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            return None, "attacking_direction_invalid"
        if coerced not in {-1, 1}:
            return None, "attacking_direction_invalid"
        coerced_values.append(coerced)

    if len(set(coerced_values)) > 1:
        return None, "attacking_direction_conflict"
    return coerced_values[0], None


def _coerce_line_x(
    *,
    line_x_m: float | None,
    line_evaluation: object | None,
) -> tuple[float | None, str | None]:
    raw_line_x = line_x_m
    if raw_line_x is None:
        raw_line_x = _extract_line_x_from_evaluation(line_evaluation)
    if raw_line_x is None:
        return None, "line_x_missing"
    if isinstance(raw_line_x, bool):
        return None, "line_x_invalid"
    try:
        line_x = float(raw_line_x)
    except (TypeError, ValueError):
        return None, "line_x_invalid"
    if not isfinite(line_x):
        return None, "line_x_invalid"
    return line_x, None


def _extract_line_x_from_evaluation(line_evaluation: object | None) -> object | None:
    if line_evaluation is None:
        return None
    if isinstance(line_evaluation, bool):
        return None
    if isinstance(line_evaluation, int | float):
        return line_evaluation
    return _extract_line_evaluation_field(line_evaluation, "line_x_m")


def _extract_line_evaluation_field(line_evaluation: object | None, field_name: str) -> object | None:
    if line_evaluation is None:
        return None
    if isinstance(line_evaluation, Mapping):
        return line_evaluation.get(field_name)
    return getattr(line_evaluation, field_name, None)


def _coerce_entity_position(
    value: PositionInput | None,
) -> tuple[EntityPosition | None, str | None]:
    if value is None:
        return None, "entity_position_missing"
    try:
        position = _coerce_entity_position_value(value)
    except (IndexError, KeyError, TypeError, ValueError):
        return None, "entity_position_invalid"
    if not isfinite(position.x_m):
        return None, "entity_position_invalid"
    if position.y_m is not None and not isfinite(position.y_m):
        return None, "entity_position_invalid"
    return position, None


def _coerce_entity_position_value(value: PositionInput) -> EntityPosition:
    if isinstance(value, EntityPosition):
        if isinstance(value.x_m, bool) or isinstance(value.y_m, bool):
            raise TypeError("boolean coordinates are invalid")
        return value
    if isinstance(value, Mapping):
        raw_x = value["x_m"] if "x_m" in value else value["x"]
        raw_y = value.get("y_m", value.get("y"))
        if isinstance(raw_x, bool) or isinstance(raw_y, bool):
            raise TypeError("boolean coordinates are invalid")
        return EntityPosition(x_m=float(raw_x), y_m=None if raw_y is None else float(raw_y))
    if isinstance(value, Sequence) and not isinstance(value, str):
        raw_y = None if len(value) < 2 else value[1]
        if isinstance(value[0], bool) or isinstance(raw_y, bool):
            raise TypeError("boolean coordinates are invalid")
        return EntityPosition(x_m=float(value[0]), y_m=None if raw_y is None else float(raw_y))
    raise TypeError("position must be an EntityPosition, mapping, or x/y sequence")


def _evaluation(
    *,
    status: Status,
    reason: str | None,
    entity_id: str | None,
    anchor_frame_id: int | str | None,
    attacking_direction: int | None,
    line_x_m: float | None,
    normalized_line_x_m: float | None,
    entity: EntityPosition | None,
    normalized_entity_x_m: float | None,
    signed_distance_to_line_m: float | None,
    distance_to_line_m: float | None,
    config: RelativePositionToLineConfig,
) -> RelativePositionToLineEvaluation:
    return RelativePositionToLineEvaluation(
        status=status,
        reason=reason,
        entity_id=entity_id,
        anchor_frame_id=anchor_frame_id,
        attacking_direction=attacking_direction,
        line_x_m=line_x_m,
        normalized_line_x_m=normalized_line_x_m,
        entity_x_m=None if entity is None else entity.x_m,
        entity_y_m=None if entity is None else entity.y_m,
        normalized_entity_x_m=normalized_entity_x_m,
        signed_distance_to_line_m=signed_distance_to_line_m,
        distance_to_line_m=distance_to_line_m,
        buffer_m=config.buffer_m,
    )
