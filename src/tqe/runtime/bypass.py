"""Threshold-free opponent-bypass measurement for M2A.

This module deliberately does not decide whether a pass is "high bypass".
It only measures which expected active opposition outfield players moved from
goal-side of the ball at release to behind the ball at controlled reception.
Recipe predicates own thresholds such as "at least five".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


Status = str


@dataclass(frozen=True)
class BypassConfig:
    goal_side_buffer_m: float = 1.0
    bypassed_buffer_m: float = 1.0


@dataclass(frozen=True)
class PlayerPosition:
    x_m: float
    y_m: float


@dataclass(frozen=True)
class BypassedOpponentsEvaluation:
    evaluation_status: Status
    coverage_status: str
    failure_reason: str | None
    attack_x_sign: int
    goal_side_buffer_m: float
    bypassed_buffer_m: float
    release_ball_attack_x_m: float | None
    reception_ball_attack_x_m: float | None
    expected_active_opponent_ids: tuple[str, ...]
    evaluated_opponent_ids: tuple[str, ...]
    missing_active_opponent_ids: tuple[str, ...]
    candidate_goal_side_ids: tuple[str, ...]
    bypassed_player_ids: tuple[str, ...]
    opponents_bypassed_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_opponents_bypassed_by_action(
    *,
    release_ball_x_m: float | None,
    reception_ball_x_m: float | None,
    release_opponent_positions: Mapping[str, PlayerPosition | tuple[float, float]],
    reception_opponent_positions: Mapping[str, PlayerPosition | tuple[float, float]],
    expected_active_opponent_ids: set[str] | frozenset[str] | list[str] | tuple[str, ...],
    attack_x_sign: int,
    excluded_opponent_ids: set[str] | frozenset[str] | list[str] | tuple[str, ...] = (),
    config: BypassConfig = BypassConfig(),
) -> BypassedOpponentsEvaluation:
    """Evaluate bypassed opponents between pass release and reception.

    Coordinates are normalized internally with ``attack_x_m = x_m * attack_x_sign``.
    Larger normalized x means closer to the attacking goal. Missing expected
    active outfield opponents make the evaluation UNKNOWN; they are never
    silently treated as non-bypassed.
    """

    if attack_x_sign not in {-1, 1}:
        raise ValueError("attack_x_sign must be -1 or 1")
    if config.goal_side_buffer_m < 0 or config.bypassed_buffer_m < 0:
        raise ValueError("bypass buffers must be non-negative")

    expected = tuple(sorted(set(expected_active_opponent_ids) - set(excluded_opponent_ids)))
    if not expected:
        return _unknown(
            attack_x_sign=attack_x_sign,
            config=config,
            release_ball_x_m=release_ball_x_m,
            reception_ball_x_m=reception_ball_x_m,
            expected_active_opponent_ids=expected,
            evaluated_opponent_ids=(),
            missing_active_opponent_ids=(),
            candidate_goal_side_ids=(),
            bypassed_player_ids=(),
            failure_reason="no_expected_active_opposition_outfield_players",
        )

    if release_ball_x_m is None or reception_ball_x_m is None:
        return _unknown(
            attack_x_sign=attack_x_sign,
            config=config,
            release_ball_x_m=release_ball_x_m,
            reception_ball_x_m=reception_ball_x_m,
            expected_active_opponent_ids=expected,
            evaluated_opponent_ids=(),
            missing_active_opponent_ids=expected,
            candidate_goal_side_ids=(),
            bypassed_player_ids=(),
            failure_reason="ball_endpoint_missing",
        )

    release_ids = set(release_opponent_positions)
    reception_ids = set(reception_opponent_positions)
    evaluated = tuple(sorted(set(expected) & release_ids & reception_ids))
    missing = tuple(sorted(set(expected) - set(evaluated)))
    release_ball_attack_x = float(release_ball_x_m) * attack_x_sign
    reception_ball_attack_x = float(reception_ball_x_m) * attack_x_sign

    candidate_goal_side: list[str] = []
    bypassed: list[str] = []
    for entity_id in evaluated:
        release_position = _coerce_position(release_opponent_positions[entity_id])
        reception_position = _coerce_position(reception_opponent_positions[entity_id])
        release_attack_x = release_position.x_m * attack_x_sign
        reception_attack_x = reception_position.x_m * attack_x_sign

        if release_attack_x > release_ball_attack_x + config.goal_side_buffer_m:
            candidate_goal_side.append(entity_id)
            if reception_attack_x < reception_ball_attack_x - config.bypassed_buffer_m:
                bypassed.append(entity_id)

    candidate_goal_side_ids = tuple(sorted(candidate_goal_side))
    bypassed_player_ids = tuple(sorted(bypassed))
    if missing:
        return _unknown(
            attack_x_sign=attack_x_sign,
            config=config,
            release_ball_x_m=release_ball_x_m,
            reception_ball_x_m=reception_ball_x_m,
            expected_active_opponent_ids=expected,
            evaluated_opponent_ids=evaluated,
            missing_active_opponent_ids=missing,
            candidate_goal_side_ids=candidate_goal_side_ids,
            bypassed_player_ids=bypassed_player_ids,
            failure_reason="expected_active_opponent_tracking_missing",
        )

    return BypassedOpponentsEvaluation(
        evaluation_status="PASS",
        coverage_status="COMPLETE",
        failure_reason=None,
        attack_x_sign=attack_x_sign,
        goal_side_buffer_m=config.goal_side_buffer_m,
        bypassed_buffer_m=config.bypassed_buffer_m,
        release_ball_attack_x_m=release_ball_attack_x,
        reception_ball_attack_x_m=reception_ball_attack_x,
        expected_active_opponent_ids=expected,
        evaluated_opponent_ids=evaluated,
        missing_active_opponent_ids=(),
        candidate_goal_side_ids=candidate_goal_side_ids,
        bypassed_player_ids=bypassed_player_ids,
        opponents_bypassed_count=len(bypassed_player_ids),
    )


def _coerce_position(value: PlayerPosition | tuple[float, float]) -> PlayerPosition:
    if isinstance(value, PlayerPosition):
        return value
    return PlayerPosition(x_m=float(value[0]), y_m=float(value[1]))


def _unknown(
    *,
    attack_x_sign: int,
    config: BypassConfig,
    release_ball_x_m: float | None,
    reception_ball_x_m: float | None,
    expected_active_opponent_ids: tuple[str, ...],
    evaluated_opponent_ids: tuple[str, ...],
    missing_active_opponent_ids: tuple[str, ...],
    candidate_goal_side_ids: tuple[str, ...],
    bypassed_player_ids: tuple[str, ...],
    failure_reason: str,
) -> BypassedOpponentsEvaluation:
    release_ball_attack_x = None if release_ball_x_m is None else float(release_ball_x_m) * attack_x_sign
    reception_ball_attack_x = (
        None if reception_ball_x_m is None else float(reception_ball_x_m) * attack_x_sign
    )
    return BypassedOpponentsEvaluation(
        evaluation_status="UNKNOWN",
        coverage_status="UNKNOWN",
        failure_reason=failure_reason,
        attack_x_sign=attack_x_sign,
        goal_side_buffer_m=config.goal_side_buffer_m,
        bypassed_buffer_m=config.bypassed_buffer_m,
        release_ball_attack_x_m=release_ball_attack_x,
        reception_ball_attack_x_m=reception_ball_attack_x,
        expected_active_opponent_ids=expected_active_opponent_ids,
        evaluated_opponent_ids=evaluated_opponent_ids,
        missing_active_opponent_ids=missing_active_opponent_ids,
        candidate_goal_side_ids=candidate_goal_side_ids,
        bypassed_player_ids=bypassed_player_ids,
        opponents_bypassed_count=len(bypassed_player_ids),
    )
