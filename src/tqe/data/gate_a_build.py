"""Build one-match canonical and verification artifacts for M1 Gate A/B."""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree

from tqe.adapters.floodlight_idsse_reader import FloodlightIDSSEReader
from tqe.ports.idsse_reader import IDSSEMatchFiles

DEFAULT_MATCH_ID = "J03WOH"
SOURCE_VERSION = "figshare-28196177-v1"
DEFAULT_RAW_BASE = Path("data/raw/idsse") / SOURCE_VERSION
DEFAULT_RAW_ROOT = DEFAULT_RAW_BASE / DEFAULT_MATCH_ID
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-a")
PERIOD_ORDER = ("firstHalf", "secondHalf")
TEAM_SIDE_TO_FLOODLIGHT = {"home": "Home", "away": "Away"}
FLOODLIGHT_TO_TEAM_SIDE = {"Home": "home", "Away": "away"}
BALL_TEAM_ID = "BALL"
BALL_ENTITY_ID = "DFL-OBJ-0000XT"


@dataclass(frozen=True)
class TeamMeta:
    team_id: str
    team_name: str
    role: str
    floodlight_key: str


@dataclass(frozen=True)
class PlayerMeta:
    match_id: str
    team_id: str
    team_role: str
    player_id: str
    shirt_number: int | None
    first_name: str | None
    last_name: str | None
    short_name: str | None
    playing_position: str | None
    starting: bool
    is_goalkeeper: bool


@dataclass(frozen=True)
class MatchMeta:
    match_id: str
    competition_id: str | None
    competition_name: str | None
    season: str | None
    match_day: str | None
    match_title: str | None
    kickoff_time_utc: str | None
    result: str | None
    pitch_length_m: float
    pitch_width_m: float
    teams: dict[str, TeamMeta]
    players: list[PlayerMeta]


@dataclass(frozen=True)
class FrameIndex:
    period: str
    frame_ids: list[int]
    timestamps_utc: list[str]


@dataclass(frozen=True)
class RawSample:
    period: str
    team_id: str
    entity_id: str
    entity_type: str
    frame_id: int
    timestamp_utc: str
    x_m: float
    y_m: float

    @property
    def key(self) -> tuple[str, str, str, int]:
        return (self.period, self.team_id, self.entity_id, self.frame_id)


@dataclass
class PositionStats:
    rows: int = 0
    min_x: float = math.inf
    max_x: float = -math.inf
    min_y: float = math.inf
    max_y: float = -math.inf
    outside_pitch_rows: int = 0
    outside_pitch_plus_5m_rows: int = 0
    rows_by_period: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    rows_by_entity_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def update(self, *, period: str, entity_type: str, x: np.ndarray, y: np.ndarray, pitch: MatchMeta) -> None:
        count = int(x.size)
        if count == 0:
            return
        self.rows += count
        self.rows_by_period[period] += count
        self.rows_by_entity_type[entity_type] += count
        self.min_x = min(self.min_x, float(np.min(x)))
        self.max_x = max(self.max_x, float(np.max(x)))
        self.min_y = min(self.min_y, float(np.min(y)))
        self.max_y = max(self.max_y, float(np.max(y)))
        half_length = pitch.pitch_length_m / 2.0
        half_width = pitch.pitch_width_m / 2.0
        outside_pitch = (
            (x < -half_length)
            | (x > half_length)
            | (y < -half_width)
            | (y > half_width)
        )
        outside_tolerant = (
            (x < -(half_length + 5.0))
            | (x > half_length + 5.0)
            | (y < -(half_width + 5.0))
            | (y > half_width + 5.0)
        )
        self.outside_pitch_rows += int(np.count_nonzero(outside_pitch))
        self.outside_pitch_plus_5m_rows += int(np.count_nonzero(outside_tolerant))


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return int(value)
    return int(value) * 1024


def parse_bool(value: str | None) -> bool:
    return str(value).lower() == "true"


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value)


