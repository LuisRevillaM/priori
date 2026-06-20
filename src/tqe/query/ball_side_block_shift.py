"""Deterministic ball-side block-shift detector for M1 Gate C."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml
from lxml import etree
from pydantic import BaseModel, Field

PERIODS = ("firstHalf", "secondHalf")
BALL_ENTITY_ID = "DFL-OBJ-0000XT"
BALL_TEAM_ID = "BALL"
FRAME_RATE_HZ = 25
PITCH_HALF_WIDTH_M = 34.0


class BallSideBlockShiftQueryV1(BaseModel):
    schema_version: str
    query_id: str
    query_version: str
    analysis_rate_hz: int
    minimum_possession_seconds: float
    wide_entry_fraction: float
    prior_central_fraction: float
    minimum_wide_dwell_seconds: float
    baseline_window_seconds: float
    shift_search_window_seconds: float
    minimum_shift_metres: float
    minimum_shift_persistence_seconds: float
    outcome_horizon_seconds: float
    opposite_side_fraction: float
    retained_after_switch_seconds: float
    maximum_analysis_gap_ms: int
    minimum_outfield_players_per_team: int
    ranking_metric: str
    ranking_direction: Literal["ascending", "descending"]
    dedupe_window_seconds: float
    accepted_result_limit: int
    accepted_per_match_limit: int
    near_miss_limit: int
    perspective_team_role: Literal["home", "away"]
    calibration_match_id: str
    evaluation_match_ids: list[str] = Field(min_length=1)

    @property
    def wide_y_threshold_m(self) -> float:
        return self.wide_entry_fraction * PITCH_HALF_WIDTH_M

    @property
    def central_y_threshold_m(self) -> float:
        return self.prior_central_fraction * PITCH_HALF_WIDTH_M

    @property
    def opposite_y_threshold_m(self) -> float:
        return self.opposite_side_fraction * PITCH_HALF_WIDTH_M


@dataclass(frozen=True)
class QueryRuntime:
    config: BallSideBlockShiftQueryV1
    config_path: Path
    query_hash: str
    canonical_config: dict[str, Any]


def load_query_runtime(config_path: Path) -> QueryRuntime:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = BallSideBlockShiftQueryV1.model_validate(raw)
    canonical = config.model_dump(mode="json")
    query_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return QueryRuntime(config=config, config_path=config_path, query_hash=query_hash, canonical_config=canonical)


def parquet_rows(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return pq.ParquetFile(path).read(columns=columns).to_pandas()


def stream_ball_state(raw_tracking_xml: Path, period: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, frame_set in etree.iterparse(str(raw_tracking_xml), events=("end",), tag="FrameSet"):
        if frame_set.get("TeamId") == BALL_TEAM_ID and frame_set.get("GameSection") == period:
            for frame in frame_set.iterfind("Frame"):
                possession_code = int(frame.get("BallPossession"))
                rows.append(
                    {
                        "frame_id": int(frame.get("N")),
                        "timestamp_utc": str(frame.get("T")),
                        "possession_team_role": "home" if possession_code == 1 else "away",
                        "ball_alive": int(frame.get("BallStatus")) == 1,
                    }
                )
            frame_set.clear()
            break
        frame_set.clear()
    if not rows:
        raise RuntimeError(f"No ball tracking state found for {raw_tracking_xml} {period}")
    return pd.DataFrame(rows)


def load_orientation(canonical_root: Path, match_id: str, period: str, team_role: str) -> int:
    rows = parquet_rows(canonical_root / "orientation.parquet")
    selected = rows[
        (rows.match_id == match_id) & (rows.period == period) & (rows.team_role == team_role)
    ]
    if selected.empty:
        raise RuntimeError(f"Missing orientation for {match_id} {period} {team_role}")
    return int(selected.iloc[0].attack_x_sign)


def outfield_player_ids(canonical_root: Path, match_id: str, team_role: str) -> set[str]:
    players = parquet_rows(canonical_root / "players.parquet")
    selected = players[
        (players.match_id == match_id) & (players.team_role == team_role) & (~players.is_goalkeeper)
    ]
    return set(selected.player_id.astype(str))


def team_id(canonical_root: Path, match_id: str, team_role: str) -> str:
    teams = parquet_rows(canonical_root / "teams.parquet")
    selected = teams[(teams.match_id == match_id) & (teams.team_role == team_role)]
    if selected.empty:
        raise RuntimeError(f"Missing team {match_id} {team_role}")
    return str(selected.iloc[0].team_id)


def segment_true(mask: np.ndarray, minimum_frames: int) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for idx, ok in enumerate(mask):
        if ok and start is None:
            start = idx
        if (not ok or idx == len(mask) - 1) and start is not None:
            end = idx - 1 if not ok else idx
            if end - start + 1 >= minimum_frames:
                segments.append((start, end))
            start = None
    return segments


def has_persistent_shift(values: pd.Series, threshold: float, persistence_frames: int) -> bool:
    if len(values) < persistence_frames:
        return False
    return bool((values >= threshold).rolling(persistence_frames).sum().max() >= persistence_frames)


def classify_outcome(
    *,
    signed_ball_y: np.ndarray,
    possession_role: np.ndarray,
    ball_alive: np.ndarray,
    side_sign: int,
    config: BallSideBlockShiftQueryV1,
) -> tuple[str, int | None]:
    horizon_frames = int(round(config.outcome_horizon_seconds * config.analysis_rate_hz))
    retain_frames = int(round(config.retained_after_switch_seconds * config.analysis_rate_hz))
    y = signed_ball_y[:horizon_frames]
    possession = possession_role[:horizon_frames]
    alive = ball_alive[:horizon_frames]

    opposite = np.where(side_sign * y <= -config.opposite_y_threshold_m)[0]
    loss = np.where((possession != config.perspective_team_role) & alive)[0]
    dead = np.where(~alive)[0]

    first_dead = int(dead[0]) if len(dead) else None
    first_loss = int(loss[0]) if len(loss) else None
    first_switch = int(opposite[0]) if len(opposite) else None

    if first_dead is not None and (
        first_switch is None or first_dead < first_switch
    ) and (first_loss is None or first_dead < first_loss):
        return "STOPPAGE", first_dead

    if first_switch is not None:
        end = min(len(possession), first_switch + retain_frames)
        retained = end - first_switch >= retain_frames and np.all(
            (possession[first_switch:end] == config.perspective_team_role) & alive[first_switch:end]
        )
        if retained:
            return "SWITCHED", first_switch
        if first_loss is not None:
            return "LOST_BEFORE_SWITCH", first_loss

    if first_loss is not None:
        return "LOST_BEFORE_SWITCH", first_loss
    return "RETAINED_NO_SWITCH", len(y) - 1 if len(y) else None


def detect_match(
    *,
    runtime: QueryRuntime,
    match_id: str,
    canonical_root: Path,
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = runtime.config
    accepted: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    defending_role = "away" if config.perspective_team_role == "home" else "home"
    defending_outfield = outfield_player_ids(canonical_root, match_id, defending_role)
    perspective_team_id = team_id(canonical_root, match_id, config.perspective_team_role)
    defending_team_id = team_id(canonical_root, match_id, defending_role)
    raw_tracking = raw_root / match_id / "tracking.xml"

    for period in PERIODS:
        positions_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
        pos = parquet_rows(
            positions_path,
            ["frame_id", "team_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
        )
        ball = (
            pos[pos.entity_type == "ball"][["frame_id", "x_m", "y_m"]]
            .sort_values("frame_id")
            .reset_index(drop=True)
        )
        state = stream_ball_state(raw_tracking, period)
        full_frame = ball.merge(state, on="frame_id").sort_values("frame_id").reset_index(drop=True)
        if FRAME_RATE_HZ % config.analysis_rate_hz != 0:
            raise RuntimeError(
                f"analysis_rate_hz={config.analysis_rate_hz} must divide source {FRAME_RATE_HZ} Hz"
            )
        analysis_step = FRAME_RATE_HZ // config.analysis_rate_hz
        frame = full_frame.iloc[::analysis_step].reset_index(drop=True)
        load_orientation(canonical_root, match_id, period, config.perspective_team_role)

        defenders = pos[
            (pos.entity_type == "player")
            & (pos.team_role == defending_role)
            & (pos.entity_id.astype(str).isin(defending_outfield))
        ]
        defender_count = defenders.groupby("frame_id").entity_id.nunique()
        defender_centroid_y = defenders.groupby("frame_id").y_m.mean().sort_index()

        frame_ids = frame.frame_id.to_numpy(dtype=np.int64)
        ball_y = frame.y_m.to_numpy(dtype=float)
        possession = frame.possession_team_role.to_numpy(dtype=object)
        alive = frame.ball_alive.to_numpy(dtype=bool)

        frame_gaps_ms = np.diff(frame_ids) / FRAME_RATE_HZ * 1000.0
        if len(frame_gaps_ms) and float(np.max(frame_gaps_ms)) > config.maximum_analysis_gap_ms:
            raise RuntimeError(
                f"Analysis stream gap exceeds {config.maximum_analysis_gap_ms} ms for "
                f"{match_id} {period}"
            )

        possession_mask = (possession == config.perspective_team_role) & alive
        minimum_possession_frames = int(round(config.minimum_possession_seconds * config.analysis_rate_hz))
        dwell_frames = int(round(config.minimum_wide_dwell_seconds * config.analysis_rate_hz))
        baseline_frames = int(round(config.baseline_window_seconds * config.analysis_rate_hz))
        search_frames = int(round(config.shift_search_window_seconds * config.analysis_rate_hz))
        persistence_frames = int(round(config.minimum_shift_persistence_seconds * config.analysis_rate_hz))
        dedupe_source_frames = int(round(config.dedupe_window_seconds * FRAME_RATE_HZ))

        for segment_start, segment_end in segment_true(possession_mask, minimum_possession_frames):
            segment_slice = slice(segment_start, segment_end + 1)
            seg_frame_ids = frame_ids[segment_slice]
            seg_ball_y = ball_y[segment_slice]
            wide = np.abs(seg_ball_y) > config.wide_y_threshold_m
            last_kept_entry = -10**12

            for i in range(max(baseline_frames, dwell_frames), len(seg_ball_y) - dwell_frames):
                if seg_frame_ids[i] - last_kept_entry < dedupe_source_frames:
                    continue
                if not (wide[i] and not wide[i - 1] and np.all(wide[i : i + dwell_frames])):
                    continue
                prior_start = max(0, i - int(round(2.0 * config.analysis_rate_hz)))
                if not np.any(np.abs(seg_ball_y[prior_start:i]) < config.central_y_threshold_m):
                    continue

                entry_frame_id = int(seg_frame_ids[i])
                side_sign = 1 if seg_ball_y[i] >= 0 else -1
                baseline_start_frame = int(seg_frame_ids[max(0, i - baseline_frames)])
                baseline_end_frame = int(seg_frame_ids[i - 1])
                baseline_series = defender_centroid_y.loc[
                    (defender_centroid_y.index >= baseline_start_frame)
                    & (defender_centroid_y.index <= baseline_end_frame)
                ]
                if baseline_series.empty:
                    continue
                baseline_centroid_y = float(baseline_series.mean())

                search_end = min(len(seg_frame_ids), i + search_frames)
                search_frame_ids = seg_frame_ids[i:search_end]
                search_series = defender_centroid_y.loc[defender_centroid_y.index.isin(search_frame_ids)]
                signed_shift = side_sign * (search_series - baseline_centroid_y)
                if signed_shift.empty:
                    continue
                max_shift = float(signed_shift.max())
                anchor_frame_id = int(signed_shift.idxmax())
                enough_defenders = bool(
                    defender_count.loc[
                        (defender_count.index >= baseline_start_frame)
                        & (defender_count.index <= int(search_frame_ids[-1]))
                    ].min()
                    >= config.minimum_outfield_players_per_team
                )
                persistent = has_persistent_shift(
                    signed_shift,
                    config.minimum_shift_metres,
                    persistence_frames,
                )

                candidate_base = {
                    "query_id": config.query_id,
                    "query_version": config.query_version,
                    "query_hash": runtime.query_hash,
                    "analysis_rate_hz": config.analysis_rate_hz,
                    "match_id": match_id,
                    "period": period,
                    "perspective_team_role": config.perspective_team_role,
                    "perspective_team_id": perspective_team_id,
                    "defending_team_role": defending_role,
                    "defending_team_id": defending_team_id,
                    "possession_start_frame_id": int(seg_frame_ids[0]),
                    "possession_end_frame_id": int(seg_frame_ids[-1]),
                    "possession_duration_seconds": round(
                        float(len(seg_frame_ids) / config.analysis_rate_hz), 3
                    ),
                    "wide_entry_frame_id": entry_frame_id,
                    "wide_entry_y_m": round(float(seg_ball_y[i]), 3),
                    "ball_side": "right" if side_sign > 0 else "left",
                    "baseline_start_frame_id": baseline_start_frame,
                    "baseline_end_frame_id": baseline_end_frame,
                    "baseline_defensive_centroid_y_m": round(baseline_centroid_y, 3),
                    "anchor_frame_id": anchor_frame_id,
                    "signed_shift_metres": round(max_shift, 3),
                    "block_shift_score": round(max_shift, 6),
                    "quality_status": "pass" if enough_defenders else "fail",
                }

                if max_shift < config.minimum_shift_metres or not persistent or not enough_defenders:
                    if max_shift >= config.minimum_shift_metres * 0.70:
                        near_misses.append(
                            {
                                **candidate_base,
                                "near_miss_reason": "below_shift_or_persistence_threshold",
                                "persistent_shift": persistent,
                                "enough_defenders": enough_defenders,
                            }
                        )
                    continue

                try:
                    anchor_idx = int(np.where(seg_frame_ids == anchor_frame_id)[0][0])
                except IndexError:
                    continue
                global_anchor_idx = segment_start + anchor_idx
                outcome, outcome_offset = classify_outcome(
                    signed_ball_y=ball_y[global_anchor_idx:],
                    possession_role=possession[global_anchor_idx:],
                    ball_alive=alive[global_anchor_idx:],
                    side_sign=side_sign,
                    config=config,
                )
                outcome_frame_id = (
                    int(frame_ids[global_anchor_idx + outcome_offset])
                    if outcome_offset is not None and global_anchor_idx + outcome_offset < len(frame_ids)
                    else int(frame_ids[min(len(frame_ids) - 1, global_anchor_idx)])
                )
                result_id = hashlib.sha256(
                    f"{runtime.query_hash}:{match_id}:{period}:{entry_frame_id}:{anchor_frame_id}".encode()
                ).hexdigest()[:16]
                result = {
                    **candidate_base,
                    "result_id": result_id,
                    "classification": outcome,
                    "outcome_frame_id": outcome_frame_id,
                    "accepted": outcome != "STOPPAGE" and candidate_base["quality_status"] == "pass",
                    "replay_start_frame_id": max(int(seg_frame_ids[0]), baseline_start_frame - FRAME_RATE_HZ * 2),
                    "replay_end_frame_id": min(int(frame_ids[-1]), outcome_frame_id + FRAME_RATE_HZ * 2),
                }
                if result["accepted"]:
                    accepted.append(result)
                    last_kept_entry = entry_frame_id
                else:
                    near_misses.append({**result, "near_miss_reason": "excluded_outcome"})

    accepted.sort(key=lambda item: (-float(item["block_shift_score"]), item["match_id"], item["period"], item["wide_entry_frame_id"]))
    near_misses.sort(key=lambda item: (-float(item["signed_shift_metres"]), item["match_id"], item["period"], item["wide_entry_frame_id"]))
    return accepted, near_misses


def select_proof_results(
    candidates: list[dict[str, Any]],
    runtime: QueryRuntime,
) -> list[dict[str, Any]]:
    config = runtime.config
    selected: list[dict[str, Any]] = []
    per_match: dict[str, int] = {}

    def try_add(candidate: dict[str, Any]) -> None:
        if len(selected) >= config.accepted_result_limit:
            return
        match_id = candidate["match_id"]
        if per_match.get(match_id, 0) >= config.accepted_per_match_limit:
            return
        if any(item["result_id"] == candidate["result_id"] for item in selected):
            return
        selected.append({**candidate, "proof_selected": True})
        per_match[match_id] = per_match.get(match_id, 0) + 1

    switched = [item for item in candidates if item["classification"] == "SWITCHED"]
    non_switched = [
        item
        for item in candidates
        if item["classification"] in {"RETAINED_NO_SWITCH", "LOST_BEFORE_SWITCH"}
    ]
    for bucket in (switched[:2], non_switched[:2], candidates):
        for candidate in bucket:
            try_add(candidate)
            if len(selected) >= config.accepted_result_limit:
                break
    selected.sort(key=lambda item: (item["match_id"], item["period"], item["wide_entry_frame_id"]))
    return selected


def selected_near_misses(
    near_misses: list[dict[str, Any]],
    runtime: QueryRuntime,
) -> list[dict[str, Any]]:
    selected = near_misses[: runtime.config.near_miss_limit]
    return [{**item, "proof_selected": True} for item in selected]
