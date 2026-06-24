"""Event-linked one-touch and pass-chain runtime capabilities.

These capabilities model a narrow observed claim: a receiver/relay player is
linked by provider events to an input completed pass and an immediate onward
completed pass, with tracking evidence for the relay touch/release. They do not
weaken controlled_pass_episode and do not infer intent, tactical causation,
decision quality, or a third-man combination.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tqe.runtime.controlled_pass import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_PERIODS,
    FRAME_COLUMNS,
    POSITION_COLUMNS,
    ControlledPassConfig,
    PeriodControlContext,
    align_event_to_frame,
    attack_x_signs,
    ball_at,
    detect_physical_release,
    euclidean,
    pass_id,
    period_analysis_rate,
    player_at,
    read_positions_table,
    read_table,
    safe_json,
)


PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

AHEAD_OF_LINE = "AHEAD_OF_LINE"
BEHIND_LINE = "BEHIND_LINE"
LEVEL_WITH_LINE = "LEVEL_WITH_LINE"

EVENT_COLUMNS = [
    "match_id",
    "period",
    "team_role",
    "row_index",
    "event_type",
    "gameclock_seconds",
    "player_id",
    "timestamp",
    "qualifier_json",
]


@dataclass(frozen=True)
class OneTouchRelayConfig:
    relay_max_event_gap_seconds: float = 3.0
    relay_touch_search_before_seconds: float = 0.8
    relay_touch_search_after_seconds: float = 0.4
    relay_touch_distance_m: float = 2.75
    maximum_relay_dwell_seconds: float = 0.56
    control_distance_m: float = 2.5
    nearest_teammate_margin_m: float = 1.0


@dataclass(frozen=True)
class RelayTouchDetection:
    status: str
    reason: str | None
    relay_touch_frame_id: int | None
    relay_touch_ball_xy: tuple[float, float] | None
    relay_touch_player_xy: tuple[float, float] | None
    relay_touch_ball_distance_m: float | None


@dataclass(frozen=True)
class OneTouchRelayOutput:
    schema_version: str
    capability: str
    capability_version: str
    status: str
    accepted_scope: dict[str, Any]
    config: dict[str, Any]
    summary: dict[str, Any]
    anchor_evaluations: list[dict[str, Any]]
    episodes: list[dict[str, Any]]
    non_match_examples: list[dict[str, Any]]


def evaluate_one_touch_relays(
    *,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    match_ids: tuple[str, ...] | list[str] | None = None,
    periods: tuple[str, ...] | list[str] = DEFAULT_PERIODS,
    config: OneTouchRelayConfig = OneTouchRelayConfig(),
) -> OneTouchRelayOutput:
    """Evaluate event-linked one-touch relay candidates over the supplied scope."""

    requested_match_ids = tuple(str(item) for item in (match_ids or canonical_match_ids(canonical_root)))
    requested_periods = tuple(str(item) for item in periods)
    orientation = read_table(canonical_root / "orientation.parquet")
    records: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    non_match_examples: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    candidate_count = 0

    for match_id in requested_match_ids:
        events = read_table(canonical_root / "events" / f"match_id={match_id}.parquet", columns=EVENT_COLUMNS)
        events = events.sort_values(["period", "row_index"]).reset_index(drop=True)
        for period in requested_periods:
            period_events = events[events["period"].astype(str) == period].reset_index(drop=True)
            if period_events.empty:
                continue
            frames = read_table(
                canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet",
                columns=FRAME_COLUMNS,
            )
            frames["_frame_ts_utc"] = pd.to_datetime(frames["timestamp_utc"], utc=True, errors="coerce")
            frames = frames.sort_values("frame_id").reset_index(drop=True)
            positions = read_positions_table(
                canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
            )
            context = PeriodControlContext(
                match_id=match_id,
                period=period,
                frames=frames,
                positions=positions,
                attack_x_sign_by_role=attack_x_signs(orientation, match_id, period),
                config=ControlledPassConfig(
                    control_distance_m=config.control_distance_m,
                    nearest_teammate_margin_m=config.nearest_teammate_margin_m,
                ),
            )
            for first, second in adjacent_event_linked_passes(period_events, config=config):
                candidate_count += 1
                record = evaluate_one_touch_candidate(first, second, context, config)
                records.append(record)
                status_counts[str(record["one_touch_relay_status"])] += 1
                if record.get("one_touch_relay_reason"):
                    reason_counts[str(record["one_touch_relay_reason"])] += 1
                if record["one_touch_relay_status"] == PASS:
                    episodes.append(record)
                elif len(non_match_examples) < 50:
                    non_match_examples.append(record)

    records.sort(
        key=lambda item: (
            item["match_id"],
            item["period"],
            item.get("input_event_row_index") or -1,
            item.get("relay_event_row_index") or -1,
        )
    )
    episodes.sort(
        key=lambda item: (
            item["match_id"],
            item["period"],
            item.get("input_event_row_index") or -1,
            item.get("relay_event_row_index") or -1,
        )
    )
    return OneTouchRelayOutput(
        schema_version="afl08.one_touch_relay_episode.v1",
        capability="one_touch_relay_episode",
        capability_version="0.1.0",
        status="pass",
        accepted_scope={
            "match_ids": list(requested_match_ids),
            "periods": list(requested_periods),
            "scope_policy": "caller_supplied_match_scope",
        },
        config=asdict(config),
        summary={
            "event_linked_candidate_count": candidate_count,
            "episode_count": len(episodes),
            "one_touch_relay_status_counts": dict(sorted(status_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        anchor_evaluations=records,
        episodes=episodes,
        non_match_examples=non_match_examples,
    )


def adjacent_event_linked_passes(
    events: pd.DataFrame,
    *,
    config: OneTouchRelayConfig,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return adjacent pass-pass pairs linked by recipient -> next passer."""

    parsed = [parse_successful_pass_event(row) for _, row in events.iterrows()]
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for first, second in zip(parsed, parsed[1:], strict=False):
        if first is None or second is None:
            continue
        if first["team_role"] != second["team_role"]:
            continue
        if first["receiver_id"] != second["passer_id"]:
            continue
        gap = None
        if first.get("gameclock_seconds") is not None and second.get("gameclock_seconds") is not None:
            gap = float(second["gameclock_seconds"]) - float(first["gameclock_seconds"])
            if gap < 0 or gap > config.relay_max_event_gap_seconds:
                continue
        first["relay_event_gap_seconds"] = gap
        pairs.append((first, second))
    return pairs


