"""Tri-state entity geometry between two observed longitudinal lines.

The kernel consumes already-declared geometric line evidence. It does not
identify tactical line roles, infer legal offside, or construct line bands.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
DECLARED_RANKS = "declared_ranks"
DEEPEST_OBSERVED_LINE = "deepest_observed_line"
ENTITY_RELATIVE_BRACKETING = "entity_relative_bracketing"


@dataclass(frozen=True)
class BetweenObservedLinesConfig:
    nearer_line_rank: int = 1
    farther_line_rank: int = 2
    line_selector: str = DECLARED_RANKS
    line_boundary_buffer_m: float = 0.5
    minimum_interline_gap_m: float = 0.0


@dataclass(frozen=True)
class BetweenObservedLinesEvaluation:
    status: str
    reason: str
    definition_version: str
    entity_id: str | None
    entity_frame_id: int | None
    line_evaluation_frame_id: int | None
    entity_x_m: float | None
    entity_y_m: float | None
    normalized_entity_x_m: float | None
    attacking_direction: int | None
    line_selector: str
    declared_nearer_line_rank: int
    declared_farther_line_rank: int
    selected_nearer_line: dict[str, Any] | None
    selected_farther_line: dict[str, Any] | None
    selected_nearer_line_rank: int | None
    selected_farther_line_rank: int | None
    signed_distance_to_nearer_line_m: float | None
    signed_distance_to_farther_line_m: float | None
    interline_gap_m: float | None
    line_boundary_buffer_m: float
    minimum_interline_gap_m: float
    line_model_status: str | None
    line_model_reason: str | None
    defender_observation_status: str | None
    defender_observation_reason: str | None
    player_track_coverage_status: str | None
    player_track_coverage_reason: str | None
    player_track_coverage_row_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["player_track_coverage_row_ids"] = list(
            self.player_track_coverage_row_ids
        )
        return payload


PositionInput = tuple[float, ...] | list[float] | Mapping[str, Any]


def evaluate_between_observed_lines(
    *,
    entity_position: PositionInput | None,
    entity_id: str | None,
    entity_frame_id: int | None,
    line_evaluation: Mapping[str, Any] | None,
    config: BetweenObservedLinesConfig = BetweenObservedLinesConfig(),
) -> BetweenObservedLinesEvaluation:
    """Evaluate strict buffered inclusion between selected observed lines."""

    _validate_config(config)
    evidence = line_evaluation or {}
    line_frame_id = _optional_int(evidence.get("line_evaluation_frame_id"))
    line_status = _optional_text(evidence.get("multi_line_status"))
    line_reason = _optional_text(evidence.get("multi_line_reason"))
    defender_status = _optional_text(evidence.get("defender_observation_status"))
    defender_reason = _optional_text(evidence.get("defender_observation_reason"))
    coverage_status = _optional_text(evidence.get("player_track_coverage_status"))
    coverage_reason = _optional_text(evidence.get("player_track_coverage_reason"))
    coverage_row_ids = tuple(
        str(item) for item in evidence.get("player_track_coverage_row_ids") or []
    )
    direction = _attacking_direction(evidence.get("attacking_direction"))
    entity = _position(entity_position)

    def result(
        status: str,
        reason: str,
        *,
        nearer: dict[str, Any] | None = None,
        farther: dict[str, Any] | None = None,
        normalized_entity_x_m: float | None = None,
        signed_nearer: float | None = None,
        signed_farther: float | None = None,
        interline_gap_m: float | None = None,
    ) -> BetweenObservedLinesEvaluation:
        return BetweenObservedLinesEvaluation(
            status=status,
            reason=reason,
            definition_version="between_observed_lines.v2",
            entity_id=entity_id,
            entity_frame_id=entity_frame_id,
            line_evaluation_frame_id=line_frame_id,
            entity_x_m=None if entity is None else entity[0],
            entity_y_m=None if entity is None else entity[1],
            normalized_entity_x_m=normalized_entity_x_m,
            attacking_direction=direction,
            line_selector=config.line_selector,
            declared_nearer_line_rank=config.nearer_line_rank,
            declared_farther_line_rank=config.farther_line_rank,
            selected_nearer_line=nearer,
            selected_farther_line=farther,
            selected_nearer_line_rank=_line_rank(nearer),
            selected_farther_line_rank=_line_rank(farther),
            signed_distance_to_nearer_line_m=signed_nearer,
            signed_distance_to_farther_line_m=signed_farther,
            interline_gap_m=interline_gap_m,
            line_boundary_buffer_m=config.line_boundary_buffer_m,
            minimum_interline_gap_m=config.minimum_interline_gap_m,
            line_model_status=line_status,
            line_model_reason=line_reason,
            defender_observation_status=defender_status,
            defender_observation_reason=defender_reason,
            player_track_coverage_status=coverage_status,
            player_track_coverage_reason=coverage_reason,
            player_track_coverage_row_ids=coverage_row_ids,
        )

    if line_evaluation is None:
        return result(UNKNOWN, "line_evaluation_missing")
    if entity_id is None or not str(entity_id):
        return result(UNKNOWN, "entity_id_missing")
    if entity_frame_id is None:
        return result(UNKNOWN, "entity_frame_missing")
    if line_frame_id is None:
        return result(UNKNOWN, "line_evaluation_frame_missing")
    if entity_frame_id != line_frame_id:
        return result(UNKNOWN, "line_entity_frame_misaligned")
    if entity is None:
        return result(UNKNOWN, "entity_position_missing_or_invalid")
    if direction is None:
        return result(UNKNOWN, "attacking_direction_invalid")

    normalized_entity_x = entity[0] * direction
    adequate = defender_status == "ADEQUATE" and coverage_status == "CERTIFIED"
    if line_status == UNKNOWN or not adequate:
        return result(
            UNKNOWN,
            _upstream_unknown_reason(
                line_reason=line_reason,
                defender_reason=defender_reason,
                coverage_reason=coverage_reason,
                adequate=adequate,
            ),
            normalized_entity_x_m=normalized_entity_x,
        )
    if line_status not in {PASS, FAIL}:
        return result(
            UNKNOWN,
            "line_model_status_invalid",
            normalized_entity_x_m=normalized_entity_x,
        )

    lines = evidence.get("observed_lines")
    if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
        return result(
            UNKNOWN if line_status == PASS else FAIL,
            "observed_lines_invalid" if line_status == PASS else "selected_line_not_observed",
            normalized_entity_x_m=normalized_entity_x,
        )
    selected, selection_reason = _select_lines(
        lines, config=config, normalized_entity_x_m=normalized_entity_x
    )
    if selected is None:
        return result(
            FAIL if adequate and selection_reason == "selected_line_not_observed" else UNKNOWN,
            selection_reason,
            normalized_entity_x_m=normalized_entity_x,
        )
    nearer, farther = selected
    near_normalized = float(nearer["normalized_line_x_m"])
    far_normalized = float(farther["normalized_line_x_m"])
    if not _orientation_aligned(nearer, direction) or not _orientation_aligned(
        farther, direction
    ):
        return result(
            UNKNOWN,
            "line_orientation_alignment_uncertain",
            nearer=nearer,
            farther=farther,
            normalized_entity_x_m=normalized_entity_x,
        )
    gap = far_normalized - near_normalized
    signed_nearer = normalized_entity_x - near_normalized
    signed_farther = normalized_entity_x - far_normalized
    common = {
        "nearer": nearer,
        "farther": farther,
        "normalized_entity_x_m": normalized_entity_x,
        "signed_nearer": signed_nearer,
        "signed_farther": signed_farther,
        "interline_gap_m": gap,
    }
    if gap <= 0.0:
        return result(UNKNOWN, "selected_line_order_ambiguous", **common)
    if gap < config.minimum_interline_gap_m:
        return result(FAIL, "minimum_interline_gap_not_met", **common)
    buffer_m = config.line_boundary_buffer_m
    if abs(signed_nearer) <= buffer_m or abs(signed_farther) <= buffer_m:
        return result(UNKNOWN, "entity_within_line_boundary_buffer", **common)
    if signed_nearer > buffer_m and signed_farther < -buffer_m:
        return result(PASS, "entity_between_observed_lines", **common)
    return result(FAIL, "entity_outside_observed_lines", **common)


def _validate_config(config: BetweenObservedLinesConfig) -> None:
    if config.nearer_line_rank < 1 or config.farther_line_rank < 1:
        raise ValueError("line ranks must be positive")
    if config.nearer_line_rank >= config.farther_line_rank:
        raise ValueError("nearer_line_rank must be less than farther_line_rank")
    if config.line_selector not in {
        DECLARED_RANKS, DEEPEST_OBSERVED_LINE, ENTITY_RELATIVE_BRACKETING
    }:
        raise ValueError(f"unsupported line_selector {config.line_selector}")
    for name, value in (
        ("line_boundary_buffer_m", config.line_boundary_buffer_m),
        ("minimum_interline_gap_m", config.minimum_interline_gap_m),
    ):
        if not isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"{name} must be finite and non-negative")


def _select_lines(
    lines: Sequence[Any],
    *,
    config: BetweenObservedLinesConfig,
    normalized_entity_x_m: float,
) -> tuple[tuple[dict[str, Any], dict[str, Any]] | None, str]:
    parsed: list[dict[str, Any]] = []
    for raw in lines:
        line = _line(raw)
        if line is None:
            return None, "observed_line_geometry_invalid"
        parsed.append(line)
    by_rank = {int(line["line_rank"]): line for line in parsed}
    if len(by_rank) != len(parsed):
        return None, "observed_line_rank_ambiguous"
    if config.line_selector == ENTITY_RELATIVE_BRACKETING:
        ordered = sorted(parsed, key=lambda line: float(line["normalized_line_x_m"]))
        candidates = [
            (ball_side, goal_side)
            for ball_side, goal_side in zip(ordered, ordered[1:])
            if float(ball_side["normalized_line_x_m"]) <= normalized_entity_x_m
            <= float(goal_side["normalized_line_x_m"])
        ]
        if len(candidates) != 1:
            return None, (
                "entity_relative_bracketing_not_observed"
                if not candidates else "entity_relative_bracketing_ambiguous"
            )
        return candidates[0], "entity_relative_bracketing_observed"
    nearer = by_rank.get(config.nearer_line_rank)
    if config.line_selector == DECLARED_RANKS:
        farther = by_rank.get(config.farther_line_rank)
    else:
        if not parsed:
            farther = None
        else:
            maximum = max(float(line["normalized_line_x_m"]) for line in parsed)
            candidates = [
                line
                for line in parsed
                if float(line["normalized_line_x_m"]) == maximum
            ]
            if len(candidates) != 1:
                return None, "deepest_observed_line_ambiguous"
            farther = candidates[0]
    if nearer is None or farther is None or nearer is farther:
        return None, "selected_line_not_observed"
    return (nearer, farther), "selected_lines_observed"


def _line(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    line_id = raw.get("line_id")
    defender_ids = raw.get("defender_ids")
    rank = _optional_int(raw.get("line_rank"))
    line_x = _finite_float(raw.get("line_x_m"))
    normalized = _finite_float(raw.get("normalized_line_x_m"))
    if (
        not isinstance(line_id, str)
        or not line_id
        or not isinstance(defender_ids, Sequence)
        or isinstance(defender_ids, (str, bytes))
        or rank is None
        or rank < 1
        or line_x is None
        or normalized is None
    ):
        return None
    return {
        **dict(raw),
        "line_id": line_id,
        "line_rank": rank,
        "line_x_m": line_x,
        "normalized_line_x_m": normalized,
        "defender_ids": [str(item) for item in defender_ids],
    }


def _orientation_aligned(line: Mapping[str, Any], direction: int) -> bool:
    line_x = float(line["line_x_m"])
    normalized = float(line["normalized_line_x_m"])
    return abs(line_x * direction - normalized) <= 0.002


def _position(value: PositionInput | None) -> tuple[float, float] | None:
    if isinstance(value, Mapping):
        raw_x, raw_y = value.get("x_m"), value.get("y_m")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        raw_x, raw_y = value[0], value[1]
    else:
        return None
    x_m, y_m = _finite_float(raw_x), _finite_float(raw_y)
    return None if x_m is None or y_m is None else (x_m, y_m)


def _attacking_direction(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        direction = int(value)
    except (TypeError, ValueError):
        return None
    return direction if direction in {-1, 1} else None


def _upstream_unknown_reason(
    *,
    line_reason: str | None,
    defender_reason: str | None,
    coverage_reason: str | None,
    adequate: bool,
) -> str:
    if not adequate and defender_reason:
        return defender_reason
    if not adequate and coverage_reason:
        return coverage_reason
    if line_reason and line_reason not in {"target_line_rank_observed"}:
        return line_reason
    return "line_model_coverage_uncertain"


def _line_rank(line: Mapping[str, Any] | None) -> int | None:
    return None if line is None else _optional_int(line.get("line_rank"))


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)
