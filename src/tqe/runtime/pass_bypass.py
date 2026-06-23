"""M2A S1B wiring from controlled pass episodes to bypass measurements."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tqe.runtime.bypass import BypassConfig, PlayerPosition, evaluate_opponents_bypassed_by_action
from tqe.runtime.controlled_pass import (
    ACCEPTED_PERIODS,
    DEFAULT_CANONICAL_ROOT,
    ControlledPassOutput,
    canonical_match_ids,
    evaluate_controlled_passes,
    read_positions_table,
)


@dataclass(frozen=True)
class PassBypassConfig:
    goal_side_buffer_m: float = 1.0
    bypassed_buffer_m: float = 1.0


@dataclass(frozen=True)
class PassBypassOutput:
    schema_version: str
    capability: str
    capability_version: str
    status: str
    accepted_scope: dict[str, Any]
    config: dict[str, Any]
    summary: dict[str, Any]
    anchor_evaluations: list[dict[str, Any]]
    non_match_examples: list[dict[str, Any]]


@dataclass(frozen=True)
class ActiveInterval:
    team_role: str
    player_id: str
    is_goalkeeper: bool | None
    active_from_frame_id: int
    active_to_frame_id: int


def evaluate_pass_bypass_measurements(
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    controlled_passes: ControlledPassOutput | None = None,
    match_ids: tuple[str, ...] | list[str] | None = None,
    periods: tuple[str, ...] | list[str] = ACCEPTED_PERIODS,
    config: PassBypassConfig = PassBypassConfig(),
) -> PassBypassOutput:
    requested_match_ids = tuple(str(item) for item in (match_ids or canonical_match_ids(canonical_root)))
    requested_periods = tuple(str(item) for item in periods)
    unsupported_periods = sorted(set(requested_periods) - set(ACCEPTED_PERIODS))
    if unsupported_periods:
        raise RuntimeError(
            "M2A pass-bypass S1B is accepted only for "
            f"periods {ACCEPTED_PERIODS}; unsupported={unsupported_periods}"
        )
    controlled = controlled_passes or evaluate_controlled_passes(
        canonical_root=canonical_root,
        match_ids=requested_match_ids,
        periods=requested_periods,
    )
    validate_controlled_scope(controlled)
    orientation = pd.read_parquet(canonical_root / "orientation.parquet")
    players = pd.read_parquet(canonical_root / "players.parquet")
    positions_cache: dict[tuple[str, str], pd.DataFrame] = {}
    timeline_cache: dict[tuple[str, str], list[ActiveInterval]] = {}

    evaluations: list[dict[str, Any]] = []
    non_match_examples: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    coverage_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    bypass_counts: Counter[int] = Counter()

    pass_by_id = {item["pass_episode_id"]: item for item in controlled.episodes}
    for anchor in controlled.anchor_evaluations:
        if anchor["controlled_pass_status"] != "PASS":
            evaluation = not_applicable_evaluation(anchor, "controlled_pass_not_proven")
        else:
            episode = pass_by_id.get(anchor["pass_episode_id"])
            if episode is None:
                evaluation = not_applicable_evaluation(anchor, "controlled_pass_episode_missing")
            else:
                positions = positions_for(
                    canonical_root,
                    positions_cache,
                    str(episode["match_id"]),
                    str(episode["period"]),
                )
                active_timeline = active_timeline_for(
                    timeline_cache,
                    positions,
                    players,
                    str(episode["match_id"]),
                    str(episode["period"]),
                )
                evaluation = evaluate_episode(
                    episode=episode,
                    positions=positions,
                    active_timeline=active_timeline,
                    orientation=orientation,
                    config=config,
                )
        evaluations.append(evaluation)
        status_counts[str(evaluation["evaluation_status"])] += 1
        coverage_counts[str(evaluation["coverage_status"])] += 1
        if evaluation.get("failure_reason"):
            reason_counts[str(evaluation["failure_reason"])] += 1
        if evaluation["evaluation_status"] == "PASS":
            bypass_counts[int(evaluation["opponents_bypassed_count"])] += 1
        elif len(non_match_examples) < 50:
            non_match_examples.append(evaluation)

    evaluations.sort(
        key=lambda item: (
            item["match_id"],
            item["period"],
            item["event_anchor_frame_id"] or -1,
            item["pass_episode_id"],
        )
    )
    return PassBypassOutput(
        schema_version="m2a.opponents_bypassed_by_action.v1",
        capability="opponents_bypassed_by_action",
        capability_version="0.1.0",
        status="pass",
        accepted_scope={
            "match_ids": list(requested_match_ids),
            "periods": list(ACCEPTED_PERIODS),
            "scope_policy": "caller_supplied_match_scope",
        },
        config=asdict(config),
        summary={
            "controlled_anchor_evaluation_count": len(controlled.anchor_evaluations),
            "bypass_anchor_evaluation_count": len(evaluations),
            "evaluation_status_counts": dict(sorted(status_counts.items())),
            "coverage_status_counts": dict(sorted(coverage_counts.items())),
            "failure_reason_counts": dict(sorted(reason_counts.items())),
            "opponents_bypassed_count_distribution": {
                str(key): bypass_counts[key] for key in sorted(bypass_counts)
            },
            "max_opponents_bypassed_count": max(bypass_counts) if bypass_counts else 0,
        },
        anchor_evaluations=evaluations,
        non_match_examples=non_match_examples,
    )


def evaluate_episode(
    *,
    episode: dict[str, Any],
    positions: pd.DataFrame,
    active_timeline: list[ActiveInterval],
    orientation: pd.DataFrame,
    config: PassBypassConfig,
) -> dict[str, Any]:
    match_id = str(episode["match_id"])
    period = str(episode["period"])
    attacking_role = str(episode["team_role"])
    defending_role = "away" if attacking_role == "home" else "home"
    attack_x_sign = attack_x_sign_for(orientation, match_id, period, attacking_role)
    common = base_evaluation(episode, defending_role)
    release_frame_id = safe_int(episode.get("physical_release_frame_id"))
    reception_frame_id = safe_int(episode.get("controlled_reception_frame_id"))
    if release_frame_id is None or reception_frame_id is None:
        return {**common, **unknown_payload("endpoint_frame_missing")}
    if attack_x_sign is None:
        return {**common, **unknown_payload("orientation_missing")}

    if active_unknown_metadata_ids(active_timeline, defending_role, release_frame_id, reception_frame_id):
        return {**common, **unknown_payload("goalkeeper_metadata_missing")}
    window_changes = active_changes_inside_window(
        active_timeline,
        start_frame_id=release_frame_id,
        end_frame_id=reception_frame_id,
    )
    if window_changes:
        payload = unknown_payload("active_player_set_changed_during_pass")
        payload["active_changes_inside_window"] = window_changes[:20]
        return {**common, **payload}

    release_expected = active_outfield_ids_at_frame(active_timeline, defending_role, release_frame_id)
    reception_expected = active_outfield_ids_at_frame(active_timeline, defending_role, reception_frame_id)
    if not release_expected or not reception_expected:
        return {**common, **unknown_payload("active_outfield_unavailable")}
    if set(release_expected) != set(reception_expected):
        payload = unknown_payload("active_player_set_changed_during_pass")
        payload["expected_active_opponent_ids"] = tuple(sorted(release_expected))
        payload["evaluated_opponent_ids"] = tuple(sorted(set(release_expected) & set(reception_expected)))
        payload["missing_active_opponent_ids"] = tuple(sorted(set(release_expected) ^ set(reception_expected)))
        return {**common, **payload}

    release_observed = observed_player_positions_at_frame(positions, release_frame_id, defending_role)
    reception_observed = observed_player_positions_at_frame(positions, reception_frame_id, defending_role)

    bypass = evaluate_opponents_bypassed_by_action(
        release_ball_x_m=float(episode["release_ball_x_m"]),
        reception_ball_x_m=float(episode["reception_ball_x_m"]),
        release_opponent_positions=release_observed,
        reception_opponent_positions=reception_observed,
        expected_active_opponent_ids=set(release_expected),
        attack_x_sign=attack_x_sign,
        config=BypassConfig(
            goal_side_buffer_m=config.goal_side_buffer_m,
            bypassed_buffer_m=config.bypassed_buffer_m,
        ),
    )
    return {
        **common,
        **bypass.to_dict(),
        "relation_id": f"opponents_bypassed:{episode['pass_episode_id']}",
        "release_frame_id": release_frame_id,
        "reception_frame_id": reception_frame_id,
        "release_ball_x_m": float(episode["release_ball_x_m"]),
        "release_ball_y_m": float(episode["release_ball_y_m"]),
        "reception_ball_x_m": float(episode["reception_ball_x_m"]),
        "reception_ball_y_m": float(episode["reception_ball_y_m"]),
    }


def base_evaluation(episode: dict[str, Any], defending_role: str) -> dict[str, Any]:
    return {
        "anchor_id": str(episode["anchor_id"]),
        "pass_episode_id": str(episode["pass_episode_id"]),
        "match_id": str(episode["match_id"]),
        "period": str(episode["period"]),
        "team_role": str(episode["team_role"]),
        "defending_team_role": defending_role,
        "passer_id": str(episode["passer_id"]),
        "receiver_id": str(episode["receiver_id"]),
        "event_row_index": int(episode["event_row_index"]),
        "event_anchor_frame_id": safe_int(episode.get("event_anchor_frame_id")),
        "physical_release_frame_id": safe_int(episode.get("physical_release_frame_id")),
        "controlled_reception_frame_id": safe_int(episode.get("controlled_reception_frame_id")),
        "forward_progression_m": episode["forward_progression_m"],
    }


def not_applicable_evaluation(anchor: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "anchor_id": str(anchor["anchor_id"]),
        "pass_episode_id": str(anchor["pass_episode_id"]),
        "match_id": str(anchor["match_id"]),
        "period": str(anchor["period"]),
        "team_role": str(anchor["team_role"]),
        "defending_team_role": "away" if str(anchor["team_role"]) == "home" else "home",
        "passer_id": str(anchor["passer_id"]),
        "receiver_id": str(anchor["receiver_id"]),
        "event_row_index": int(anchor["event_row_index"]),
        "event_anchor_frame_id": anchor["event_anchor_frame_id"],
        "physical_release_frame_id": anchor["physical_release_frame_id"],
        "controlled_reception_frame_id": anchor["controlled_reception_frame_id"],
        "forward_progression_m": anchor["forward_progression_m"],
        **unknown_payload(reason),
    }


def unknown_payload(reason: str) -> dict[str, Any]:
    return {
        "relation_id": None,
        "evaluation_status": "UNKNOWN",
        "coverage_status": "UNKNOWN",
        "failure_reason": reason,
        "attack_x_sign": None,
        "goal_side_buffer_m": None,
        "bypassed_buffer_m": None,
        "release_ball_attack_x_m": None,
        "reception_ball_attack_x_m": None,
        "expected_active_opponent_ids": (),
        "evaluated_opponent_ids": (),
        "missing_active_opponent_ids": (),
        "candidate_goal_side_ids": (),
        "bypassed_player_ids": (),
        "opponents_bypassed_count": 0,
        "active_changes_inside_window": (),
    }


def validate_controlled_scope(controlled: ControlledPassOutput) -> None:
    rows = list(controlled.anchor_evaluations) + list(controlled.episodes)
    periods = {str(item.get("period")) for item in rows if item.get("period") is not None}
    unsupported_periods = sorted(periods - set(ACCEPTED_PERIODS))
    if unsupported_periods:
        raise RuntimeError(
            "Injected controlled_passes fall outside M2A-S1B period scope: "
            f"periods={unsupported_periods}"
        )


def active_timeline_for(
    cache: dict[tuple[str, str], list[ActiveInterval]],
    positions: pd.DataFrame,
    players: pd.DataFrame,
    match_id: str,
    period: str,
) -> list[ActiveInterval]:
    key = (match_id, period)
    if key in cache:
        return cache[key]
    metadata = player_metadata(players, match_id)
    player_rows = positions[positions["entity_type"] == "player"][
        ["frame_id", "team_role", "entity_id"]
    ]
    intervals: list[ActiveInterval] = []
    grouped = player_rows.groupby(["team_role", "entity_id"], sort=True, observed=True)["frame_id"]
    for (team_role, player_id), frame_series in grouped:
        info = metadata.get(str(player_id))
        intervals.extend(
            intervals_for_player(
                team_role=str(team_role),
                player_id=str(player_id),
                is_goalkeeper=None if info is None else info,
                frame_ids=[int(item) for item in frame_series.tolist()],
                max_missing_gap_frames=1,
            )
        )
    cache[key] = intervals
    return intervals


def player_metadata(players: pd.DataFrame, match_id: str) -> dict[str, bool | None]:
    rows = players[players["match_id"] == match_id]
    metadata: dict[str, bool | None] = {}
    for row in rows.itertuples(index=False):
        value = row.is_goalkeeper
        metadata[str(row.player_id)] = None if pd.isna(value) else bool(value)
    return metadata


def intervals_for_player(
    *,
    team_role: str,
    player_id: str,
    is_goalkeeper: bool | None,
    frame_ids: list[int],
    max_missing_gap_frames: int,
) -> list[ActiveInterval]:
    if not frame_ids:
        return []
    ordered = sorted(set(int(frame_id) for frame_id in frame_ids))
    intervals: list[ActiveInterval] = []
    start = ordered[0]
    prev = ordered[0]
    for frame_id in ordered[1:]:
        if frame_id - prev <= max_missing_gap_frames + 1:
            prev = frame_id
            continue
        intervals.append(
            ActiveInterval(
                team_role=team_role,
                player_id=player_id,
                is_goalkeeper=is_goalkeeper,
                active_from_frame_id=start,
                active_to_frame_id=prev,
            )
        )
        start = frame_id
        prev = frame_id
    intervals.append(
        ActiveInterval(
            team_role=team_role,
            player_id=player_id,
            is_goalkeeper=is_goalkeeper,
            active_from_frame_id=start,
            active_to_frame_id=prev,
        )
    )
    return intervals


def active_outfield_ids_at_frame(
    intervals: list[ActiveInterval],
    team_role: str,
    frame_id: int,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            interval.player_id
            for interval in intervals
            if interval.team_role == team_role
            and interval.is_goalkeeper is False
            and interval.active_from_frame_id <= frame_id <= interval.active_to_frame_id
        )
    )


def active_unknown_metadata_ids(
    intervals: list[ActiveInterval],
    team_role: str,
    release_frame_id: int,
    reception_frame_id: int,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            interval.player_id
            for interval in intervals
            if interval.team_role == team_role
            and interval.is_goalkeeper is None
            and (
                interval.active_from_frame_id <= release_frame_id <= interval.active_to_frame_id
                or interval.active_from_frame_id <= reception_frame_id <= interval.active_to_frame_id
            )
        )
    )


def active_changes_inside_window(
    intervals: list[ActiveInterval],
    *,
    start_frame_id: int,
    end_frame_id: int,
) -> tuple[dict[str, Any], ...]:
    changes: list[dict[str, Any]] = []
    for interval in intervals:
        for frame_id, change_type in (
            (interval.active_from_frame_id, "IN"),
            (interval.active_to_frame_id + 1, "OUT"),
        ):
            if start_frame_id < frame_id <= end_frame_id:
                changes.append(
                    {
                        "team_role": interval.team_role,
                        "player_id": interval.player_id,
                        "frame_id": frame_id,
                        "change_type": change_type,
                    }
                )
    return tuple(sorted(changes, key=lambda item: (item["frame_id"], item["team_role"], item["player_id"])))


def observed_player_positions_at_frame(
    positions: pd.DataFrame,
    frame_id: int,
    team_role: str,
) -> dict[str, PlayerPosition]:
    rows = positions[
        (positions["frame_id"] == frame_id)
        & (positions["entity_type"] == "player")
        & (positions["team_role"] == team_role)
    ]
    observed: dict[str, PlayerPosition] = {}
    for row in rows.itertuples(index=False):
        observed[str(row.entity_id)] = PlayerPosition(x_m=float(row.x_m), y_m=float(row.y_m))
    return observed


def safe_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def attack_x_sign_for(
    orientation: pd.DataFrame,
    match_id: str,
    period: str,
    team_role: str,
) -> int | None:
    rows = orientation[
        (orientation["match_id"] == match_id)
        & (orientation["period"] == period)
        & (orientation["team_role"] == team_role)
    ]
    if rows.empty:
        return None
    value = int(rows.iloc[0]["attack_x_sign"])
    return value if value in {-1, 1} else None


def positions_for(
    canonical_root: Path,
    cache: dict[tuple[str, str], pd.DataFrame],
    match_id: str,
    period: str,
) -> pd.DataFrame:
    key = (match_id, period)
    if key not in cache:
        cache[key] = read_positions_table(canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet")
    return cache[key]


def output_to_json(output: PassBypassOutput) -> str:
    return json.dumps(asdict(output), indent=2, sort_keys=True)
