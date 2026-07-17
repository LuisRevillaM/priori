"""Adapt the provider-neutral tracking exchange into canonical Parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from tqe.evidence.observation_manifest import (
    ObservationCoverageRow,
    ObservationManifestDocument,
    ObservationModality,
    ObservationWindow,
)
from tqe.ports.canonical_tracking import CanonicalTrackingExchange


EVENT_SCHEMA = pa.schema(
    [
        ("match_id", pa.string()),
        ("period", pa.string()),
        ("team_role", pa.string()),
        ("row_index", pa.int64()),
        ("event_type", pa.string()),
        ("gameclock_seconds", pa.float64()),
        ("team_id", pa.string()),
        ("player_id", pa.string()),
        ("outcome", pa.float64()),
        ("at_x", pa.float64()),
        ("at_y", pa.float64()),
        ("to_x", pa.float64()),
        ("to_y", pa.float64()),
        ("timestamp", pa.string()),
        ("minute", pa.float64()),
        ("second", pa.float64()),
        ("qualifier_json", pa.string()),
        ("source_parser", pa.string()),
    ]
)


def write_table(path: Path, rows: list[dict[str, Any]], schema: pa.Schema | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=schema) if rows else pa.Table.from_pylist([], schema=schema)
    pq.write_table(table, path, compression="zstd")


def adapt_exchange(input_path: Path, canonical_root: Path) -> dict[str, Any]:
    exchange = CanonicalTrackingExchange.model_validate_json(input_path.read_text(encoding="utf-8"))
    canonical_root.mkdir(parents=True, exist_ok=True)
    match_rows: list[dict[str, Any]] = []
    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []
    orientation_rows: list[dict[str, Any]] = []
    summary_matches: list[dict[str, Any]] = []
    observation_rows: list[ObservationCoverageRow] = []

    for match in exchange.matches:
        teams_by_role = {team.team_role: team for team in match.teams}
        entities_by_id = {entity.entity_id: entity for entity in match.entities}
        match_rows.append(
            {
                "match_id": match.match_id,
                "competition_id": None,
                "competition_name": None,
                "season": None,
                "match_day": None,
                "match_title": match.match_id,
                "kickoff_time_utc": match.frames[0].timestamp_utc if match.frames else None,
                "result": None,
                "pitch_length_m": match.pitch_length_m,
                "pitch_width_m": match.pitch_width_m,
            }
        )
        for team in match.teams:
            team_rows.append(
                {
                    "match_id": match.match_id,
                    "team_id": team.team_id,
                    "team_name": team.team_name,
                    "team_role": team.team_role,
                    "floodlight_key": team.team_role.title(),
                }
            )
            orientation_rows.append(
                {
                    "match_id": match.match_id,
                    "period": match.period,
                    "team_id": team.team_id,
                    "team_role": team.team_role,
                    "start_side": "left" if team.team_role == "home" else "right",
                    "attack_x_sign": 1 if team.team_role == "home" else -1,
                    "evidence_event_id": None,
                    "source": "canonical_tracking_exchange declared orientation",
                }
            )
        for entity in match.entities:
            team = teams_by_role[entity.team_role]
            player_rows.append(
                {
                    "match_id": match.match_id,
                    "team_id": team.team_id,
                    "team_role": entity.team_role,
                    "player_id": entity.entity_id,
                    "shirt_number": entity.shirt_number,
                    "first_name": None,
                    "last_name": None,
                    "short_name": entity.entity_id,
                    "playing_position": "GK" if entity.is_goalkeeper else None,
                    "starting": False,
                    "is_goalkeeper": entity.is_goalkeeper,
                }
            )

        frame_rows: list[dict[str, Any]] = []
        frame_state_rows: list[dict[str, Any]] = []
        position_rows: list[dict[str, Any]] = []
        for frame in match.frames:
            reasons_json = json.dumps(sorted(set(frame.position_gate_reasons)), separators=(",", ":"))
            frame_rows.append(
                {
                    "match_id": match.match_id,
                    "period": match.period,
                    "frame_id": frame.frame_id,
                    "timestamp_utc": frame.timestamp_utc,
                    "analysis_rate_hz": match.frame_rate_hz,
                    "position_evidence": frame.position_evidence,
                    "position_gate_reasons_json": reasons_json,
                }
            )
            frame_state_rows.append(
                {
                    "match_id": match.match_id,
                    "period": match.period,
                    "frame_id": frame.frame_id,
                    "possession_team_role": frame.possession_team_role,
                    "ball_alive": frame.ball_alive,
                    "possession_evidence": frame.possession_evidence,
                    "ball_evidence": frame.ball_evidence,
                    "evidence_reasons_json": reasons_json,
                }
            )
            for position in frame.positions:
                entity = entities_by_id[position.entity_id]
                team = teams_by_role[entity.team_role]
                position_rows.append(
                    {
                        "match_id": match.match_id,
                        "period": match.period,
                        "frame_id": frame.frame_id,
                        "timestamp_utc": frame.timestamp_utc,
                        "team_id": team.team_id,
                        "team_role": entity.team_role,
                        "entity_id": entity.entity_id,
                        "entity_type": "player",
                        "x_m": position.x_m,
                        "y_m": position.y_m,
                        "source_parser": exchange.source_adapter,
                        "position_evidence": "KNOWN",
                        "evidence_reasons_json": "[]",
                    }
                )
            if frame.ball_evidence == "KNOWN" and frame.ball_x_m is not None and frame.ball_y_m is not None:
                position_rows.append(
                    {
                        "match_id": match.match_id,
                        "period": match.period,
                        "frame_id": frame.frame_id,
                        "timestamp_utc": frame.timestamp_utc,
                        "team_id": "BALL",
                        "team_role": "ball",
                        "entity_id": "BALL",
                        "entity_type": "ball",
                        "x_m": frame.ball_x_m,
                        "y_m": frame.ball_y_m,
                        "source_parser": exchange.source_adapter,
                        "position_evidence": "KNOWN",
                        "evidence_reasons_json": "[]",
                    }
                )

        base = f"match_id={match.match_id}"
        write_table(canonical_root / "frames" / base / f"period={match.period}.parquet", frame_rows)
        write_table(canonical_root / "frame_state" / base / f"period={match.period}.parquet", frame_state_rows)
        write_table(canonical_root / "positions" / base / f"period={match.period}.parquet", position_rows)
        write_table(canonical_root / "events" / f"match_id={match.match_id}.parquet", [], EVENT_SCHEMA)
        if match.frames:
            window = ObservationWindow(
                start_frame_id=match.frames[0].frame_id,
                end_frame_id=match.frames[-1].frame_id,
            )
            provenance_token = f"{exchange.source_adapter}:{match.match_id}:{match.period}"
            fully_observed_player_tracks = all(
                frame.position_evidence == "KNOWN"
                and len(frame.positions) == len(match.entities)
                for frame in match.frames
            )
            observation_rows.extend(
                [
                    ObservationCoverageRow(
                        row_id=f"{match.match_id}:{match.period}:event",
                        modality=ObservationModality.EVENT,
                        match_id=match.match_id,
                        period=match.period,
                        window=window,
                        status="UNCERTIFIED",
                        reason="vision_adapter_did_not_supply_certified_event_coverage",
                        provenance_token=provenance_token,
                    ),
                    ObservationCoverageRow(
                        row_id=f"{match.match_id}:{match.period}:ball",
                        modality=ObservationModality.BALL,
                        match_id=match.match_id,
                        period=match.period,
                        window=window,
                        status="UNCERTIFIED",
                        reason="vision_adapter_ball_coverage_not_certified",
                        provenance_token=provenance_token,
                    ),
                    ObservationCoverageRow(
                        row_id=f"{match.match_id}:{match.period}:possession",
                        modality=ObservationModality.POSSESSION,
                        match_id=match.match_id,
                        period=match.period,
                        window=window,
                        status="UNCERTIFIED",
                        reason="vision_adapter_possession_coverage_not_certified",
                        provenance_token=provenance_token,
                    ),
                    ObservationCoverageRow(
                        row_id=f"{match.match_id}:{match.period}:player_track",
                        modality=ObservationModality.PLAYER_TRACK,
                        match_id=match.match_id,
                        period=match.period,
                        window=window,
                        status="CERTIFIED" if fully_observed_player_tracks else "UNCERTIFIED",
                        reason=(
                            "every_declared_entity_observed_at_every_frame"
                            if fully_observed_player_tracks
                            else "position_gates_or_missing_entities_prevent_interval_certification"
                        ),
                        provenance_token=provenance_token,
                    ),
                ]
            )
        summary_matches.append(
            {
                "match_id": match.match_id,
                "period": match.period,
                "frames": len(frame_rows),
                "known_position_frames": sum(row["position_evidence"] == "KNOWN" for row in frame_rows),
                "positions": len(position_rows),
            }
        )

    write_table(canonical_root / "matches.parquet", match_rows)
    write_table(canonical_root / "teams.parquet", team_rows)
    write_table(canonical_root / "players.parquet", player_rows)
    write_table(canonical_root / "orientation.parquet", orientation_rows)
    observation_manifest = ObservationManifestDocument(
        schema_version="tqe.observation_manifest.v1",
        manifest_id=f"{exchange.source_adapter}.observation_manifest",
        producer=exchange.source_adapter,
        rows=tuple(observation_rows),
    )
    (canonical_root / "observation-manifest.json").write_text(
        json.dumps(observation_manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "canonical_tracking_adapter_summary.v1",
        "input_schema_version": exchange.schema_version,
        "source_adapter": exchange.source_adapter,
        "observation_manifest_row_count": len(observation_rows),
        "matches": summary_matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("canonical_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(adapt_exchange(args.input, args.canonical_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
