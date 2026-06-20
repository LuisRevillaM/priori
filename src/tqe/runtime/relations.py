"""Runtime relation implementations for M1.1."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

FRAME_RATE_HZ = 25
PITCH_HALF_WIDTH_M = 34.0
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
BALL_ENTITY_ID = "DFL-OBJ-0000XT"


@dataclass(frozen=True)
class CorridorConfig:
    analysis_rate_hz: int = 5
    max_window_seconds: float = 4.0
    minimum_progression_m: float = 8.0
    minimum_segment_length_m: float = 8.0
    maximum_segment_length_m: float = 45.0
    minimum_clearance_m: float = 5.0
    open_after_frames: int = 2
    close_after_frames: int = 2


def evaluate_geometric_progressive_corridors(
    *,
    results: list[dict[str, Any]],
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    config: CorridorConfig = CorridorConfig(),
) -> dict[str, Any]:
    orientation = read_table(canonical_root / "orientation.parquet")
    players = read_table(canonical_root / "players.parquet")
    positions_cache: dict[tuple[str, str], pd.DataFrame] = {}
    episodes: list[dict[str, Any]] = []
    negative_examples: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()

    for result in results:
        match_id = str(result["match_id"])
        period = str(result["period"])
        perspective_role = str(result["perspective_team_role"])
        defending_role = str(result["defending_team_role"])
        positions = positions_for(canonical_root, positions_cache, match_id, period)
        attack_x_sign = load_attack_x_sign(orientation, match_id, period, perspective_role)
        attacking_outfield = outfield_player_ids(players, match_id, perspective_role)
        defending_outfield = outfield_player_ids(players, match_id, defending_role)
        relation_rows, negatives, counts = evaluate_result_window(
            result=result,
            positions=positions,
            attack_x_sign=attack_x_sign,
            attacking_outfield=attacking_outfield,
            defending_outfield=defending_outfield,
            config=config,
        )
        episodes.extend(relation_rows)
        negative_examples.extend(negatives)
        state_counts.update(counts)

    episodes.sort(
        key=lambda item: (
            item["match_id"],
            item["period"],
            item["result_id"],
            item["open_frame_id"],
            item["target_player_id"],
        )
    )
    negative_examples.sort(
        key=lambda item: (
            item["match_id"],
            item["period"],
            item["result_id"],
            item["frame_id"],
            item["target_player_id"],
        )
    )
    selected_negative_examples = negative_examples[:40]
    unknown_invalid_controls = build_unknown_invalid_controls(results, canonical_root, players, positions_cache)
    visual_review_cases = select_visual_review_cases(episodes, selected_negative_examples)

    by_match = Counter(str(item["match_id"]) for item in episodes)
    by_destination_lane = Counter(str(item["destination_lane"]) for item in episodes)
    by_destination_side = Counter(str(item["destination_side"]) for item in episodes)
    return {
        "schema_version": "1.0",
        "relation": "geometric_progressive_corridor",
        "relation_version": "0.1.0",
        "status": "pass",
        "config": asdict(config),
        "summary": {
            "episode_count": len(episodes),
            "result_count_with_episode": len({item["result_id"] for item in episodes}),
            "match_count_with_episode": len(by_match),
            "by_match": dict(sorted(by_match.items())),
            "by_destination_lane": dict(sorted(by_destination_lane.items())),
            "by_destination_side": dict(sorted(by_destination_side.items())),
            "state_counts": dict(sorted(state_counts.items())),
        },
        "episodes": episodes,
        "negative_examples": selected_negative_examples,
        "unknown_invalid_controls": unknown_invalid_controls,
        "visual_review_cases": visual_review_cases,
        "disallowed_claims": [
            "No pass probability is inferred.",
            "No optimality or decision-quality claim is emitted.",
            "No player intent, causation, or missed-opportunity claim is emitted.",
            "No receiver body-orientation or offside model is evaluated.",
        ],
        "artifact_hash": stable_hash({"episodes": episodes, "config": asdict(config)}),
    }


def evaluate_result_window(
    *,
    result: dict[str, Any],
    positions: pd.DataFrame,
    attack_x_sign: int,
    attacking_outfield: set[str],
    defending_outfield: set[str],
    config: CorridorConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    step = FRAME_RATE_HZ // config.analysis_rate_hz
    max_end = int(result["anchor_frame_id"] + config.max_window_seconds * FRAME_RATE_HZ)
    outcome_end = int(result.get("outcome_frame_id", max_end))
    frame_ids = list(range(int(result["anchor_frame_id"]), min(outcome_end, max_end) + 1, step))
    scoped = positions[positions.frame_id.isin(frame_ids)]
    by_frame = {int(frame_id): frame.copy() for frame_id, frame in scoped.groupby("frame_id")}
    states_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    state_counts: Counter[str] = Counter()
    negative_examples: list[dict[str, Any]] = []

    for frame_id in frame_ids:
        frame = by_frame.get(frame_id)
        if frame is None:
            state_counts["UNKNOWN"] += 1
            continue
        ball = frame[frame.entity_type == "ball"]
        attackers = frame[
            (frame.entity_type == "player")
            & (frame.team_role == result["perspective_team_role"])
            & (frame.entity_id.astype(str).isin(attacking_outfield))
        ]
        defenders = frame[
            (frame.entity_type == "player")
            & (frame.team_role == result["defending_team_role"])
            & (frame.entity_id.astype(str).isin(defending_outfield))
        ]
        for attacker in attackers.itertuples(index=False):
            state = corridor_state(
                result=result,
                frame_id=frame_id,
                ball=ball,
                target=attacker._asdict(),
                defenders=defenders,
                attack_x_sign=attack_x_sign,
                config=config,
            )
            states_by_target[str(attacker.entity_id)].append(state)
            state_counts[state["status"]] += 1
            if state["status"] == "FAIL" and state.get("failure_reason") == "clearance_below_threshold":
                negative_examples.append(state)

    episodes: list[dict[str, Any]] = []
    for target_player_id, states in states_by_target.items():
        episodes.extend(episodes_from_states(result, target_player_id, states, config))
    return episodes, negative_examples, state_counts


def corridor_state(
    *,
    result: dict[str, Any],
    frame_id: int,
    ball: pd.DataFrame | None,
    target: dict[str, Any] | None,
    defenders: pd.DataFrame | None,
    attack_x_sign: int,
    config: CorridorConfig,
) -> dict[str, Any]:
    common = {
        "result_id": str(result["result_id"]),
        "match_id": str(result["match_id"]),
        "period": str(result["period"]),
        "frame_id": int(frame_id),
        "target_player_id": str(target["entity_id"]) if target else None,
    }
    if ball is None or ball.empty:
        return {**common, "status": "UNKNOWN", "reason": "source_ball_unavailable"}
    if target is None or "x_m" not in target or "y_m" not in target:
        return {**common, "status": "UNKNOWN", "reason": "target_player_unavailable"}
    if defenders is None or defenders.empty:
        return {**common, "status": "UNKNOWN", "reason": "defenders_unavailable"}

    ball_row = ball.iloc[0]
    source = point_payload(float(ball_row.x_m), float(ball_row.y_m))
    destination = point_payload(float(target["x_m"]), float(target["y_m"]))
    dx = destination["x_m"] - source["x_m"]
    dy = destination["y_m"] - source["y_m"]
    segment_length = math.hypot(dx, dy)
    if not math.isfinite(segment_length) or segment_length <= 0.001:
        return {
            **common,
            "status": "INVALID",
            "reason": "invalid_relation_geometry",
            "source_point": source,
            "target_point": destination,
        }

    forward_progression = attack_x_sign * dx
    limiting_defender_id: str | None = None
    minimum_clearance = math.inf
    for defender in defenders.itertuples(index=False):
        clearance = point_segment_distance(
            float(defender.x_m),
            float(defender.y_m),
            source["x_m"],
            source["y_m"],
            destination["x_m"],
            destination["y_m"],
        )
        if clearance < minimum_clearance:
            minimum_clearance = clearance
            limiting_defender_id = str(defender.entity_id)

    payload = {
        **common,
        "source_entity_id": BALL_ENTITY_ID,
        "source_point": source,
        "target_point": destination,
        "forward_progression_m": round(forward_progression, 3),
        "segment_length_m": round(segment_length, 3),
        "minimum_clearance_m": round(minimum_clearance, 3),
        "limiting_defender_id": limiting_defender_id,
        "destination_side": destination_side(destination["y_m"]),
        "destination_lane": destination_lane(destination["y_m"]),
    }
    payload["destination_region"] = f"{payload['destination_side']}_{payload['destination_lane']}"
    payload["destination_region_type"] = "side_lane_band"
    payload["destination_region_bounds"] = destination_region_bounds(
        payload["destination_side"],
        payload["destination_lane"],
    )
    if forward_progression < config.minimum_progression_m:
        return {**payload, "status": "FAIL", "failure_reason": "insufficient_forward_progression"}
    if segment_length < config.minimum_segment_length_m:
        return {**payload, "status": "FAIL", "failure_reason": "segment_too_short"}
    if segment_length > config.maximum_segment_length_m:
        return {**payload, "status": "FAIL", "failure_reason": "segment_too_long"}
    if minimum_clearance < config.minimum_clearance_m:
        return {**payload, "status": "FAIL", "failure_reason": "clearance_below_threshold"}
    return {**payload, "status": "PASS"}


def episodes_from_states(
    result: dict[str, Any],
    target_player_id: str,
    states: list[dict[str, Any]],
    config: CorridorConfig,
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    pass_count = 0
    fail_count = 0
    pending_start: dict[str, Any] | None = None
    open_state: dict[str, Any] | None = None
    open_confirm_frame_id: int | None = None
    last_pass_state: dict[str, Any] | None = None
    episode_pass_states: list[dict[str, Any]] = []

    def close_episode(close_reason: str) -> None:
        nonlocal open_state, open_confirm_frame_id, last_pass_state, episode_pass_states
        if open_state is None or last_pass_state is None:
            return
        frame_count = len(episode_pass_states)
        if frame_count < config.open_after_frames:
            return
        minimum_clearance_state = min(
            episode_pass_states,
            key=lambda item: float(item["minimum_clearance_m"]),
        )
        relation_id = relation_id_for(
            str(result["result_id"]),
            target_player_id,
            int(open_state["frame_id"]),
            int(last_pass_state["frame_id"]),
        )
        episodes.append(
            {
                "relation_id": relation_id,
                "relation": "geometric_progressive_corridor",
                "relation_version": "0.1.0",
                "status": "PASS",
                "result_id": str(result["result_id"]),
                "match_id": str(result["match_id"]),
                "period": str(result["period"]),
                "perspective_team_role": str(result["perspective_team_role"]),
                "source_entity_id": BALL_ENTITY_ID,
                "target_player_id": target_player_id,
                "open_frame_id": int(open_state["frame_id"]),
                "open_confirm_frame_id": open_confirm_frame_id,
                "close_frame_id": int(last_pass_state["frame_id"]),
                "duration_seconds": round(frame_count / config.analysis_rate_hz, 3),
                "minimum_clearance_m": minimum_clearance_state["minimum_clearance_m"],
                "limiting_defender_id": minimum_clearance_state["limiting_defender_id"],
                "forward_progression_m": open_state["forward_progression_m"],
                "segment_length_m": open_state["segment_length_m"],
                "destination_side": open_state["destination_side"],
                "destination_region": open_state["destination_region"],
                "destination_region_type": open_state["destination_region_type"],
                "destination_region_bounds": open_state["destination_region_bounds"],
                "destination_lane": open_state["destination_lane"],
                "source_open_point": open_state["source_point"],
                "target_open_point": open_state["target_point"],
                "source_close_point": last_pass_state["source_point"],
                "target_close_point": last_pass_state["target_point"],
                "open_after_frames": config.open_after_frames,
                "close_after_frames": config.close_after_frames,
                "close_reason": close_reason,
                "evidence_fields": [
                    "open_frame_id",
                    "close_frame_id",
                    "duration_seconds",
                    "minimum_clearance_m",
                    "target_player_id",
                    "destination_side",
                    "destination_region",
                    "destination_region_type",
                    "destination_region_bounds",
                    "destination_lane",
                    "limiting_defender_id",
                    "source_open_point",
                    "target_open_point",
                    "source_close_point",
                    "target_close_point",
                ],
            }
        )

    for state in states:
        if state["status"] == "PASS":
            fail_count = 0
            pass_count += 1
            if pass_count == 1:
                pending_start = state
            if open_state is None and pass_count >= config.open_after_frames:
                open_state = pending_start
                open_confirm_frame_id = int(state["frame_id"])
                episode_pass_states = [pending_start] if pending_start is not None else []
            if open_state is not None:
                last_pass_state = state
                if not episode_pass_states or episode_pass_states[-1]["frame_id"] != state["frame_id"]:
                    episode_pass_states.append(state)
            continue

        if open_state is not None:
            fail_count += 1
            if fail_count >= config.close_after_frames:
                close_episode("closed_after_failures")
                open_state = None
                open_confirm_frame_id = None
                last_pass_state = None
                episode_pass_states = []
                pass_count = 0
                fail_count = 0
                pending_start = None
            continue

        pass_count = 0
        pending_start = None

    if open_state is not None and last_pass_state is not None:
        close_episode("window_end")
    return episodes


def build_unknown_invalid_controls(
    results: list[dict[str, Any]],
    canonical_root: Path,
    players: pd.DataFrame,
    positions_cache: dict[tuple[str, str], pd.DataFrame],
) -> list[dict[str, Any]]:
    if not results:
        return []
    result = results[0]
    match_id = str(result["match_id"])
    period = str(result["period"])
    positions = positions_for(canonical_root, positions_cache, match_id, period)
    frame_id = int(result["anchor_frame_id"])
    frame = positions[positions.frame_id == frame_id]
    ball = frame[frame.entity_type == "ball"]
    defenders = frame[
        (frame.entity_type == "player") & (frame.team_role == result["defending_team_role"])
    ]
    unavailable = unavailable_attacker(players, frame, match_id, str(result["perspective_team_role"]))
    available_target = frame[
        (frame.entity_type == "player") & (frame.team_role == result["perspective_team_role"])
    ].head(1)
    target = available_target.iloc[0].to_dict() if not available_target.empty else None
    return [
        {
            "control_id": "target_player_unavailable",
            "state": corridor_state(
                result=result,
                frame_id=frame_id,
                ball=ball,
                target=unavailable,
                defenders=defenders,
                attack_x_sign=1,
                config=CorridorConfig(),
            ),
        },
        {
            "control_id": "invalid_relation_geometry",
            "state": corridor_state(
                result=result,
                frame_id=frame_id,
                ball=ball,
                target=ball.iloc[0].to_dict() if not ball.empty else target,
                defenders=defenders,
                attack_x_sign=1,
                config=CorridorConfig(),
            ),
        },
    ]


def unavailable_attacker(
    players: pd.DataFrame,
    frame: pd.DataFrame,
    match_id: str,
    team_role: str,
) -> dict[str, Any] | None:
    roster = list(
        players[
            (players.match_id == match_id)
            & (players.team_role == team_role)
            & (~players.is_goalkeeper)
        ].player_id.astype(str)
    )
    present = set(frame[frame.team_role == team_role].entity_id.astype(str))
    for player_id in roster:
        if player_id not in present:
            return {"entity_id": player_id}
    return None


def select_visual_review_cases(
    episodes: list[dict[str, Any]],
    negative_examples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_matches: set[str] = set()
    for episode in episodes:
        if episode["match_id"] in seen_matches:
            continue
        seen_matches.add(str(episode["match_id"]))
        cases.append({"case_type": "positive", "relation_id": episode["relation_id"], "episode": episode})
        if len(cases) >= 3:
            break
    if negative_examples:
        cases.append({"case_type": "negative", "state": negative_examples[0]})
    flicker = next((episode for episode in episodes if episode["close_reason"] == "closed_after_failures"), None)
    if flicker is not None:
        cases.append({"case_type": "flicker_boundary", "relation_id": flicker["relation_id"], "episode": flicker})
    return cases


def write_visual_review_svgs(cases: list[dict[str, Any]], output_dir: Path) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    for index, case in enumerate(cases):
        case_type = str(case["case_type"])
        path = output_dir / f"{index + 1:02d}-{case_type}.svg"
        path.write_text(svg_for_case(case), encoding="utf-8")
        written.append({"case_type": case_type, "path": str(path)})
    return written


def svg_for_case(case: dict[str, Any]) -> str:
    if "episode" in case:
        episode = case["episode"]
        source = episode["source_open_point"]
        target = episode["target_open_point"]
        title = f"{case['case_type']} {episode['relation_id']}"
        color = "#1f8a5b"
    else:
        state = case["state"]
        source = state.get("source_point", {"x_m": 0.0, "y_m": 0.0})
        target = state.get("target_point", {"x_m": 0.0, "y_m": 0.0})
        title = f"{case['case_type']} {state.get('failure_reason', state.get('reason'))}"
        color = "#b12a34"
    sx, sy = pitch_to_svg(source["x_m"], source["y_m"])
    tx, ty = pitch_to_svg(target["x_m"], target["y_m"])
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">',
            f"<title>{escape_xml(title)}</title>",
            '<rect x="20" y="20" width="600" height="380" fill="#0b6b43" stroke="#ffffff" stroke-width="2"/>',
            '<line x1="320" y1="20" x2="320" y2="400" stroke="#ffffff" stroke-width="1"/>',
            f'<line x1="{sx:.2f}" y1="{sy:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" stroke="{color}" stroke-width="5"/>',
            f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="7" fill="#f4d35e"/>',
            f'<circle cx="{tx:.2f}" cy="{ty:.2f}" r="7" fill="#ffffff"/>',
            f'<text x="28" y="38" fill="#ffffff" font-size="16">{escape_xml(title)}</text>',
            "</svg>",
            "",
        ]
    )


def pitch_to_svg(x_m: float, y_m: float) -> tuple[float, float]:
    x = 20 + ((x_m + 52.5) / 105.0) * 600
    y = 20 + ((34.0 - y_m) / 68.0) * 380
    return x, y


def point_payload(x_m: float, y_m: float) -> dict[str, float]:
    return {"x_m": round(x_m, 3), "y_m": round(y_m, 3)}


def point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    denominator = dx * dx + dy * dy
    if denominator <= 1e-9:
        return math.nan
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denominator))
    qx = ax + t * dx
    qy = ay + t * dy
    return math.hypot(px - qx, py - qy)


def destination_side(y_m: float) -> str:
    if y_m > 0:
        return "right"
    if y_m < 0:
        return "left"
    return "central"


def destination_lane(y_m: float) -> str:
    absolute_y = abs(y_m)
    if absolute_y >= PITCH_HALF_WIDTH_M * 0.66:
        return "wide"
    if absolute_y >= PITCH_HALF_WIDTH_M * 0.33:
        return "half_space"
    return "central"


def destination_region_bounds(destination_side: str, destination_lane: str) -> dict[str, float]:
    if destination_lane == "wide":
        minimum_abs_y = PITCH_HALF_WIDTH_M * 0.66
        maximum_abs_y = PITCH_HALF_WIDTH_M
    elif destination_lane == "half_space":
        minimum_abs_y = PITCH_HALF_WIDTH_M * 0.33
        maximum_abs_y = PITCH_HALF_WIDTH_M * 0.66
    elif destination_lane == "central":
        minimum_abs_y = 0.0
        maximum_abs_y = PITCH_HALF_WIDTH_M * 0.33
    else:
        raise RuntimeError(f"Unsupported destination lane {destination_lane}")

    if destination_side == "left":
        return {
            "min_y_m": round(-maximum_abs_y, 3),
            "max_y_m": round(-minimum_abs_y, 3),
        }
    if destination_side == "right":
        return {
            "min_y_m": round(minimum_abs_y, 3),
            "max_y_m": round(maximum_abs_y, 3),
        }
    if destination_side == "central":
        return {
            "min_y_m": round(-maximum_abs_y, 3),
            "max_y_m": round(maximum_abs_y, 3),
        }
    raise RuntimeError(f"Unsupported destination side {destination_side}")


def load_attack_x_sign(orientation: pd.DataFrame, match_id: str, period: str, team_role: str) -> int:
    selected = orientation[
        (orientation.match_id == match_id)
        & (orientation.period == period)
        & (orientation.team_role == team_role)
    ]
    if selected.empty:
        raise RuntimeError(f"Missing orientation for {match_id} {period} {team_role}")
    return int(selected.iloc[0].attack_x_sign)


def outfield_player_ids(players: pd.DataFrame, match_id: str, team_role: str) -> set[str]:
    selected = players[
        (players.match_id == match_id)
        & (players.team_role == team_role)
        & (~players.is_goalkeeper)
    ]
    return set(selected.player_id.astype(str))


def positions_for(
    canonical_root: Path,
    cache: dict[tuple[str, str], pd.DataFrame],
    match_id: str,
    period: str,
) -> pd.DataFrame:
    key = (match_id, period)
    if key not in cache:
        cache[key] = read_table(
            canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet",
            columns=["frame_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
        )
    return cache[key]


def read_table(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return pq.ParquetFile(path).read(columns=columns).to_pandas()


def relation_id_for(result_id: str, target_player_id: str, open_frame_id: int, close_frame_id: int) -> str:
    seed = f"geometric_progressive_corridor:0.1.0:{result_id}:{target_player_id}:{open_frame_id}:{close_frame_id}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