def parse_successful_pass_event(row: pd.Series) -> dict[str, Any] | None:
    event_type = str(row.get("event_type") or "")
    if "Pass" not in event_type:
        return None
    qualifier = safe_json(row.get("qualifier_json"))
    if qualifier.get("Evaluation") != "successfullyCompleted":
        return None
    passer = qualifier.get("Player") or row.get("player_id")
    receiver = qualifier.get("Recipient")
    if not passer or not receiver:
        return None
    phase_raw = qualifier.get("BallPossessionPhase")
    try:
        phase = None if phase_raw is None else int(phase_raw)
    except (TypeError, ValueError):
        phase = None
    return {
        "match_id": str(row["match_id"]),
        "period": str(row["period"]),
        "row_index": int(row["row_index"]),
        "event_type": event_type,
        "event_timestamp": str(row["timestamp"]),
        "gameclock_seconds": float(row["gameclock_seconds"]) if pd.notna(row.get("gameclock_seconds")) else None,
        "team_role": str(row["team_role"]),
        "passer_id": str(passer),
        "receiver_id": str(receiver),
        "ball_possession_phase": phase,
    }


def evaluate_one_touch_candidate(
    input_event: dict[str, Any],
    relay_event: dict[str, Any],
    context: PeriodControlContext,
    config: OneTouchRelayConfig,
) -> dict[str, Any]:
    input_anchor_frame_id, input_event_offset_ms = align_event_to_frame(input_event, context.frames)
    relay_anchor_frame_id, relay_event_offset_ms = align_event_to_frame(relay_event, context.frames)
    input_event = {**input_event, "event_anchor_frame_id": input_anchor_frame_id}
    relay_event = {**relay_event, "event_anchor_frame_id": relay_anchor_frame_id}
    input_release = detect_physical_release(input_event, context)
    relay_release = detect_physical_release(relay_event, context)
    relay_touch = detect_relay_touch(
        context=context,
        relay_player_id=str(input_event["receiver_id"]),
        team_role=str(input_event["team_role"]),
        start_frame_id=input_release.physical_release_frame_id,
        relay_event_anchor_frame_id=relay_anchor_frame_id,
        relay_release_frame_id=relay_release.physical_release_frame_id,
        config=config,
    )
    status, reason = one_touch_status(input_release.status, relay_release.status, relay_touch, context, config)
    dwell_seconds = None
    if relay_touch.relay_touch_frame_id is not None and relay_release.physical_release_frame_id is not None:
        dwell_seconds = (relay_release.physical_release_frame_id - relay_touch.relay_touch_frame_id) / context.analysis_rate_hz
        if status == PASS and dwell_seconds > config.maximum_relay_dwell_seconds:
            status = FAIL
            reason = "relay_dwell_exceeded"
    input_pass_episode_id = pass_id(input_event)
    relay_pass_episode_id = pass_id(relay_event)
    forward_progression_m = relay_forward_progression(input_event, relay_event, context, input_release, relay_release)
    anchor_frame_id = (
        relay_touch.relay_touch_frame_id
        or relay_release.physical_release_frame_id
        or relay_anchor_frame_id
        or input_release.physical_release_frame_id
        or input_anchor_frame_id
    )
    return {
        "anchor_id": f"one_touch_relay:{input_pass_episode_id}:{relay_pass_episode_id}",
        "input_pass_episode_id": input_pass_episode_id,
        "relay_pass_episode_id": relay_pass_episode_id,
        "match_id": str(input_event["match_id"]),
        "period": str(input_event["period"]),
        "team_role": str(input_event["team_role"]),
        "input_event_row_index": int(input_event["row_index"]),
        "relay_event_row_index": int(relay_event["row_index"]),
        "input_event_type": str(input_event["event_type"]),
        "relay_event_type": str(relay_event["event_type"]),
        "input_event_timestamp": str(input_event["event_timestamp"]),
        "relay_event_timestamp": str(relay_event["event_timestamp"]),
        "input_event_anchor_frame_id": input_anchor_frame_id,
        "relay_event_anchor_frame_id": relay_anchor_frame_id,
        "input_event_frame_offset_ms": input_event_offset_ms,
        "relay_event_frame_offset_ms": relay_event_offset_ms,
        "input_passer_id": str(input_event["passer_id"]),
        "relay_player_id": str(input_event["receiver_id"]),
        "declared_next_pass_recipient_id": str(relay_event["receiver_id"]),
        "input_physical_release_frame_id": input_release.physical_release_frame_id,
        "relay_touch_frame_id": relay_touch.relay_touch_frame_id,
        "relay_physical_release_frame_id": relay_release.physical_release_frame_id,
        "relay_event_gap_seconds": input_event.get("relay_event_gap_seconds"),
        "relay_dwell_seconds": dwell_seconds,
        "maximum_relay_dwell_seconds": config.maximum_relay_dwell_seconds,
        "relay_touch_distance_m": relay_touch.relay_touch_ball_distance_m,
        "relay_touch_distance_threshold_m": config.relay_touch_distance_m,
        "one_touch_relay_status": status,
        "one_touch_relay_reason": reason,
        "input_release_detection_status": input_release.status,
        "input_release_detection_reason": input_release.reason,
        "relay_release_detection_status": relay_release.status,
        "relay_release_detection_reason": relay_release.reason,
        "relay_touch_detection_status": relay_touch.status,
        "relay_touch_detection_reason": relay_touch.reason,
        "forward_progression_m": forward_progression_m,
        "anchor_frame_id": anchor_frame_id,
        "start_frame_id": input_release.physical_release_frame_id or input_anchor_frame_id or anchor_frame_id,
        "end_frame_id": relay_release.physical_release_frame_id or relay_touch.relay_touch_frame_id or anchor_frame_id,
        "entity_refs": [
            str(input_event["passer_id"]),
            str(input_event["receiver_id"]),
            str(relay_event["receiver_id"]),
        ],
        "input_release_ball_point": point_from_xy_tuple(input_release.release_ball_xy),
        "input_release_player_point": point_from_xy_tuple(input_release.release_player_xy),
        "relay_touch_ball_point": point_from_xy_tuple(relay_touch.relay_touch_ball_xy),
        "relay_touch_player_point": point_from_xy_tuple(relay_touch.relay_touch_player_xy),
        "relay_release_ball_point": point_from_xy_tuple(relay_release.release_ball_xy),
        "relay_release_player_point": point_from_xy_tuple(relay_release.release_player_xy),
    }


