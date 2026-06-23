"""M2A-S0A event/tracking preflight for controlled completed passes.

This module is intentionally read-only with respect to runtime semantics. It
inspects canonical event and tracking data to determine whether M2A can safely
derive controlled pass episodes from real IDSSE/DFL data.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


PASS_EVENT_TYPES = ("Pass",)
DEFAULT_RELEASE_SEARCH_BEFORE_SECONDS = 1.0
DEFAULT_RELEASE_SEARCH_AFTER_SECONDS = 3.0
DEFAULT_RECEPTION_SEARCH_SECONDS = 6.0
DEFAULT_CONTROL_DISTANCE_M = 2.5
DEFAULT_NEAREST_MARGIN_M = 1.0
DEFAULT_DWELL_SECONDS = 0.24
DEFAULT_MIN_COVERAGE_RATIO = 0.98


@dataclass(frozen=True)
class PreflightConfig:
    canonical_root: str
    release_search_before_seconds: float
    release_search_after_seconds: float
    reception_search_seconds: float
    control_distance_m: float
    nearest_margin_m: float
    dwell_seconds: float
    min_coverage_ratio: float


@dataclass
class PassPreflightRecord:
    match_id: str
    period: str
    row_index: int
    event_type: str
    event_timestamp: str
    gameclock_seconds: float | None
    team_role: str
    passer_id: str
    receiver_id: str
    event_frame_id: int | None
    event_frame_offset_ms: float | None
    release_frame_id: int | None
    release_delta_seconds: float | None
    release_ball_distance_m: float | None
    release_control_status: str
    reception_frame_id: int | None
    reception_delta_seconds: float | None
    reception_ball_distance_m: float | None
    reception_control_status: str
    controlled_pass_status: str
    failure_reason: str | None
    inspected_frames: int
    covered_frames: int
    coverage_ratio: float | None


def _safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _percentile(values: list[float], q: float) -> float | None:
    cleaned = sorted(v for v in values if v is not None and math.isfinite(v))
    if not cleaned:
        return None
    idx = min(len(cleaned) - 1, max(0, round((len(cleaned) - 1) * q)))
    return float(cleaned[idx])


def _summary_stats(values: list[float]) -> dict[str, float | None]:
    cleaned = [v for v in values if v is not None and math.isfinite(v)]
    return {
        "count": len(cleaned),
        "min": min(cleaned) if cleaned else None,
        "p50": _percentile(cleaned, 0.50),
        "p90": _percentile(cleaned, 0.90),
        "p95": _percentile(cleaned, 0.95),
        "max": max(cleaned) if cleaned else None,
    }


def _position_at(
    player_index: pd.DataFrame,
    frame_id: int,
    entity_id: str,
) -> tuple[str, tuple[float, float]] | None:
    try:
        row = player_index.loc[(frame_id, entity_id)]
    except KeyError:
        return None
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return str(row["team_role"]), (float(row["x_m"]), float(row["y_m"]))


def _ball_at(ball_by_frame: pd.DataFrame, frame_id: int) -> tuple[float, float] | None:
    try:
        row = ball_by_frame.loc[frame_id]
    except KeyError:
        return None
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return (float(row["x_m"]), float(row["y_m"]))


def _nearest_teammate_allows_control(
    player_index: pd.DataFrame,
    frame_id: int,
    player_id: str,
    team_role: str,
    ball_xy: tuple[float, float],
    player_ball_distance_m: float,
    nearest_margin_m: float,
) -> bool:
    try:
        frame_players = player_index.loc[frame_id]
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
    nearest = float(distances.min())
    return player_ball_distance_m <= nearest + nearest_margin_m


def _candidate_events(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        event_type = str(event.get("event_type") or "")
        if not any(token in event_type for token in PASS_EVENT_TYPES):
            continue
        qualifier = _safe_json(event.get("qualifier_json"))
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
                "event_timestamp": event["timestamp"],
                "gameclock_seconds": (
                    float(event["gameclock_seconds"])
                    if pd.notna(event.get("gameclock_seconds"))
                    else None
                ),
                "team_role": str(event["team_role"]),
                "passer_id": str(passer),
                "receiver_id": str(receiver),
                "_event_ts_utc": pd.to_datetime(event["timestamp"], utc=True, errors="coerce"),
            }
        )
    return pd.DataFrame(rows)


def _align_events_to_frames(events: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    event_rows = events.sort_values("_event_ts_utc").reset_index(drop=True)
    frame_rows = frames[["frame_id", "_frame_ts_utc"]].sort_values("_frame_ts_utc")
    aligned = pd.merge_asof(
        event_rows,
        frame_rows,
        left_on="_event_ts_utc",
        right_on="_frame_ts_utc",
        direction="nearest",
        tolerance=pd.Timedelta(milliseconds=100),
    )
    aligned["event_frame_offset_ms"] = (
        (aligned["_frame_ts_utc"] - aligned["_event_ts_utc"]).dt.total_seconds() * 1000.0
    )
    return aligned


def _find_release(
    *,
    aligned_event: pd.Series,
    frame_ids: list[int],
    frame_index_by_id: dict[int, int],
    player_index: pd.DataFrame,
    ball_by_frame: pd.DataFrame,
    config: PreflightConfig,
    analysis_rate_hz: float,
) -> tuple[int | None, float | None, float | None, str, str | None]:
    event_frame_id = aligned_event.get("frame_id")
    if pd.isna(event_frame_id):
        return None, None, None, "UNKNOWN", "event_timestamp_did_not_align_to_frame"
    event_frame_id = int(event_frame_id)
    event_idx = frame_index_by_id.get(event_frame_id)
    if event_idx is None:
        return None, None, None, "UNKNOWN", "event_frame_missing_from_period"

    before_frames = math.ceil(config.release_search_before_seconds * analysis_rate_hz)
    after_frames = math.ceil(config.release_search_after_seconds * analysis_rate_hz)
    start_idx = max(0, event_idx - before_frames)
    end_idx = min(len(frame_ids) - 1, event_idx + after_frames)
    best: tuple[float, int, float] | None = None
    missing_any = False

    for idx in range(start_idx, end_idx + 1):
        frame_id = frame_ids[idx]
        ball_xy = _ball_at(ball_by_frame, frame_id)
        player = _position_at(player_index, frame_id, str(aligned_event["passer_id"]))
        if ball_xy is None or player is None:
            missing_any = True
            continue
        team_role, player_xy = player
        distance = _distance(ball_xy, player_xy)
        nearest_ok = _nearest_teammate_allows_control(
            player_index,
            frame_id,
            str(aligned_event["passer_id"]),
            team_role,
            ball_xy,
            distance,
            config.nearest_margin_m,
        )
        if distance <= config.control_distance_m and nearest_ok:
            delta = (frame_id - event_frame_id) / analysis_rate_hz
            candidate = (distance, frame_id, delta)
            if best is None or candidate[0] < best[0]:
                best = candidate

    if best is None:
        status = "UNKNOWN" if missing_any else "FAIL"
        reason = "release_tracking_missing" if missing_any else "passer_not_in_control_near_event"
        return None, None, None, status, reason
    distance, frame_id, delta = best
    return frame_id, delta, distance, "PASS", None


def _find_reception(
    *,
    release_frame_id: int | None,
    aligned_event: pd.Series,
    frame_ids: list[int],
    frame_index_by_id: dict[int, int],
    player_index: pd.DataFrame,
    ball_by_frame: pd.DataFrame,
    config: PreflightConfig,
    analysis_rate_hz: float,
) -> tuple[int | None, float | None, float | None, str, str | None, int, int, float | None]:
    if release_frame_id is None:
        return None, None, None, "UNKNOWN", "release_not_proven", 0, 0, None
    release_idx = frame_index_by_id.get(release_frame_id)
    if release_idx is None:
        return None, None, None, "UNKNOWN", "release_frame_missing_from_period", 0, 0, None

    max_frames = math.ceil(config.reception_search_seconds * analysis_rate_hz)
    dwell_frames = max(1, math.ceil(config.dwell_seconds * analysis_rate_hz))
    end_idx = min(len(frame_ids) - 1, release_idx + max_frames)

    run_start_frame_id: int | None = None
    run_start_delta: float | None = None
    run_start_distance: float | None = None
    run_length = 0
    inspected = 0
    covered = 0

    for idx in range(release_idx + 1, end_idx + 1):
        inspected += 1
        frame_id = frame_ids[idx]
        ball_xy = _ball_at(ball_by_frame, frame_id)
        player = _position_at(player_index, frame_id, str(aligned_event["receiver_id"]))
        if ball_xy is None or player is None:
            run_start_frame_id = None
            run_start_delta = None
            run_start_distance = None
            run_length = 0
            continue
        covered += 1
        team_role, player_xy = player
        distance = _distance(ball_xy, player_xy)
        nearest_ok = _nearest_teammate_allows_control(
            player_index,
            frame_id,
            str(aligned_event["receiver_id"]),
            team_role,
            ball_xy,
            distance,
            config.nearest_margin_m,
        )
        controlled = distance <= config.control_distance_m and nearest_ok
        if controlled:
            if run_length == 0:
                run_start_frame_id = frame_id
                run_start_delta = (frame_id - release_frame_id) / analysis_rate_hz
                run_start_distance = distance
            run_length += 1
            if run_length >= dwell_frames:
                return (
                    run_start_frame_id,
                    run_start_delta,
                    run_start_distance,
                    "PASS",
                    None,
                    inspected,
                    covered,
                    covered / inspected if inspected else None,
                )
        else:
            run_start_frame_id = None
            run_start_delta = None
            run_start_distance = None
            run_length = 0

    coverage_ratio = covered / inspected if inspected else None
    if coverage_ratio is None or coverage_ratio < config.min_coverage_ratio:
        return (
            None,
            None,
            None,
            "UNKNOWN",
            "receiver_or_ball_tracking_missing_in_reception_window",
            inspected,
            covered,
            coverage_ratio,
        )
    return (
        None,
        None,
        None,
        "FAIL",
        "receiver_control_not_found_after_release",
        inspected,
        covered,
        coverage_ratio,
    )


def _period_analysis_rate(frames: pd.DataFrame) -> float:
    if "analysis_rate_hz" in frames.columns and frames["analysis_rate_hz"].notna().any():
        return float(frames["analysis_rate_hz"].dropna().iloc[0])
    timestamps = frames["_frame_ts_utc"].sort_values()
    deltas = timestamps.diff().dt.total_seconds().dropna()
    if deltas.empty:
        return 25.0
    median_delta = float(deltas.median())
    return 1.0 / median_delta if median_delta > 0 else 25.0


def run_preflight(
    canonical_root: Path,
    config: PreflightConfig,
    match_ids: set[str] | None = None,
) -> dict[str, Any]:
    event_files = sorted((canonical_root / "events").glob("match_id=*.parquet"))
    if match_ids:
        event_files = [
            path
            for path in event_files
            if path.stem.split("match_id=", 1)[-1] in match_ids
        ]
    records: list[PassPreflightRecord] = []
    period_errors: list[dict[str, str]] = []

    for event_file in event_files:
        events = pd.read_parquet(event_file)
        candidates = _candidate_events(events)
        if candidates.empty:
            continue
        match_id = str(candidates["match_id"].iloc[0])

        for period, period_events in candidates.groupby("period", sort=True):
            frames_path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
            positions_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
            if not frames_path.exists() or not positions_path.exists():
                period_errors.append(
                    {
                        "match_id": match_id,
                        "period": str(period),
                        "error": "missing_frames_or_positions",
                    }
                )
                continue

            frames = pd.read_parquet(frames_path)
            frames["_frame_ts_utc"] = _to_utc(frames["timestamp_utc"])
            frames = frames.sort_values("frame_id").reset_index(drop=True)
            analysis_rate_hz = _period_analysis_rate(frames)
            aligned = _align_events_to_frames(period_events, frames)
            frame_ids = [int(value) for value in frames["frame_id"].tolist()]
            frame_index_by_id = {frame_id: idx for idx, frame_id in enumerate(frame_ids)}

            positions = pd.read_parquet(
                positions_path,
                columns=["frame_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
            )
            ball_by_frame = (
                positions[positions["entity_type"] == "ball"][["frame_id", "x_m", "y_m"]]
                .set_index("frame_id")
                .sort_index()
            )
            player_positions = positions[positions["entity_type"] == "player"][
                ["frame_id", "team_role", "entity_id", "x_m", "y_m"]
            ].copy()
            player_index = player_positions.set_index(["frame_id", "entity_id"]).sort_index()

            for _, aligned_event in aligned.iterrows():
                release_frame_id, release_delta, release_distance, release_status, release_reason = _find_release(
                    aligned_event=aligned_event,
                    frame_ids=frame_ids,
                    frame_index_by_id=frame_index_by_id,
                    player_index=player_index,
                    ball_by_frame=ball_by_frame,
                    config=config,
                    analysis_rate_hz=analysis_rate_hz,
                )
                (
                    reception_frame_id,
                    reception_delta,
                    reception_distance,
                    reception_status,
                    reception_reason,
                    inspected_frames,
                    covered_frames,
                    coverage_ratio,
                ) = _find_reception(
                    release_frame_id=release_frame_id,
                    aligned_event=aligned_event,
                    frame_ids=frame_ids,
                    frame_index_by_id=frame_index_by_id,
                    player_index=player_index,
                    ball_by_frame=ball_by_frame,
                    config=config,
                    analysis_rate_hz=analysis_rate_hz,
                )

                statuses = {release_status, reception_status}
                if statuses == {"PASS"}:
                    controlled_status = "PASS"
                    reason = None
                elif "UNKNOWN" in statuses:
                    controlled_status = "UNKNOWN"
                    reason = release_reason or reception_reason
                else:
                    controlled_status = "FAIL"
                    reason = release_reason or reception_reason

                event_frame_id = aligned_event.get("frame_id")
                event_frame_offset_ms = aligned_event.get("event_frame_offset_ms")
                records.append(
                    PassPreflightRecord(
                        match_id=str(aligned_event["match_id"]),
                        period=str(aligned_event["period"]),
                        row_index=int(aligned_event["row_index"]),
                        event_type=str(aligned_event["event_type"]),
                        event_timestamp=str(aligned_event["event_timestamp"]),
                        gameclock_seconds=(
                            float(aligned_event["gameclock_seconds"])
                            if pd.notna(aligned_event.get("gameclock_seconds"))
                            else None
                        ),
                        team_role=str(aligned_event["team_role"]),
                        passer_id=str(aligned_event["passer_id"]),
                        receiver_id=str(aligned_event["receiver_id"]),
                        event_frame_id=int(event_frame_id) if pd.notna(event_frame_id) else None,
                        event_frame_offset_ms=(
                            float(event_frame_offset_ms)
                            if pd.notna(event_frame_offset_ms)
                            else None
                        ),
                        release_frame_id=release_frame_id,
                        release_delta_seconds=release_delta,
                        release_ball_distance_m=release_distance,
                        release_control_status=release_status,
                        reception_frame_id=reception_frame_id,
                        reception_delta_seconds=reception_delta,
                        reception_ball_distance_m=reception_distance,
                        reception_control_status=reception_status,
                        controlled_pass_status=controlled_status,
                        failure_reason=reason,
                        inspected_frames=inspected_frames,
                        covered_frames=covered_frames,
                        coverage_ratio=coverage_ratio,
                    )
                )

    record_dicts = [asdict(record) for record in records]
    status_counts = pd.Series([record.controlled_pass_status for record in records]).value_counts().to_dict()
    release_counts = pd.Series([record.release_control_status for record in records]).value_counts().to_dict()
    reception_counts = pd.Series([record.reception_control_status for record in records]).value_counts().to_dict()
    reason_counts = (
        pd.Series([record.failure_reason for record in records if record.failure_reason])
        .value_counts()
        .to_dict()
    )

    samples: dict[str, list[dict[str, Any]]] = {}
    for status in ("PASS", "FAIL", "UNKNOWN"):
        samples[status] = [
            record
            for record in record_dicts
            if record["controlled_pass_status"] == status
        ][:10]

    return {
        "schema_version": "m2a.s0a.event_preflight.v1",
        "config": asdict(config),
        "period_errors": period_errors,
        "summary": {
            "candidate_completed_pass_events": len(records),
            "controlled_pass_status_counts": {str(k): int(v) for k, v in status_counts.items()},
            "release_control_status_counts": {str(k): int(v) for k, v in release_counts.items()},
            "reception_control_status_counts": {str(k): int(v) for k, v in reception_counts.items()},
            "failure_reason_counts": {str(k): int(v) for k, v in reason_counts.items()},
            "event_frame_offset_ms": _summary_stats(
                [record.event_frame_offset_ms for record in records if record.event_frame_offset_ms is not None]
            ),
            "release_delta_seconds_from_event": _summary_stats(
                [record.release_delta_seconds for record in records if record.release_delta_seconds is not None]
            ),
            "reception_delta_seconds_from_release": _summary_stats(
                [record.reception_delta_seconds for record in records if record.reception_delta_seconds is not None]
            ),
            "release_ball_distance_m": _summary_stats(
                [record.release_ball_distance_m for record in records if record.release_ball_distance_m is not None]
            ),
            "reception_ball_distance_m": _summary_stats(
                [record.reception_ball_distance_m for record in records if record.reception_ball_distance_m is not None]
            ),
        },
        "samples": samples,
        "records": record_dicts,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    samples = report["samples"]
    lines = [
        "# M2A-S0A Event/Tracking Preflight",
        "",
        "Status: preliminary real-data preflight evidence. This report does not freeze M2A contracts.",
        "",
        "## Key Counts",
        "",
        f"- Candidate completed pass events: {summary['candidate_completed_pass_events']}",
        f"- Controlled pass status: `{summary['controlled_pass_status_counts']}`",
        f"- Release control status: `{summary['release_control_status_counts']}`",
        f"- Reception control status: `{summary['reception_control_status_counts']}`",
        f"- Failure reasons: `{summary['failure_reason_counts']}`",
        "",
        "## Timing And Alignment",
        "",
        f"- Event-to-frame offset ms: `{summary['event_frame_offset_ms']}`",
        f"- Physical release delta from event seconds: `{summary['release_delta_seconds_from_event']}`",
        f"- Controlled reception delta from release seconds: `{summary['reception_delta_seconds_from_release']}`",
        "",
        "## Physical Endpoint Distances",
        "",
        f"- Release ball distance m: `{summary['release_ball_distance_m']}`",
        f"- Reception ball distance m: `{summary['reception_ball_distance_m']}`",
        "",
        "## Initial Interpretation",
        "",
        "- IDSSE event timestamps align tightly to tracking frame timestamps, but they should not be treated as the physical pass release frame.",
        "- The preflight searches for physical release control near the event and controlled receiver possession after release.",
        "- S0C must still integrate active-player denominator proof and pure bypass measurement before runtime implementation begins.",
        "",
    ]
    for status in ("PASS", "FAIL", "UNKNOWN"):
        lines.extend([f"## Sample {status} Records", ""])
        for record in samples[status][:5]:
            lines.append(
                "- "
                f"{record['match_id']} {record['period']} row {record['row_index']} "
                f"{record['passer_id']}->{record['receiver_id']} "
                f"event_frame={record['event_frame_id']} release={record['release_frame_id']} "
                f"reception={record['reception_frame_id']} reason={record['failure_reason']}"
            )
        if not samples[status]:
            lines.append("- none")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", default="data/canonical/v1")
    parser.add_argument("--out-json", default="artifacts/m2a/s0a-event-preflight.json")
    parser.add_argument("--out-csv", default="artifacts/m2a/s0a-event-preflight-records.csv")
    parser.add_argument(
        "--out-md",
        default="delivery/m2a-high-bypass-completed-pass/M2A_S0A_EVENT_PREFLIGHT.md",
    )
    parser.add_argument("--release-before", type=float, default=DEFAULT_RELEASE_SEARCH_BEFORE_SECONDS)
    parser.add_argument("--release-after", type=float, default=DEFAULT_RELEASE_SEARCH_AFTER_SECONDS)
    parser.add_argument("--reception-window", type=float, default=DEFAULT_RECEPTION_SEARCH_SECONDS)
    parser.add_argument("--control-distance", type=float, default=DEFAULT_CONTROL_DISTANCE_M)
    parser.add_argument("--nearest-margin", type=float, default=DEFAULT_NEAREST_MARGIN_M)
    parser.add_argument("--dwell-seconds", type=float, default=DEFAULT_DWELL_SECONDS)
    parser.add_argument("--min-coverage-ratio", type=float, default=DEFAULT_MIN_COVERAGE_RATIO)
    parser.add_argument(
        "--match-id",
        action="append",
        default=[],
        help="Restrict preflight to one match id. May be supplied multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = PreflightConfig(
        canonical_root=args.canonical_root,
        release_search_before_seconds=args.release_before,
        release_search_after_seconds=args.release_after,
        reception_search_seconds=args.reception_window,
        control_distance_m=args.control_distance,
        nearest_margin_m=args.nearest_margin,
        dwell_seconds=args.dwell_seconds,
        min_coverage_ratio=args.min_coverage_ratio,
    )
    match_ids = set(args.match_id) if args.match_id else None
    report = run_preflight(Path(args.canonical_root), config, match_ids=match_ids)

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    pd.DataFrame(report["records"]).to_csv(out_csv, index=False)
    write_markdown(report, out_md)

    summary = report["summary"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
