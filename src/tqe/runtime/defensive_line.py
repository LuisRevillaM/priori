"""Pure geometric defensive-line observation.

This module identifies only an observed band of defending outfield players with
similar goalward x positions. It does not classify tactical intent, tactical
line names, or whether a line was broken.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass


Status = str


@dataclass(frozen=True)
class DefensiveLineConfig:
    goal_side_buffer_m: float = 1.0
    line_band_width_m: float = 2.0
    minimum_defenders: int = 4
    tie_epsilon_m: float = 1e-9


@dataclass(frozen=True)
class DefensivePlayerPosition:
    x_m: float
    y_m: float


@dataclass(frozen=True)
class DefenderPositionEvidence:
    player_id: str
    x_m: float
    y_m: float
    normalized_x_m: float | None
    goal_side_of_ball: bool


@dataclass(frozen=True)
class DefensiveLineEvaluation:
    status: Status
    reason: str | None
    line_type: str | None
    selected_band_id: str | None
    anchor_frame_id: int | str | None
    attacking_direction: int | None
    ball_x_m: float | None
    normalized_ball_x_m: float | None
    line_x_m: float | None
    normalized_line_x_m: float | None
    defender_ids: tuple[str, ...]
    goalkeeper_id: str | None
    defenders_goal_side_count: int
    compactness_m: float | None
    goal_side_buffer_m: float
    line_band_width_m: float
    minimum_defenders: int
    candidate_band_count: int
    ambiguous_band_defender_ids: tuple[tuple[str, ...], ...]
    defender_positions_used: tuple[DefenderPositionEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ObservedDefender:
    player_id: str
    position: DefensivePlayerPosition
    normalized_x_m: float


@dataclass(frozen=True)
class _CandidateBand:
    defender_ids: tuple[str, ...]
    line_x_m: float
    normalized_line_x_m: float
    compactness_m: float


PositionInput = (
    DefensivePlayerPosition
    | tuple[float, float]
    | list[float]
    | Mapping[str, float]
)


def evaluate_defensive_line_model(
    *,
    ball_x_m: float | None,
    defending_player_positions: Mapping[str, PositionInput],
    attacking_direction: int | None = None,
    attack_x_sign: int | None = None,
    goalkeeper_id: str | None = None,
    goalkeeper_id_known: bool = True,
    active_defender_ids_known: bool = True,
    anchor_frame_id: int | str | None = None,
    config: DefensiveLineConfig = DefensiveLineConfig(),
) -> DefensiveLineEvaluation:
    """Evaluate whether defenders form an observed geometric defensive line.

    Coordinates are normalized internally with
    ``normalized_x_m = x_m * attacking_direction``. Larger normalized x is
    goalward for the attacking team. Goal-side candidates must sit strictly
    beyond the ball plus ``goal_side_buffer_m``.
    """

    _validate_config(config)
    resolved_direction, direction_reason = _resolve_attacking_direction(
        attacking_direction=attacking_direction,
        attack_x_sign=attack_x_sign,
    )

    raw_positions, invalid_position_ids = _coerce_positions(
        defending_player_positions=defending_player_positions,
        goalkeeper_id=goalkeeper_id,
    )
    normalized_ball_x = (
        None
        if ball_x_m is None or resolved_direction is None
        else float(ball_x_m) * resolved_direction
    )
    evidence = _position_evidence(
        positions=raw_positions,
        attacking_direction=resolved_direction,
        normalized_ball_x_m=normalized_ball_x,
        config=config,
    )

    if direction_reason is not None:
        return _unknown(
            reason=direction_reason,
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )
    if not goalkeeper_id_known:
        return _unknown(
            reason="goalkeeper_identity_uncertain",
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )
    if not active_defender_ids_known:
        return _unknown(
            reason="active_defender_denominator_uncertain",
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )
    if invalid_position_ids:
        return _unknown(
            reason="defender_position_invalid",
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )
    if ball_x_m is None:
        return _unknown(
            reason="ball_x_missing",
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )
    if len(raw_positions) < config.minimum_defenders:
        return _unknown(
            reason="too_few_outfield_defenders",
            attacking_direction=resolved_direction,
            anchor_frame_id=anchor_frame_id,
            ball_x_m=ball_x_m,
            normalized_ball_x_m=normalized_ball_x,
            goalkeeper_id=goalkeeper_id,
            config=config,
            defender_positions_used=evidence,
        )

    assert resolved_direction is not None
    assert normalized_ball_x is not None
    observed = tuple(
        _ObservedDefender(
            player_id=player_id,
            position=position,
            normalized_x_m=position.x_m * resolved_direction,
        )
        for player_id, position in raw_positions
    )
    candidates = tuple(
        sorted(
            (
                defender
                for defender in observed
                if defender.normalized_x_m > normalized_ball_x + config.goal_side_buffer_m
            ),
            key=lambda defender: (defender.normalized_x_m, defender.player_id),
        )
    )
    bands = _qualifying_bands(
        candidates=candidates,
        attacking_direction=resolved_direction,
        config=config,
    )
    if not bands:
        return DefensiveLineEvaluation(
            status="FAIL",
            reason="no_qualifying_line",
            line_type=None,
            selected_band_id=None,
            anchor_frame_id=anchor_frame_id,
            attacking_direction=resolved_direction,
            ball_x_m=float(ball_x_m),
            normalized_ball_x_m=normalized_ball_x,
            line_x_m=None,
            normalized_line_x_m=None,
            defender_ids=(),
            goalkeeper_id=goalkeeper_id,
            defenders_goal_side_count=len(candidates),
            compactness_m=None,
            goal_side_buffer_m=config.goal_side_buffer_m,
            line_band_width_m=config.line_band_width_m,
            minimum_defenders=config.minimum_defenders,
            candidate_band_count=0,
            ambiguous_band_defender_ids=(),
            defender_positions_used=evidence,
        )

    best_bands = _best_bands(bands, tie_epsilon_m=config.tie_epsilon_m)
    if len({band.defender_ids for band in best_bands}) > 1:
        return DefensiveLineEvaluation(
            status="UNKNOWN",
            reason="ambiguous_candidate_lines",
            line_type=None,
            selected_band_id=None,
            anchor_frame_id=anchor_frame_id,
            attacking_direction=resolved_direction,
            ball_x_m=float(ball_x_m),
            normalized_ball_x_m=normalized_ball_x,
            line_x_m=None,
            normalized_line_x_m=None,
            defender_ids=(),
            goalkeeper_id=goalkeeper_id,
            defenders_goal_side_count=len(candidates),
            compactness_m=None,
            goal_side_buffer_m=config.goal_side_buffer_m,
            line_band_width_m=config.line_band_width_m,
            minimum_defenders=config.minimum_defenders,
            candidate_band_count=len(bands),
            ambiguous_band_defender_ids=tuple(sorted(band.defender_ids for band in best_bands)),
            defender_positions_used=evidence,
        )

    selected = best_bands[0]
    return DefensiveLineEvaluation(
        status="PASS",
        reason="observed_defensive_line",
        line_type="observed_defensive_line",
        selected_band_id="observed_defensive_line",
        anchor_frame_id=anchor_frame_id,
        attacking_direction=resolved_direction,
        ball_x_m=float(ball_x_m),
        normalized_ball_x_m=normalized_ball_x,
        line_x_m=selected.line_x_m,
        normalized_line_x_m=selected.normalized_line_x_m,
        defender_ids=selected.defender_ids,
        goalkeeper_id=goalkeeper_id,
        defenders_goal_side_count=len(candidates),
        compactness_m=selected.compactness_m,
        goal_side_buffer_m=config.goal_side_buffer_m,
        line_band_width_m=config.line_band_width_m,
        minimum_defenders=config.minimum_defenders,
        candidate_band_count=len(bands),
        ambiguous_band_defender_ids=(),
        defender_positions_used=evidence,
    )


def _resolve_attacking_direction(
    *,
    attacking_direction: int | None,
    attack_x_sign: int | None,
) -> tuple[int | None, str | None]:
    if (
        attacking_direction is not None
        and attack_x_sign is not None
        and attacking_direction != attack_x_sign
    ):
        return None, "attacking_direction_conflict"
    resolved = attacking_direction if attacking_direction is not None else attack_x_sign
    if resolved not in {-1, 1}:
        return None, "attacking_direction_invalid"
    return int(resolved), None


def _validate_config(config: DefensiveLineConfig) -> None:
    if config.goal_side_buffer_m < 0:
        raise ValueError("goal_side_buffer_m must be non-negative")
    if config.line_band_width_m < 0:
        raise ValueError("line_band_width_m must be non-negative")
    if config.minimum_defenders < 1:
        raise ValueError("minimum_defenders must be at least 1")
    if config.tie_epsilon_m < 0:
        raise ValueError("tie_epsilon_m must be non-negative")


def _coerce_positions(
    *,
    defending_player_positions: Mapping[str, PositionInput],
    goalkeeper_id: str | None,
) -> tuple[tuple[tuple[str, DefensivePlayerPosition], ...], tuple[str, ...]]:
    positions: list[tuple[str, DefensivePlayerPosition]] = []
    invalid_ids: list[str] = []
    for raw_player_id in sorted(defending_player_positions, key=str):
        player_id = str(raw_player_id)
        if goalkeeper_id is not None and player_id == str(goalkeeper_id):
            continue
        try:
            position = _coerce_position(defending_player_positions[raw_player_id])
        except (IndexError, KeyError, TypeError, ValueError):
            invalid_ids.append(player_id)
            continue
        positions.append((player_id, position))
    return tuple(positions), tuple(invalid_ids)


def _coerce_position(value: PositionInput) -> DefensivePlayerPosition:
    if isinstance(value, DefensivePlayerPosition):
        return value
    if isinstance(value, Mapping):
        return DefensivePlayerPosition(
            x_m=float(value["x_m"]),
            y_m=float(value.get("y_m", 0.0)),
        )
    if isinstance(value, Sequence) and not isinstance(value, str):
        return DefensivePlayerPosition(x_m=float(value[0]), y_m=float(value[1]))
    raise TypeError("position must be a DefensivePlayerPosition, mapping, or x/y sequence")


def _position_evidence(
    *,
    positions: tuple[tuple[str, DefensivePlayerPosition], ...],
    attacking_direction: int | None,
    normalized_ball_x_m: float | None,
    config: DefensiveLineConfig,
) -> tuple[DefenderPositionEvidence, ...]:
    evidence: list[DefenderPositionEvidence] = []
    for player_id, position in positions:
        normalized_x = None if attacking_direction is None else position.x_m * attacking_direction
        goal_side = (
            False
            if normalized_x is None or normalized_ball_x_m is None
            else normalized_x > normalized_ball_x_m + config.goal_side_buffer_m
        )
        evidence.append(
            DefenderPositionEvidence(
                player_id=player_id,
                x_m=position.x_m,
                y_m=position.y_m,
                normalized_x_m=normalized_x,
                goal_side_of_ball=goal_side,
            )
        )
    return tuple(evidence)


def _qualifying_bands(
    *,
    candidates: tuple[_ObservedDefender, ...],
    attacking_direction: int,
    config: DefensiveLineConfig,
) -> tuple[_CandidateBand, ...]:
    bands: list[_CandidateBand] = []
    for start_index in range(len(candidates)):
        for end_index in range(start_index + config.minimum_defenders - 1, len(candidates)):
            band_candidates = candidates[start_index : end_index + 1]
            compactness = band_candidates[-1].normalized_x_m - band_candidates[0].normalized_x_m
            if compactness > config.line_band_width_m + config.tie_epsilon_m:
                break
            normalized_line_x = sum(item.normalized_x_m for item in band_candidates) / len(band_candidates)
            line_x = normalized_line_x / attacking_direction
            bands.append(
                _CandidateBand(
                    defender_ids=tuple(sorted(item.player_id for item in band_candidates)),
                    line_x_m=line_x,
                    normalized_line_x_m=normalized_line_x,
                    compactness_m=compactness,
                )
            )
    return tuple(bands)


def _best_bands(
    bands: tuple[_CandidateBand, ...],
    *,
    tie_epsilon_m: float,
) -> tuple[_CandidateBand, ...]:
    max_count = max(len(band.defender_ids) for band in bands)
    count_winners = [band for band in bands if len(band.defender_ids) == max_count]
    min_compactness = min(band.compactness_m for band in count_winners)
    return tuple(
        band for band in count_winners if abs(band.compactness_m - min_compactness) <= tie_epsilon_m
    )


def _unknown(
    *,
    reason: str,
    attacking_direction: int | None,
    anchor_frame_id: int | str | None,
    ball_x_m: float | None,
    normalized_ball_x_m: float | None,
    goalkeeper_id: str | None,
    config: DefensiveLineConfig,
    defender_positions_used: tuple[DefenderPositionEvidence, ...],
) -> DefensiveLineEvaluation:
    defenders_goal_side_count = sum(1 for item in defender_positions_used if item.goal_side_of_ball)
    return DefensiveLineEvaluation(
        status="UNKNOWN",
        reason=reason,
        line_type=None,
        selected_band_id=None,
        anchor_frame_id=anchor_frame_id,
        attacking_direction=attacking_direction,
        ball_x_m=None if ball_x_m is None else float(ball_x_m),
        normalized_ball_x_m=normalized_ball_x_m,
        line_x_m=None,
        normalized_line_x_m=None,
        defender_ids=(),
        goalkeeper_id=goalkeeper_id,
        defenders_goal_side_count=defenders_goal_side_count,
        compactness_m=None,
        goal_side_buffer_m=config.goal_side_buffer_m,
        line_band_width_m=config.line_band_width_m,
        minimum_defenders=config.minimum_defenders,
        candidate_band_count=0,
        ambiguous_band_defender_ids=(),
        defender_positions_used=defender_positions_used,
    )