def detect_relay_touch(
    *,
    context: PeriodControlContext,
    relay_player_id: str,
    team_role: str,
    start_frame_id: int | None,
    relay_event_anchor_frame_id: int | None,
    relay_release_frame_id: int | None,
    config: OneTouchRelayConfig,
) -> RelayTouchDetection:
    if start_frame_id is None or relay_event_anchor_frame_id is None:
        return RelayTouchDetection(UNKNOWN, "relay_touch_window_missing", None, None, None, None)
    start_index = context.frame_index_by_id.get(int(start_frame_id))
    event_index = context.frame_index_by_id.get(int(relay_event_anchor_frame_id))
    if start_index is None or event_index is None:
        return RelayTouchDetection(UNKNOWN, "relay_touch_tracking_missing", None, None, None, None)
    before = math.ceil(config.relay_touch_search_before_seconds * context.analysis_rate_hz)
    after = math.ceil(config.relay_touch_search_after_seconds * context.analysis_rate_hz)
    lower = max(start_index + 1, event_index - before)
    upper = min(len(context.frame_ids) - 1, event_index + after)
    if relay_release_frame_id is not None:
        release_index = context.frame_index_by_id.get(int(relay_release_frame_id))
        if release_index is not None:
            upper = min(upper, release_index)
    if lower > upper:
        return RelayTouchDetection(UNKNOWN, "relay_touch_window_empty", None, None, None, None)

    observed: list[tuple[int, float, tuple[float, float], tuple[float, float]]] = []
    missing = 0
    for frame_id in context.frame_ids[lower : upper + 1]:
        ball_xy = ball_at(context, frame_id)
        player = player_at(context, frame_id, relay_player_id)
        if ball_xy is None or player is None:
            missing += 1
            continue
        player_role, player_xy = player
        if player_role != team_role:
            continue
        distance = euclidean(ball_xy, player_xy)
        if distance <= config.relay_touch_distance_m:
            observed.append((frame_id, distance, ball_xy, player_xy))
    if observed:
        frame_id, distance, ball_xy, player_xy = min(
            observed,
            key=lambda item: (abs(item[0] - int(relay_event_anchor_frame_id)), item[1]),
        )
        return RelayTouchDetection(PASS, None, frame_id, ball_xy, player_xy, distance)
    if missing == (upper - lower + 1):
        return RelayTouchDetection(UNKNOWN, "relay_touch_tracking_missing", None, None, None, None)
    return RelayTouchDetection(FAIL, "relay_touch_not_observed", None, None, None, None)


