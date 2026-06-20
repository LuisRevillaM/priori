"""Gate B verification for the M1 seven-match corpus proof."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tqe.data.gate_a_build import BALL_ENTITY_ID, BALL_TEAM_ID, PERIOD_ORDER
from tqe.idsse.source_lock import DATASET_DOI, EXPECTED_MATCH_IDS, FIGSHARE_ARTICLE_ID, hash_file

DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-b")
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def check(status: str, check_id: str, message: str, evidence: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"id": check_id, "status": status, "message": message}
    if evidence is not None:
        result["evidence"] = evidence
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parquet_rows(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows


def parquet_schema_fingerprint(path: Path) -> list[tuple[str, str]]:
    schema = pq.ParquetFile(path).schema_arrow
    return [(field.name, str(field.type)) for field in schema]


def read_parquet_rows(path: Path, columns: list[str] | None = None) -> list[dict[str, Any]]:
    return pq.ParquetFile(path).read(columns=columns).to_pylist()


def validate_source_manifest(artifact_dir: Path) -> list[dict[str, Any]]:
    manifest_path = artifact_dir / "source-manifest.json"
    if not manifest_path.exists():
        return [check("fail", "source_manifest.exists", "Gate B source manifest is missing.", str(manifest_path))]

    checks = [check("pass", "source_manifest.exists", "Gate B source manifest exists.", str(manifest_path))]
    try:
        manifest = load_json(manifest_path)
    except json.JSONDecodeError as exc:
        return checks + [check("fail", "source_manifest.valid_json", f"Invalid JSON: {exc}", str(manifest_path))]

    source = manifest.get("source", {})
    checks.extend(
        [
            check(
                "pass" if manifest.get("scope") == "corpus" else "fail",
                "source_manifest.scope",
                "Source manifest scope is corpus.",
            ),
            check(
                "pass" if source.get("dataset_doi") == DATASET_DOI else "fail",
                "source_manifest.dataset_doi",
                f"Dataset DOI is {DATASET_DOI}.",
            ),
            check(
                "pass" if source.get("article_id") == FIGSHARE_ARTICLE_ID else "fail",
                "source_manifest.article_id",
                f"Figshare article ID is {FIGSHARE_ARTICLE_ID}.",
            ),
            check(
                "pass" if manifest.get("expected_match_ids") == list(EXPECTED_MATCH_IDS) else "fail",
                "source_manifest.expected_match_ids",
                "Manifest records the expected seven match IDs in order.",
            ),
            check(
                "pass" if manifest.get("complete") is True else "fail",
                "source_manifest.complete",
                "All source files are locally locked.",
            ),
        ]
    )

    matches = manifest.get("matches", [])
    by_match = {match.get("match_id"): match for match in matches}
    checks.append(
        check(
            "pass" if set(by_match) == set(EXPECTED_MATCH_IDS) and len(matches) == len(EXPECTED_MATCH_IDS) else "fail",
            "source_manifest.match_set",
            "Manifest includes exactly the seven expected matches.",
        )
    )
    for match_id in EXPECTED_MATCH_IDS:
        match = by_match.get(match_id)
        if not match:
            checks.append(check("fail", f"source_manifest.{match_id}.exists", f"{match_id} missing."))
            continue
        checks.append(
            check(
                "pass" if match.get("complete") is True else "fail",
                f"source_manifest.{match_id}.complete",
                f"{match_id} source manifest is complete.",
            )
        )
        files = match.get("files", [])
        checks.append(
            check(
                "pass" if {file.get("kind") for file in files} == {"metadata", "events", "tracking"} else "fail",
                f"source_manifest.{match_id}.file_set",
                f"{match_id} includes metadata, events, and tracking files.",
            )
        )
        for file_record in files:
            kind = str(file_record.get("kind"))
            local_path = Path(str(file_record.get("local_path", "")))
            if not local_path.exists():
                checks.append(check("fail", f"raw_file.{match_id}.{kind}.exists", "Raw file missing.", str(local_path)))
                continue
            checks.append(check("pass", f"raw_file.{match_id}.{kind}.exists", "Raw file exists.", str(local_path)))
            source_size = int(file_record.get("source_size") or -1)
            checks.append(
                check(
                    "pass" if local_path.stat().st_size == source_size else "fail",
                    f"raw_file.{match_id}.{kind}.size",
                    "Raw file size matches official source size.",
                    str(local_path),
                )
            )
            source_md5 = file_record.get("source_md5")
            if source_md5:
                checks.append(
                    check(
                        "pass" if hash_file(local_path, "md5") == source_md5 else "fail",
                        f"raw_file.{match_id}.{kind}.md5",
                        "Raw file MD5 matches official source checksum.",
                        str(local_path),
                    )
                )
            checks.append(
                check(
                    "pass" if hash_file(local_path, "sha256") == file_record.get("local_sha256") else "fail",
                    f"raw_file.{match_id}.{kind}.sha256",
                    "Raw file SHA-256 matches manifest.",
                    str(local_path),
                )
            )
    return checks


def validate_report_artifacts(artifact_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    checks: list[dict[str, Any]] = []
    corpus_summary: dict[str, Any] | None = None
    required = (
        "corpus-summary.json",
        "raw-parity-report.json",
        "data-quality-report.json",
        "resource-report.json",
    )
    for name in required:
        path = artifact_dir / name
        if not path.exists():
            checks.append(check("fail", f"gate_b_artifact.{name}.exists", f"{name} is missing.", str(path)))
            continue
        checks.append(check("pass", f"gate_b_artifact.{name}.exists", f"{name} exists.", str(path)))
        try:
            payload = load_json(path)
        except json.JSONDecodeError as exc:
            checks.append(check("fail", f"gate_b_artifact.{name}.valid_json", f"Invalid JSON: {exc}", str(path)))
            continue
        checks.append(
            check(
                "pass" if payload.get("status") == "pass" else "fail",
                f"gate_b_artifact.{name}.status",
                f"{name} reports status=pass.",
                str(path),
            )
        )
        if name == "corpus-summary.json":
            corpus_summary = payload

    if corpus_summary is not None:
        checks.append(
            check(
                "pass" if corpus_summary.get("expected_match_ids") == list(EXPECTED_MATCH_IDS) else "fail",
                "corpus_summary.expected_match_ids",
                "Corpus summary records the expected seven match IDs in order.",
            )
        )
        checks.append(
            check(
                "pass" if corpus_summary.get("processing_mode") == "sequential_one_match_at_a_time" else "fail",
                "corpus_summary.processing_mode",
                "Corpus processing mode is sequential one match at a time.",
            )
        )
    return checks, corpus_summary


def summary_rows(corpus_summary: dict[str, Any], match_id: str, table_key: str) -> int:
    for match in corpus_summary.get("matches", []):
        if match.get("match_id") == match_id:
            return int(match["tables"][table_key]["rows"])
    raise KeyError((match_id, table_key))


def validate_canonical_files(canonical_root: Path, corpus_summary: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    frame_schema: list[tuple[str, str]] | None = None
    position_schema: list[tuple[str, str]] | None = None
    event_schema: list[tuple[str, str]] | None = None

    for match_id in EXPECTED_MATCH_IDS:
        for period in PERIOD_ORDER:
            frame_path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
            position_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
            for kind, path in (("frames", frame_path), ("positions", position_path)):
                if not path.exists():
                    checks.append(check("fail", f"canonical.{match_id}.{period}.{kind}.exists", "Canonical file missing.", str(path)))
                    continue
                checks.append(check("pass", f"canonical.{match_id}.{period}.{kind}.exists", "Canonical file exists.", str(path)))

            if frame_path.exists():
                schema = parquet_schema_fingerprint(frame_path)
                if frame_schema is None:
                    frame_schema = schema
                checks.append(
                    check(
                        "pass" if schema == frame_schema else "fail",
                        f"canonical.{match_id}.{period}.frames.schema",
                        "Frame schema matches corpus frame schema.",
                        str(frame_path),
                    )
                )
                rows = parquet_rows(frame_path)
                expected_rows = summary_rows(corpus_summary, match_id, f"frames_{period}")
                checks.append(
                    check(
                        "pass" if rows == expected_rows else "fail",
                        f"canonical.{match_id}.{period}.frames.rows",
                        "Frame row count matches locked canonical summary.",
                        str(frame_path),
                    )
                )
                frame_ids = [row["frame_id"] for row in read_parquet_rows(frame_path, ["frame_id"])]
                checks.append(
                    check(
                        "pass" if len(frame_ids) == len(set(frame_ids)) else "fail",
                        f"canonical.{match_id}.{period}.frames.unique",
                        "No duplicate frame IDs exist for match/period.",
                        str(frame_path),
                    )
                )

            if position_path.exists():
                schema = parquet_schema_fingerprint(position_path)
                if position_schema is None:
                    position_schema = schema
                checks.append(
                    check(
                        "pass" if schema == position_schema else "fail",
                        f"canonical.{match_id}.{period}.positions.schema",
                        "Position schema matches corpus position schema.",
                        str(position_path),
                    )
                )
                rows = parquet_rows(position_path)
                expected_rows = summary_rows(corpus_summary, match_id, f"positions_{period}")
                checks.append(
                    check(
                        "pass" if rows == expected_rows else "fail",
                        f"canonical.{match_id}.{period}.positions.rows",
                        "Position row count matches locked canonical summary.",
                        str(position_path),
                    )
                )

        event_path = canonical_root / "events" / f"match_id={match_id}.parquet"
        if not event_path.exists():
            checks.append(check("fail", f"canonical.{match_id}.events.exists", "Events file missing.", str(event_path)))
        else:
            checks.append(check("pass", f"canonical.{match_id}.events.exists", "Events file exists.", str(event_path)))
            schema = parquet_schema_fingerprint(event_path)
            if event_schema is None:
                event_schema = schema
            checks.append(
                check(
                    "pass" if schema == event_schema else "fail",
                    f"canonical.{match_id}.events.schema",
                    "Event schema matches corpus event schema.",
                    str(event_path),
                )
            )
            rows = parquet_rows(event_path)
            expected_rows = summary_rows(corpus_summary, match_id, "events")
            checks.append(
                check(
                    "pass" if rows == expected_rows else "fail",
                    f"canonical.{match_id}.events.rows",
                    "Event row count matches locked canonical summary.",
                    str(event_path),
                )
            )
    return checks


def validate_aggregate_metadata(canonical_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, set[str]]]]:
    checks: list[dict[str, Any]] = []
    paths = {
        "matches": canonical_root / "matches.parquet",
        "teams": canonical_root / "teams.parquet",
        "players": canonical_root / "players.parquet",
        "orientation": canonical_root / "orientation.parquet",
    }
    for name, path in paths.items():
        checks.append(
            check(
                "pass" if path.exists() else "fail",
                f"canonical.aggregate.{name}.exists",
                f"Aggregate {name} table exists.",
                str(path),
            )
        )
    if not all(path.exists() for path in paths.values()):
        return checks, {}

    matches = read_parquet_rows(paths["matches"])
    teams = read_parquet_rows(paths["teams"])
    players = read_parquet_rows(paths["players"])
    orientation = read_parquet_rows(paths["orientation"])

    checks.extend(
        [
            check(
                "pass" if {row["match_id"] for row in matches} == set(EXPECTED_MATCH_IDS) else "fail",
                "canonical.aggregate.matches.match_set",
                "Aggregate matches table contains exactly the expected match IDs.",
                str(paths["matches"]),
            ),
            check(
                "pass" if len(teams) == len(EXPECTED_MATCH_IDS) * 2 else "fail",
                "canonical.aggregate.teams.rows",
                "Aggregate teams table has two teams per match.",
                str(paths["teams"]),
            ),
            check(
                "pass" if len(orientation) == len(EXPECTED_MATCH_IDS) * 4 else "fail",
                "canonical.aggregate.orientation.rows",
                "Aggregate orientation table has two teams across two halves per match.",
                str(paths["orientation"]),
            ),
            check(
                "pass" if len(players) >= len(EXPECTED_MATCH_IDS) * 30 else "fail",
                "canonical.aggregate.players.rows",
                "Aggregate players table has plausible roster coverage.",
                str(paths["players"]),
            ),
        ]
    )

    for match_id in EXPECTED_MATCH_IDS:
        rows = [row for row in orientation if row["match_id"] == match_id]
        checks.append(
            check(
                "pass"
                if len(rows) == 4
                and {row["period"] for row in rows} == set(PERIOD_ORDER)
                and all(row["team_role"] in {"home", "away"} for row in rows)
                and all(
                    {row["attack_x_sign"] for row in rows if row["period"] == period} == {-1, 1}
                    for period in PERIOD_ORDER
                )
                else "fail",
                f"canonical.aggregate.orientation.{match_id}",
                f"{match_id} orientation has both teams and both halves.",
                str(paths["orientation"]),
            )
        )

    away_by_match = {
        row["match_id"]: row["team_name"]
        for row in teams
        if row["team_role"] == "away"
    }
    checks.append(
        check(
            "pass" if "bayern" in away_by_match.get("J03WMX", "").lower() else "fail",
            "canonical.aggregate.perspective.J03WMX",
            "J03WMX preserves Bayern as away perspective.",
            str(paths["teams"]),
        )
    )
    checks.append(
        check(
            "pass" if "leverkusen" in away_by_match.get("J03WN1", "").lower() else "fail",
            "canonical.aggregate.perspective.J03WN1",
            "J03WN1 preserves Leverkusen as away perspective.",
            str(paths["teams"]),
        )
    )

    players_by_match: dict[str, set[str]] = {match_id: set() for match_id in EXPECTED_MATCH_IDS}
    team_ids_by_match: dict[str, set[str]] = {match_id: set() for match_id in EXPECTED_MATCH_IDS}
    for row in players:
        players_by_match[row["match_id"]].add(row["player_id"])
    for row in teams:
        team_ids_by_match[row["match_id"]].add(row["team_id"])
    return checks, {"players": players_by_match, "teams": team_ids_by_match}


def validate_position_entity_identity(canonical_root: Path, identity_sets: dict[str, dict[str, set[str]]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not identity_sets:
        return checks
    players_by_match = identity_sets["players"]
    team_ids_by_match = identity_sets["teams"]
    for match_id in EXPECTED_MATCH_IDS:
        valid_players = players_by_match[match_id]
        valid_teams = team_ids_by_match[match_id]
        for period in PERIOD_ORDER:
            path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
            if not path.exists():
                continue
            rows = read_parquet_rows(path, ["team_id", "team_role", "entity_id", "entity_type"])
            invalid_count = 0
            for row in rows:
                if row["entity_type"] == "ball":
                    if row["team_id"] != BALL_TEAM_ID or row["team_role"] != "ball" or row["entity_id"] != BALL_ENTITY_ID:
                        invalid_count += 1
                elif row["entity_type"] == "player":
                    if row["team_id"] not in valid_teams or row["entity_id"] not in valid_players:
                        invalid_count += 1
                else:
                    invalid_count += 1
            checks.append(
                check(
                    "pass" if invalid_count == 0 else "fail",
                    f"canonical.{match_id}.{period}.positions.entity_identity",
                    "Position entity IDs map to rostered players or canonical ball identity.",
                    str(path),
                )
            )
    return checks


def validate_quality_reports(artifact_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    report_path = artifact_dir / "data-quality-report.json"
    if not report_path.exists():
        return [check("fail", "data_quality.exists", "Aggregate data quality report is missing.", str(report_path))]
    report = load_json(report_path)
    checks.append(
        check(
            "pass" if report.get("total_outside_pitch_plus_5m_rows") == 0 else "fail",
            "data_quality.coordinate_bounds.pitch_plus_5m",
            "No corpus position observations exceed pitch dimensions plus 5m tolerance.",
            str(report_path),
        )
    )
    for match in report.get("matches", []):
        checks.append(
            check(
                "pass" if match.get("status") == "pass" and match.get("orientation_rows") == 4 else "fail",
                f"data_quality.{match.get('match_id')}.status",
                f"{match.get('match_id')} data quality and orientation checks pass.",
                str(report_path),
            )
        )
    return checks


def build_report(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(validate_source_manifest(artifact_dir))
    report_checks, corpus_summary = validate_report_artifacts(artifact_dir)
    checks.extend(report_checks)
    if corpus_summary is not None:
        checks.extend(validate_canonical_files(canonical_root, corpus_summary))
    metadata_checks, identity_sets = validate_aggregate_metadata(canonical_root)
    checks.extend(metadata_checks)
    checks.extend(validate_position_entity_identity(canonical_root, identity_sets))
    checks.extend(validate_quality_reports(artifact_dir))

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
        "not_ready": sum(1 for item in checks if item["status"] == "not_ready"),
    }
    status = "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail"
    return {
        "schema_version": "1.0",
        "gate": "Gate B - Corpus Proof",
        "generated_at": utc_now_iso(),
        "status": status,
        "artifact_dir": str(artifact_dir),
        "canonical_root": str(canonical_root),
        "summary": summary,
        "checks": checks,
        "next_required": [] if status == "pass" else ["Fix failing corpus invariants before Gate C."],
    }


def write_report(report: dict[str, Any], artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "verification-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    report = build_report(artifact_dir=artifact_dir, canonical_root=Path(args.canonical_root))
    report_path = write_report(report, artifact_dir)
    print(f"Wrote {report_path}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
