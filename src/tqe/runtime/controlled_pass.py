"""Controlled completed-pass runtime capability for M2A.

This module implements the first S1 slice unlocked by the M2A-S0C contract:
derive controlled pass episodes from canonical event and tracking data for the
accepted J03WOY scope. It deliberately does not emit high-bypass results and
does not expose Hermes-facing catalog entries.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


BALL_ENTITY_ID = "DFL-OBJ-0000XT"
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
ACCEPTED_MATCH_IDS = ("J03WOY",)
ACCEPTED_PERIODS = ("firstHalf", "secondHalf")


@dataclass(frozen=True)
class ControlledPassConfig:
    release_search_before_seconds: float = 1.0
    release_search_after_seconds: float = 3.0
    reception_search_seconds: float = 6.0
    control_distance_m: float = 2.5
    nearest_teammate_margin_m: float = 1.0
    minimum_receiver_dwell_seconds: float = 0.24
    departure_frames: int = 3
    departure_distance_delta_m: float = 0.50
    max_missing_frame_ratio: float = 0.02


@dataclass(frozen=True)
class FrameControlState:
    frame_id: int
    controls: bool
    distance_m: float | None
    ball_xy: tuple[float, float] | None
    player_xy: tuple[float, float] | None
    missing: bool


@dataclass(frozen=True)
class ReleaseDetection:
    status: str
    reason: str | None
    event_anchor_frame_id: int | None
    physical_release_frame_id: int | None
    event_to_release_offset_ms: float | None
    release_ball_xy: tuple[float, float] | None
    release_player_xy: tuple[float, float] | None
    release_ball_distance_m: float | None


@dataclass(frozen=True)
class ReceptionDetection:
    status: str
    reason: str | None
    controlled_reception_frame_id: int | None
    release_to_reception_seconds: float | None
    reception_ball_xy: tuple[float, float] | None
    receiver_xy: tuple[float, float] | None
    reception_ball_distance_m: float | None


@dataclass(frozen=True)
class ControlledPassOutput:
    schema_version: str
    capability: str
    capability_version: str
    status: str
    accepted_scope: dict[str, Any]
    config: dict[str, Any]
    summary: dict[str, Any]
    episodes: list[dict[str, Any]]
    anchor_evaluations: list[dict[str, Any]]
    non_match_examples: list[dict[str, Any]]


def evaluate_controlled_passes(
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    match_ids: tuple[str, ...] | list[str] = ACCEPTED_MATCH_IDS,
    periods: tuple[str, ...] | list[str] = ACCEPTED_PERIODS,
    config: ControlledPassConfig = ControlledPassConfig(),
) -> ControlledPassOutput:
    """Evaluate controlled pass episodes for accepted M2A S1 scope."""

    requested_match_ids = tuple(str(item) for item in match_ids)
    requested_periods = tuple(str(item) for item in periods)
    unsupported = sorted(set(requested_match_ids) - set(ACCEPTED_MATCH_IDS))
    if unsupported:
        raise RuntimeError(
            "M2A controlled_pass_episode S1A is accepted only for "
            f"{ACCEPTED_MATCH_IDS}; unsupported={unsupported}"
        )
    orientation = read_table(canonical_root / "orientation.parquet")
    episodes: list[dict[str, Any]] = []
    anchor_evaluations: list[dict[str, Any]] = []
    non_match_examples: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    release_counts: Counter[str] = Counter()
    reception_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for match_id in requested_match_ids:
        events = read_table(canonical_root / "events" / f"match_id={match_id}.parquet")
        candidates = candidate_pass_events(events)
        for period in requested_periods:
            period_candidates = [item for item in candidates if item["period"] == period]
            if not period_candidates:
                continue
            frames = read_table(canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet")
            frames["_frame_ts_utc"] = pd.to_datetime(frames["timestamp_utc"], utc=True, errors="coerce")
            frames = frames.sort_values("frame_id").reset_index(drop=True)
            positions = read_table(canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet")
            context = PeriodControlContext(
                match_id=match_id,
                period=period,
                frames=frames,
                positions=positions,
                attack_x_sign_by_role=attack_x_signs(orientation, match_id, period),
                config=config,
            )
            for event in period_candidates:
                episode, evaluation = evaluate_candidate(event, context)
                status_counts[str(evaluation["controlled_pass_status"])] += 1
                release_counts[str(evaluation["release_detection_status"])] += 1
                reception_counts[str(evaluation["controlled_reception_status"])] += 1
                if evaluation.get("release_detection_reason"):
                    reason_counts[str(evaluation["release_detection_reason"])] += 1
                if evaluation.get("controlled_reception_reason"):
                    reason_counts[str(evaluation["controlled_reception_reason"])] += 1
                anchor_evaluations.append(evaluation)
                if episode is not None:
                    episodes.append(episode)
                elif len(non_match_examples) < 50:
                    non_match_examples.append(evaluation)

    episodes.sort(key=lambda item: (item["match_id"], item["period"], item["event_anchor_frame_id"], item["pass_episode_id"]))
    anchor_evaluations.sort(key=lambda item: (item["match_id"], item["period"], item["event_anchor_frame_id"] or -1, item["pass_episode_id"]))
    return ControlledPassOutput(
        schema_version="m2a.controlled_pass_episode.v1",
        capability="controlled_pass_episode",
        capability_version="0.1.0",
        status="pass",
        accepted_scope={
            "match_ids": list(ACCEPTED_MATCH_IDS),
            "periods": list(ACCEPTED_PERIODS),
            "all_corpus_execution": "blocked_until_reduced_player_and_tracking_gap_policy_is_extended",
        },
        config=asdict(config),
        summary={
            "candidate_event_count": len(anchor_evaluations),
            "episode_count": len(episodes),
            "controlled_pass_status_counts": dict(sorted(status_counts.items())),
            "release_detection_status_counts": dict(sorted(release_counts.items())),
            "reception_status_counts": dict(sorted(reception_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "event_to_release_offset_ms": numeric_summary(
                [item["event_to_release_offset_ms"] for item in anchor_evaluations if item["event_to_release_offset_ms"] is not None]
            ),
            "release_to_reception_seconds": numeric_summary(
                [item["release_to_reception_seconds"] for item in anchor_evaluations if item["release_to_reception_seconds"] is not None]
            ),
            "forward_progression_m": numeric_summary(
                [item["forward_progression_m"] for item in anchor_evaluations if item["forward_progression_m"] is not None]
            ),
        },
        episodes=episodes,
        anchor_evaluations=anchor_evaluations,
        non_match_examples=non_match_examples,
    )


class PeriodControlContext:
    def __init__(
        self,
        *,
        match_id: str,
        period: str,
        frames: pd.DataFrame,
        positions: pd.DataFrame,
        attack_x_sign_by_role: dict[str, int],
        config: ControlledPassConfig,
    ) -> None:
        self.match_id = match_id
        self.period = period
        self.frames = frames
        self.positions = positions
        self.attack_x_sign_by_role = attack_x_sign_by_role
        self.config = config
        self.analysis_rate_hz = period_analysis_rate(frames)
        self.frame_ids = [int(item) for item in frames["frame_id"].tolist()]
        self.frame_index_by_id = {frame_id: index for index, frame_id in enumerate(self.frame_ids)}
        self.ball_by_frame = (
            positions[positions["entity_type"] == "ball"][["frame_id", "x_m", "y_m"]]
            .set_index("frame_id")
            .sort_index()
        )
        player_positions = positions[positions["entity_type"] == "player"][
            ["frame_id", "team_role", "entity_id", "x_m", "y_m"]
        ].copy()
        self.player_index = player_positions.set_index(["frame_id", "entity_id"]).sort_index()


def evaluate_candidate(
    event: dict[str, Any],
    context: PeriodControlContext,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    event_anchor_frame_id, event_offset_ms = align_event_to_frame(event, context.frames)
    event["event_anchor_frame_id"] = event_anchor_frame_id
    release = detect_physical_release(event, context)
    reception = detect_controlled_reception(event, context, release)
    forward_progression_m = forward_progression(event, context, release, reception)
    controlled_status = controlled_pass_status(release, reception, forward_progression_m)
    pass_episode_id = pass_id(event)
    anchor_id = f"controlled_pass:{pass_episode_id}"
    common = {
        "anchor_id": anchor_id,
        "pass_episode_id": pass_episode_id,
        "match_id": str(event["match_id"]),
        "period": str(event["period"]),
        "team_role": str(event["team_role"]),
        "passer_id": str(event["passer_id"]),
        "receiver_id": str(event["receiver_id"]),
        "event_row_index": int(event["row_index"]),
        "event_type": str(event["event_type"]),
        "event_timestamp": str(event["event_timestamp"]),
        "gameclock_seconds": event.get("gameclock_seconds"),
        "event_anchor_frame_id": event_anchor_frame_id,
        "event_frame_offset_ms": event_offset_ms,
        "physical_release_frame_id": release.physical_release_frame_id,
        "event_to_release_offset_ms": release.event_to_release_offset_ms,
        "release_detection_status": release.status,
        "release_detection_reason": release.reason,
        "release_control_status": "PASS" if release.status == "PASS" else release.status,
        "controlled_reception_frame_id": reception.controlled_reception_frame_id,
        "release_to_reception_seconds": reception.release_to_reception_seconds,
        "controlled_reception_status": reception.status,
        "controlled_reception_reason": reception.reason,
        "possession_continuity_status": possession_continuity_status(event, reception),
        "forward_progression_m": forward_progression_m,
        "controlled_pass_status": controlled_status,
        "evaluation_status": controlled_status,
    }
    if controlled_status != "PASS":
        return None, common
    assert release.release_ball_xy is not None
    assert release.release_player_xy is not None
    assert reception.reception_ball_xy is not None
    assert reception.receiver_xy is not None
    episode = {
        **common,
        "release_ball_x_m": release.release_ball_xy[0],
        "release_ball_y_m": release.release_ball_xy[1],
        "passer_x_m": release.release_player_xy[0],
        "passer_y_m": release.release_player_xy[1],
        "release_ball_distance_m": release.release_ball_distance_m,
        "reception_ball_x_m": reception.reception_ball_xy[0],
        "reception_ball_y_m": reception.reception_ball_xy[1],
        "receiver_x_m": reception.receiver_xy[0],
        "receiver_y_m": reception.receiver_xy[1],
        "reception_ball_distance_m": reception.reception_ball_distance_m,
        "temporal_status": "PASS",
    }
    return episode, common


def detect_physical_release(event: dict[str, Any], context: PeriodControlContext) -> ReleaseDetection:
    event_anchor_frame_id = event.get("event_anchor_frame_id")
    if event_anchor_frame_id is None:
        return ReleaseDetection(
            status="UNKNOWN",
            reason="missing_tracking",
            event_anchor_frame_id=None,
            physical_release_frame_id=None,
            event_to_release_offset_ms=None,
            release_ball_xy=None,
            release_player_xy=None,
            release_ball_distance_m=None,
        )
    anchor_index = context.frame_index_by_id.get(int(event_anchor_frame_id))
    if anchor_index is None:
        return ReleaseDetection(
            status="UNKNOWN",
            reason="missing_tracking",
            event_anchor_frame_id=int(event_anchor_frame_id),
            physical_release_frame_id=None,
            event_to_release_offset_ms=None,
            release_ball_xy=None,
            release_player_xy=None,
            release_ball_distance_m=None,
        )
    before = math.ceil(context.config.release_search_before_seconds * context.analysis_rate_hz)
    after = math.ceil(context.config.release_search_after_seconds * context.analysis_rate_hz)
    start = max(0, anchor_index - before)
    end = min(len(context.frame_ids) - 1, anchor_index + after)
    states = [
        control_state(context, frame_id, str(event["passer_id"]), str(event["team_role"]))
        for frame_id in context.frame_ids[start : end + 1]
    ]
    if all(state.missing for state in states):
        return ReleaseDetection(
            status="UNKNOWN",
            reason="missing_tracking",
            event_anchor_frame_id=int(event_anchor_frame_id),
            physical_release_frame_id=None,
            event_to_release_offset_ms=None,
            release_ball_xy=None,
            release_player_xy=None,
            release_ball_distance_m=None,
        )
    transitions: list[FrameControlState] = []
    for index, state in enumerate(states):
        if state.missing or not state.controls or state.distance_m is None:
            continue
        lookahead = states[index + 1 : index + 1 + context.config.departure_frames]
        if len(lookahead) < context.config.departure_frames or any(item.missing for item in lookahead):
            continue
        if any(item.controls for item in lookahead):
            continue
        final = lookahead[-1]
        if final.distance_m is None:
            continue
        if final.distance_m < state.distance_m + context.config.departure_distance_delta_m:
            continue
        transitions.append(state)
    if not transitions:
        if any(state.controls for state in states):
            reason = "unique_release_transition_not_found"
            status = "UNKNOWN"
        else:
            reason = "release_not_confirmed"
            status = "FAIL"
        return ReleaseDetection(
            status=status,
            reason=reason,
            event_anchor_frame_id=int(event_anchor_frame_id),
            physical_release_frame_id=None,
            event_to_release_offset_ms=None,
            release_ball_xy=None,
            release_player_xy=None,
            release_ball_distance_m=None,
        )
    release_state = min(transitions, key=lambda item: abs(item.frame_id - int(event_anchor_frame_id)))
    assert release_state.ball_xy is not None
    assert release_state.player_xy is not None
    event_to_release_ms = (release_state.frame_id - int(event_anchor_frame_id)) / context.analysis_rate_hz * 1000.0
    return ReleaseDetection(
        status="PASS",
        reason=None,
        event_anchor_frame_id=int(event_anchor_frame_id),
        physical_release_frame_id=release_state.frame_id,
        event_to_release_offset_ms=event_to_release_ms,
        release_ball_xy=release_state.ball_xy,
        release_player_xy=release_state.player_xy,
        release_ball_distance_m=release_state.distance_m,
    )


def detect_controlled_reception(
    event: dict[str, Any],
    context: PeriodControlContext,
    release: ReleaseDetection,
) -> ReceptionDetection:
    if release.status != "PASS" or release.physical_release_frame_id is None:
        return ReceptionDetection(
            status="UNKNOWN",
            reason="release_not_confirmed" if release.status != "FAIL" else "release_contradicted",
            controlled_reception_frame_id=None,
            release_to_reception_seconds=None,
            reception_ball_xy=None,
            receiver_xy=None,
            reception_ball_distance_m=None,
        )
    release_index = context.frame_index_by_id.get(release.physical_release_frame_id)
    if release_index is None:
        return ReceptionDetection(
            status="UNKNOWN",
            reason="missing_tracking",
            controlled_reception_frame_id=None,
            release_to_reception_seconds=None,
            reception_ball_xy=None,
            receiver_xy=None,
            reception_ball_distance_m=None,
        )
    end = min(
        len(context.frame_ids) - 1,
        release_index + math.ceil(context.config.reception_search_seconds * context.analysis_rate_hz),
    )
    dwell_frames = max(1, math.ceil(context.config.minimum_receiver_dwell_seconds * context.analysis_rate_hz))
    receiver_run: list[FrameControlState] = []
    other_run_count = 0
    missing_count = 0
    inspected = 0
    for frame_id in context.frame_ids[release_index + 1 : end + 1]:
        inspected += 1
        state = control_state(context, frame_id, str(event["receiver_id"]), str(event["team_role"]))
        if state.missing:
            missing_count += 1
            receiver_run = []
            other_run_count = 0
            continue
        if state.controls:
            receiver_run.append(state)
            other_run_count = 0
            if len(receiver_run) >= dwell_frames:
                first = receiver_run[0]
                assert first.ball_xy is not None
                assert first.player_xy is not None
                return ReceptionDetection(
                    status="PASS",
                    reason=None,
                    controlled_reception_frame_id=first.frame_id,
                    release_to_reception_seconds=(first.frame_id - release.physical_release_frame_id)
                    / context.analysis_rate_hz,
                    reception_ball_xy=first.ball_xy,
                    receiver_xy=first.player_xy,
                    reception_ball_distance_m=first.distance_m,
                )
            continue
        receiver_run = []
        nearest = nearest_player_to_ball(context, frame_id)
        if nearest and nearest["distance_m"] <= context.config.control_distance_m and nearest["entity_id"] != str(event["receiver_id"]):
            other_run_count += 1
            if other_run_count >= dwell_frames:
                return ReceptionDetection(
                    status="FAIL",
                    reason="another_player_controlled_first"
                    if nearest["team_role"] == str(event["team_role"])
                    else "possession_definitively_broke",
                    controlled_reception_frame_id=None,
                    release_to_reception_seconds=None,
                    reception_ball_xy=None,
                    receiver_xy=None,
                    reception_ball_distance_m=None,
                )
        else:
            other_run_count = 0
    if inspected and (missing_count / inspected) > context.config.max_missing_frame_ratio:
        return ReceptionDetection(
            status="UNKNOWN",
            reason="missing_tracking",
            controlled_reception_frame_id=None,
            release_to_reception_seconds=None,
            reception_ball_xy=None,
            receiver_xy=None,
            reception_ball_distance_m=None,
        )
    return ReceptionDetection(
        status="FAIL",
        reason="reception_window_expired",
        controlled_reception_frame_id=None,
        release_to_reception_seconds=None,
        reception_ball_xy=None,
        receiver_xy=None,
        reception_ball_distance_m=None,
    )


def control_state(
    context: PeriodControlContext,
    frame_id: int,
    entity_id: str,
    team_role: str,
) -> FrameControlState:
    ball_xy = ball_at(context, frame_id)
    player = player_at(context, frame_id, entity_id)
    if ball_xy is None or player is None:
        return FrameControlState(frame_id, False, None, ball_xy, None if player is None else player[1], True)
    player_role, player_xy = player
    distance = euclidean(ball_xy, player_xy)
    controls = (
        player_role == team_role
        and distance <= context.config.control_distance_m
        and nearest_teammate_allows_control(context, frame_id, entity_id, team_role, ball_xy, distance)
    )
    return FrameControlState(frame_id, controls, distance, ball_xy, player_xy, False)


def nearest_teammate_allows_control(
    context: PeriodControlContext,
    frame_id: int,
    entity_id: str,
    team_role: str,
    ball_xy: tuple[float, float],
    player_distance_m: float,
) -> bool:
    try:
        frame_players = context.player_index.loc[frame_id]
    except KeyError:
        return False
    if isinstance(frame_players, pd.Series):
        frame_players = frame_players.to_frame().T
    teammates = frame_players[frame_players["team_role"] == team_role]
    if teammates.empty:
        return False
    distances = (
        (teammates["x_m"].astype(float) - ball_xy[0]) ** 2
        + (teammates["y_m"].astype(float) - ball_xy[1]) ** 2
    ) ** 0.5
    return player_distance_m <= float(distances.min()) + context.config.nearest_teammate_margin_m


def nearest_player_to_ball(context: PeriodControlContext, frame_id: int) -> dict[str, Any] | None:
    ball_xy = ball_at(context, frame_id)
    if ball_xy is None:
        return None
    try:
        frame_players = context.player_index.loc[frame_id]
    except KeyError:
        return None
    if isinstance(frame_players, pd.Series):
        frame_players = frame_players.to_frame().T
    distances = (
        (frame_players["x_m"].astype(float) - ball_xy[0]) ** 2
        + (frame_players["y_m"].astype(float) - ball_xy[1]) ** 2
    ) ** 0.5
    idx = distances.idxmin()
    row = frame_players.loc[idx]
    return {
        "entity_id": str(row["entity_id"]) if "entity_id" in row else str(idx),
        "team_role": str(row["team_role"]),
        "distance_m": float(distances.loc[idx]),
    }


def forward_progression(
    event: dict[str, Any],
    context: PeriodControlContext,
    release: ReleaseDetection,
    reception: ReceptionDetection,
) -> float | None:
    if release.release_ball_xy is None or reception.reception_ball_xy is None:
        return None
    attack_x_sign = context.attack_x_sign_by_role.get(str(event["team_role"]))
    if attack_x_sign not in {-1, 1}:
        return None
    return (reception.reception_ball_xy[0] - release.release_ball_xy[0]) * attack_x_sign


def controlled_pass_status(
    release: ReleaseDetection,
    reception: ReceptionDetection,
    forward_progression_m: float | None,
) -> str:
    if release.status == "PASS" and reception.status == "PASS" and forward_progression_m is not None:
        return "PASS"
    if release.status == "FAIL" or reception.status == "FAIL":
        return "FAIL"
    return "UNKNOWN"


def possession_continuity_status(event: dict[str, Any], reception: ReceptionDetection) -> str:
    if reception.status == "PASS":
        return "PASS"
    if reception.status == "FAIL":
        return "FAIL"
    return "UNKNOWN"


def align_event_to_frame(event: dict[str, Any], frames: pd.DataFrame) -> tuple[int | None, float | None]:
    event_ts = pd.to_datetime(event["event_timestamp"], utc=True, errors="coerce")
    if pd.isna(event_ts):
        return None, None
    idx = (frames["_frame_ts_utc"] - event_ts).abs().idxmin()
    frame = frames.loc[idx]
    offset_ms = float((frame["_frame_ts_utc"] - event_ts).total_seconds() * 1000.0)
    if abs(offset_ms) > 100.0:
        return None, offset_ms
    return int(frame["frame_id"]), offset_ms


def ball_at(context: PeriodControlContext, frame_id: int) -> tuple[float, float] | None:
    try:
        row = context.ball_by_frame.loc[frame_id]
    except KeyError:
        return None
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return (float(row["x_m"]), float(row["y_m"]))


def player_at(context: PeriodControlContext, frame_id: int, entity_id: str) -> tuple[str, tuple[float, float]] | None:
    try:
        row = context.player_index.loc[(frame_id, entity_id)]
    except KeyError:
        return None
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return str(row["team_role"]), (float(row["x_m"]), float(row["y_m"]))


def attack_x_signs(orientation: pd.DataFrame, match_id: str, period: str) -> dict[str, int]:
    rows = orientation[(orientation["match_id"] == match_id) & (orientation["period"] == period)]
    return {str(row["team_role"]): int(row["attack_x_sign"]) for _, row in rows.iterrows()}


def period_analysis_rate(frames: pd.DataFrame) -> float:
    if "analysis_rate_hz" in frames.columns and frames["analysis_rate_hz"].notna().any():
        return float(frames["analysis_rate_hz"].dropna().iloc[0])
    deltas = frames["_frame_ts_utc"].sort_values().diff().dt.total_seconds().dropna()
    if deltas.empty:
        return 25.0
    median = float(deltas.median())
    return 1.0 / median if median > 0 else 25.0


def candidate_pass_events(events: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        event_type = str(event.get("event_type") or "")
        if "Pass" not in event_type:
            continue
        qualifier = safe_json(event.get("qualifier_json"))
        if qualifier.get("Evaluation") != "successfullyCompleted":
            continue
        passer = qualifier.get("Player") or event.get("player_id")
        receiver = qualifier.get("Recipient")
        if not passer or not receiver:
            continue
        rows.append(
            {
                "match_id": str(event["match_id"]),
                "period": str(event["period"]),
                "row_index": int(event["row_index"]),
                "event_type": event_type,
                "event_timestamp": str(event["timestamp"]),
                "gameclock_seconds": float(event["gameclock_seconds"]) if pd.notna(event.get("gameclock_seconds")) else None,
                "team_role": str(event["team_role"]),
                "passer_id": str(passer),
                "receiver_id": str(receiver),
            }
        )
    return rows


def pass_id(event: dict[str, Any]) -> str:
    return (
        f"{event['match_id']}:{event['period']}:{event['team_role']}:"
        f"{event['row_index']}:{event['passer_id']}:{event['receiver_id']}"
    )


def safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    cleaned = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not cleaned:
        return {"count": 0, "min": None, "p50": None, "p90": None, "p95": None, "max": None}
    return {
        "count": len(cleaned),
        "min": cleaned[0],
        "p50": percentile(cleaned, 0.50),
        "p90": percentile(cleaned, 0.90),
        "p95": percentile(cleaned, 0.95),
        "max": cleaned[-1],
    }


def percentile(values: list[float], q: float) -> float:
    idx = min(len(values) - 1, max(0, round((len(values) - 1) * q)))
    return values[idx]