def one_touch_status(
    input_release_status: str,
    relay_release_status: str,
    relay_touch: RelayTouchDetection,
    context: PeriodControlContext,
    config: OneTouchRelayConfig,
) -> tuple[str, str | None]:
    if input_release_status == UNKNOWN:
        return UNKNOWN, "input_release_not_confirmed"
    if input_release_status == FAIL:
        return FAIL, "input_release_contradicted"
    if relay_release_status == UNKNOWN:
        return UNKNOWN, "relay_release_not_confirmed"
    if relay_release_status == FAIL:
        return FAIL, "relay_release_contradicted"
    if relay_touch.status == UNKNOWN:
        return UNKNOWN, relay_touch.reason
    if relay_touch.status == FAIL:
        return FAIL, relay_touch.reason
    if relay_touch.relay_touch_frame_id is None:
        return UNKNOWN, "relay_touch_frame_missing"
    # The relay is event-linked, but the "one-touch" claim still requires the
    # observed touch-to-release interval to stay under the frozen dwell bound.
    # The caller passes the release frame through the context-independent record
    # computation, so this function only handles the status branches.
    return PASS, None


def relay_forward_progression(
    input_event: dict[str, Any],
    relay_event: dict[str, Any],
    context: PeriodControlContext,
    input_release: Any,
    relay_release: Any,
) -> float | None:
    if input_release.release_ball_xy is None or relay_release.release_ball_xy is None:
        return None
    attack_x_sign = context.attack_x_sign_by_role.get(str(input_event["team_role"]))
    if attack_x_sign not in {-1, 1}:
        return None
    return (relay_release.release_ball_xy[0] - input_release.release_ball_xy[0]) * attack_x_sign


