"""Pure geometric support-arrival evaluation.

This module evaluates only whether declared candidate players are observed
inside a declared geometric support region within a declared arrival window and
for a declared duration. It does not infer tactical intention, support quality,
pass optimality, communication, scanning, or causal effect.

Supported region modes:

* ``WITHIN_DISTANCE_OF_REFERENCE_POINT``: candidate is within
  ``maximum_support_distance_m`` of a static ``reference_point`` or dynamic
  ``reference_positions`` point.
* ``BEHIND_BALL_OUTLET``: same distance requirement, and candidate x-position
  is behind or level with the reference point in the declared attacking
  direction.
* ``AHEAD_OF_BALL_OPTION``: same distance requirement, and candidate x-position
  is ahead of or level with the reference point in the declared attacking
  direction.

All boundaries are inclusive with a tiny floating-point tolerance. Dynamic
reference points and candidate positions are evaluated at supplied frame IDs.
Timing must be supplied through ``analysis_rate_hz`` or explicit
``frame_times``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from math import ceil, hypot, isfinite
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

WITHIN_DISTANCE_OF_REFERENCE_POINT = "WITHIN_DISTANCE_OF_REFERENCE_POINT"
BEHIND_BALL_OUTLET = "BEHIND_BALL_OUTLET"
AHEAD_OF_BALL_OPTION = "AHEAD_OF_BALL_OPTION"
SUPPORTED_REGION_MODES = (
    WITHIN_DISTANCE_OF_REFERENCE_POINT,
    BEHIND_BALL_OUTLET,
    AHEAD_OF_BALL_OPTION,
)

Status = str
FrameId = int | str | None
PositionInput = tuple[float, ...] | list[float] | Mapping[str, Any]

_EPSILON = 1e-9


class SupportArrivalStatus(str, Enum):
    PASS = PASS
    FAIL = FAIL
    UNKNOWN = UNKNOWN


class SupportArrivalReason(str, Enum):
    REQUIREMENT_SATISFIED = "support_arrival_requirement_satisfied"
    REQUIREMENT_NOT_MET = "support_arrival_requirement_not_met"
    INVALID_CONFIG = "invalid_support_arrival_config"
    UNSUPPORTED_REGION_MODE = "unsupported_support_region_mode"
    ATTACKING_DIRECTION_INVALID = "attacking_direction_invalid"
    ANCHOR_FRAME_MISSING = "anchor_frame_missing"
    FRAME_TIMING_MISSING = "frame_timing_missing"
    ANCHOR_TIME_MISSING = "anchor_time_missing"
    INVALID_FRAME_TIMING = "invalid_frame_timing"
    IRREGULAR_FRAME_TIMING = "irregular_frame_timing"
    FRAME_COVERAGE_MISSING = "frame_coverage_missing"
    CANDIDATE_POSITIONS_MISSING = "candidate_positions_missing"
    NO_CANDIDATE_PLAYERS = "no_candidate_players"
    INVALID_PLAYER_IDS = "invalid_player_ids"
    MISSING_CANDIDATE_EVIDENCE = "missing_candidate_evidence"
    CANDIDATE_FRAME_EVIDENCE_MISSING = "candidate_frame_evidence_missing"
    CANDIDATE_COORDINATES_INVALID = "candidate_coordinates_invalid"
    DUPLICATE_CANDIDATE_FRAME_RECORDS = "duplicate_candidate_frame_records"
    REFERENCE_POINT_MISSING = "reference_point_missing"
    REFERENCE_POINT_INVALID = "reference_point_invalid"
    REFERENCE_POSITION_MISSING = "reference_position_missing"
    REFERENCE_COORDINATES_INVALID = "reference_coordinates_invalid"
    DUPLICATE_REFERENCE_FRAME_RECORDS = "duplicate_reference_frame_records"


@dataclass(frozen=True)
class SupportArrivalConfig:
    support_region_mode: str = WITHIN_DISTANCE_OF_REFERENCE_POINT
    maximum_arrival_seconds: float = 1.0
    minimum_duration_seconds: float = 0.0
    maximum_support_distance_m: float = 5.0
    minimum_supporting_players: int = 1
    attacking_direction: int | None = None


@dataclass(frozen=True)
class SupportArrivalConfigEvidence:
    support_region_mode: str | None
    maximum_arrival_seconds: float | None
    minimum_duration_seconds: float | None
    maximum_support_distance_m: float | None
    minimum_supporting_players: int | None
    attacking_direction: int | None
    timing_source: str | None
    analysis_rate_hz: float | None
    supported_region_modes: tuple[str, ...]
    boundary_policy: str
    invalid_config_fields: tuple[str, ...]


@dataclass(frozen=True)
class SupportFrameEvidence:
    frame_id: FrameId
    seconds_after_anchor: float | None
    in_support_region: bool | None
    reason: str | None
    distance_to_reference_m: float | None
    candidate_x_m: float | None
    candidate_y_m: float | None
    reference_x_m: float | None
    reference_y_m: float | None


@dataclass(frozen=True)
class SupportPlayerEvidence:
    player_id: str
    status: Status
    reason: str
    first_arrival_frame_id: FrameId
    first_arrival_seconds_after_anchor: float | None
    support_duration_seconds: float | None
    observed_frame_ids: tuple[FrameId, ...]
    qualifying_frame_ids: tuple[FrameId, ...]
    missing_frame_ids: tuple[FrameId, ...]
    invalid_frame_ids: tuple[FrameId, ...]
    duplicate_frame_ids: tuple[FrameId, ...]
    frame_evidence: tuple[SupportFrameEvidence, ...]


@dataclass(frozen=True)
class SupportArrivalEvaluation:
    status: Status
    reason: str
    anchor_id: str | None
    anchor_frame_id: FrameId
    reference_player_id: str | None
    support_window_start_frame_id: FrameId
    support_window_end_frame_id: FrameId
    support_window_start_seconds_after_anchor: float | None
    support_window_end_seconds_after_anchor: float | None
    analysis_frame_ids: tuple[FrameId, ...]
    supporting_player_ids: tuple[str, ...]
    first_arrival_frame_id: FrameId
    first_arrival_seconds_after_anchor: float | None
    support_duration_seconds: float | None
    candidate_player_ids: tuple[str, ...]
    evaluated_candidate_player_ids: tuple[str, ...]
    missing_candidate_player_ids: tuple[str, ...]
    invalid_candidate_player_ids: tuple[str, ...]
    invalid_coordinate_player_ids: tuple[str, ...]
    duplicate_candidate_player_ids: tuple[str, ...]
    missing_frame_ids: tuple[FrameId, ...]
    invalid_frame_ids: tuple[FrameId, ...]
    missing_reference_frame_ids: tuple[FrameId, ...]
    invalid_reference_frame_ids: tuple[FrameId, ...]
    duplicate_reference_frame_ids: tuple[FrameId, ...]
    per_player_evidence: tuple[SupportPlayerEvidence, ...]
    coverage_status: str
    config_evidence: SupportArrivalConfigEvidence

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ResolvedConfig:
    support_region_mode: str | None
    maximum_arrival_seconds: float | None
    minimum_duration_seconds: float | None
    maximum_support_distance_m: float | None
    minimum_supporting_players: int | None
    attacking_direction: int | None
    invalid_config_fields: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class _PositionRecord:
    index: int
    player_id: str | None
    frame_id: FrameId
    x_m: float | None
    y_m: float | None
    team_id: str | None
    invalid_player_id: str | None
    frame_invalid: bool
    coordinate_invalid: bool


@dataclass(frozen=True)
class _Point:
    x_m: float
    y_m: float


@dataclass(frozen=True)
class _Timing:
    timing_source: str | None
    analysis_rate_hz: float | None
    frame_times: dict[FrameId, float]
    analysis_frame_ids: tuple[FrameId, ...]
    support_window_end_frame_id: FrameId
    missing_frame_ids: tuple[FrameId, ...]
    invalid_frame_ids: tuple[FrameId, ...]
    reason: str | None


@dataclass(frozen=True)
class _ReferenceEvidence:
    points_by_frame: dict[FrameId, _Point]
    missing_reference_frame_ids: tuple[FrameId, ...]
    invalid_reference_frame_ids: tuple[FrameId, ...]
    duplicate_reference_frame_ids: tuple[FrameId, ...]
    reason: str | None


def evaluate_support_arrival_relation(
    *,
    anchor: Mapping[str, object] | None = None,
    anchor_id: str | None = None,
    anchor_frame_id: object | None = None,
    reference_player_id: object | None = None,
    reference_positions: Sequence[object] | None = None,
    reference_point: PositionInput | None = None,
    candidate_positions: Sequence[object] | None = None,
    candidate_player_ids: Sequence[object] | None = None,
    allowed_candidate_player_ids: Sequence[object] | None = None,
    allowed_candidate_team_ids: Sequence[object] | None = None,
    excluded_candidate_player_ids: Sequence[object] | None = None,
    frame_times: Mapping[object, object] | Sequence[object] | None = None,
    analysis_rate_hz: object | None = None,
    support_criteria: Mapping[str, object] | None = None,
    config: SupportArrivalConfig = SupportArrivalConfig(),
    support_region_mode: object | None = None,
    maximum_arrival_seconds: object | None = None,
    minimum_duration_seconds: object | None = None,
    maximum_support_distance_m: object | None = None,
    minimum_supporting_players: object | None = None,
    attacking_direction: object | None = None,
) -> SupportArrivalEvaluation:
    """Evaluate a declared geometric support-arrival relation.

    Candidate and reference inputs are plain dictionaries, dataclass-like
    objects, or simple ``(x, y)`` positions. The result is deterministic and
    JSON-compatible through ``to_dict()``.
    """

    if anchor is not None:
        if anchor_id is None:
            anchor_id = _string_or_none(_first_field(anchor, "anchor_id", "id", "action_id"))
        if anchor_frame_id is None:
            anchor_frame_id = _first_field(anchor, "anchor_frame_id", "frame_id", "frame")

    normalized_anchor_frame_id, anchor_frame_invalid = _normalize_frame_id(anchor_frame_id)
    normalized_reference_player_id, reference_player_invalid = _coerce_optional_player_id(reference_player_id)
    resolved_config = _resolve_config(
        config=config,
        support_criteria=support_criteria,
        support_region_mode=support_region_mode,
        maximum_arrival_seconds=maximum_arrival_seconds,
        minimum_duration_seconds=minimum_duration_seconds,
        maximum_support_distance_m=maximum_support_distance_m,
        minimum_supporting_players=minimum_supporting_players,
        attacking_direction=attacking_direction,
    )
    horizon_seconds = (
        None
        if resolved_config.maximum_arrival_seconds is None or resolved_config.minimum_duration_seconds is None
        else resolved_config.maximum_arrival_seconds + resolved_config.minimum_duration_seconds
    )

    candidate_records = _parse_position_records(candidate_positions or ())
    reference_records = _parse_position_records(reference_positions or ())
    candidate_ids, invalid_candidate_ids = _resolve_candidate_ids(
        candidate_records=candidate_records,
        candidate_player_ids=candidate_player_ids,
        allowed_candidate_player_ids=allowed_candidate_player_ids,
        allowed_candidate_team_ids=allowed_candidate_team_ids,
        excluded_candidate_player_ids=excluded_candidate_player_ids,
    )
    if reference_player_invalid:
        invalid_candidate_ids = _sorted_tuple((*invalid_candidate_ids, "reference_player_id:invalid_player_id"))

    timing = _resolve_timing(
        anchor_frame_id=normalized_anchor_frame_id,
        anchor_frame_invalid=anchor_frame_invalid,
        horizon_seconds=horizon_seconds,
        frame_times=frame_times,
        analysis_rate_hz=analysis_rate_hz,
    )
    config_evidence = SupportArrivalConfigEvidence(
        support_region_mode=resolved_config.support_region_mode,
        maximum_arrival_seconds=resolved_config.maximum_arrival_seconds,
        minimum_duration_seconds=resolved_config.minimum_duration_seconds,
        maximum_support_distance_m=resolved_config.maximum_support_distance_m,
        minimum_supporting_players=resolved_config.minimum_supporting_players,
        attacking_direction=resolved_config.attacking_direction,
        timing_source=timing.timing_source,
        analysis_rate_hz=timing.analysis_rate_hz,
        supported_region_modes=SUPPORTED_REGION_MODES,
        boundary_policy="distance_and_direction_boundaries_inclusive",
        invalid_config_fields=resolved_config.invalid_config_fields,
    )

    empty_base = {
        "anchor_id": anchor_id,
        "anchor_frame_id": normalized_anchor_frame_id,
        "reference_player_id": normalized_reference_player_id,
        "support_window_start_frame_id": normalized_anchor_frame_id,
        "support_window_end_frame_id": timing.support_window_end_frame_id,
        "support_window_start_seconds_after_anchor": 0.0 if normalized_anchor_frame_id is not None else None,
        "support_window_end_seconds_after_anchor": horizon_seconds,
        "analysis_frame_ids": timing.analysis_frame_ids,
        "supporting_player_ids": (),
        "first_arrival_frame_id": None,
        "first_arrival_seconds_after_anchor": None,
        "support_duration_seconds": None,
        "candidate_player_ids": candidate_ids,
        "evaluated_candidate_player_ids": (),
        "missing_candidate_player_ids": (),
        "invalid_candidate_player_ids": invalid_candidate_ids,
        "invalid_coordinate_player_ids": (),
        "duplicate_candidate_player_ids": (),
        "missing_frame_ids": timing.missing_frame_ids,
        "invalid_frame_ids": timing.invalid_frame_ids,
        "missing_reference_frame_ids": (),
        "invalid_reference_frame_ids": (),
        "duplicate_reference_frame_ids": (),
        "per_player_evidence": (),
        "config_evidence": config_evidence,
    }

    if resolved_config.reason is not None:
        return _evaluation(UNKNOWN, resolved_config.reason, {**empty_base, "coverage_status": UNKNOWN})
    if timing.reason is not None:
        return _evaluation(UNKNOWN, timing.reason, {**empty_base, "coverage_status": UNKNOWN})
    if candidate_positions is None or len(candidate_records) == 0:
        return _evaluation(
            UNKNOWN,
            SupportArrivalReason.CANDIDATE_POSITIONS_MISSING.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )
    if invalid_candidate_ids:
        return _evaluation(
            UNKNOWN,
            SupportArrivalReason.INVALID_PLAYER_IDS.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )
    if not candidate_ids:
        return _evaluation(
            UNKNOWN,
            SupportArrivalReason.NO_CANDIDATE_PLAYERS.value,
            {**empty_base, "coverage_status": UNKNOWN},
        )

    selected_records = [record for record in candidate_records if record.player_id in set(candidate_ids)]
    records_by_player = _records_by_player(selected_records, timing.analysis_frame_ids)
    candidate_ids_with_records = _sorted_tuple(records_by_player)
    missing_candidate_ids = _sorted_tuple(set(candidate_ids) - set(candidate_ids_with_records))

    reference_evidence = _resolve_reference_evidence(
        reference_point=reference_point,
        reference_records=reference_records,
        reference_player_id=normalized_reference_player_id,
        analysis_frame_ids=timing.analysis_frame_ids,
    )

    per_player = tuple(
        _evaluate_candidate(
            player_id=player_id,
            records=records_by_player.get(player_id, ()),
            analysis_frame_ids=timing.analysis_frame_ids,
            frame_times=timing.frame_times,
            reference_points=reference_evidence.points_by_frame,
            config=resolved_config,
        )
        for player_id in candidate_ids
    )

    evaluated_candidate_ids = _sorted_tuple(
        evidence.player_id for evidence in per_player if evidence.observed_frame_ids or evidence.status == PASS
    )
    invalid_coordinate_player_ids = _sorted_tuple(
        evidence.player_id for evidence in per_player if evidence.invalid_frame_ids
    )
    duplicate_candidate_player_ids = _sorted_tuple(
        evidence.player_id for evidence in per_player if evidence.duplicate_frame_ids
    )
    missing_frame_ids = _sorted_tuple(
        set(timing.missing_frame_ids)
        | {
            frame_id
            for evidence in per_player
            for frame_id in evidence.missing_frame_ids
        }
    )
    invalid_frame_ids = _sorted_tuple(
        set(timing.invalid_frame_ids)
        | {
            frame_id
            for evidence in per_player
            for frame_id in evidence.invalid_frame_ids
        }
        | set(reference_evidence.invalid_reference_frame_ids)
    )

    pass_evidence = tuple(
        sorted(
            (evidence for evidence in per_player if evidence.status == PASS),
            key=lambda item: (
                float("inf")
                if item.first_arrival_seconds_after_anchor is None
                else item.first_arrival_seconds_after_anchor,
                _stable_sort_key(item.player_id),
            ),
        )
    )
    supporting_player_ids = tuple(evidence.player_id for evidence in pass_evidence)
    counted_support = pass_evidence[: resolved_config.minimum_supporting_players or 0]
    first_arrival_frame_id = counted_support[0].first_arrival_frame_id if counted_support else None
    first_arrival_seconds = counted_support[0].first_arrival_seconds_after_anchor if counted_support else None
    support_duration = _aggregate_support_duration(counted_support)

    result_base = {
        **empty_base,
        "supporting_player_ids": supporting_player_ids,
        "first_arrival_frame_id": first_arrival_frame_id,
        "first_arrival_seconds_after_anchor": first_arrival_seconds,
        "support_duration_seconds": support_duration,
        "evaluated_candidate_player_ids": evaluated_candidate_ids,
        "missing_candidate_player_ids": missing_candidate_ids,
        "invalid_coordinate_player_ids": invalid_coordinate_player_ids,
        "duplicate_candidate_player_ids": duplicate_candidate_player_ids,
        "missing_frame_ids": missing_frame_ids,
        "invalid_frame_ids": invalid_frame_ids,
        "missing_reference_frame_ids": reference_evidence.missing_reference_frame_ids,
        "invalid_reference_frame_ids": reference_evidence.invalid_reference_frame_ids,
        "duplicate_reference_frame_ids": reference_evidence.duplicate_reference_frame_ids,
        "per_player_evidence": per_player,
    }

    unknown_reason = _unknown_reason(
        per_player=per_player,
        missing_candidate_player_ids=missing_candidate_ids,
        reference_evidence=reference_evidence,
    )
    if len(pass_evidence) >= (resolved_config.minimum_supporting_players or 0):
        coverage_status = "COMPLETE" if unknown_reason is None else "SUFFICIENT"
        return _evaluation(
            PASS,
            SupportArrivalReason.REQUIREMENT_SATISFIED.value,
            {**result_base, "coverage_status": coverage_status},
        )
    if unknown_reason is not None:
        return _evaluation(UNKNOWN, unknown_reason, {**result_base, "coverage_status": UNKNOWN})
    return _evaluation(
        FAIL,
        SupportArrivalReason.REQUIREMENT_NOT_MET.value,
        {**result_base, "coverage_status": "COMPLETE"},
    )


def _resolve_config(
    *,
    config: SupportArrivalConfig,
    support_criteria: Mapping[str, object] | None,
    support_region_mode: object | None,
    maximum_arrival_seconds: object | None,
    minimum_duration_seconds: object | None,
    maximum_support_distance_m: object | None,
    minimum_supporting_players: object | None,
    attacking_direction: object | None,
) -> _ResolvedConfig:
    mode = _criteria_or_override(
        support_criteria,
        "support_region_mode",
        support_region_mode,
        config.support_region_mode,
    )
    max_arrival = _criteria_or_override(
        support_criteria,
        "maximum_arrival_seconds",
        maximum_arrival_seconds,
        config.maximum_arrival_seconds,
    )
    min_duration = _criteria_or_override(
        support_criteria,
        "minimum_duration_seconds",
        minimum_duration_seconds,
        config.minimum_duration_seconds,
    )
    max_distance = _criteria_or_override(
        support_criteria,
        "maximum_support_distance_m",
        maximum_support_distance_m,
        config.maximum_support_distance_m,
    )
    min_players = _criteria_or_override(
        support_criteria,
        "minimum_supporting_players",
        minimum_supporting_players,
        config.minimum_supporting_players,
    )
    direction = _criteria_or_override(
        support_criteria,
        "attacking_direction",
        attacking_direction,
        config.attacking_direction,
    )

    invalid_fields: list[str] = []
    normalized_mode = str(mode).strip().upper() if mode is not None else None
    if normalized_mode not in SUPPORTED_REGION_MODES:
        return _ResolvedConfig(
            normalized_mode,
            None,
            None,
            None,
            None,
            None,
            ("support_region_mode",),
            SupportArrivalReason.UNSUPPORTED_REGION_MODE.value,
        )

    max_arrival_float = _non_negative_float(max_arrival)
    min_duration_float = _non_negative_float(min_duration)
    max_distance_float = _non_negative_float(max_distance)
    min_players_int = _positive_int(min_players)
    if max_arrival_float is None:
        invalid_fields.append("maximum_arrival_seconds")
    if min_duration_float is None:
        invalid_fields.append("minimum_duration_seconds")
    if max_distance_float is None:
        invalid_fields.append("maximum_support_distance_m")
    if min_players_int is None:
        invalid_fields.append("minimum_supporting_players")

    direction_int = None
    if direction is not None or normalized_mode in {BEHIND_BALL_OUTLET, AHEAD_OF_BALL_OPTION}:
        direction_int = _attacking_direction(direction)
        if direction_int is None:
            return _ResolvedConfig(
                normalized_mode,
                max_arrival_float,
                min_duration_float,
                max_distance_float,
                min_players_int,
                None,
                _sorted_tuple((*invalid_fields, "attacking_direction")),
                SupportArrivalReason.ATTACKING_DIRECTION_INVALID.value,
            )

    if invalid_fields:
        return _ResolvedConfig(
            normalized_mode,
            max_arrival_float,
            min_duration_float,
            max_distance_float,
            min_players_int,
            direction_int,
            _sorted_tuple(invalid_fields),
            SupportArrivalReason.INVALID_CONFIG.value,
        )
    return _ResolvedConfig(
        normalized_mode,
        max_arrival_float,
        min_duration_float,
        max_distance_float,
        min_players_int,
        direction_int,
        (),
        None,
    )


def _criteria_or_override(
    support_criteria: Mapping[str, object] | None,
    field_name: str,
    explicit_value: object | None,
    default_value: object | None,
) -> object | None:
    if explicit_value is not None:
        return explicit_value
    if support_criteria is not None and field_name in support_criteria:
        return support_criteria[field_name]
    return default_value


def _resolve_timing(
    *,
    anchor_frame_id: FrameId,
    anchor_frame_invalid: bool,
    horizon_seconds: float | None,
    frame_times: Mapping[object, object] | Sequence[object] | None,
    analysis_rate_hz: object | None,
) -> _Timing:
    if anchor_frame_invalid or anchor_frame_id is None:
        return _Timing(None, None, {}, (), None, (), (), SupportArrivalReason.ANCHOR_FRAME_MISSING.value)
    if horizon_seconds is None:
        return _Timing(None, None, {}, (), None, (), (), SupportArrivalReason.INVALID_CONFIG.value)

    rate = _positive_float(analysis_rate_hz)
    if analysis_rate_hz is not None and rate is None:
        return _Timing(None, None, {}, (), None, (), (), SupportArrivalReason.INVALID_FRAME_TIMING.value)
    if rate is not None:
        anchor_numeric = _integral_frame_id(anchor_frame_id)
        if anchor_numeric is None:
            return _Timing(None, rate, {}, (), None, (), (), SupportArrivalReason.FRAME_TIMING_MISSING.value)
        final_offset = int(ceil(max(horizon_seconds, 0.0) * rate - _EPSILON))
        frame_ids = tuple(range(anchor_numeric, anchor_numeric + final_offset + 1))
        frame_times_by_id = {frame_id: (frame_id - anchor_numeric) / rate for frame_id in frame_ids}
        return _Timing(
            "analysis_rate_hz",
            rate,
            frame_times_by_id,
            frame_ids,
            frame_ids[-1] if frame_ids else None,
            (),
            (),
            None,
        )

    parsed_times, duplicate_time_frame_ids, invalid_time_frame_ids = _parse_frame_times(frame_times)
    if frame_times is None or not parsed_times:
        return _Timing(None, None, {}, (), None, (), invalid_time_frame_ids, SupportArrivalReason.FRAME_TIMING_MISSING.value)
    if duplicate_time_frame_ids or invalid_time_frame_ids:
        return _Timing(
            "frame_times",
            None,
            parsed_times,
            (),
            None,
            (),
            _sorted_tuple(set(duplicate_time_frame_ids) | set(invalid_time_frame_ids)),
            SupportArrivalReason.INVALID_FRAME_TIMING.value,
        )
    if anchor_frame_id not in parsed_times:
        return _Timing("frame_times", None, parsed_times, (), None, (), (), SupportArrivalReason.ANCHOR_TIME_MISSING.value)

    anchor_time = parsed_times[anchor_frame_id]
    horizon_time = anchor_time + horizon_seconds
    window_items = [
        (frame_id, time_seconds - anchor_time)
        for frame_id, time_seconds in parsed_times.items()
        if anchor_time - _EPSILON <= time_seconds <= horizon_time + _EPSILON
    ]
    window_items.sort(key=lambda item: (item[1], _stable_sort_key(item[0])))
    if not window_items:
        return _Timing("frame_times", None, {}, (), None, (), (), SupportArrivalReason.FRAME_COVERAGE_MISSING.value)
    if window_items[-1][1] + _EPSILON < horizon_seconds:
        return _Timing(
            "frame_times",
            None,
            dict(window_items),
            tuple(item[0] for item in window_items),
            window_items[-1][0],
            (),
            (),
            SupportArrivalReason.FRAME_COVERAGE_MISSING.value,
        )
    if _has_integral_frame_gaps(tuple(frame_id for frame_id, _ in window_items)):
        return _Timing(
            "frame_times",
            None,
            dict(window_items),
            tuple(item[0] for item in window_items),
            window_items[-1][0],
            (),
            (),
            SupportArrivalReason.FRAME_COVERAGE_MISSING.value,
        )
    if _has_irregular_intervals(tuple(time for _, time in window_items)):
        return _Timing(
            "frame_times",
            None,
            dict(window_items),
            tuple(item[0] for item in window_items),
            window_items[-1][0],
            (),
            (),
            SupportArrivalReason.IRREGULAR_FRAME_TIMING.value,
        )
    return _Timing(
        "frame_times",
        None,
        dict(window_items),
        tuple(item[0] for item in window_items),
        window_items[-1][0],
        (),
        (),
        None,
    )


def _resolve_reference_evidence(
    *,
    reference_point: PositionInput | None,
    reference_records: Sequence[_PositionRecord],
    reference_player_id: str | None,
    analysis_frame_ids: tuple[FrameId, ...],
) -> _ReferenceEvidence:
    if reference_point is not None:
        point = _point_from_value(reference_point)
        if point is None:
            return _ReferenceEvidence(
                {},
                analysis_frame_ids,
                (),
                (),
                SupportArrivalReason.REFERENCE_POINT_INVALID.value,
            )
        return _ReferenceEvidence({frame_id: point for frame_id in analysis_frame_ids}, (), (), (), None)

    if not reference_records:
        return _ReferenceEvidence(
            {},
            analysis_frame_ids,
            (),
            (),
            SupportArrivalReason.REFERENCE_POINT_MISSING.value,
        )

    selected = [
        record
        for record in reference_records
        if reference_player_id is None or record.player_id == reference_player_id
    ]
    records_by_frame: dict[FrameId, list[_PositionRecord]] = {frame_id: [] for frame_id in analysis_frame_ids}
    for record in selected:
        if record.frame_id in records_by_frame:
            records_by_frame[record.frame_id].append(record)

    points_by_frame: dict[FrameId, _Point] = {}
    duplicate_frame_ids: list[FrameId] = []
    invalid_frame_ids: list[FrameId] = []
    missing_frame_ids: list[FrameId] = []
    for frame_id in analysis_frame_ids:
        records = records_by_frame[frame_id]
        if not records:
            missing_frame_ids.append(frame_id)
            continue
        if len(records) > 1:
            duplicate_frame_ids.append(frame_id)
            continue
        record = records[0]
        if record.coordinate_invalid:
            invalid_frame_ids.append(frame_id)
            continue
        if record.x_m is None or record.y_m is None:
            invalid_frame_ids.append(frame_id)
            continue
        points_by_frame[frame_id] = _Point(record.x_m, record.y_m)

    reason = None
    if duplicate_frame_ids:
        reason = SupportArrivalReason.DUPLICATE_REFERENCE_FRAME_RECORDS.value
    elif invalid_frame_ids:
        reason = SupportArrivalReason.REFERENCE_COORDINATES_INVALID.value
    elif missing_frame_ids:
        reason = SupportArrivalReason.REFERENCE_POSITION_MISSING.value
    return _ReferenceEvidence(
        points_by_frame,
        _sorted_tuple(missing_frame_ids),
        _sorted_tuple(invalid_frame_ids),
        _sorted_tuple(duplicate_frame_ids),
        reason,
    )


def _evaluate_candidate(
    *,
    player_id: str,
    records: Sequence[_PositionRecord],
    analysis_frame_ids: tuple[FrameId, ...],
    frame_times: Mapping[FrameId, float],
    reference_points: Mapping[FrameId, _Point],
    config: _ResolvedConfig,
) -> SupportPlayerEvidence:
    records_by_frame: dict[FrameId, list[_PositionRecord]] = {frame_id: [] for frame_id in analysis_frame_ids}
    for record in records:
        if record.frame_id in records_by_frame:
            records_by_frame[record.frame_id].append(record)

    frame_evidence: list[SupportFrameEvidence] = []
    missing_frame_ids: list[FrameId] = []
    invalid_frame_ids: list[FrameId] = []
    duplicate_frame_ids: list[FrameId] = []
    observed_frame_ids: list[FrameId] = []
    for frame_id in analysis_frame_ids:
        seconds_after_anchor = frame_times.get(frame_id)
        records_for_frame = records_by_frame[frame_id]
        reference = reference_points.get(frame_id)
        if not records_for_frame:
            missing_frame_ids.append(frame_id)
            frame_evidence.append(
                SupportFrameEvidence(frame_id, seconds_after_anchor, None, "candidate_position_missing", None, None, None, None, None)
            )
            continue
        observed_frame_ids.append(frame_id)
        if len(records_for_frame) > 1:
            duplicate_frame_ids.append(frame_id)
            frame_evidence.append(
                SupportFrameEvidence(frame_id, seconds_after_anchor, None, "duplicate_candidate_frame_record", None, None, None, None, None)
            )
            continue
        record = records_for_frame[0]
        if record.coordinate_invalid or record.x_m is None or record.y_m is None:
            invalid_frame_ids.append(frame_id)
            frame_evidence.append(
                SupportFrameEvidence(frame_id, seconds_after_anchor, None, "candidate_coordinates_invalid", None, None, None, None, None)
            )
            continue
        if reference is None:
            frame_evidence.append(
                SupportFrameEvidence(
                    frame_id,
                    seconds_after_anchor,
                    None,
                    "reference_position_missing",
                    None,
                    record.x_m,
                    record.y_m,
                    None,
                    None,
                )
            )
            continue
        in_region, distance = _in_support_region(record, reference, config)
        frame_evidence.append(
            SupportFrameEvidence(
                frame_id,
                seconds_after_anchor,
                in_region,
                "inside_support_region" if in_region else "outside_support_region",
                distance,
                record.x_m,
                record.y_m,
                reference.x_m,
                reference.y_m,
            )
        )

    qualifying = _qualifying_run(frame_evidence, config)
    if qualifying is not None:
        first_index, last_index = qualifying
        first = frame_evidence[first_index]
        last = frame_evidence[last_index]
        duration = None
        if first.seconds_after_anchor is not None and last.seconds_after_anchor is not None:
            duration = last.seconds_after_anchor - first.seconds_after_anchor
        return SupportPlayerEvidence(
            player_id=player_id,
            status=PASS,
            reason="support_arrival_observed",
            first_arrival_frame_id=first.frame_id,
            first_arrival_seconds_after_anchor=first.seconds_after_anchor,
            support_duration_seconds=duration,
            observed_frame_ids=_sorted_tuple(observed_frame_ids),
            qualifying_frame_ids=tuple(item.frame_id for item in frame_evidence[first_index : last_index + 1]),
            missing_frame_ids=_sorted_tuple(missing_frame_ids),
            invalid_frame_ids=_sorted_tuple(invalid_frame_ids),
            duplicate_frame_ids=_sorted_tuple(duplicate_frame_ids),
            frame_evidence=tuple(frame_evidence),
        )

    if duplicate_frame_ids:
        status = UNKNOWN
        reason = SupportArrivalReason.DUPLICATE_CANDIDATE_FRAME_RECORDS.value
    elif invalid_frame_ids:
        status = UNKNOWN
        reason = SupportArrivalReason.CANDIDATE_COORDINATES_INVALID.value
    elif missing_frame_ids:
        status = UNKNOWN
        reason = SupportArrivalReason.CANDIDATE_FRAME_EVIDENCE_MISSING.value
    elif any(frame.reason in {"reference_position_missing", "reference_coordinates_invalid"} for frame in frame_evidence):
        status = UNKNOWN
        reason = SupportArrivalReason.REFERENCE_POSITION_MISSING.value
    else:
        status = FAIL
        reason = "support_arrival_not_observed"

    return SupportPlayerEvidence(
        player_id=player_id,
        status=status,
        reason=reason,
        first_arrival_frame_id=None,
        first_arrival_seconds_after_anchor=None,
        support_duration_seconds=_longest_inside_duration(frame_evidence),
        observed_frame_ids=_sorted_tuple(observed_frame_ids),
        qualifying_frame_ids=(),
        missing_frame_ids=_sorted_tuple(missing_frame_ids),
        invalid_frame_ids=_sorted_tuple(invalid_frame_ids),
        duplicate_frame_ids=_sorted_tuple(duplicate_frame_ids),
        frame_evidence=tuple(frame_evidence),
    )


def _qualifying_run(
    frame_evidence: Sequence[SupportFrameEvidence],
    config: _ResolvedConfig,
) -> tuple[int, int] | None:
    maximum_arrival = config.maximum_arrival_seconds or 0.0
    minimum_duration = config.minimum_duration_seconds or 0.0
    index = 0
    while index < len(frame_evidence):
        frame = frame_evidence[index]
        if frame.in_support_region is not True:
            index += 1
            continue
        if frame.seconds_after_anchor is None or frame.seconds_after_anchor > maximum_arrival + _EPSILON:
            index += 1
            continue
        run_end = index
        while run_end + 1 < len(frame_evidence) and frame_evidence[run_end + 1].in_support_region is True:
            run_end += 1
        candidate_end = index
        while candidate_end <= run_end:
            start_seconds = frame_evidence[index].seconds_after_anchor
            end_seconds = frame_evidence[candidate_end].seconds_after_anchor
            if start_seconds is not None and end_seconds is not None:
                if end_seconds - start_seconds + _EPSILON >= minimum_duration:
                    return index, candidate_end
            candidate_end += 1
        index = run_end + 1
    return None


def _longest_inside_duration(frame_evidence: Sequence[SupportFrameEvidence]) -> float | None:
    longest: float | None = None
    index = 0
    while index < len(frame_evidence):
        if frame_evidence[index].in_support_region is not True:
            index += 1
            continue
        run_end = index
        while run_end + 1 < len(frame_evidence) and frame_evidence[run_end + 1].in_support_region is True:
            run_end += 1
        start = frame_evidence[index].seconds_after_anchor
        end = frame_evidence[run_end].seconds_after_anchor
        if start is not None and end is not None:
            duration = end - start
            longest = duration if longest is None else max(longest, duration)
        index = run_end + 1
    return longest


def _in_support_region(record: _PositionRecord, reference: _Point, config: _ResolvedConfig) -> tuple[bool, float]:
    distance = hypot(float(record.x_m) - reference.x_m, float(record.y_m) - reference.y_m)
    if distance > (config.maximum_support_distance_m or 0.0) + _EPSILON:
        return False, distance
    if config.support_region_mode == WITHIN_DISTANCE_OF_REFERENCE_POINT:
        return True, distance

    candidate_attack_x = float(record.x_m) * (config.attacking_direction or 1)
    reference_attack_x = reference.x_m * (config.attacking_direction or 1)
    if config.support_region_mode == BEHIND_BALL_OUTLET:
        return candidate_attack_x <= reference_attack_x + _EPSILON, distance
    if config.support_region_mode == AHEAD_OF_BALL_OPTION:
        return candidate_attack_x + _EPSILON >= reference_attack_x, distance
    return False, distance


def _unknown_reason(
    *,
    per_player: Sequence[SupportPlayerEvidence],
    missing_candidate_player_ids: tuple[str, ...],
    reference_evidence: _ReferenceEvidence,
) -> str | None:
    if missing_candidate_player_ids:
        return SupportArrivalReason.MISSING_CANDIDATE_EVIDENCE.value
    if reference_evidence.reason is not None:
        return reference_evidence.reason
    for evidence in per_player:
        if evidence.status == UNKNOWN:
            return evidence.reason
    return None


def _aggregate_support_duration(evidence: Sequence[SupportPlayerEvidence]) -> float | None:
    durations = [item.support_duration_seconds for item in evidence if item.support_duration_seconds is not None]
    if not durations:
        return None
    return min(durations)


def _parse_position_records(values: Sequence[object]) -> tuple[_PositionRecord, ...]:
    records: list[_PositionRecord] = []
    for index, value in enumerate(values):
        player_id, invalid_player_id = _coerce_player_id(
            _first_field(value, "player_id", "entity_id", "id"),
            fallback=f"record[{index}]",
        )
        frame_id, frame_invalid = _normalize_frame_id(_first_field(value, "frame_id", "frame", "anchor_frame_id"))
        x_m, x_invalid = _required_float(_first_field(value, "x_m", "x"))
        y_m, y_invalid = _required_float(_first_field(value, "y_m", "y"))
        records.append(
            _PositionRecord(
                index=index,
                player_id=None if invalid_player_id else player_id,
                frame_id=frame_id,
                x_m=x_m,
                y_m=y_m,
                team_id=_string_or_none(_first_field(value, "team_id", "team_role", "team")),
                invalid_player_id=player_id if invalid_player_id else None,
                frame_invalid=frame_invalid,
                coordinate_invalid=x_invalid or y_invalid,
            )
        )
    return tuple(records)


def _resolve_candidate_ids(
    *,
    candidate_records: Sequence[_PositionRecord],
    candidate_player_ids: Sequence[object] | None,
    allowed_candidate_player_ids: Sequence[object] | None,
    allowed_candidate_team_ids: Sequence[object] | None,
    excluded_candidate_player_ids: Sequence[object] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    explicit_ids, invalid_candidate_ids = (
        _normalize_player_id_sequence(candidate_player_ids, label="candidate_player_ids")
        if candidate_player_ids is not None
        else (None, ())
    )
    allowed_ids, invalid_allowed_ids = (
        _normalize_player_id_sequence(allowed_candidate_player_ids, label="allowed_candidate_player_ids")
        if allowed_candidate_player_ids is not None
        else (None, ())
    )
    excluded_ids, invalid_excluded_ids = (
        _normalize_player_id_sequence(excluded_candidate_player_ids, label="excluded_candidate_player_ids")
        if excluded_candidate_player_ids is not None
        else ((), ())
    )
    allowed_team_ids = None if allowed_candidate_team_ids is None else {str(value) for value in allowed_candidate_team_ids}

    include_invalid_record_ids = explicit_ids is None and allowed_ids is None
    invalid_record_ids = (
        tuple(record.invalid_player_id for record in candidate_records if record.invalid_player_id)
        if include_invalid_record_ids
        else ()
    )
    invalid_ids = _sorted_tuple(
        set(invalid_candidate_ids)
        | set(invalid_allowed_ids)
        | set(invalid_excluded_ids)
        | set(invalid_record_ids)
    )
    excluded_set = set(excluded_ids or ())

    if explicit_ids is not None:
        selected = set(explicit_ids)
        if allowed_ids is not None:
            selected &= set(allowed_ids)
    elif allowed_ids is not None:
        selected = set(allowed_ids)
    else:
        selected = {
            record.player_id
            for record in candidate_records
            if record.player_id is not None and _team_allowed(record.team_id, allowed_team_ids)
        }
    selected -= excluded_set
    return _sorted_tuple(selected), invalid_ids


def _records_by_player(
    records: Sequence[_PositionRecord],
    analysis_frame_ids: tuple[FrameId, ...],
) -> dict[str, tuple[_PositionRecord, ...]]:
    frame_id_set = set(analysis_frame_ids)
    grouped: dict[str, list[_PositionRecord]] = {}
    for record in records:
        if record.player_id is None or record.frame_invalid:
            continue
        if record.frame_id not in frame_id_set:
            continue
        grouped.setdefault(record.player_id, []).append(record)
    return {
        player_id: tuple(sorted(player_records, key=lambda item: _stable_sort_key(item.frame_id)))
        for player_id, player_records in sorted(grouped.items(), key=lambda item: _stable_sort_key(item[0]))
    }


def _parse_frame_times(
    values: Mapping[object, object] | Sequence[object] | None,
) -> tuple[dict[FrameId, float], tuple[FrameId, ...], tuple[FrameId, ...]]:
    if values is None:
        return {}, (), ()

    items: list[tuple[object | None, object | None]] = []
    if isinstance(values, Mapping):
        items = list(values.items())
    else:
        for item in values:
            items.append(
                (
                    _first_field(item, "frame_id", "frame", "anchor_frame_id"),
                    _first_field(item, "time_seconds", "time_s", "timestamp_s", "seconds", "t"),
                )
            )

    parsed: dict[FrameId, float] = {}
    duplicate_frame_ids: list[FrameId] = []
    invalid_frame_ids: list[FrameId] = []
    seen: set[FrameId] = set()
    for raw_frame_id, raw_time in items:
        frame_id, frame_invalid = _normalize_frame_id(raw_frame_id)
        time_value = _required_float(raw_time)[0]
        if frame_invalid or time_value is None:
            invalid_frame_ids.append(frame_id)
            continue
        if frame_id in seen:
            duplicate_frame_ids.append(frame_id)
            continue
        seen.add(frame_id)
        parsed[frame_id] = time_value
    return parsed, _sorted_tuple(duplicate_frame_ids), _sorted_tuple(invalid_frame_ids)


def _has_irregular_intervals(times: tuple[float, ...]) -> bool:
    if len(times) <= 2:
        return False
    deltas = [times[index + 1] - times[index] for index in range(len(times) - 1)]
    if any(delta <= _EPSILON for delta in deltas):
        return True
    nominal = min(deltas)
    return any(abs(delta - nominal) > max(_EPSILON, nominal * 1e-6) for delta in deltas)


def _has_integral_frame_gaps(frame_ids: tuple[FrameId, ...]) -> bool:
    integral_frame_ids = [_integral_frame_id(frame_id) for frame_id in frame_ids]
    if any(frame_id is None for frame_id in integral_frame_ids):
        return False
    ordered = sorted(set(frame_id for frame_id in integral_frame_ids if frame_id is not None))
    return any(ordered[index + 1] - ordered[index] > 1 for index in range(len(ordered) - 1))


def _point_from_value(value: PositionInput) -> _Point | None:
    x_m, x_invalid = _required_float(_position_x(value))
    y_m, y_invalid = _required_float(_position_y(value))
    if x_invalid or y_invalid or x_m is None or y_m is None:
        return None
    return _Point(x_m, y_m)


def _position_x(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get("x_m", value.get("x"))
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value[0] if value else None
    return getattr(value, "x_m", getattr(value, "x", None))


def _position_y(value: object | None) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value.get("y_m", value.get("y"))
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value[1] if len(value) > 1 else None
    return getattr(value, "y_m", getattr(value, "y", None))


def _normalize_player_id_sequence(
    values: Sequence[object],
    *,
    label: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized: list[str] = []
    invalid: list[str] = []
    for index, value in enumerate(values):
        player_id, is_invalid = _coerce_player_id(value, fallback=f"{label}[{index}]")
        if is_invalid:
            invalid.append(player_id)
        else:
            normalized.append(player_id)
    return _sorted_tuple(normalized), _sorted_tuple(invalid)


def _coerce_optional_player_id(value: object | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    player_id, invalid = _coerce_player_id(value, fallback="reference_player_id")
    return (None if invalid else player_id), invalid


def _coerce_player_id(value: object | None, *, fallback: str) -> tuple[str, bool]:
    if value is None or isinstance(value, bool):
        return f"{fallback}:invalid_player_id", True
    player_id = str(value).strip()
    if not player_id:
        return f"{fallback}:invalid_player_id", True
    return player_id, False


def _normalize_frame_id(value: object | None) -> tuple[FrameId, bool]:
    if value is None or isinstance(value, bool):
        return None, True
    if isinstance(value, int | str):
        frame_id = value if isinstance(value, int) else value.strip()
        if frame_id == "":
            return None, True
        return frame_id, False
    if isinstance(value, float) and isfinite(value) and value.is_integer():
        return int(value), False
    return str(value), False


def _integral_frame_id(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and isfinite(value) and value.is_integer():
        return int(value)
    try:
        text = str(value).strip()
        if not text or "." in text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


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


def _non_negative_float(value: object | None) -> float | None:
    number = _required_float(value)[0]
    if number is None or number < 0.0:
        return None
    return number


def _positive_float(value: object | None) -> float | None:
    number = _required_float(value)[0]
    if number is None or number <= 0.0:
        return None
    return number


def _positive_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, float):
        if not isfinite(value) or not value.is_integer():
            return None
        result = int(value)
        return result if result >= 1 else None
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if result >= 1 else None


def _attacking_direction(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result in {-1, 1} else None


def _team_allowed(team_id: str | None, allowed_team_ids: set[str] | None) -> bool:
    if allowed_team_ids is None:
        return True
    return team_id in allowed_team_ids


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


def _sorted_tuple(values: object) -> tuple:
    return tuple(sorted(set(values), key=_stable_sort_key))


def _evaluation(status: str, reason: str, base: Mapping[str, Any]) -> SupportArrivalEvaluation:
    return SupportArrivalEvaluation(status=status, reason=reason, **base)
