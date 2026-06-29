"""Generate the Workbench Moment-0 line-break replay bundle."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.pass_bypass import attack_x_sign_for  # noqa: E402
from tqe.query.ball_side_block_shift import stream_ball_state  # noqa: E402

PLAN_PATH = REPO_ROOT / "config/query-plans/q3_receiver_second_line_no_underneath_support.experimental.v1.json"
OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-zero.json"
CATALOG_OUT_PATH = REPO_ROOT / "apps/workbench-alpha/src/generated/moment-zero-catalog.json"
PREFERRED_REPRESENTATIVE_RESULT_ID = "99a17527b542b7a3"
FRAME_RATE_HZ = 25
PITCH = {"length_m": 105.0, "width_m": 68.0, "coordinate_contract": "centered_metres"}


def main() -> None:
    canonical_root = Path(os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"))
    raw_root = Path(os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"))
    document_payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    bound_plan = bind_document(TacticalQueryDocument.model_validate(document_payload))
    execution = TacticalQueryExecutor(canonical_root=canonical_root, raw_root=raw_root).execute(bound_plan)
    rows = execution_result_rows(execution)
    candidates = [
        row
        for row in rows
        if row["requested_evidence"].get("support_arrival_status") == "FAIL"
        and row["requested_evidence"].get("line_break_status") == "PASS"
        and row["requested_evidence"].get("coverage_status") == "COMPLETE"
    ]
    if not candidates:
        raise RuntimeError("No line-break-without-underneath-outlet candidates found.")
    source_plan = {
        "path": str(PLAN_PATH.relative_to(REPO_ROOT)),
        "document_hash": stable_hash(document_payload),
        "plan_id": bound_plan.plan_id,
    }
    payloads = [
        payload_from_moment(moment, canonical_root=canonical_root, raw_root=raw_root, source_plan=source_plan)
        for moment in sorted(candidates, key=lambda row: int(row["anchor_frame_id"]))
    ]
    payloads.sort(key=line_break_no_support_payload_sort_key)
    payload = payloads[0]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CATALOG_OUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "coach_moment_catalog.line_break_no_underneath_support.v0",
                "moment_kind": "line_break_no_underneath_support",
                "count": len(payloads),
                "moments": payloads,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(OUT_PATH.relative_to(REPO_ROOT)),
                "catalog_path": str(CATALOG_OUT_PATH.relative_to(REPO_ROOT)),
                "result_id": payload["moment"]["result_id"],
                "frame_count": len(payload["replay"]["frames"]),
                "catalog_count": len(payloads),
                "clean_control_pass_count": sum(
                    1
                    for item in payloads
                    if item["moment"]["clean_control_retention"]["status"] == "PASS"
                ),
            },
            sort_keys=True,
        )
    )


def payload_from_moment(
    moment: dict[str, Any],
    *,
    canonical_root: Path,
    raw_root: Path,
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    evidence = moment["requested_evidence"]
    release_frame_id = int(evidence["physical_release_frame_id"])
    reception_frame_id = int(evidence["controlled_reception_frame_id"])
    support_window_end_frame_id = reception_frame_id + math.ceil(float(evidence["maximum_arrival_seconds"]) * FRAME_RATE_HZ)
    start_frame_id = max(release_frame_id - 20, 0)
    end_frame_id = max(support_window_end_frame_id + 18, reception_frame_id + FRAME_RATE_HZ * 8)
    replay = replay_window(
        canonical_root=canonical_root,
        match_id=str(moment["match_id"]),
        period=str(moment["period"]),
        start_frame_id=start_frame_id,
        end_frame_id=end_frame_id,
        raw_root=None,
    )
    receiver_id = str(evidence["receiver_id"])
    passer_id = pass_actor_ids(str(evidence["pass_episode_id"]))[0]
    reference_point = entity_point_at_frame(replay["frames"], reception_frame_id, receiver_id)
    orientation_rows = pd.read_parquet(canonical_root / "orientation.parquet")
    attacking_direction = attack_x_sign_for(
        orientation_rows,
        str(moment["match_id"]),
        str(moment["period"]),
        str(moment["perspective_team_role"]),
    )
    outcome_sequence = observed_ball_outcome_sequence(
        replay=replay,
        start_frame_id=reception_frame_id,
        end_frame_id=min(support_window_end_frame_id + 18, reception_frame_id + FRAME_RATE_HZ * 4),
        attacking_direction=attacking_direction,
    )
    possession_retention = raw_possession_retention_not_evaluated(
        start_frame_id=reception_frame_id,
        end_frame_id=reception_frame_id + FRAME_RATE_HZ * 4,
        perspective_team_role=str(moment["perspective_team_role"]),
    )
    clean_control_retention = clean_control_retention_sequence(
        replay=replay,
        start_frame_id=reception_frame_id,
        end_frame_id=reception_frame_id + FRAME_RATE_HZ * 4,
        perspective_team_role=str(moment["perspective_team_role"]),
        defending_team_role=str(moment["defending_team_role"]),
        receiver_id=receiver_id,
    )
    payload = {
        "schema_version": "moment_zero.line_break_no_underneath_support.v0",
        "source_plan": source_plan,
        "moment": {
            "result_id": moment["result_id"],
            "classification": moment["classification"],
            "match_id": moment["match_id"],
            "period": moment["period"],
            "perspective_team_role": moment["perspective_team_role"],
            "defending_team_role": moment["defending_team_role"],
            "anchor_frame_id": int(moment["anchor_frame_id"]),
            "release_frame_id": release_frame_id,
            "reception_frame_id": reception_frame_id,
            "support_window_end_frame_id": support_window_end_frame_id,
            "passer_id": passer_id,
            "receiver_id": receiver_id,
            "defensive_line_player_ids": evidence["defensive_line_player_ids"],
            "line_x_m": float(evidence["line_x_m"]),
            "observed_lines": evidence["observed_lines"],
            "support_region": {
                "mode": evidence["support_region_mode"],
                "reference_point": reference_point,
                "maximum_support_distance_m": float(evidence["maximum_support_distance_m"]),
                "maximum_arrival_seconds": float(evidence["maximum_arrival_seconds"]),
                "attacking_direction": attacking_direction,
                "candidate_player_ids": evidence["candidate_player_ids"],
                "supporting_player_ids": evidence["supporting_player_ids"],
                "support_arrival_status": evidence["support_arrival_status"],
                "support_arrival_reason": evidence["support_arrival_reason"],
                "coverage_status": evidence["coverage_status"],
            },
            "outcome_sequence": outcome_sequence,
            "possession_retention": possession_retention,
            "clean_control_retention": clean_control_retention,
            "requested_evidence": evidence,
        },
        "replay": replay,
        "visual_contract": {
            "defensive_line": ["line_x_m", "observed_lines", "defensive_line_player_ids"],
            "pass_path": ["physical_release_frame_id", "controlled_reception_frame_id", "pass_episode_id"],
            "receiver_crossing": ["receiver_id", "release_relative_position_status", "reception_relative_position_status"],
            "empty_support_region": [
                "support_region_mode",
                "maximum_support_distance_m",
                "supporting_player_ids",
                "support_arrival_status",
                "coverage_status",
            ],
            "observed_outcome_sequence": [
                "outcome_sequence.start_frame_id",
                "outcome_sequence.end_frame_id",
                "outcome_sequence.ball_start_point",
                "outcome_sequence.ball_end_point",
                "outcome_sequence.forward_progression_m",
                "outcome_sequence.progression_status",
                "outcome_sequence.final_third_status",
                "outcome_sequence.final_third_outcome",
            ],
            "observed_possession_retention": [
                "possession_retention.status",
                "possession_retention.start_frame_id",
                "possession_retention.end_frame_id",
                "possession_retention.observed_seconds_after_reception",
                "possession_retention.perspective_team_role",
                "possession_retention.possession_team_role_at_end",
            ],
            "observed_clean_control_retention": [
                "clean_control_retention.status",
                "clean_control_retention.start_frame_id",
                "clean_control_retention.end_frame_id",
                "clean_control_retention.receiver_clean_control_max_seconds",
                "clean_control_retention.team_clean_control_max_seconds",
                "clean_control_retention.provider_loss_frame_count",
            ],
            "prohibited_visual_claims": [
                "intent",
                "quality",
                "causation",
                "optimality",
                "who should have supported",
            ],
        },
    }
    return payload


def replay_window(
    *,
    canonical_root: Path,
    match_id: str,
    period: str,
    start_frame_id: int,
    end_frame_id: int,
    raw_root: Path | None = None,
) -> dict[str, Any]:
    frame_path = period_parquet_path(canonical_root / "frames" / f"match_id={match_id}", period)
    position_path = period_parquet_path(canonical_root / "positions" / f"match_id={match_id}", period)
    frames = filter_frame_window(pq.ParquetFile(frame_path).read(), start_frame_id, end_frame_id)
    positions = filter_frame_window(pq.ParquetFile(position_path).read(), start_frame_id, end_frame_id)
    ball_state_by_frame = (
        replay_ball_state_by_frame(raw_root=raw_root, match_id=match_id, period=period, start_frame_id=start_frame_id, end_frame_id=end_frame_id)
        if raw_root is not None
        else {}
    )
    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in positions.to_pylist():
        positions_by_frame.setdefault(int(row["frame_id"]), []).append(
            {
                "team_id": row["team_id"],
                "team_role": row["team_role"],
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "x_m": round(float(row["x_m"]), 3),
                "y_m": round(float(row["y_m"]), 3),
            }
        )
    replay_frames = []
    for frame in frames.to_pylist():
        frame_id = int(frame["frame_id"])
        replay_frames.append(
            {
                "frame_id": frame_id,
                "timestamp_utc": frame.get("timestamp_utc"),
                "ball_state": ball_state_by_frame.get(frame_id),
                "entities": positions_by_frame.get(frame_id, []),
            }
        )
    return {
        "schema_version": "1.0",
        "replay_window_id": f"moment_zero_{match_id}_{period}_{start_frame_id}_{end_frame_id}",
        "source_kind": "result",
        "source_id": "moment_zero",
        "match_id": match_id,
        "period": period,
        "frame_rate_hz": FRAME_RATE_HZ,
        "generated_at": "deterministic_from_q3_plan",
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "anchor_frame_id": replay_frames[min(len(replay_frames) - 1, max(0, FRAME_RATE_HZ * 3))]["frame_id"],
        "pitch": PITCH,
        "canonical_sources": {
            "frames": canonical_source_id(frame_path, canonical_root),
            "positions": canonical_source_id(position_path, canonical_root),
            "frames_sha256": sha256_file(frame_path),
            "positions_sha256": sha256_file(position_path),
            **(raw_tracking_source(raw_root, match_id) if raw_root is not None else {}),
        },
        "frames": replay_frames,
    }


def replay_ball_state_by_frame(
    *,
    raw_root: Path,
    match_id: str,
    period: str,
    start_frame_id: int,
    end_frame_id: int,
) -> dict[int, dict[str, Any]]:
    raw_tracking = raw_root / match_id / "tracking.xml"
    if not raw_tracking.exists():
        return {}
    ball_state = cached_ball_state(str(raw_tracking), period)
    window = ball_state[(ball_state.frame_id >= start_frame_id) & (ball_state.frame_id <= end_frame_id)]
    states: dict[int, dict[str, Any]] = {}
    for row in window.itertuples(index=False):
        possession_team_role = getattr(row, "possession_team_role", None)
        states[int(row.frame_id)] = {
            "ball_alive": bool(getattr(row, "ball_alive", False)),
            "possession_team_role": None if pd.isna(possession_team_role) else str(possession_team_role),
        }
    return states


def raw_tracking_source(raw_root: Path | None, match_id: str) -> dict[str, str]:
    if raw_root is None:
        return {}
    raw_tracking = raw_root / match_id / "tracking.xml"
    if not raw_tracking.exists():
        return {}
    return {
        "raw_tracking": str(Path("data/raw/idsse/figshare-28196177-v1") / match_id / "tracking.xml"),
        "raw_tracking_sha256": sha256_file(raw_tracking),
    }


@lru_cache(maxsize=32)
def cached_ball_state(raw_tracking_path: str, period: str) -> pd.DataFrame:
    return stream_ball_state(Path(raw_tracking_path), period)


def filter_frame_window(table: Any, start_frame_id: int, end_frame_id: int) -> Any:
    mask = pc.and_(
        pc.greater_equal(table["frame_id"], start_frame_id),
        pc.less_equal(table["frame_id"], end_frame_id),
    )
    return table.filter(mask)


def period_parquet_path(root: Path, period: str) -> Path:
    candidates = [root / f"{period}.parquet", root / f"period={period}.parquet"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def pass_actor_ids(pass_episode_id: str) -> tuple[str, str]:
    parts = pass_episode_id.split(":")
    if len(parts) < 2:
        raise ValueError(f"Unexpected pass episode id: {pass_episode_id}")
    return parts[-2], parts[-1]


def entity_point_at_frame(frames: list[dict[str, Any]], frame_id: int, entity_id: str) -> dict[str, float]:
    for frame in frames:
        if int(frame["frame_id"]) != frame_id:
            continue
        for entity in frame["entities"]:
            if entity["entity_id"] == entity_id:
                return {"x_m": float(entity["x_m"]), "y_m": float(entity["y_m"])}
    raise RuntimeError(f"Missing {entity_id} at frame {frame_id}")


def observed_ball_outcome_sequence(
    *,
    replay: dict[str, Any],
    start_frame_id: int,
    end_frame_id: int,
    attacking_direction: int,
) -> dict[str, Any]:
    minimum_progression_m = 8.0
    start_ball = ball_point_at_frame(replay["frames"], start_frame_id)
    end_frame = max(
        (
            frame
            for frame in replay["frames"]
            if start_frame_id <= int(frame["frame_id"]) <= end_frame_id and ball_point_from_frame(frame) is not None
        ),
        key=lambda frame: int(frame["frame_id"]),
        default=None,
    )
    end_ball = ball_point_from_frame(end_frame) if end_frame else None
    if start_ball is None or end_ball is None:
        return {
            "mode": "observed_ball_position_after_reception",
            "status": "UNKNOWN",
            "reason": "ball_tracking_missing",
            "start_frame_id": start_frame_id,
            "end_frame_id": start_frame_id,
            "observed_seconds_after_reception": 0.0,
            "ball_start_point": start_ball,
            "ball_end_point": end_ball,
            "forward_progression_m": None,
            "minimum_progression_m": minimum_progression_m,
            "progression_status": "UNKNOWN",
            "distance_m": None,
            "start_normalized_x_m": None,
            "end_normalized_x_m": None,
            "final_third_status": "UNKNOWN",
            "final_third_start_status": "UNKNOWN",
            "final_third_outcome": "UNKNOWN",
            "claim_boundary": "Measured observable ball outcome after reception only; no quality, intent, causation, possession-control, or decision-value claim.",
        }
    actual_end_frame_id = int(end_frame["frame_id"])
    dx = float(end_ball["x_m"]) - float(start_ball["x_m"])
    dy = float(end_ball["y_m"]) - float(start_ball["y_m"])
    normalized_start_x = float(start_ball["x_m"]) * int(attacking_direction)
    normalized_end_x = float(end_ball["x_m"]) * int(attacking_direction)
    final_third_threshold = float(replay["pitch"]["length_m"]) / 6.0
    forward_progression_m = round(dx * int(attacking_direction), 2)
    starts_in_final_third = normalized_start_x > final_third_threshold
    ends_in_final_third = normalized_end_x > final_third_threshold
    if starts_in_final_third and ends_in_final_third:
        final_third_outcome = "remained_in_final_third"
    elif ends_in_final_third:
        final_third_outcome = "reached_final_third"
    else:
        final_third_outcome = "did_not_reach_final_third"
    return {
        "mode": "measured_ball_outcome_after_reception",
        "status": "PASS",
        "reason": "ball_tracking_observed",
        "start_frame_id": start_frame_id,
        "end_frame_id": actual_end_frame_id,
        "observed_seconds_after_reception": round((actual_end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2),
        "ball_start_point": start_ball,
        "ball_end_point": end_ball,
        "forward_progression_m": forward_progression_m,
        "minimum_progression_m": minimum_progression_m,
        "progression_status": "PASS" if forward_progression_m >= minimum_progression_m else "FAIL",
        "distance_m": round(math.hypot(dx, dy), 2),
        "start_normalized_x_m": round(normalized_start_x, 2),
        "end_normalized_x_m": round(normalized_end_x, 2),
        "final_third_start_status": "PASS" if starts_in_final_third else "FAIL",
        "final_third_status": "PASS" if ends_in_final_third else "FAIL",
        "final_third_outcome": final_third_outcome,
        "final_third_threshold_normalized_x_m": round(final_third_threshold, 2),
        "claim_boundary": "Measured observable ball outcome after reception only; no quality, intent, causation, possession-control, or decision-value claim.",
    }


def possession_retention_sequence(
    *,
    raw_root: Path,
    match_id: str,
    period: str,
    perspective_team_role: str,
    start_frame_id: int,
    end_frame_id: int,
) -> dict[str, Any]:
    raw_tracking = raw_root / match_id / "tracking.xml"
    required_retention_seconds = round((end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2)
    if not raw_tracking.exists():
        return {
            "mode": "raw_ball_possession_retention_after_reception",
            "status": "UNKNOWN",
            "reason": "raw_tracking_missing",
            "start_frame_id": start_frame_id,
            "end_frame_id": start_frame_id,
            "observed_seconds_after_reception": 0.0,
            "required_retention_seconds": required_retention_seconds,
            "perspective_team_role": perspective_team_role,
            "possession_team_role_at_start": None,
            "possession_team_role_at_end": None,
            "ball_alive_frame_count": 0,
            "retained_frame_count": 0,
            "claim_boundary": "Observed raw ball-possession team role after reception only; no control quality, tactical quality, intent, or causal claim.",
        }
    ball_state = cached_ball_state(str(raw_tracking), period)
    window = ball_state[(ball_state.frame_id >= start_frame_id) & (ball_state.frame_id <= end_frame_id)].copy()
    if window.empty:
        return {
            "mode": "raw_ball_possession_retention_after_reception",
            "status": "UNKNOWN",
            "reason": "possession_window_missing",
            "start_frame_id": start_frame_id,
            "end_frame_id": start_frame_id,
            "observed_seconds_after_reception": 0.0,
            "required_retention_seconds": required_retention_seconds,
            "perspective_team_role": perspective_team_role,
            "possession_team_role_at_start": None,
            "possession_team_role_at_end": None,
            "ball_alive_frame_count": 0,
            "retained_frame_count": 0,
            "claim_boundary": "Observed raw ball-possession team role after reception only; no control quality, tactical quality, intent, or causal claim.",
        }
    alive = window[window.ball_alive]
    retained = alive[alive.possession_team_role == perspective_team_role]
    actual_end_frame_id = int(window.frame_id.max())
    status = "PASS" if len(alive) > 0 and len(retained) == len(alive) else "FAIL"
    reason = "same_team_ball_alive_possession_retained" if status == "PASS" else "possession_role_changed_or_ball_not_alive"
    return {
        "mode": "raw_ball_possession_retention_after_reception",
        "status": status,
        "reason": reason,
        "start_frame_id": start_frame_id,
        "end_frame_id": actual_end_frame_id,
        "observed_seconds_after_reception": round((actual_end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2),
        "required_retention_seconds": required_retention_seconds,
        "perspective_team_role": perspective_team_role,
        "possession_team_role_at_start": str(window.iloc[0].possession_team_role),
        "possession_team_role_at_end": str(window.iloc[-1].possession_team_role),
        "ball_alive_frame_count": int(len(alive)),
        "retained_frame_count": int(len(retained)),
        "claim_boundary": "Observed raw ball-possession team role after reception only; no control quality, tactical quality, intent, or causal claim.",
    }


def raw_possession_retention_not_evaluated(
    *,
    start_frame_id: int,
    end_frame_id: int,
    perspective_team_role: str,
) -> dict[str, Any]:
    return {
        "mode": "raw_ball_possession_retention_not_used_for_clean_control",
        "status": "UNKNOWN",
        "reason": "provider_possession_not_used_for_product_control_claim",
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "observed_seconds_after_reception": round((end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2),
        "required_retention_seconds": round((end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2),
        "perspective_team_role": perspective_team_role,
        "possession_team_role_at_start": None,
        "possession_team_role_at_end": None,
        "ball_alive_frame_count": 0,
        "retained_frame_count": 0,
        "claim_boundary": (
            "Raw provider possession is not used to back the product control claim; "
            "clean control is evaluated from observed tracking proximity and receiver-ball co-movement."
        ),
    }


def clean_control_retention_sequence(
    *,
    replay: dict[str, Any],
    start_frame_id: int,
    end_frame_id: int,
    perspective_team_role: str,
    defending_team_role: str,
    receiver_id: str,
) -> dict[str, Any]:
    max_team_control_distance_m = 1.8
    max_receiver_control_distance_m = 1.8
    minimum_distance_margin_m = 0.5
    minimum_receiver_control_seconds = 1.0
    minimum_team_control_seconds = 1.0
    maximum_opponent_clean_control_seconds = 0.2
    minimum_receiver_comovement_seconds = 0.6
    maximum_relative_drift_m_per_frame = 0.25
    minimum_moving_alignment_cosine = 0.25
    frames = [
        frame
        for frame in replay.get("frames", [])
        if start_frame_id <= int(frame.get("frame_id", -1)) <= end_frame_id
    ]
    required_seconds = round((end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2)
    if not frames:
        return clean_control_retention_payload(
            status="UNKNOWN",
            reason="control_window_missing",
            start_frame_id=start_frame_id,
            end_frame_id=start_frame_id,
            observed_seconds=0.0,
            required_seconds=required_seconds,
            perspective_team_role=perspective_team_role,
            defending_team_role=defending_team_role,
            receiver_id=receiver_id,
            max_team_control_distance_m=max_team_control_distance_m,
            max_receiver_control_distance_m=max_receiver_control_distance_m,
            minimum_distance_margin_m=minimum_distance_margin_m,
            minimum_receiver_control_seconds=minimum_receiver_control_seconds,
            minimum_team_control_seconds=minimum_team_control_seconds,
            maximum_opponent_clean_control_seconds=maximum_opponent_clean_control_seconds,
            minimum_receiver_comovement_seconds=minimum_receiver_comovement_seconds,
            maximum_relative_drift_m_per_frame=maximum_relative_drift_m_per_frame,
            minimum_moving_alignment_cosine=minimum_moving_alignment_cosine,
        )

    ball_alive_frame_ids: list[int] = []
    provider_loss_frame_ids: list[int] = []
    team_clean_frame_ids: list[int] = []
    receiver_clean_frame_ids: list[int] = []
    receiver_comovement_frame_ids: list[int] = []
    opponent_clean_frame_ids: list[int] = []
    contested_frame_ids: list[int] = []
    missing_state_frame_ids: list[int] = []
    missing_tracking_frame_ids: list[int] = []
    team_clean_player_ids: set[str] = set()
    terminal_team_player_id: str | None = None
    terminal_team_distance_m: float | None = None
    terminal_opponent_distance_m: float | None = None

    for frame in frames:
        frame_id = int(frame["frame_id"])
        ball_state = frame.get("ball_state")
        if isinstance(ball_state, dict) and not bool(ball_state.get("ball_alive", True)):
            continue
        if not isinstance(ball_state, dict):
            missing_state_frame_ids.append(frame_id)
        ball_alive_frame_ids.append(frame_id)
        ball = ball_point_from_frame(frame)
        nearest_team = nearest_player_to_ball_in_frame(frame, perspective_team_role)
        nearest_opponent = nearest_player_to_ball_in_frame(frame, defending_team_role)
        if ball is None or nearest_team is None or nearest_opponent is None:
            missing_tracking_frame_ids.append(frame_id)
            continue

        possession_team_role = ball_state.get("possession_team_role") if isinstance(ball_state, dict) else None
        if possession_team_role is not None and possession_team_role != perspective_team_role:
            provider_loss_frame_ids.append(frame_id)

        team_distance = float(nearest_team["distance_m"])
        opponent_distance = float(nearest_opponent["distance_m"])
        terminal_team_player_id = str(nearest_team["entity_id"])
        terminal_team_distance_m = team_distance
        terminal_opponent_distance_m = opponent_distance

        if (
            team_distance <= max_team_control_distance_m
            and opponent_distance >= team_distance + minimum_distance_margin_m
        ):
            team_clean_frame_ids.append(frame_id)
            team_clean_player_ids.add(str(nearest_team["entity_id"]))

        receiver_distance = entity_distance_to_ball_in_frame(frame, receiver_id)
        if (
            receiver_distance is not None
            and receiver_distance <= max_receiver_control_distance_m
            and opponent_distance >= float(receiver_distance) + minimum_distance_margin_m
        ):
            receiver_clean_frame_ids.append(frame_id)

        if (
            possession_team_role is not None
            and possession_team_role != perspective_team_role
            and opponent_distance <= max_team_control_distance_m
            and team_distance >= opponent_distance + minimum_distance_margin_m
        ):
            opponent_clean_frame_ids.append(frame_id)

        if (
            team_distance <= max_team_control_distance_m + minimum_distance_margin_m
            and opponent_distance <= max_team_control_distance_m + minimum_distance_margin_m
            and abs(team_distance - opponent_distance) < minimum_distance_margin_m
        ):
            contested_frame_ids.append(frame_id)

    frames_by_id = {int(frame["frame_id"]): frame for frame in frames}
    for frame_id in receiver_clean_frame_ids:
        current = frames_by_id.get(frame_id)
        next_frame = frames_by_id.get(frame_id + 1)
        if current is None or next_frame is None:
            continue
        if receiver_ball_comovement_status(
            current,
            next_frame,
            receiver_id=receiver_id,
            maximum_receiver_control_distance_m=max_receiver_control_distance_m,
            maximum_relative_drift_m_per_frame=maximum_relative_drift_m_per_frame,
            minimum_moving_alignment_cosine=minimum_moving_alignment_cosine,
        ):
            receiver_comovement_frame_ids.append(frame_id)

    actual_end_frame_id = int(frames[-1]["frame_id"])
    observed_seconds = round((actual_end_frame_id - start_frame_id) / FRAME_RATE_HZ, 2)
    team_clean_seconds = round(max_contiguous_frame_seconds(team_clean_frame_ids), 2)
    receiver_clean_seconds = round(max_contiguous_frame_seconds(receiver_clean_frame_ids), 2)
    receiver_comovement_seconds = round(max_contiguous_frame_seconds(receiver_comovement_frame_ids), 2)
    opponent_clean_seconds = round(max_contiguous_frame_seconds(opponent_clean_frame_ids), 2)

    if not ball_alive_frame_ids:
        status = "UNKNOWN"
        reason = "no_ball_alive_frames_in_window"
    elif provider_loss_frame_ids:
        status = "FAIL"
        reason = "provider_possession_changed"
    elif receiver_clean_seconds < minimum_receiver_control_seconds:
        status = "FAIL"
        reason = "receiver_clean_control_too_short"
    elif receiver_comovement_seconds < minimum_receiver_comovement_seconds:
        status = "FAIL"
        reason = "receiver_ball_comovement_too_short"
    elif team_clean_seconds < minimum_team_control_seconds:
        status = "FAIL"
        reason = "team_clean_control_too_short"
    elif opponent_clean_seconds > maximum_opponent_clean_control_seconds:
        status = "FAIL"
        reason = "opponent_clean_control_observed"
    else:
        status = "PASS"
        reason = "clean_team_control_observed"

    return clean_control_retention_payload(
        status=status,
        reason=reason,
        start_frame_id=start_frame_id,
        end_frame_id=actual_end_frame_id,
        observed_seconds=observed_seconds,
        required_seconds=required_seconds,
        perspective_team_role=perspective_team_role,
        defending_team_role=defending_team_role,
        receiver_id=receiver_id,
        max_team_control_distance_m=max_team_control_distance_m,
        max_receiver_control_distance_m=max_receiver_control_distance_m,
        minimum_distance_margin_m=minimum_distance_margin_m,
        minimum_receiver_control_seconds=minimum_receiver_control_seconds,
        minimum_team_control_seconds=minimum_team_control_seconds,
        maximum_opponent_clean_control_seconds=maximum_opponent_clean_control_seconds,
        minimum_receiver_comovement_seconds=minimum_receiver_comovement_seconds,
        maximum_relative_drift_m_per_frame=maximum_relative_drift_m_per_frame,
        minimum_moving_alignment_cosine=minimum_moving_alignment_cosine,
        ball_alive_frame_count=len(ball_alive_frame_ids),
        provider_loss_frame_count=len(provider_loss_frame_ids),
        receiver_clean_control_frame_count=len(receiver_clean_frame_ids),
        receiver_clean_control_max_seconds=receiver_clean_seconds,
        receiver_ball_comovement_frame_count=len(receiver_comovement_frame_ids),
        receiver_ball_comovement_max_seconds=receiver_comovement_seconds,
        team_clean_control_frame_count=len(team_clean_frame_ids),
        team_clean_control_max_seconds=team_clean_seconds,
        opponent_clean_control_frame_count=len(opponent_clean_frame_ids),
        opponent_clean_control_max_seconds=opponent_clean_seconds,
        contested_frame_count=len(contested_frame_ids),
        missing_ball_state_frame_count=len(missing_state_frame_ids),
        missing_tracking_frame_count=len(missing_tracking_frame_ids),
        team_clean_control_player_ids=sorted(team_clean_player_ids),
        terminal_team_control_player_id=terminal_team_player_id,
        terminal_team_distance_m=None if terminal_team_distance_m is None else round(terminal_team_distance_m, 2),
        terminal_opponent_distance_m=None
        if terminal_opponent_distance_m is None
        else round(terminal_opponent_distance_m, 2),
        sample_provider_loss_frame_ids=provider_loss_frame_ids[:5],
        sample_contested_frame_ids=contested_frame_ids[:5],
    )


def clean_control_retention_payload(
    *,
    status: str,
    reason: str,
    start_frame_id: int,
    end_frame_id: int,
    observed_seconds: float,
    required_seconds: float,
    perspective_team_role: str,
    defending_team_role: str,
    receiver_id: str,
    max_team_control_distance_m: float,
    max_receiver_control_distance_m: float,
    minimum_distance_margin_m: float,
    minimum_receiver_control_seconds: float,
    minimum_team_control_seconds: float,
    maximum_opponent_clean_control_seconds: float,
    minimum_receiver_comovement_seconds: float,
    maximum_relative_drift_m_per_frame: float,
    minimum_moving_alignment_cosine: float,
    ball_alive_frame_count: int = 0,
    provider_loss_frame_count: int = 0,
    receiver_clean_control_frame_count: int = 0,
    receiver_clean_control_max_seconds: float = 0.0,
    receiver_ball_comovement_frame_count: int = 0,
    receiver_ball_comovement_max_seconds: float = 0.0,
    team_clean_control_frame_count: int = 0,
    team_clean_control_max_seconds: float = 0.0,
    opponent_clean_control_frame_count: int = 0,
    opponent_clean_control_max_seconds: float = 0.0,
    contested_frame_count: int = 0,
    missing_ball_state_frame_count: int = 0,
    missing_tracking_frame_count: int = 0,
    team_clean_control_player_ids: list[str] | None = None,
    terminal_team_control_player_id: str | None = None,
    terminal_team_distance_m: float | None = None,
    terminal_opponent_distance_m: float | None = None,
    sample_provider_loss_frame_ids: list[int] | None = None,
    sample_contested_frame_ids: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "tracking_clean_team_control_after_reception_v0",
        "status": status,
        "reason": reason,
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "observed_seconds_after_reception": observed_seconds,
        "required_retention_seconds": required_seconds,
        "perspective_team_role": perspective_team_role,
        "defending_team_role": defending_team_role,
        "receiver_id": receiver_id,
        "provider_possession_required": False,
        "maximum_team_control_distance_m": max_team_control_distance_m,
        "maximum_receiver_control_distance_m": max_receiver_control_distance_m,
        "minimum_distance_margin_m": minimum_distance_margin_m,
        "minimum_receiver_control_seconds": minimum_receiver_control_seconds,
        "minimum_team_control_seconds": minimum_team_control_seconds,
        "maximum_opponent_clean_control_seconds": maximum_opponent_clean_control_seconds,
        "minimum_receiver_comovement_seconds": minimum_receiver_comovement_seconds,
        "maximum_relative_drift_m_per_frame": maximum_relative_drift_m_per_frame,
        "minimum_moving_alignment_cosine": minimum_moving_alignment_cosine,
        "ball_alive_frame_count": ball_alive_frame_count,
        "provider_loss_frame_count": provider_loss_frame_count,
        "receiver_clean_control_frame_count": receiver_clean_control_frame_count,
        "receiver_clean_control_max_seconds": receiver_clean_control_max_seconds,
        "receiver_ball_comovement_frame_count": receiver_ball_comovement_frame_count,
        "receiver_ball_comovement_max_seconds": receiver_ball_comovement_max_seconds,
        "team_clean_control_frame_count": team_clean_control_frame_count,
        "team_clean_control_max_seconds": team_clean_control_max_seconds,
        "opponent_clean_control_frame_count": opponent_clean_control_frame_count,
        "opponent_clean_control_max_seconds": opponent_clean_control_max_seconds,
        "contested_frame_count": contested_frame_count,
        "missing_ball_state_frame_count": missing_ball_state_frame_count,
        "missing_tracking_frame_count": missing_tracking_frame_count,
        "team_clean_control_player_ids": team_clean_control_player_ids or [],
        "terminal_team_control_player_id": terminal_team_control_player_id,
        "terminal_team_distance_m": terminal_team_distance_m,
        "terminal_opponent_distance_m": terminal_opponent_distance_m,
        "sample_provider_loss_frame_ids": sample_provider_loss_frame_ids or [],
        "sample_contested_frame_ids": sample_contested_frame_ids or [],
        "claim_boundary": (
            "Observed tracking proximity and receiver-ball co-movement after reception only; "
            "no pass quality, individual technique grade, decision value, intent, causation, or tactical optimality claim."
        ),
    }


def max_contiguous_frame_seconds(frame_ids: list[int]) -> float:
    if not frame_ids:
        return 0.0
    best = 0
    current = 0
    previous: int | None = None
    for frame_id in sorted(frame_ids):
        if previous is None or frame_id == previous + 1:
            current += 1
        else:
            best = max(best, current)
            current = 1
        previous = frame_id
    return max(best, current) / FRAME_RATE_HZ


def nearest_player_to_ball_in_frame(frame: dict[str, Any], team_role: str) -> dict[str, Any] | None:
    ball = ball_point_from_frame(frame)
    if ball is None:
        return None
    best: dict[str, Any] | None = None
    for entity in frame.get("entities", []):
        if entity.get("entity_type") != "player" or entity.get("team_role") != team_role:
            continue
        distance = math.hypot(float(entity["x_m"]) - ball["x_m"], float(entity["y_m"]) - ball["y_m"])
        if best is None or distance < float(best["distance_m"]):
            best = {"entity_id": str(entity["entity_id"]), "distance_m": distance}
    return best


def entity_distance_to_ball_in_frame(frame: dict[str, Any], entity_id: str) -> float | None:
    ball = ball_point_from_frame(frame)
    if ball is None:
        return None
    for entity in frame.get("entities", []):
        if str(entity.get("entity_id")) != entity_id:
            continue
        return math.hypot(float(entity["x_m"]) - ball["x_m"], float(entity["y_m"]) - ball["y_m"])
    return None


def receiver_ball_comovement_status(
    current_frame: dict[str, Any],
    next_frame: dict[str, Any],
    *,
    receiver_id: str,
    maximum_receiver_control_distance_m: float,
    maximum_relative_drift_m_per_frame: float,
    minimum_moving_alignment_cosine: float,
) -> bool:
    current_ball = ball_point_from_frame(current_frame)
    next_ball = ball_point_from_frame(next_frame)
    current_receiver = entity_point_from_frame(current_frame, receiver_id)
    next_receiver = entity_point_from_frame(next_frame, receiver_id)
    if current_ball is None or next_ball is None or current_receiver is None or next_receiver is None:
        return False
    current_distance = math.hypot(
        current_ball["x_m"] - current_receiver["x_m"],
        current_ball["y_m"] - current_receiver["y_m"],
    )
    next_distance = math.hypot(
        next_ball["x_m"] - next_receiver["x_m"],
        next_ball["y_m"] - next_receiver["y_m"],
    )
    if current_distance > maximum_receiver_control_distance_m or next_distance > maximum_receiver_control_distance_m:
        return False
    current_offset = (
        current_ball["x_m"] - current_receiver["x_m"],
        current_ball["y_m"] - current_receiver["y_m"],
    )
    next_offset = (
        next_ball["x_m"] - next_receiver["x_m"],
        next_ball["y_m"] - next_receiver["y_m"],
    )
    relative_drift = math.hypot(next_offset[0] - current_offset[0], next_offset[1] - current_offset[1])
    if relative_drift > maximum_relative_drift_m_per_frame:
        return False
    ball_delta = (next_ball["x_m"] - current_ball["x_m"], next_ball["y_m"] - current_ball["y_m"])
    receiver_delta = (
        next_receiver["x_m"] - current_receiver["x_m"],
        next_receiver["y_m"] - current_receiver["y_m"],
    )
    ball_speed = math.hypot(ball_delta[0], ball_delta[1])
    receiver_speed = math.hypot(receiver_delta[0], receiver_delta[1])
    if ball_speed < 0.04 or receiver_speed < 0.04:
        return True
    cosine = (ball_delta[0] * receiver_delta[0] + ball_delta[1] * receiver_delta[1]) / (ball_speed * receiver_speed)
    return cosine >= minimum_moving_alignment_cosine


def entity_point_from_frame(frame: dict[str, Any], entity_id: str) -> dict[str, float] | None:
    for entity in frame.get("entities", []):
        if str(entity.get("entity_id")) == entity_id:
            return {"x_m": float(entity["x_m"]), "y_m": float(entity["y_m"])}
    return None


def line_break_no_support_payload_sort_key(payload: dict[str, Any]) -> tuple[int, int, int]:
    moment = payload["moment"]
    clean_rank = 0 if moment["clean_control_retention"]["status"] == "PASS" else 1
    retention_rank = 0 if moment["possession_retention"]["status"] == "PASS" else 1
    return (clean_rank, retention_rank, int(moment["anchor_frame_id"]))


def ball_point_at_frame(frames: list[dict[str, Any]], frame_id: int) -> dict[str, float] | None:
    frame = next((item for item in frames if int(item["frame_id"]) == frame_id), None)
    return ball_point_from_frame(frame)


def ball_point_from_frame(frame: dict[str, Any] | None) -> dict[str, float] | None:
    if frame is None:
        return None
    for entity in frame["entities"]:
        if entity["entity_type"] == "ball":
            return {"x_m": float(entity["x_m"]), "y_m": float(entity["y_m"])}
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_source_id(path: Path, canonical_root: Path) -> str:
    return str(Path("data/canonical/v1") / path.relative_to(canonical_root))


if __name__ == "__main__":
    main()