def evaluate_receiver_line_transition(
    *,
    relay_evidence: dict[str, Any] | None,
    observed_line_evidence: dict[str, Any] | None,
    release_relative_position_evidence: dict[str, Any] | None,
    relay_relative_position_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "receiver_line_transition_status": UNKNOWN,
        "receiver_line_transition_reason": None,
        "line_anchor_id": None if observed_line_evidence is None else observed_line_evidence.get("anchor_id"),
        "line_anchor_frame_id": None if observed_line_evidence is None else observed_line_evidence.get("line_evaluation_frame_id"),
        "line_x_m": None if observed_line_evidence is None else observed_line_evidence.get("line_x_m"),
        "normalized_line_x_m": None if observed_line_evidence is None else observed_line_evidence.get("normalized_line_x_m"),
        "attacking_direction": None if observed_line_evidence is None else observed_line_evidence.get("attacking_direction"),
        "release_relative_position_status": None,
        "release_signed_distance_to_line_m": None,
        "relay_relative_position_status": None,
        "relay_signed_distance_to_line_m": None,
    }
    if relay_evidence is None:
        return {**base, "receiver_line_transition_reason": "relay_evidence_missing"}
    if relay_evidence.get("one_touch_relay_status") == UNKNOWN:
        return {**base, "receiver_line_transition_reason": "relay_status_unknown"}
    if relay_evidence.get("one_touch_relay_status") != PASS:
        return {
            **base,
            "receiver_line_transition_status": FAIL,
            "receiver_line_transition_reason": "relay_not_established",
        }
    if observed_line_evidence is None:
        return {**base, "receiver_line_transition_reason": "line_evidence_missing"}
    if observed_line_evidence.get("line_status") == UNKNOWN:
        return {**base, "receiver_line_transition_reason": "line_not_observed"}
    if observed_line_evidence.get("line_status") != PASS:
        return {
            **base,
            "receiver_line_transition_status": FAIL,
            "receiver_line_transition_reason": "line_not_observed",
        }
    if release_relative_position_evidence is None:
        return {**base, "receiver_line_transition_reason": "release_relative_position_missing"}
    if relay_relative_position_evidence is None:
        return {**base, "receiver_line_transition_reason": "relay_relative_position_missing"}
    release_status = str(release_relative_position_evidence.get("relative_position_status"))
    relay_status = str(relay_relative_position_evidence.get("relative_position_status"))
    base = {
        **base,
        "release_relative_position_status": release_status,
        "release_signed_distance_to_line_m": release_relative_position_evidence.get("signed_distance_to_line_m"),
        "relay_relative_position_status": relay_status,
        "relay_signed_distance_to_line_m": relay_relative_position_evidence.get("signed_distance_to_line_m"),
    }
    if UNKNOWN in {release_status, relay_status}:
        return {**base, "receiver_line_transition_reason": "relative_position_unknown"}
    if release_status not in {BEHIND_LINE, LEVEL_WITH_LINE, AHEAD_OF_LINE}:
        return {**base, "receiver_line_transition_reason": "release_relative_position_invalid"}
    if relay_status not in {BEHIND_LINE, LEVEL_WITH_LINE, AHEAD_OF_LINE}:
        return {**base, "receiver_line_transition_reason": "relay_relative_position_invalid"}
    if release_status == AHEAD_OF_LINE:
        return {
            **base,
            "receiver_line_transition_status": FAIL,
            "receiver_line_transition_reason": "receiver_already_beyond_line_at_input_release",
        }
    if relay_status != AHEAD_OF_LINE:
        return {
            **base,
            "receiver_line_transition_status": FAIL,
            "receiver_line_transition_reason": "receiver_not_beyond_line_at_relay_touch",
        }
    return {
        **base,
        "receiver_line_transition_status": PASS,
        "receiver_line_transition_reason": "receiver_transitioned_beyond_observed_line",
    }


def evaluate_pass_chain(
    *,
    relay_evidence: dict[str, Any] | None,
    terminal_controlled_pass_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    if relay_evidence is None:
        return {"pass_chain_status": UNKNOWN, "pass_chain_reason": "relay_evidence_missing"}
    if relay_evidence.get("one_touch_relay_status") == UNKNOWN:
        return {"pass_chain_status": UNKNOWN, "pass_chain_reason": "relay_status_unknown"}
    if relay_evidence.get("one_touch_relay_status") != PASS:
        return {"pass_chain_status": FAIL, "pass_chain_reason": "relay_not_established"}
    if terminal_controlled_pass_evidence is None:
        return {"pass_chain_status": UNKNOWN, "pass_chain_reason": "terminal_controlled_pass_evidence_missing"}
    terminal_status = terminal_controlled_pass_evidence.get("controlled_pass_status")
    if terminal_status == UNKNOWN:
        return {"pass_chain_status": UNKNOWN, "pass_chain_reason": "terminal_controlled_pass_unknown"}
    if terminal_status != PASS:
        return {"pass_chain_status": FAIL, "pass_chain_reason": "terminal_controlled_pass_not_established"}
    return {"pass_chain_status": PASS, "pass_chain_reason": "event_linked_relay_and_terminal_controlled_reception"}


def canonical_match_ids(canonical_root: Path) -> tuple[str, ...]:
    matches_path = canonical_root / "matches.parquet"
    if not matches_path.exists():
        return ("J03WOY",)
    matches = pd.read_parquet(matches_path, columns=["match_id"])
    return tuple(str(item) for item in matches["match_id"].dropna().tolist())


def point_from_xy_tuple(value: tuple[float, float] | None) -> dict[str, float] | None:
    if value is None:
        return None
    return {"x_m": float(value[0]), "y_m": float(value[1])}
