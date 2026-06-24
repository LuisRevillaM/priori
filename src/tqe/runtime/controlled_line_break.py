"""Pure controlled-pass line-crossing episode evaluation.

This module evaluates a narrow observed claim: a supplied controlled pass moved
from not-yet-beyond a supplied observed line to beyond that same line. It does
not infer a defensive line, classify tactical intent, decide pass optimality, or
name the role of the supplied line.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

AHEAD_OF_LINE = "AHEAD_OF_LINE"
BEHIND_LINE = "BEHIND_LINE"
LEVEL_WITH_LINE = "LEVEL_WITH_LINE"

Status = str
PositionInput = tuple[float, ...] | list[float] | Mapping[str, Any]


class ControlledLineBreakStatus(str, Enum):
    PASS = PASS
    FAIL = FAIL
    UNKNOWN = UNKNOWN


class ControlledLineBreakReason(str, Enum):
    OBSERVED_LINE_BREAK = "observed_controlled_pass_crossed_supplied_line"
    CONTROLLED_PASS_EVIDENCE_MISSING = "controlled_pass_evidence_missing"
    LINE_EVIDENCE_MISSING = "line_evidence_missing"
    LINE_X_MISSING = "line_x_missing"
    LINE_X_INVALID = "line_x_invalid"
    LINE_NOT_OBSERVED = "line_not_observed"
    ATTACKING_DIRECTION_INVALID = "attacking_direction_invalid"
    ATTACKING_DIRECTION_CONFLICT = "attacking_direction_conflict"
    RELEASE_RELATION_EVIDENCE_MISSING = "release_relation_evidence_missing"
    RECEPTION_RELATION_EVIDENCE_MISSING = "reception_relation_evidence_missing"
    RELEASE_RELATION_EVIDENCE_AMBIGUOUS = "release_relation_evidence_ambiguous"
    RECEPTION_RELATION_EVIDENCE_AMBIGUOUS = "reception_relation_evidence_ambiguous"
    RELATION_LINE_CONFLICT = "relation_line_conflict"
    RELATION_DIRECTION_CONFLICT = "relation_direction_conflict"
    RELATION_POSITION_UNKNOWN = "relation_position_unknown"
    RELATION_POSITION_INVALID = "relation_position_invalid"
    RELATION_POSITION_CONTRADICTORY = "relation_position_contradictory"
    CONTROLLED_PASS_NOT_ESTABLISHED = "controlled_pass_not_established"
    RELEASE_ALREADY_AHEAD_OF_LINE = "release_already_ahead_of_line"
    RELEASE_LEVEL_NOT_ACCEPTED = "release_level_not_accepted"
    RECEPTION_NOT_AHEAD_OF_LINE = "reception_not_ahead_of_line"


@dataclass(frozen=True)
class ControlledLineBreakConfig:
    line_buffer_m: float = 0.0
    release_level_counts_as_not_yet_beyond: bool = True
    tie_epsilon_m: float = 1e-9


@dataclass(frozen=True)
class ControlledPassEvidence:
    anchor_id: str | None = None
    pass_episode_id: str | None = None
    status: Status | None = PASS
    relation_id: str | None = None
    evidence_id: str | None = None
    release_anchor_frame_id: int | str | None = None
    reception_anchor_frame_id: int | str | None = None


@dataclass(frozen=True)
class ObservedLineEvidence:
    line_x_m: float | None
    attacking_direction: int | None
    anchor_id: str | None = None
    status: Status | None = PASS
    relation_id: str | None = None
    evidence_id: str | None = None
    anchor_frame_id: int | str | None = None


@dataclass(frozen=True)
class RelativePositionEvidence:
    status: Status | None = None
    entity_position: PositionInput | None = None
    signed_distance_to_line_m: float | None = None
    line_x_m: float | None = None
    attacking_direction: int | None = None
    entity_id: str | None = None
    relation_id: str | None = None
    evidence_id: str | None = None
    anchor_id: str | None = None
    anchor_frame_id: int | str | None = None
    phase: str | None = None


@dataclass(frozen=True)
class ControlledLineBreakEvaluation:
    status: Status
    reason: str | None
    anchor_id: str | None
    controlled_pass_anchor_id: str | None
    line_anchor_id: str | None
    controlled_pass_relation_id: str | None
    controlled_pass_evidence_id: str | None
    line_relation_id: str | None
    line_evidence_id: str | None
    release_relation_id: str | None
    release_evidence_id: str | None
    reception_relation_id: str | None
    reception_evidence_id: str | None
    pass_episode_id: str | None
    release_anchor_frame_id: int | str | None
    reception_anchor_frame_id: int | str | None
    line_anchor_frame_id: int | str | None
    attacking_direction: int | None
    line_x_m: float | None
    normalized_line_x_m: float | None
    release_status: str | None
    release_reason: str | None
    release_signed_distance_to_line_m: float | None
    release_distance_to_line_m: float | None
    reception_status: str | None
    reception_reason: str | None
    reception_signed_distance_to_line_m: float | None
    reception_distance_to_line_m: float | None
    line_buffer_m: float
    release_level_counts_as_not_yet_beyond: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _RelationSide:
    status: str | None
    reason: str | None
    signed_distance_to_line_m: float | None
    distance_to_line_m: float | None
    relation_id: str | None
    evidence_id: str | None
    anchor_frame_id: int | str | None


def evaluate_controlled_line_break_episode(
    *,
    controlled_pass_evidence: object | None,
    observed_line_evidence: object | None,
    release_relative_position_evidence: object | None = None,
    reception_relative_position_evidence: object | None = None,
    relative_position_evidence: Sequence[object] | None = None,
    attacking_direction: int | None = None,
    anchor_id: str | None = None,
    config: ControlledLineBreakConfig = ControlledLineBreakConfig(),
) -> ControlledLineBreakEvaluation:
    """Evaluate whether a controlled pass crossed a supplied observed line."""

    _validate_config(config)
    release_relative_position_evidence, reception_relative_position_evidence, selection_reason = (
        _resolve_relative_evidence(
            release_relative_position_evidence=release_relative_position_evidence,
            reception_relative_position_evidence=reception_relative_position_evidence,
            relative_position_evidence=relative_position_evidence,
        )
    )

    controlled = _controlled_pass_metadata(controlled_pass_evidence)
    line = _line_metadata(observed_line_evidence)
    resolved_direction, direction_reason = _resolve_attacking_direction(
        attacking_direction,
        line.attacking_direction,
        _extract_field(release_relative_position_evidence, "attacking_direction"),
        _extract_field(reception_relative_position_evidence, "attacking_direction"),
    )
    normalized_line_x = None if line.line_x_m is None or resolved_direction is None else line.line_x_m * resolved_direction

    release_side = _coerce_relation_side(
        release_relative_position_evidence,
        line_x_m=line.line_x_m,
        attacking_direction=resolved_direction,
        config=config,
    )
    reception_side = _coerce_relation_side(
        reception_relative_position_evidence,
        line_x_m=line.line_x_m,
        attacking_direction=resolved_direction,
        config=config,
    )

    base = {
        "anchor_id": anchor_id or _default_anchor_id(controlled.anchor_id, line.anchor_id),
        "controlled_pass_anchor_id": controlled.anchor_id,
        "line_anchor_id": line.anchor_id,
        "controlled_pass_relation_id": controlled.relation_id,
        "controlled_pass_evidence_id": controlled.evidence_id,
        "line_relation_id": line.relation_id,
        "line_evidence_id": line.evidence_id,
        "release_relation_id": release_side.relation_id,
        "release_evidence_id": release_side.evidence_id,
        "reception_relation_id": reception_side.relation_id,
        "reception_evidence_id": reception_side.evidence_id,
        "pass_episode_id": controlled.pass_episode_id,
        "release_anchor_frame_id": release_side.anchor_frame_id or controlled.release_anchor_frame_id,
        "reception_anchor_frame_id": reception_side.anchor_frame_id or controlled.reception_anchor_frame_id,
        "line_anchor_frame_id": line.anchor_frame_id,
        "attacking_direction": resolved_direction,
        "line_x_m": line.line_x_m,
        "normalized_line_x_m": normalized_line_x,
        "release_status": release_side.status,
        "release_reason": release_side.reason,
        "release_signed_distance_to_line_m": release_side.signed_distance_to_line_m,
        "release_distance_to_line_m": release_side.distance_to_line_m,
        "reception_status": reception_side.status,
        "reception_reason": reception_side.reason,
        "reception_signed_distance_to_line_m": reception_side.signed_distance_to_line_m,
        "reception_distance_to_line_m": reception_side.distance_to_line_m,
        "line_buffer_m": config.line_buffer_m,
        "release_level_counts_as_not_yet_beyond": config.release_level_counts_as_not_yet_beyond,
    }

    if controlled_pass_evidence is None:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.CONTROLLED_PASS_EVIDENCE_MISSING.value, base)
    if observed_line_evidence is None:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.LINE_EVIDENCE_MISSING.value, base)
    if selection_reason is not None:
        return _evaluation(UNKNOWN, selection_reason, base)
    if controlled.status == UNKNOWN:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.CONTROLLED_PASS_NOT_ESTABLISHED.value, base)
    if controlled.status is not None and controlled.status != PASS:
        return _evaluation(FAIL, ControlledLineBreakReason.CONTROLLED_PASS_NOT_ESTABLISHED.value, base)
    if line.status == UNKNOWN:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.LINE_NOT_OBSERVED.value, base)
    if line.status is not None and line.status != PASS:
        return _evaluation(FAIL, ControlledLineBreakReason.LINE_NOT_OBSERVED.value, base)
    if line.line_reason is not None:
        return _evaluation(UNKNOWN, line.line_reason, base)
    if direction_reason is not None:
        return _evaluation(UNKNOWN, direction_reason, base)
    if release_relative_position_evidence is None:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.RELEASE_RELATION_EVIDENCE_MISSING.value, base)
    if reception_relative_position_evidence is None:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.RECEPTION_RELATION_EVIDENCE_MISSING.value, base)
    relation_conflict = _relation_conflict_reason(
        line_x_m=line.line_x_m,
        attacking_direction=resolved_direction,
        relation_evidences=(release_relative_position_evidence, reception_relative_position_evidence),
        config=config,
    )
    if relation_conflict is not None:
        return _evaluation(UNKNOWN, relation_conflict, base)
    if release_side.reason is not None:
        return _evaluation(UNKNOWN, release_side.reason, base)
    if reception_side.reason is not None:
        return _evaluation(UNKNOWN, reception_side.reason, base)

    if release_side.status == AHEAD_OF_LINE:
        return _evaluation(FAIL, ControlledLineBreakReason.RELEASE_ALREADY_AHEAD_OF_LINE.value, base)
    if release_side.status == LEVEL_WITH_LINE and not config.release_level_counts_as_not_yet_beyond:
        return _evaluation(FAIL, ControlledLineBreakReason.RELEASE_LEVEL_NOT_ACCEPTED.value, base)
    if release_side.status not in {BEHIND_LINE, LEVEL_WITH_LINE}:
        return _evaluation(UNKNOWN, ControlledLineBreakReason.RELATION_POSITION_UNKNOWN.value, base)
    if reception_side.status != AHEAD_OF_LINE:
        return _evaluation(FAIL, ControlledLineBreakReason.RECEPTION_NOT_AHEAD_OF_LINE.value, base)

    return _evaluation(PASS, ControlledLineBreakReason.OBSERVED_LINE_BREAK.value, base)


def _validate_config(config: ControlledLineBreakConfig) -> None:
    if not isfinite(float(config.line_buffer_m)):
        raise ValueError("line_buffer_m must be finite")
    if config.line_buffer_m < 0:
        raise ValueError("line_buffer_m must be non-negative")
    if not isfinite(float(config.tie_epsilon_m)):
        raise ValueError("tie_epsilon_m must be finite")
    if config.tie_epsilon_m < 0:
        raise ValueError("tie_epsilon_m must be non-negative")
    if not isinstance(config.release_level_counts_as_not_yet_beyond, bool):
        raise ValueError("release_level_counts_as_not_yet_beyond must be boolean")


@dataclass(frozen=True)
class _ControlledPassMetadata:
    anchor_id: str | None
    pass_episode_id: str | None
    status: str | None
    relation_id: str | None
    evidence_id: str | None
    release_anchor_frame_id: int | str | None
    reception_anchor_frame_id: int | str | None


@dataclass(frozen=True)
class _LineMetadata:
    anchor_id: str | None
    status: str | None
    relation_id: str | None
    evidence_id: str | None
    anchor_frame_id: int | str | None
    line_x_m: float | None
    line_reason: str | None
    attacking_direction: object | None


def _controlled_pass_metadata(value: object | None) -> _ControlledPassMetadata:
    return _ControlledPassMetadata(
        anchor_id=_string_or_none(_first_field(value, "anchor_id", "controlled_pass_anchor_id")),
        pass_episode_id=_string_or_none(_first_field(value, "pass_episode_id")),
        status=_status_or_none(_first_field(value, "controlled_pass_status", "evaluation_status", "status")),
        relation_id=_string_or_none(_first_field(value, "relation_id", "controlled_pass_relation_id")),
        evidence_id=_string_or_none(_first_field(value, "evidence_id", "controlled_pass_evidence_id")),
        release_anchor_frame_id=_first_field(value, "physical_release_frame_id", "release_anchor_frame_id"),
        reception_anchor_frame_id=_first_field(value, "controlled_reception_frame_id", "reception_anchor_frame_id"),
    )


def _line_metadata(value: object | None) -> _LineMetadata:
    line_x, line_reason = _coerce_line_x(_first_field(value, "line_x_m", "x_m"))
    return _LineMetadata(
        anchor_id=_string_or_none(_first_field(value, "anchor_id", "line_anchor_id", "selected_band_id")),
        status=_status_or_none(_first_field(value, "line_status", "evaluation_status", "status")),
        relation_id=_string_or_none(_first_field(value, "relation_id", "line_relation_id")),
        evidence_id=_string_or_none(_first_field(value, "evidence_id", "line_evidence_id")),
        anchor_frame_id=_first_field(value, "line_evaluation_frame_id", "line_anchor_frame_id", "anchor_frame_id"),
        line_x_m=line_x,
        line_reason=line_reason,
        attacking_direction=_first_field(value, "attacking_direction", "attack_x_sign"),
    )


def _resolve_relative_evidence(
    *,
    release_relative_position_evidence: object | None,
    reception_relative_position_evidence: object | None,
    relative_position_evidence: Sequence[object] | None,
) -> tuple[object | None, object | None, str | None]:
    release = release_relative_position_evidence
    reception = reception_relative_position_evidence
    if relative_position_evidence is None:
        return release, reception, None

    release_records = []
    reception_records = []
    for record in relative_position_evidence:
        phase = _phase_value(record)
        if phase in {"release", "pass_release", "physical_release", "release_side"}:
            release_records.append(record)
        elif phase in {"reception", "controlled_reception", "receive", "reception_side"}:
            reception_records.append(record)

    if release is None and len(release_records) == 1:
        release = release_records[0]
    elif release is None and len(release_records) > 1:
        return release, reception, ControlledLineBreakReason.RELEASE_RELATION_EVIDENCE_AMBIGUOUS.value

    if reception is None and len(reception_records) == 1:
        reception = reception_records[0]
    elif reception is None and len(reception_records) > 1:
        return release, reception, ControlledLineBreakReason.RECEPTION_RELATION_EVIDENCE_AMBIGUOUS.value

    return release, reception, None


def _coerce_relation_side(
    value: object | None,
    *,
    line_x_m: float | None,
    attacking_direction: int | None,
    config: ControlledLineBreakConfig,
) -> _RelationSide:
    relation_id = _string_or_none(_first_field(value, "relation_id", "relative_position_relation_id"))
    evidence_id = _string_or_none(_first_field(value, "evidence_id", "relative_position_evidence_id"))
    anchor_frame_id = _first_field(value, "anchor_frame_id")
    status = _normalize_relation_status(
        _first_field(value, "relative_position_status", "status", "relation_status", "position_status")
    )
    raw_signed_distance = _first_field(value, "signed_distance_to_line_m")
    signed_distance, distance_reason = _coerce_optional_float(
        raw_signed_distance,
        invalid_reason=ControlledLineBreakReason.RELATION_POSITION_INVALID.value,
    )

    if value is None:
        return _RelationSide(None, None, None, None, None, None, None)
    if status == UNKNOWN:
        return _RelationSide(
            status,
            ControlledLineBreakReason.RELATION_POSITION_UNKNOWN.value,
            signed_distance,
            None if signed_distance is None else abs(signed_distance),
            relation_id,
            evidence_id,
            anchor_frame_id,
        )
    if distance_reason is not None:
        return _RelationSide(status, distance_reason, None, None, relation_id, evidence_id, anchor_frame_id)

    computed_distance = signed_distance
    if computed_distance is None:
        try:
            entity_x = _entity_x_from_relation(value)
        except ValueError as exc:
            return _RelationSide(status, str(exc), None, None, relation_id, evidence_id, anchor_frame_id)
        if entity_x is not None and line_x_m is not None and attacking_direction is not None:
            computed_distance = (entity_x * attacking_direction) - (line_x_m * attacking_direction)

    computed_status = None if computed_distance is None else _classify_signed_distance(computed_distance, config)
    if status is None:
        status = computed_status
    elif computed_status is not None and status != computed_status:
        return _RelationSide(
            status,
            ControlledLineBreakReason.RELATION_POSITION_CONTRADICTORY.value,
            computed_distance,
            abs(computed_distance),
            relation_id,
            evidence_id,
            anchor_frame_id,
        )

    if status is None:
        return _RelationSide(
            None,
            ControlledLineBreakReason.RELATION_POSITION_UNKNOWN.value,
            computed_distance,
            None if computed_distance is None else abs(computed_distance),
            relation_id,
            evidence_id,
            anchor_frame_id,
        )

    return _RelationSide(
        status,
        None,
        computed_distance,
        None if computed_distance is None else abs(computed_distance),
        relation_id,
        evidence_id,
        anchor_frame_id,
    )


def _relation_conflict_reason(
    *,
    line_x_m: float | None,
    attacking_direction: int | None,
    relation_evidences: tuple[object | None, ...],
    config: ControlledLineBreakConfig,
) -> str | None:
    for relation in relation_evidences:
        relation_line_x, line_reason = _coerce_line_x(_first_field(relation, "line_x_m"))
        if line_reason == ControlledLineBreakReason.LINE_X_INVALID.value:
            return ControlledLineBreakReason.RELATION_POSITION_INVALID.value
        if relation_line_x is not None and line_x_m is not None:
            if abs(relation_line_x - line_x_m) > config.tie_epsilon_m:
                return ControlledLineBreakReason.RELATION_LINE_CONFLICT.value
        relation_direction = _first_field(relation, "attacking_direction", "attack_x_sign")
        if relation_direction is not None and attacking_direction is not None:
            resolved_relation_direction, reason = _resolve_attacking_direction(relation_direction)
            if reason is not None:
                return ControlledLineBreakReason.RELATION_DIRECTION_CONFLICT.value
            if resolved_relation_direction != attacking_direction:
                return ControlledLineBreakReason.RELATION_DIRECTION_CONFLICT.value
    return None


def _resolve_attacking_direction(*values: object | None) -> tuple[int | None, str | None]:
    direction_values = [value for value in values if value is not None]
    if not direction_values:
        return None, ControlledLineBreakReason.ATTACKING_DIRECTION_INVALID.value

    coerced_values = []
    for value in direction_values:
        if isinstance(value, bool):
            return None, ControlledLineBreakReason.ATTACKING_DIRECTION_INVALID.value
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            return None, ControlledLineBreakReason.ATTACKING_DIRECTION_INVALID.value
        if coerced not in {-1, 1}:
            return None, ControlledLineBreakReason.ATTACKING_DIRECTION_INVALID.value
        coerced_values.append(coerced)

    if len(set(coerced_values)) > 1:
        return None, ControlledLineBreakReason.ATTACKING_DIRECTION_CONFLICT.value
    return coerced_values[0], None


def _coerce_line_x(value: object | None) -> tuple[float | None, str | None]:
    if value is None:
        return None, ControlledLineBreakReason.LINE_X_MISSING.value
    if isinstance(value, bool):
        return None, ControlledLineBreakReason.LINE_X_INVALID.value
    try:
        line_x = float(value)
    except (TypeError, ValueError):
        return None, ControlledLineBreakReason.LINE_X_INVALID.value
    if not isfinite(line_x):
        return None, ControlledLineBreakReason.LINE_X_INVALID.value
    return line_x, None


def _coerce_optional_float(value: object | None, *, invalid_reason: str) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, invalid_reason
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None, invalid_reason
    if not isfinite(result):
        return None, invalid_reason
    return result, None


def _classify_signed_distance(signed_distance: float, config: ControlledLineBreakConfig) -> str:
    if signed_distance > config.line_buffer_m:
        return AHEAD_OF_LINE
    if signed_distance < -config.line_buffer_m:
        return BEHIND_LINE
    return LEVEL_WITH_LINE


def _entity_x_from_relation(value: object) -> float | None:
    explicit_x = _first_field(value, "entity_x_m", "x_m")
    if explicit_x is None:
        entity_position = _extract_field(value, "entity_position")
        explicit_x = _position_x(entity_position)
    entity_x, reason = _coerce_optional_float(
        explicit_x,
        invalid_reason=ControlledLineBreakReason.RELATION_POSITION_INVALID.value,
    )
    if reason is not None:
        raise ValueError(reason)
    return entity_x


def _position_x(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        if "x_m" in value:
            return value["x_m"]
        return value.get("x")
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value[0] if value else None
    return getattr(value, "x_m", getattr(value, "x", None))


def _normalize_relation_status(value: object | None) -> str | None:
    status = _status_or_none(value)
    if status in {AHEAD_OF_LINE, BEHIND_LINE, LEVEL_WITH_LINE, UNKNOWN}:
        return status
    return None


def _status_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    status = str(value)
    return status if status else None


def _phase_value(value: object) -> str | None:
    raw_phase = _first_field(value, "phase", "side", "moment", "event")
    if raw_phase is None:
        return None
    return str(raw_phase).strip().lower()


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


def _default_anchor_id(controlled_pass_anchor_id: str | None, line_anchor_id: str | None) -> str | None:
    if controlled_pass_anchor_id is None or line_anchor_id is None:
        return None
    return f"controlled_line_break:{controlled_pass_anchor_id}:{line_anchor_id}"


def _evaluation(status: str, reason: str | None, base: Mapping[str, Any]) -> ControlledLineBreakEvaluation:
    return ControlledLineBreakEvaluation(status=status, reason=reason, **base)
