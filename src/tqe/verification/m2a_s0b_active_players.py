"""M2A-S0B active-player timeline preflight.

The active-player denominator for M2A is the observed/trusted on-pitch set, not
the registered squad. This verifier derives active intervals from canonical
tracking positions, cross-checks metadata/substitution events, and flags pass
windows whose active set changes between release and reception.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")


@dataclass(frozen=True)
class ActiveTimelineConfig:
    canonical_root: str
    max_missing_gap_frames: int = 1


@dataclass(frozen=True)
class PlayerInterval:
    match_id: str
    period: str
    team_role: str
    player_id: str
    is_goalkeeper: bool | None
    interval_index: int
    active_from_frame_id: int
    active_to_frame_id: int
    observed_frame_count: int


@dataclass(frozen=True)
class ActiveChange:
    match_id: str
    period: str
    team_role: str
    frame_id: int
    change_type: str
    player_id: str


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


def _match_id_from_path(path: Path) -> str:
    return path.name.split("match_id=", 1)[-1]


def _player_metadata(players: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    for _, row in players.iterrows():
        metadata[(str(row["match_id"]), str(row["player_id"]))] = {
            "team_role": str(row["team_role"]),
            "is_goalkeeper": bool(row["is_goalkeeper"]),
            "starting": bool(row["starting"]),
            "team_id": str(row["team_id"]),
        }
    return metadata


def _intervals_for_player(
    *,
    match_id: str,
    period: str,
    team_role: str,
    player_id: str,
    frame_ids: list[int],
    is_goalkeeper: bool | None,
    max_missing_gap_frames: int,
) -> list[PlayerInterval]:
    if not frame_ids:
        return []
    ordered = sorted(set(int(frame_id) for frame_id in frame_ids))
    intervals: list[PlayerInterval] = []
    start = ordered[0]
    prev = ordered[0]
    count = 1
    interval_index = 0
    for frame_id in ordered[1:]:
        if frame_id - prev <= max_missing_gap_frames + 1:
            count += 1
            prev = frame_id
            continue
        intervals.append(
            PlayerInterval(
                match_id=match_id,
                period=period,
                team_role=team_role,
                player_id=player_id,
                is_goalkeeper=is_goalkeeper,
                interval_index=interval_index,
                active_from_frame_id=start,
                active_to_frame_id=prev,
                observed_frame_count=count,
            )
        )
        interval_index += 1
        start = frame_id
        prev = frame_id
        count = 1
    intervals.append(
        PlayerInterval(
            match_id=match_id,
            period=period,
            team_role=team_role,
            player_id=player_id,
            is_goalkeeper=is_goalkeeper,
            interval_index=interval_index,
            active_from_frame_id=start,
            active_to_frame_id=prev,
            observed_frame_count=count,
        )
    )
    return intervals


def build_active_intervals(
    *,
    positions: pd.DataFrame,
    players_by_id: dict[tuple[str, str], dict[str, Any]],
    match_id: str,
    period: str,
    max_missing_gap_frames: int,
) -> list[PlayerInterval]:
    player_positions = positions[positions["entity_type"] == "player"][
        ["frame_id", "team_role", "entity_id"]
    ].copy()
    intervals: list[PlayerInterval] = []
    grouped = player_positions.groupby(["team_role", "entity_id"], sort=True)["frame_id"]
    for (team_role, player_id), frame_series in grouped:
        metadata = players_by_id.get((match_id, str(player_id)))
        intervals.extend(
            _intervals_for_player(
                match_id=match_id,
                period=period,
                team_role=str(team_role),
                player_id=str(player_id),
                frame_ids=[int(item) for item in frame_series.tolist()],
                is_goalkeeper=None if metadata is None else bool(metadata["is_goalkeeper"]),
                max_missing_gap_frames=max_missing_gap_frames,
            )
        )
    return intervals


def active_changes_from_intervals(intervals: list[PlayerInterval]) -> list[ActiveChange]:
    changes: list[ActiveChange] = []
    for interval in intervals:
        changes.append(
            ActiveChange(
                match_id=interval.match_id,
                period=interval.period,
                team_role=interval.team_role,
                frame_id=interval.active_from_frame_id,
                change_type="IN",
                player_id=interval.player_id,
            )
        )
        changes.append(
            ActiveChange(
                match_id=interval.match_id,
                period=interval.period,
                team_role=interval.team_role,
                frame_id=interval.active_to_frame_id + 1,
                change_type="OUT",
                player_id=interval.player_id,
            )
        )
    return changes


def frame_count_deviations(positions: pd.DataFrame) -> dict[str, Any]:
    player_positions = positions[positions["entity_type"] == "player"]
    counts = (
        player_positions.groupby(["frame_id", "team_role"], sort=True)["entity_id"]
        .nunique()
        .reset_index(name="active_player_count")
    )
    deviations = counts[counts["active_player_count"] != 11]
    return {
        "count": int(len(deviations)),
        "samples": deviations.head(100).to_dict("records"),
    }


def active_set_at_frame(intervals: list[PlayerInterval], team_role: str, frame_id: int) -> set[str]:
    return {
        interval.player_id
        for interval in intervals
        if interval.team_role == team_role
        and interval.active_from_frame_id <= frame_id <= interval.active_to_frame_id
    }


def outfield_set_at_frame(intervals: list[PlayerInterval], team_role: str, frame_id: int) -> set[str]:
    return {
        interval.player_id
        for interval in intervals
        if interval.team_role == team_role
        and interval.is_goalkeeper is False
        and interval.active_from_frame_id <= frame_id <= interval.active_to_frame_id
    }


def changes_inside_window(
    changes: list[ActiveChange],
    *,
    start_frame_id: int,
    end_frame_id: int,
) -> list[ActiveChange]:
    return [
        change
        for change in changes
        if start_frame_id < change.frame_id <= end_frame_id
    ]


def substitution_events(events: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    subs = events[events["event_type"].astype(str).str.contains("Substitution", na=False)]
    for _, row in subs.iterrows():
        qualifier = _safe_json(row.get("qualifier_json"))
        rows.append(
            {
                "match_id": str(row["match_id"]),
                "period": str(row["period"]),
                "team_role": str(row["team_role"]),
                "row_index": int(row["row_index"]),
                "event_type": str(row["event_type"]),
                "timestamp": str(row["timestamp"]),
                "gameclock_seconds": (
                    float(row["gameclock_seconds"])
                    if pd.notna(row.get("gameclock_seconds"))
                    else None
                ),
                "player_in": qualifier.get("PlayerIn"),
                "player_out": qualifier.get("PlayerOut"),
            }
        )
    return rows


def align_substitutions_to_frames(
    substitutions: list[dict[str, Any]],
    frames_by_period: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    aligned: list[dict[str, Any]] = []
    for event in substitutions:
        frames = frames_by_period.get(str(event["period"]))
        if frames is None or frames.empty:
            aligned.append({**event, "nearest_frame_id": None, "frame_offset_ms": None})
            continue
        ts = pd.to_datetime(event["timestamp"], utc=True, errors="coerce")
        if pd.isna(ts):
            aligned.append({**event, "nearest_frame_id": None, "frame_offset_ms": None})
            continue
        idx = (frames["_frame_ts_utc"] - ts).abs().idxmin()
        frame = frames.loc[idx]
        aligned.append(
            {
                **event,
                "nearest_frame_id": int(frame["frame_id"]),
                "frame_offset_ms": float((frame["_frame_ts_utc"] - ts).total_seconds() * 1000.0),
            }
        )
    return aligned


def pass_window_analysis(
    *,
    pass_records_path: Path | None,
    intervals_by_key: dict[tuple[str, str], list[PlayerInterval]],
    changes_by_key: dict[tuple[str, str], list[ActiveChange]],
) -> dict[str, Any]:
    if pass_records_path is None or not pass_records_path.exists():
        return {
            "status": "SKIPPED",
            "reason": "pass_records_not_available",
            "window_count": 0,
            "windows_with_active_set_change": 0,
            "samples": [],
        }
    records = pd.read_csv(pass_records_path)
    usable = records[
        records["release_frame_id"].notna()
        & records["reception_frame_id"].notna()
        & (records["controlled_pass_status"] == "PASS")
    ].copy()
    samples: list[dict[str, Any]] = []
    changed_count = 0
    unusable_denominator_count = 0

    for _, row in usable.iterrows():
        match_id = str(row["match_id"])
        period = str(row["period"])
        team_role = str(row["team_role"])
        defending_role = "away" if team_role == "home" else "home"
        release = int(row["release_frame_id"])
        reception = int(row["reception_frame_id"])
        intervals = intervals_by_key.get((match_id, period), [])
        changes = changes_by_key.get((match_id, period), [])
        window_changes = changes_inside_window(changes, start_frame_id=release, end_frame_id=reception)
        release_outfield = outfield_set_at_frame(intervals, defending_role, release)
        reception_outfield = outfield_set_at_frame(intervals, defending_role, reception)
        denominator_usable = bool(release_outfield) and bool(reception_outfield)
        if window_changes:
            changed_count += 1
        if not denominator_usable:
            unusable_denominator_count += 1
        if window_changes or not denominator_usable:
            samples.append(
                {
                    "match_id": match_id,
                    "period": period,
                    "row_index": int(row["row_index"]),
                    "team_role": team_role,
                    "defending_role": defending_role,
                    "release_frame_id": release,
                    "reception_frame_id": reception,
                    "release_defending_outfield_count": len(release_outfield),
                    "reception_defending_outfield_count": len(reception_outfield),
                    "active_changes": [asdict(change) for change in window_changes[:10]],
                }
            )

    return {
        "status": "PASS",
        "pass_records_path": str(pass_records_path),
        "window_count": int(len(usable)),
        "windows_with_active_set_change": int(changed_count),
        "windows_with_unusable_defending_outfield_denominator": int(unusable_denominator_count),
        "samples": samples[:25],
    }


def period_role_aggregates(period_summaries: list[dict[str, Any]]) -> dict[str, dict[str, float | int | None]]:
    if not period_summaries:
        return {}
    frame = pd.DataFrame(period_summaries)
    fields = [
        "unique_tracked_players",
        "active_players_at_period_start",
        "active_players_at_period_end",
        "outfield_at_period_start",
        "outfield_at_period_end",
        "interval_count",
    ]
    aggregates: dict[str, dict[str, float | int | None]] = {}
    for team_role, group in frame.groupby("team_role", sort=True):
        role_values: dict[str, float | int | None] = {}
        for field in fields:
            series = group[field]
            role_values[f"{field}_min"] = int(series.min())
            role_values[f"{field}_max"] = int(series.max())
            role_values[f"{field}_mean"] = float(series.mean())
        aggregates[str(team_role)] = role_values
    return aggregates


def run_preflight(
    *,
    canonical_root: Path,
    config: ActiveTimelineConfig,
    match_ids: set[str] | None,
    pass_records_path: Path | None,
) -> dict[str, Any]:
    players = pd.read_parquet(canonical_root / "players.parquet")
    players_by_id = _player_metadata(players)

    intervals: list[PlayerInterval] = []
    changes: list[ActiveChange] = []
    deviation_count = 0
    deviation_samples: list[dict[str, Any]] = []
    substitution_rows: list[dict[str, Any]] = []
    period_summaries: list[dict[str, Any]] = []
    intervals_by_key: dict[tuple[str, str], list[PlayerInterval]] = {}
    changes_by_key: dict[tuple[str, str], list[ActiveChange]] = {}

    frame_roots = sorted((canonical_root / "positions").glob("match_id=*"))
    for match_root in frame_roots:
        match_id = _match_id_from_path(match_root)
        if match_ids and match_id not in match_ids:
            continue
        event_path = canonical_root / "events" / f"match_id={match_id}.parquet"
        events = pd.read_parquet(event_path) if event_path.exists() else pd.DataFrame()
        match_substitutions = substitution_events(events) if not events.empty else []
        frames_by_period: dict[str, pd.DataFrame] = {}

        for positions_path in sorted(match_root.glob("period=*.parquet")):
            period = positions_path.stem.split("period=", 1)[-1]
            frames_path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
            frames = pd.read_parquet(frames_path)
            frames["_frame_ts_utc"] = pd.to_datetime(frames["timestamp_utc"], utc=True, errors="coerce")
            frames_by_period[period] = frames
            positions = pd.read_parquet(
                positions_path,
                columns=["frame_id", "team_role", "entity_id", "entity_type"],
            )
            period_intervals = build_active_intervals(
                positions=positions,
                players_by_id=players_by_id,
                match_id=match_id,
                period=period,
                max_missing_gap_frames=config.max_missing_gap_frames,
            )
            period_changes = active_changes_from_intervals(period_intervals)
            intervals.extend(period_intervals)
            changes.extend(period_changes)
            intervals_by_key[(match_id, period)] = period_intervals
            changes_by_key[(match_id, period)] = period_changes
            period_deviations = frame_count_deviations(positions)
            deviation_count += int(period_deviations["count"])
            if len(deviation_samples) < 100:
                remaining = 100 - len(deviation_samples)
                deviation_samples.extend(
                    {
                        **item,
                        "match_id": match_id,
                        "period": period,
                    }
                    for item in period_deviations["samples"][:remaining]
                )
            for team_role in ("home", "away"):
                role_intervals = [item for item in period_intervals if item.team_role == team_role]
                first_frame = int(frames["frame_id"].min())
                last_frame = int(frames["frame_id"].max())
                active_start = active_set_at_frame(role_intervals, team_role, first_frame)
                active_end = active_set_at_frame(role_intervals, team_role, last_frame)
                outfield_start = outfield_set_at_frame(role_intervals, team_role, first_frame)
                outfield_end = outfield_set_at_frame(role_intervals, team_role, last_frame)
                unique_players = {item.player_id for item in role_intervals}
                unknown_metadata = [
                    item.player_id
                    for item in role_intervals
                    if item.is_goalkeeper is None
                ]
                period_summaries.append(
                    {
                        "match_id": match_id,
                        "period": period,
                        "team_role": team_role,
                        "unique_tracked_players": len(unique_players),
                        "active_players_at_period_start": len(active_start),
                        "active_players_at_period_end": len(active_end),
                        "outfield_at_period_start": len(outfield_start),
                        "outfield_at_period_end": len(outfield_end),
                        "interval_count": len(role_intervals),
                        "unknown_metadata_player_ids": sorted(set(unknown_metadata)),
                    }
                )

        substitution_rows.extend(align_substitutions_to_frames(match_substitutions, frames_by_period))

    unknown_metadata_ids = sorted(
        {
            interval.player_id
            for interval in intervals
            if interval.is_goalkeeper is None
        }
    )
    pass_windows = pass_window_analysis(
        pass_records_path=pass_records_path,
        intervals_by_key=intervals_by_key,
        changes_by_key=changes_by_key,
    )

    return {
            "schema_version": "m2a.s0b.active_players.v1",
        "config": asdict(config),
            "summary": {
                "tracked_player_interval_count": len(intervals),
                "active_change_count": len(changes),
            "frame_count_deviation_count": deviation_count,
            "frame_count_deviation_sample_count": len(deviation_samples),
            "unknown_metadata_player_ids": unknown_metadata_ids,
            "substitution_event_count_including_duplicates": len(substitution_rows),
            "period_role_count_summary": period_role_aggregates(period_summaries),
        },
        "period_summaries": period_summaries,
        "frame_count_deviations": deviation_samples,
        "substitution_events": substitution_rows,
        "pass_window_analysis": pass_windows,
        "intervals": [asdict(interval) for interval in intervals],
        "changes": [asdict(change) for change in changes],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    pass_windows = report["pass_window_analysis"]
    lines = [
        "# M2A-S0B Active-Player Timeline Preflight",
        "",
        "Status: preliminary active-player denominator evidence. This report does not freeze M2A contracts.",
        "",
        "## Summary",
        "",
        f"- Tracked player intervals: {summary['tracked_player_interval_count']}",
        f"- Active-set change markers: {summary['active_change_count']}",
        f"- Frame/team count deviations from 11 players: {summary['frame_count_deviation_count']}",
        f"- Stored deviation samples: {summary['frame_count_deviation_sample_count']}",
        f"- Unknown tracked-player metadata IDs: `{summary['unknown_metadata_player_ids']}`",
        f"- Substitution event rows, duplicates included: {summary['substitution_event_count_including_duplicates']}",
        "",
        "## Pass Window Impact",
        "",
        f"- Status: `{pass_windows['status']}`",
        f"- Controlled pass windows checked: {pass_windows['window_count']}",
        f"- Windows with active-set change: {pass_windows['windows_with_active_set_change']}",
        f"- Windows with empty/unusable defending outfield denominator: {pass_windows['windows_with_unusable_defending_outfield_denominator']}",
        "",
        "## Policy Implication",
        "",
        "- The expected opposition denominator should be the active defending outfield set at release and reception.",
        "- Full roster counts must not be used as expected evidence.",
        "- A reduced active outfield denominator can be valid after a dismissal; S0C must distinguish dismissals from tracking gaps before freezing accepted match windows.",
        "- If the active set changes inside a pass window, the pass/bypass coverage should become UNKNOWN.",
        "- If goalkeeper metadata is missing, the affected denominator is UNKNOWN.",
        "",
        "## Sample Period Summaries",
        "",
    ]
    for item in report["period_summaries"][:20]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} {item['team_role']}: "
            f"unique={item['unique_tracked_players']} "
            f"start={item['active_players_at_period_start']} "
            f"end={item['active_players_at_period_end']} "
            f"outfield_start={item['outfield_at_period_start']} "
            f"outfield_end={item['outfield_at_period_end']} "
            f"intervals={item['interval_count']}"
        )
    lines.extend(["", "## Active-Set Change Samples", ""])
    for item in report["changes"][:20]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} {item['team_role']} "
            f"frame={item['frame_id']} {item['change_type']} {item['player_id']}"
        )
    if not report["changes"]:
        lines.append("- none")
    lines.extend(["", "## Incomplete Period/Role Samples", ""])
    incomplete = [
        item
        for item in report["period_summaries"]
        if item["active_players_at_period_start"] != 11
        or item["active_players_at_period_end"] != 11
        or item["outfield_at_period_start"] != 10
        or item["outfield_at_period_end"] != 10
    ]
    for item in incomplete[:20]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} {item['team_role']}: "
            f"start={item['active_players_at_period_start']} "
            f"end={item['active_players_at_period_end']} "
            f"outfield_start={item['outfield_at_period_start']} "
            f"outfield_end={item['outfield_at_period_end']}"
        )
    if not incomplete:
        lines.append("- none")
    lines.extend(["", "## Frame Count Deviation Samples", ""])
    for item in report["frame_count_deviations"][:20]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} {item['team_role']} "
            f"frame={item['frame_id']} active_players={item['active_player_count']}"
        )
    if not report["frame_count_deviations"]:
        lines.append("- none")
    lines.extend(["", "## Pass Window Change Samples", ""])
    for item in pass_windows["samples"][:10]:
        lines.append(
            "- "
            f"{item['match_id']} {item['period']} row {item['row_index']} "
            f"{item['team_role']} release={item['release_frame_id']} "
            f"reception={item['reception_frame_id']} "
            f"changes={len(item['active_changes'])}"
        )
    if not pass_windows["samples"]:
        lines.append("- none")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--out-json", default="artifacts/m2a/s0b-active-player-timeline.json")
    parser.add_argument("--out-md", default="delivery/m2a-high-bypass-completed-pass/M2A_S0B_ACTIVE_PLAYERS.md")
    parser.add_argument("--pass-records", default=None)
    parser.add_argument("--match-id", action="append", default=[])
    parser.add_argument("--max-missing-gap-frames", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ActiveTimelineConfig(
        canonical_root=args.canonical_root,
        max_missing_gap_frames=args.max_missing_gap_frames,
    )
    report = run_preflight(
        canonical_root=Path(args.canonical_root),
        config=config,
        match_ids=set(args.match_id) if args.match_id else None,
        pass_records_path=Path(args.pass_records) if args.pass_records else None,
    )
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(report, out_md)
    print(json.dumps({"summary": report["summary"], "pass_window_analysis": report["pass_window_analysis"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