def ensure_clean_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_table(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd")


def write_match_scoped_table(path: Path, match_id: str, rows: list[dict[str, Any]]) -> None:
    existing_rows: list[dict[str, Any]] = []
    if path.exists():
        existing_rows = [
            row for row in pq.ParquetFile(path).read().to_pylist() if row["match_id"] != match_id
        ]
    write_table(path, table_from_rows(existing_rows + rows))


def parse_match_metadata(metadata_xml: Path) -> MatchMeta:
    tree = etree.parse(str(metadata_xml))
    general = tree.find(".//General")
    environment = tree.find(".//Environment")
    if general is None or environment is None:
        raise RuntimeError("metadata.xml is missing General or Environment nodes")

    match_id = str(general.get("MatchId")).replace("DFL-MAT-", "")
    team_nodes = tree.findall(".//Teams/Team")
    teams: dict[str, TeamMeta] = {}
    players: list[PlayerMeta] = []
    for team_node in team_nodes:
        raw_role = str(team_node.get("Role"))
        role = "away" if raw_role == "guest" else raw_role
        floodlight_key = TEAM_SIDE_TO_FLOODLIGHT[role]
        team_id = str(team_node.get("TeamId"))
        team = TeamMeta(
            team_id=team_id,
            team_name=str(team_node.get("TeamName")),
            role=role,
            floodlight_key=floodlight_key,
        )
        teams[role] = team
        for player_node in team_node.findall(".//Player"):
            position = player_node.get("PlayingPosition")
            players.append(
                PlayerMeta(
                    match_id=match_id,
                    team_id=team_id,
                    team_role=role,
                    player_id=str(player_node.get("PersonId")),
                    shirt_number=parse_int(player_node.get("ShirtNumber")),
                    first_name=player_node.get("FirstName"),
                    last_name=player_node.get("LastName"),
                    short_name=player_node.get("Shortname"),
                    playing_position=position,
                    starting=parse_bool(player_node.get("Starting")),
                    is_goalkeeper=position == "TW",
                )
            )

    return MatchMeta(
        match_id=match_id,
        competition_id=general.get("CompetitionId"),
        competition_name=general.get("CompetitionName"),
        season=general.get("Season"),
        match_day=general.get("MatchDay"),
        match_title=general.get("MatchTitle"),
        kickoff_time_utc=general.get("KickoffTime"),
        result=general.get("Result"),
        pitch_length_m=float(environment.get("PitchX")),
        pitch_width_m=float(environment.get("PitchY")),
        teams=teams,
        players=players,
    )


def extract_ball_frame_index(tracking_xml: Path) -> dict[str, FrameIndex]:
    frame_index: dict[str, FrameIndex] = {}
    for _, elem in etree.iterparse(str(tracking_xml), events=("end",), tag="FrameSet"):
        if elem.get("TeamId") != BALL_TEAM_ID:
            elem.clear()
            continue
        period = str(elem.get("GameSection"))
        frame_ids: list[int] = []
        timestamps: list[str] = []
        for frame in elem.iterfind("Frame"):
            frame_ids.append(int(frame.get("N")))
            timestamps.append(str(frame.get("T")))
        frame_index[period] = FrameIndex(period=period, frame_ids=frame_ids, timestamps_utc=timestamps)
        elem.clear()
    missing = set(PERIOD_ORDER) - set(frame_index)
    if missing:
        raise RuntimeError(f"Missing ball frame indexes for periods: {sorted(missing)}")
    return frame_index


def extract_orientation(events_xml: Path, match_meta: MatchMeta) -> list[dict[str, Any]]:
    team_role_by_id = {team.team_id: role for role, team in match_meta.teams.items()}
    rows: list[dict[str, Any]] = []
    seen_periods: set[str] = set()
    for _, event in etree.iterparse(str(events_xml), events=("end",), tag="Event"):
        kickoff = event.find("KickOff")
        if kickoff is None:
            event.clear()
            continue
        period = str(kickoff.get("GameSection"))
        if period not in PERIOD_ORDER or period in seen_periods:
            event.clear()
            continue
        seen_periods.add(period)
        team_left = str(kickoff.get("TeamLeft"))
        team_right = str(kickoff.get("TeamRight"))
        event_id = event.get("EventId")
        for side, team_id, attack_sign in (
            ("left", team_left, 1),
            ("right", team_right, -1),
        ):
            rows.append(
                {
                    "match_id": match_meta.match_id,
                    "period": period,
                    "team_id": team_id,
                    "team_role": team_role_by_id.get(team_id),
                    "start_side": side,
                    "attack_x_sign": attack_sign,
                    "evidence_event_id": event_id,
                    "source": "events.xml KickOff TeamLeft/TeamRight",
                }
            )
        event.clear()
    return rows


def extract_raw_samples(tracking_xml: Path, match_meta: MatchMeta) -> list[RawSample]:
    canonical_team_ids = {team.team_id for team in match_meta.teams.values()}
    wanted_by_period_team: set[tuple[str, str]] = set()
    samples: list[RawSample] = []
    for _, elem in etree.iterparse(str(tracking_xml), events=("end",), tag="FrameSet"):
        period = str(elem.get("GameSection"))
        team_id = str(elem.get("TeamId"))
        if team_id != BALL_TEAM_ID and team_id not in canonical_team_ids:
            elem.clear()
            continue
        entity_id = str(elem.get("PersonId"))
        key = (period, team_id)
        should_sample = team_id == BALL_TEAM_ID or key not in wanted_by_period_team
        if not should_sample:
            elem.clear()
            continue
        frames = elem.findall("Frame")
        if not frames:
            elem.clear()
            continue
        wanted_by_period_team.add(key)
        indexes = sorted({0, len(frames) // 2, len(frames) - 1})
        entity_type = "ball" if team_id == BALL_TEAM_ID else "player"
        for index in indexes:
            frame = frames[index]
            samples.append(
                RawSample(
                    period=period,
                    team_id=team_id,
                    entity_id=entity_id,
                    entity_type=entity_type,
                    frame_id=int(frame.get("N")),
                    timestamp_utc=str(frame.get("T")),
                    x_m=float(frame.get("X")),
                    y_m=float(frame.get("Y")),
                )
            )
        elem.clear()
    return samples


def table_from_rows(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(rows)


def write_match_tables(canonical_root: Path, match_meta: MatchMeta, orientation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches_path = canonical_root / "matches.parquet"
    teams_path = canonical_root / "teams.parquet"
    players_path = canonical_root / "players.parquet"
    orientation_path = canonical_root / "orientation.parquet"

    match_rows = [
        {
            "match_id": match_meta.match_id,
            "competition_id": match_meta.competition_id,
            "competition_name": match_meta.competition_name,
            "season": match_meta.season,
            "match_day": match_meta.match_day,
            "match_title": match_meta.match_title,
            "kickoff_time_utc": match_meta.kickoff_time_utc,
            "result": match_meta.result,
            "pitch_length_m": match_meta.pitch_length_m,
            "pitch_width_m": match_meta.pitch_width_m,
        }
    ]
    team_rows = [
        {
            "match_id": match_meta.match_id,
            "team_id": team.team_id,
            "team_name": team.team_name,
            "team_role": team.role,
            "floodlight_key": team.floodlight_key,
        }
        for team in match_meta.teams.values()
    ]
    player_rows = [player.__dict__ for player in match_meta.players]

    write_match_scoped_table(matches_path, match_meta.match_id, match_rows)
    write_match_scoped_table(teams_path, match_meta.match_id, team_rows)
    write_match_scoped_table(players_path, match_meta.match_id, player_rows)
    write_match_scoped_table(orientation_path, match_meta.match_id, orientation_rows)
    return {
        "matches": {"path": str(matches_path), "rows": len(match_rows)},
        "teams": {"path": str(teams_path), "rows": len(team_rows)},
        "players": {"path": str(players_path), "rows": len(player_rows)},
        "orientation": {"path": str(orientation_path), "rows": len(orientation_rows)},
    }


def write_frame_tables(canonical_root: Path, match_id: str, frame_index: dict[str, FrameIndex]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for period, index in frame_index.items():
        path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
        write_table(
            path,
            pa.table(
                {
                    "match_id": [match_id] * len(index.frame_ids),
                    "period": [period] * len(index.frame_ids),
                    "frame_id": index.frame_ids,
                    "timestamp_utc": index.timestamps_utc,
                    "analysis_rate_hz": [25] * len(index.frame_ids),
                }
            ),
        )
        outputs[f"frames_{period}"] = {"path": str(path), "rows": len(index.frame_ids)}
    return outputs


def position_schema() -> pa.Schema:
    return pa.schema(
        [
            ("match_id", pa.string()),
            ("period", pa.string()),
            ("frame_id", pa.int64()),
            ("timestamp_utc", pa.string()),
            ("team_id", pa.string()),
            ("team_role", pa.string()),
            ("entity_id", pa.string()),
            ("entity_type", pa.string()),
            ("x_m", pa.float64()),
            ("y_m", pa.float64()),
            ("source_parser", pa.string()),
        ]
    )


def build_position_table(
    *,
    match_id: str,
    frame_ids: np.ndarray,
    timestamps: np.ndarray,
    period: str,
    team_id: str,
    team_role: str,
    entity_id: str,
    entity_type: str,
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[pa.Table, np.ndarray, np.ndarray, np.ndarray]:
    mask = ~np.isnan(x) & ~np.isnan(y)
    valid_x = x[mask].astype(float)
    valid_y = y[mask].astype(float)
    valid_frame_ids = frame_ids[mask].astype(np.int64)
    table = pa.table(
        {
            "match_id": [match_id] * int(np.count_nonzero(mask)),
            "period": [period] * int(np.count_nonzero(mask)),
            "frame_id": valid_frame_ids,
            "timestamp_utc": timestamps[mask],
            "team_id": [team_id] * int(np.count_nonzero(mask)),
            "team_role": [team_role] * int(np.count_nonzero(mask)),
            "entity_id": [entity_id] * int(np.count_nonzero(mask)),
            "entity_type": [entity_type] * int(np.count_nonzero(mask)),
            "x_m": valid_x,
            "y_m": valid_y,
            "source_parser": ["floodlight.dfl.read_position_data_xml"] * int(np.count_nonzero(mask)),
        },
        schema=position_schema(),
    )
    return table, valid_frame_ids, valid_x, valid_y


def write_positions(
    *,
    canonical_root: Path,
    match_meta: MatchMeta,
    position_read: Any,
    frame_index: dict[str, FrameIndex],
    raw_samples: list[RawSample],
) -> tuple[dict[str, Any], PositionStats, dict[tuple[str, str, str, int], tuple[float, float]]]:
    sample_keys = {sample.key for sample in raw_samples}
    canonical_samples: dict[tuple[str, str, str, int], tuple[float, float]] = {}
    stats = PositionStats()
    outputs: dict[str, Any] = {}
    schema = position_schema()

    for period in PERIOD_ORDER:
        index = frame_index[period]
        frame_ids = np.asarray(index.frame_ids, dtype=np.int64)
        timestamps = np.asarray(index.timestamps_utc, dtype=object)
        frame_row_by_id = {frame_id: row for row, frame_id in enumerate(index.frame_ids)}
        path = canonical_root / "positions" / f"match_id={match_meta.match_id}" / f"period={period}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = pq.ParquetWriter(path, schema, compression="zstd")
        period_rows = 0
        try:
            for floodlight_team_key in ("Home", "Away"):
                team_role = FLOODLIGHT_TO_TEAM_SIDE[floodlight_team_key]
                team = match_meta.teams[team_role]
                xy_obj = position_read.xy[period][floodlight_team_key]
                teamsheet = position_read.teamsheets[floodlight_team_key].teamsheet
                for _, player in teamsheet.iterrows():
                    x_id = int(player["xID"])
                    entity_id = str(player["pID"])
                    x = xy_obj.xy[:, x_id * 2]
                    y = xy_obj.xy[:, x_id * 2 + 1]
                    table, valid_frame_ids, valid_x, valid_y = build_position_table(
                        match_id=match_meta.match_id,
                        frame_ids=frame_ids,
                        timestamps=timestamps,
                        period=period,
                        team_id=team.team_id,
                        team_role=team_role,
                        entity_id=entity_id,
                        entity_type="player",
                        x=x,
                        y=y,
                    )
                    if table.num_rows:
                        writer.write_table(table)
                        period_rows += table.num_rows
                        stats.update(period=period, entity_type="player", x=valid_x, y=valid_y, pitch=match_meta)
                    for key in sample_keys:
                        sample_period, sample_team_id, sample_entity_id, sample_frame_id = key
                        if (
                            sample_period == period
                            and sample_team_id == team.team_id
                            and sample_entity_id == entity_id
                            and sample_frame_id in frame_row_by_id
                        ):
                            row = frame_row_by_id[sample_frame_id]
                            if not (np.isnan(x[row]) or np.isnan(y[row])):
                                canonical_samples[key] = (float(x[row]), float(y[row]))

            ball_xy = position_read.xy[period]["Ball"].xy
            table, valid_frame_ids, valid_x, valid_y = build_position_table(
                match_id=match_meta.match_id,
                frame_ids=frame_ids,
                timestamps=timestamps,
                period=period,
                team_id=BALL_TEAM_ID,
                team_role="ball",
                entity_id=BALL_ENTITY_ID,
                entity_type="ball",
                x=ball_xy[:, 0],
                y=ball_xy[:, 1],
            )
            if table.num_rows:
                writer.write_table(table)
                period_rows += table.num_rows
                stats.update(period=period, entity_type="ball", x=valid_x, y=valid_y, pitch=match_meta)
            for key in sample_keys:
                sample_period, sample_team_id, sample_entity_id, sample_frame_id = key
                if (
                    sample_period == period
                    and sample_team_id == BALL_TEAM_ID
                    and sample_entity_id == BALL_ENTITY_ID
                    and sample_frame_id in frame_row_by_id
                ):
                    row = frame_row_by_id[sample_frame_id]
                    canonical_samples[key] = (float(ball_xy[row, 0]), float(ball_xy[row, 1]))
        finally:
            writer.close()
        outputs[f"positions_{period}"] = {"path": str(path), "rows": period_rows}

    return outputs, stats, canonical_samples


def write_events(canonical_root: Path, match_id: str, event_read: Any) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for period, team_map in event_read.events.items():
        for floodlight_team_key, events in team_map.items():
            frame = events.events
            for row_index, event in frame.iterrows():
                rows.append(
                    {
                        "match_id": match_id,
                        "period": period,
                        "team_role": FLOODLIGHT_TO_TEAM_SIDE[floodlight_team_key],
                        "row_index": int(row_index),
                        "event_type": str(event.get("eID")),
                        "gameclock_seconds": parse_float(event.get("gameclock")),
                        "team_id": event.get("tID"),
                        "player_id": event.get("pID"),
                        "outcome": parse_float(event.get("outcome")),
                        "at_x": parse_float(event.get("at_x")),
                        "at_y": parse_float(event.get("at_y")),
                        "to_x": parse_float(event.get("to_x")),
                        "to_y": parse_float(event.get("to_y")),
                        "timestamp": str(event.get("timestamp")),
                        "minute": parse_float(event.get("minute")),
                        "second": parse_float(event.get("second")),
                        "qualifier_json": json.dumps(event.get("qualifier"), sort_keys=True),
                        "source_parser": "floodlight.dfl.read_event_data_xml",
                    }
                )
    path = canonical_root / "events" / f"match_id={match_id}.parquet"
    write_table(path, table_from_rows(rows))
    return {"events": {"path": str(path), "rows": len(rows)}}


def compare_raw_samples(
    raw_samples: list[RawSample],
    canonical_samples: dict[tuple[str, str, str, int], tuple[float, float]],
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    max_abs_delta = 0.0
    failures = 0
    tolerance = 1e-9
    for sample in raw_samples:
        canonical = canonical_samples.get(sample.key)
        if canonical is None:
            failures += 1
            comparisons.append(
                {
                    **sample.__dict__,
                    "status": "fail",
                    "message": "No canonical position row found for raw sample.",
                }
            )
            continue
        delta_x = abs(sample.x_m - canonical[0])
        delta_y = abs(sample.y_m - canonical[1])
        max_abs_delta = max(max_abs_delta, delta_x, delta_y)
        status = "pass" if delta_x <= tolerance and delta_y <= tolerance else "fail"
        if status != "pass":
            failures += 1
        comparisons.append(
            {
                **sample.__dict__,
                "canonical_x_m": canonical[0],
                "canonical_y_m": canonical[1],
                "delta_x_m": delta_x,
                "delta_y_m": delta_y,
                "status": status,
            }
        )
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass" if failures == 0 else "fail",
        "tolerance_m": tolerance,
        "sample_count": len(raw_samples),
        "failure_count": failures,
        "max_abs_delta_m": max_abs_delta,
        "comparisons": comparisons,
    }


def build_data_quality_report(
    *,
    match_meta: MatchMeta,
    frame_index: dict[str, FrameIndex],
    orientation_rows: list[dict[str, Any]],
    position_stats: PositionStats,
    floodlight_frame_counts: dict[str, dict[str, int]],
    event_rows: int,
) -> dict[str, Any]:
    frame_counts = {period: len(index.frame_ids) for period, index in frame_index.items()}
    orientation_periods = {row["period"] for row in orientation_rows}
    floodlight_frame_count_matches = all(
        team_count == frame_counts[period]
        for period, team_counts in floodlight_frame_counts.items()
        for team_count in team_counts.values()
    )
    checks = [
        {
            "id": "frames.firstHalf.non_empty",
            "status": "pass" if frame_counts.get("firstHalf", 0) > 0 else "fail",
            "value": frame_counts.get("firstHalf", 0),
        },
        {
            "id": "frames.secondHalf.non_empty",
            "status": "pass" if frame_counts.get("secondHalf", 0) > 0 else "fail",
            "value": frame_counts.get("secondHalf", 0),
        },
        {
            "id": "positions.within_pitch_plus_5m",
            "status": "pass" if position_stats.outside_pitch_plus_5m_rows == 0 else "fail",
            "value": position_stats.outside_pitch_plus_5m_rows,
        },
        {
            "id": "orientation.both_halves_from_kickoff",
            "status": "pass" if orientation_periods == set(PERIOD_ORDER) else "fail",
            "value": sorted(orientation_periods),
        },
        {
            "id": "floodlight.frame_counts_match_raw_ball_frames",
            "status": "pass" if floodlight_frame_count_matches else "fail",
            "value": floodlight_frame_counts,
        },
        {
            "id": "events.non_empty",
            "status": "pass" if event_rows > 0 else "fail",
            "value": event_rows,
        },
    ]
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass" if all(check["status"] == "pass" for check in checks) else "fail",
        "match_id": match_meta.match_id,
        "pitch": {
            "length_m": match_meta.pitch_length_m,
            "width_m": match_meta.pitch_width_m,
            "coordinate_contract": "centered_metres",
        },
        "frame_counts": frame_counts,
        "floodlight_frame_counts": floodlight_frame_counts,
        "position_rows": position_stats.rows,
        "position_rows_by_period": dict(position_stats.rows_by_period),
        "position_rows_by_entity_type": dict(position_stats.rows_by_entity_type),
        "coordinate_bounds": {
            "min_x_m": position_stats.min_x,
            "max_x_m": position_stats.max_x,
            "min_y_m": position_stats.min_y,
            "max_y_m": position_stats.max_y,
            "outside_pitch_rows": position_stats.outside_pitch_rows,
            "outside_pitch_plus_5m_rows": position_stats.outside_pitch_plus_5m_rows,
        },
        "orientation": orientation_rows,
        "checks": checks,
    }


def build_resource_report(
    *,
    started_at: float,
    floodlight_position_seconds: float,
    floodlight_event_seconds: float,
    bytes_read: int,
) -> dict[str, Any]:
    elapsed = time.perf_counter() - started_at
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "runtime_seconds": elapsed,
        "floodlight_position_read_seconds": floodlight_position_seconds,
        "floodlight_event_read_seconds": floodlight_event_seconds,
        "max_rss_bytes": max_rss_bytes(),
        "input_bytes": bytes_read,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def build_canonical_summary(
    *,
    match_id: str,
    table_outputs: dict[str, Any],
    raw_samples: list[RawSample],
    raw_parity_report: dict[str, Any],
    data_quality_report: dict[str, Any],
) -> dict[str, Any]:
    status = (
        "pass"
        if raw_parity_report["status"] == "pass" and data_quality_report["status"] == "pass"
        else "fail"
    )
    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": status,
        "match_id": match_id,
        "canonical_version": "v1",
        "source_parser": "floodlight.dfl plus raw XML frame index",
        "tables": table_outputs,
        "raw_parity": {
            "status": raw_parity_report["status"],
            "sample_count": raw_parity_report["sample_count"],
            "max_abs_delta_m": raw_parity_report["max_abs_delta_m"],
        },
        "data_quality": {
            "status": data_quality_report["status"],
            "check_count": len(data_quality_report["checks"]),
        },
        "raw_sample_count": len(raw_samples),
    }


def build_gate_a(
    *,
    match_id: str = DEFAULT_MATCH_ID,
    raw_root: Path | None = None,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    raw_root = raw_root or (DEFAULT_RAW_BASE / match_id)
    files = IDSSEMatchFiles(
        match_id=match_id,
        metadata_xml=raw_root / "metadata.xml",
        events_xml=raw_root / "events.xml",
        tracking_xml=raw_root / "tracking.xml",
    )
    for path in (files.metadata_xml, files.events_xml, files.tracking_xml):
        if not path.exists():
            raise FileNotFoundError(path)

    reader = FloodlightIDSSEReader()
    match_meta = parse_match_metadata(files.metadata_xml)
    if match_meta.match_id != match_id:
        raise RuntimeError(f"Raw metadata match ID {match_meta.match_id} does not match requested {match_id}")
    frame_index = extract_ball_frame_index(files.tracking_xml)
    raw_samples = extract_raw_samples(files.tracking_xml, match_meta)
    orientation_rows = extract_orientation(files.events_xml, match_meta)

    position_start = time.perf_counter()
    position_read = reader.read_positions(files)
    floodlight_position_seconds = time.perf_counter() - position_start
    event_start = time.perf_counter()
    event_read = reader.read_events(files)
    floodlight_event_seconds = time.perf_counter() - event_start
    floodlight_frame_counts = {
        period: {team_key: int(xy.xy.shape[0]) for team_key, xy in team_map.items()}
        for period, team_map in position_read.xy.items()
    }

    table_outputs: dict[str, Any] = {}
    table_outputs.update(write_match_tables(canonical_root, match_meta, orientation_rows))
    table_outputs.update(write_frame_tables(canonical_root, match_meta.match_id, frame_index))
    position_outputs, position_stats, canonical_samples = write_positions(
        canonical_root=canonical_root,
        match_meta=match_meta,
        position_read=position_read,
        frame_index=frame_index,
        raw_samples=raw_samples,
    )
    table_outputs.update(position_outputs)
    event_outputs = write_events(canonical_root, match_meta.match_id, event_read)
    table_outputs.update(event_outputs)

    raw_parity_report = compare_raw_samples(raw_samples, canonical_samples)
    data_quality_report = build_data_quality_report(
        match_meta=match_meta,
        frame_index=frame_index,
        orientation_rows=orientation_rows,
        position_stats=position_stats,
        floodlight_frame_counts=floodlight_frame_counts,
        event_rows=event_outputs["events"]["rows"],
    )
    resource_report = build_resource_report(
        started_at=started_at,
        floodlight_position_seconds=floodlight_position_seconds,
        floodlight_event_seconds=floodlight_event_seconds,
        bytes_read=sum(path.stat().st_size for path in (files.metadata_xml, files.events_xml, files.tracking_xml)),
    )
    canonical_summary = build_canonical_summary(
        table_outputs=table_outputs,
        match_id=match_meta.match_id,
        raw_samples=raw_samples,
        raw_parity_report=raw_parity_report,
        data_quality_report=data_quality_report,
    )

    write_json(artifact_dir / "canonical-summary.json", canonical_summary)
    write_json(artifact_dir / "raw-parity-report.json", raw_parity_report)
    write_json(artifact_dir / "data-quality-report.json", data_quality_report)
    write_json(artifact_dir / "resource-report.json", resource_report)

    return {
        "canonical_summary": canonical_summary,
        "raw_parity_report": raw_parity_report,
        "data_quality_report": data_quality_report,
        "resource_report": resource_report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-id", default=DEFAULT_MATCH_ID)
    parser.add_argument("--raw-root")
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_gate_a(
        match_id=args.match_id,
        raw_root=Path(args.raw_root) if args.raw_root else None,
        canonical_root=Path(args.canonical_root),
        artifact_dir=Path(args.artifact_dir),
    )
    print(
        json.dumps(
            {
                "status": result["canonical_summary"]["status"],
                "tables": result["canonical_summary"]["tables"],
                "raw_parity": result["raw_parity_report"]["status"],
                "data_quality": result["data_quality_report"]["status"],
                "runtime_seconds": result["resource_report"]["runtime_seconds"],
                "max_rss_bytes": result["resource_report"]["max_rss_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["canonical_summary"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
