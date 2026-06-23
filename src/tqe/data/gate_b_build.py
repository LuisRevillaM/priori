"""Build M1 Gate B corpus artifacts across all seven IDSSE matches."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.data.gate_a_build import (
    DEFAULT_CANONICAL_ROOT,
    DEFAULT_RAW_BASE,
    MatchMeta,
    build_gate_a,
    extract_orientation,
    parse_match_metadata,
    table_from_rows,
    write_json,
    write_table,
)
from tqe.data.team_branding import team_branding_fields
from tqe.idsse.source_lock import EXPECTED_MATCH_IDS, SOURCE_VERSION

DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-b")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return int(value)
    return int(value) * 1024


def raw_match_root(raw_base: Path, match_id: str) -> Path:
    return raw_base / SOURCE_VERSION / match_id


def metadata_rows(match_meta: MatchMeta) -> dict[str, list[dict[str, Any]]]:
    return {
        "matches": [
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
        ],
        "teams": [
            {
                "match_id": match_meta.match_id,
                "team_id": team.team_id,
                "team_name": team.team_name,
                "team_role": team.role,
                "floodlight_key": team.floodlight_key,
                **team_branding_fields(team.team_id, team.team_name),
            }
            for team in match_meta.teams.values()
        ],
        "players": [player.__dict__ for player in match_meta.players],
    }


def write_corpus_metadata(raw_base: Path, canonical_root: Path) -> dict[str, Any]:
    all_matches: list[dict[str, Any]] = []
    all_teams: list[dict[str, Any]] = []
    all_players: list[dict[str, Any]] = []
    all_orientation: list[dict[str, Any]] = []

    for match_id in EXPECTED_MATCH_IDS:
        root = raw_match_root(raw_base, match_id)
        metadata_xml = root / "metadata.xml"
        events_xml = root / "events.xml"
        match_meta = parse_match_metadata(metadata_xml)
        if match_meta.match_id != match_id:
            raise RuntimeError(f"Metadata mismatch: expected {match_id}, got {match_meta.match_id}")
        rows = metadata_rows(match_meta)
        all_matches.extend(rows["matches"])
        all_teams.extend(rows["teams"])
        all_players.extend(rows["players"])
        all_orientation.extend(extract_orientation(events_xml, match_meta))

    outputs = {
        "matches": {"path": str(canonical_root / "matches.parquet"), "rows": len(all_matches)},
        "teams": {"path": str(canonical_root / "teams.parquet"), "rows": len(all_teams)},
        "players": {"path": str(canonical_root / "players.parquet"), "rows": len(all_players)},
        "orientation": {
            "path": str(canonical_root / "orientation.parquet"),
            "rows": len(all_orientation),
        },
    }
    write_table(canonical_root / "matches.parquet", table_from_rows(all_matches))
    write_table(canonical_root / "teams.parquet", table_from_rows(all_teams))
    write_table(canonical_root / "players.parquet", table_from_rows(all_players))
    write_table(canonical_root / "orientation.parquet", table_from_rows(all_orientation))
    return outputs


def aggregate_reports(match_results: list[dict[str, Any]], started_at: float) -> dict[str, dict[str, Any]]:
    raw_parity_reports = [result["raw_parity_report"] for result in match_results]
    data_quality_reports = [result["data_quality_report"] for result in match_results]
    resource_reports = [result["resource_report"] for result in match_results]
    canonical_summaries = [result["canonical_summary"] for result in match_results]

    raw_parity = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass" if all(report["status"] == "pass" for report in raw_parity_reports) else "fail",
        "match_count": len(raw_parity_reports),
        "sample_count": sum(int(report["sample_count"]) for report in raw_parity_reports),
        "failure_count": sum(int(report["failure_count"]) for report in raw_parity_reports),
        "max_abs_delta_m": max(float(report["max_abs_delta_m"]) for report in raw_parity_reports),
        "matches": [
            {
                "match_id": summary["match_id"],
                "status": report["status"],
                "sample_count": report["sample_count"],
                "failure_count": report["failure_count"],
                "max_abs_delta_m": report["max_abs_delta_m"],
            }
            for summary, report in zip(canonical_summaries, raw_parity_reports, strict=True)
        ],
    }

    data_quality = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass" if all(report["status"] == "pass" for report in data_quality_reports) else "fail",
        "match_count": len(data_quality_reports),
        "total_position_rows": sum(int(report["position_rows"]) for report in data_quality_reports),
        "total_outside_pitch_plus_5m_rows": sum(
            int(report["coordinate_bounds"]["outside_pitch_plus_5m_rows"])
            for report in data_quality_reports
        ),
        "matches": [
            {
                "match_id": report["match_id"],
                "status": report["status"],
                "frame_counts": report["frame_counts"],
                "position_rows": report["position_rows"],
                "coordinate_bounds": report["coordinate_bounds"],
                "orientation_rows": len(report["orientation"]),
            }
            for report in data_quality_reports
        ],
    }

    resource = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "runtime_seconds": time.perf_counter() - started_at,
        "max_rss_bytes": max_rss_bytes(),
        "processing_mode": "sequential_one_match_at_a_time",
        "matches": [
            {
                "match_id": summary["match_id"],
                "runtime_seconds": report["runtime_seconds"],
                "max_rss_bytes": report["max_rss_bytes"],
                "input_bytes": report["input_bytes"],
            }
            for summary, report in zip(canonical_summaries, resource_reports, strict=True)
        ],
    }

    corpus = {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "status": "pass"
        if raw_parity["status"] == "pass" and data_quality["status"] == "pass"
        else "fail",
        "expected_match_ids": list(EXPECTED_MATCH_IDS),
        "match_count": len(canonical_summaries),
        "processing_mode": resource["processing_mode"],
        "matches": [
            {
                "match_id": summary["match_id"],
                "status": summary["status"],
                "tables": summary["tables"],
                "raw_parity": summary["raw_parity"],
                "data_quality": summary["data_quality"],
            }
            for summary in canonical_summaries
        ],
    }

    return {
        "corpus_summary": corpus,
        "raw_parity": raw_parity,
        "data_quality": data_quality,
        "resource": resource,
    }


def build_gate_b(
    *,
    raw_base: Path = DEFAULT_RAW_BASE.parent,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    match_results: list[dict[str, Any]] = []

    for match_id in EXPECTED_MATCH_IDS:
        result = build_gate_a(
            match_id=match_id,
            raw_root=raw_match_root(raw_base, match_id),
            canonical_root=canonical_root,
            artifact_dir=artifact_dir / "matches" / match_id,
        )
        match_results.append(
            {
                "canonical_summary": result["canonical_summary"],
                "raw_parity_report": result["raw_parity_report"],
                "data_quality_report": result["data_quality_report"],
                "resource_report": result["resource_report"],
            }
        )
        gc.collect()

    aggregate_metadata = write_corpus_metadata(raw_base, canonical_root)
    reports = aggregate_reports(match_results, started_at)
    reports["corpus_summary"]["aggregate_metadata"] = aggregate_metadata

    write_json(artifact_dir / "corpus-summary.json", reports["corpus_summary"])
    write_json(artifact_dir / "raw-parity-report.json", reports["raw_parity"])
    write_json(artifact_dir / "data-quality-report.json", reports["data_quality"])
    write_json(artifact_dir / "resource-report.json", reports["resource"])
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-base", default="data/raw/idsse")
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reports = build_gate_b(
        raw_base=Path(args.raw_base),
        canonical_root=Path(args.canonical_root),
        artifact_dir=Path(args.artifact_dir),
    )
    summary = reports["corpus_summary"]
    print(
        json.dumps(
            {
                "status": summary["status"],
                "match_count": summary["match_count"],
                "raw_parity": reports["raw_parity"]["status"],
                "data_quality": reports["data_quality"]["status"],
                "runtime_seconds": reports["resource"]["runtime_seconds"],
                "max_rss_bytes": reports["resource"]["max_rss_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
