"""Build Gate C tactical evidence artifacts from the frozen query."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from tqe.idsse.source_lock import DATASET_DOI, FIGSHARE_ARTICLE_ID, SOURCE_VERSION
from tqe.query.ball_side_block_shift import (
    FRAME_RATE_HZ,
    BallSideBlockShiftQueryV1,
    detect_match,
    load_query_runtime,
    selected_near_misses,
    select_proof_results,
)

DEFAULT_CONFIG_PATH = Path("config/queries/ball_side_block_shift.v1.yaml")
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
DEFAULT_RAW_ROOT = Path("data/raw/idsse") / SOURCE_VERSION
DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-c")
DEFAULT_EVIDENCE_ROOT = Path("artifacts/m1/evidence")
DEFAULT_FEATURE_ROOT = Path("data/features/v1/ball_side_block_shift")


@dataclass(frozen=True)
class PeriodTables:
    frames: pd.DataFrame
    positions: pd.DataFrame
    orientation: list[dict[str, Any]]
    frame_path: Path
    position_path: Path
    orientation_path: Path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(item["classification"]) for item in candidates)
    by_match = Counter(str(item["match_id"]) for item in candidates)
    return {
        "count": len(candidates),
        "by_classification": dict(sorted(by_class.items())),
        "by_match": dict(sorted(by_match.items())),
    }


def hard_floor_summary(selected: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = Counter(str(item["classification"]) for item in selected)
    by_match = Counter(str(item["match_id"]) for item in selected)
    max_match_share = max(by_match.values()) / len(selected) if selected else 0.0
    non_switched = by_class.get("RETAINED_NO_SWITCH", 0) + by_class.get("LOST_BEFORE_SWITCH", 0)
    checks = {
        "minimum_accepted_results": len(selected) >= 8,
        "minimum_match_span": len(by_match) >= 3,
        "minimum_switched": by_class.get("SWITCHED", 0) >= 2,
        "minimum_non_switched": non_switched >= 2,
        "maximum_single_match_share": max_match_share <= 0.60,
        "no_quality_fail": all(item.get("quality_status") != "fail" for item in selected),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "selected_count": len(selected),
        "by_classification": dict(sorted(by_class.items())),
        "by_match": dict(sorted(by_match.items())),
        "max_single_match_share": round(max_match_share, 4),
    }


def load_match_metadata(canonical_root: Path) -> dict[str, dict[str, Any]]:
    rows = pq.ParquetFile(canonical_root / "matches.parquet").read().to_pylist()
    return {str(row["match_id"]): row for row in rows}


def load_team_metadata(canonical_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows = pq.ParquetFile(canonical_root / "teams.parquet").read().to_pylist()
    return {(str(row["match_id"]), str(row["team_role"])): row for row in rows}


def load_period_tables(
    *,
    canonical_root: Path,
    match_id: str,
    period: str,
    cache: dict[tuple[str, str], PeriodTables],
) -> PeriodTables:
    key = (match_id, period)
    if key in cache:
        return cache[key]
    frame_path = canonical_root / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
    position_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
    orientation_path = canonical_root / "orientation.parquet"
    orientation = [
        row
        for row in pq.ParquetFile(orientation_path).read().to_pylist()
        if row["match_id"] == match_id and row["period"] == period
    ]
    tables = PeriodTables(
        frames=pq.ParquetFile(frame_path).read().to_pandas(),
        positions=pq.ParquetFile(position_path).read().to_pandas(),
        orientation=orientation,
        frame_path=frame_path,
        position_path=position_path,
        orientation_path=orientation_path,
    )
    cache[key] = tables
    return tables


def replay_from_canonical(
    *,
    result: dict[str, Any],
    tables: PeriodTables,
    match: dict[str, Any],
) -> dict[str, Any]:
    start_frame = int(result["replay_start_frame_id"])
    end_frame = int(result["replay_end_frame_id"])
    frame_rows = tables.frames[
        (tables.frames.frame_id >= start_frame) & (tables.frames.frame_id <= end_frame)
    ].sort_values("frame_id")
    position_rows = tables.positions[
        (tables.positions.frame_id >= start_frame) & (tables.positions.frame_id <= end_frame)
    ].sort_values(["frame_id", "team_role", "entity_type", "entity_id"])

    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for row in position_rows.itertuples(index=False):
        positions_by_frame.setdefault(int(row.frame_id), []).append(
            {
                "team_id": str(row.team_id),
                "team_role": str(row.team_role),
                "entity_id": str(row.entity_id),
                "entity_type": str(row.entity_type),
                "x_m": round(float(row.x_m), 3),
                "y_m": round(float(row.y_m), 3),
            }
        )

    frames = [
        {
            "frame_id": int(row.frame_id),
            "timestamp_utc": str(row.timestamp_utc),
            "entities": positions_by_frame.get(int(row.frame_id), []),
        }
        for row in frame_rows.itertuples(index=False)
    ]

    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "result_id": result["result_id"],
        "match_id": result["match_id"],
        "period": result["period"],
        "frame_rate_hz": FRAME_RATE_HZ,
        "analysis_rate_hz": result["analysis_rate_hz"],
        "start_frame_id": start_frame,
        "end_frame_id": end_frame,
        "pitch": {
            "length_m": float(match["pitch_length_m"]),
            "width_m": float(match["pitch_width_m"]),
            "coordinate_contract": "centered_metres",
        },
        "canonical_sources": {
            "frames": str(tables.frame_path),
            "positions": str(tables.position_path),
            "orientation": str(tables.orientation_path),
            "frames_sha256": sha256_file(tables.frame_path),
            "positions_sha256": sha256_file(tables.position_path),
            "orientation_sha256": sha256_file(tables.orientation_path),
        },
        "orientation": tables.orientation,
        "frames": frames,
    }


def bundle_from_result(
    *,
    result: dict[str, Any],
    replay_path: Path,
    match: dict[str, Any],
    teams: dict[tuple[str, str], dict[str, Any]],
    query_hash: str,
) -> dict[str, Any]:
    match_id = str(result["match_id"])
    return {
        "schema_version": "1.0",
        "bundle_id": result["result_id"],
        "generated_at": utc_now_iso(),
        "status": "pass",
        "result_id": result["result_id"],
        "query": {
            "query_id": result["query_id"],
            "query_version": result["query_version"],
            "query_hash": query_hash,
        },
        "provenance": {
            "source_dataset_doi": DATASET_DOI,
            "figshare_article_id": FIGSHARE_ARTICLE_ID,
            "canonical_source": "data/canonical/v1",
            "raw_source": f"data/raw/idsse/{SOURCE_VERSION}",
        },
        "match": {
            "match_id": match_id,
            "period": result["period"],
            "title": match["match_title"],
            "pitch_length_m": float(match["pitch_length_m"]),
            "pitch_width_m": float(match["pitch_width_m"]),
        },
        "perspective": {
            "attacking_team_role": result["perspective_team_role"],
            "attacking_team_id": result["perspective_team_id"],
            "attacking_team_name": teams[(match_id, result["perspective_team_role"])]["team_name"],
            "defending_team_role": result["defending_team_role"],
            "defending_team_id": result["defending_team_id"],
            "defending_team_name": teams[(match_id, result["defending_team_role"])]["team_name"],
        },
        "window": {
            "frame_rate_hz": FRAME_RATE_HZ,
            "analysis_rate_hz": result["analysis_rate_hz"],
            "replay_start_frame_id": result["replay_start_frame_id"],
            "replay_end_frame_id": result["replay_end_frame_id"],
            "baseline_start_frame_id": result["baseline_start_frame_id"],
            "baseline_end_frame_id": result["baseline_end_frame_id"],
            "wide_entry_frame_id": result["wide_entry_frame_id"],
            "anchor_frame_id": result["anchor_frame_id"],
            "outcome_frame_id": result["outcome_frame_id"],
        },
        "classification": result["classification"],
        "quality": {
            "status": result["quality_status"],
            "block_shift_score": result["block_shift_score"],
        },
        "evidence_payload": {
            "ball_side": result["ball_side"],
            "wide_entry_y_m": result["wide_entry_y_m"],
            "baseline_defensive_centroid_y_m": result["baseline_defensive_centroid_y_m"],
            "signed_shift_metres": result["signed_shift_metres"],
            "possession_start_frame_id": result["possession_start_frame_id"],
            "possession_end_frame_id": result["possession_end_frame_id"],
            "possession_duration_seconds": result["possession_duration_seconds"],
        },
        "replay_reference": {
            "path": str(replay_path),
            "format": "static_json_frames",
        },
    }


def write_feature_tables(
    *,
    feature_root: Path,
    calibration: list[dict[str, Any]],
    evaluation: list[dict[str, Any]],
    near_misses: list[dict[str, Any]],
) -> None:
    feature_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(calibration + evaluation).to_parquet(feature_root / "accepted_candidates.parquet")
    pd.DataFrame(near_misses).to_parquet(feature_root / "near_misses.parquet")


def build_gate_c(
    *,
    config_path: Path,
    canonical_root: Path,
    raw_root: Path,
    artifact_dir: Path,
    evidence_root: Path,
    feature_root: Path,
) -> dict[str, Any]:
    runtime = load_query_runtime(config_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    query_freeze = {
        "schema_version": "1.0",
        "status": "pass",
        "generated_at": utc_now_iso(),
        "query_hash": runtime.query_hash,
        "config_path": str(config_path),
        "canonical_config": runtime.canonical_config,
        "calibration_match_id": runtime.config.calibration_match_id,
        "evaluation_match_ids": runtime.config.evaluation_match_ids,
        "freeze_rule": "Calibration is limited to J03WOH; evaluation uses this unchanged hash.",
    }
    write_json(artifact_dir / "query-freeze.json", query_freeze)
    write_json(artifact_dir / "query-schema.json", BallSideBlockShiftQueryV1.model_json_schema())

    calibration_candidates, calibration_near_misses = detect_match(
        runtime=runtime,
        match_id=runtime.config.calibration_match_id,
        canonical_root=canonical_root,
        raw_root=raw_root,
    )
    calibration_report = {
        "schema_version": "1.0",
        "status": "pass" if calibration_candidates else "fail",
        "generated_at": utc_now_iso(),
        "query_hash": runtime.query_hash,
        "match_id": runtime.config.calibration_match_id,
        "accepted_summary": summarize_candidates(calibration_candidates),
        "near_miss_summary": {"count": len(calibration_near_misses)},
        "threshold_change_after_this_report": "forbidden_without_new_query_version",
    }
    write_json(artifact_dir / "calibration-report.json", calibration_report)

    evaluation_candidates: list[dict[str, Any]] = []
    evaluation_near_misses: list[dict[str, Any]] = []
    per_match: list[dict[str, Any]] = []
    for match_id in runtime.config.evaluation_match_ids:
        accepted, near_misses = detect_match(
            runtime=runtime,
            match_id=match_id,
            canonical_root=canonical_root,
            raw_root=raw_root,
        )
        evaluation_candidates.extend(accepted)
        evaluation_near_misses.extend(near_misses)
        per_match.append(
            {
                "match_id": match_id,
                "accepted_summary": summarize_candidates(accepted),
                "near_miss_count": len(near_misses),
            }
        )

    selected = select_proof_results(evaluation_candidates, runtime)
    selected_near = selected_near_misses(evaluation_near_misses, runtime)
    floor = hard_floor_summary(selected)
    evaluation_report = {
        "schema_version": "1.0",
        "status": floor["status"],
        "generated_at": utc_now_iso(),
        "query_hash": runtime.query_hash,
        "evaluation_match_ids": runtime.config.evaluation_match_ids,
        "per_match": per_match,
        "all_accepted_summary": summarize_candidates(evaluation_candidates),
        "selected_hard_floor": floor,
        "selected_result_ids": [item["result_id"] for item in selected],
        "selected_results": selected,
    }
    write_json(artifact_dir / "evaluation-report.json", evaluation_report)
    write_json(artifact_dir / "accepted-results.json", selected)
    write_json(artifact_dir / "near-misses.json", selected_near)
    write_feature_tables(
        feature_root=feature_root,
        calibration=calibration_candidates,
        evaluation=evaluation_candidates,
        near_misses=evaluation_near_misses,
    )

    match_lookup = load_match_metadata(canonical_root)
    team_lookup = load_team_metadata(canonical_root)
    table_cache: dict[tuple[str, str], PeriodTables] = {}
    bundles: list[dict[str, Any]] = []
    for result in selected:
        bundle_dir = evidence_root / result["result_id"]
        replay_path = bundle_dir / "replay.json"
        tables = load_period_tables(
            canonical_root=canonical_root,
            match_id=result["match_id"],
            period=result["period"],
            cache=table_cache,
        )
        replay = replay_from_canonical(
            result=result,
            tables=tables,
            match=match_lookup[str(result["match_id"])],
        )
        write_json(replay_path, replay)
        bundle = bundle_from_result(
            result=result,
            replay_path=replay_path,
            match=match_lookup[str(result["match_id"])],
            teams=team_lookup,
            query_hash=runtime.query_hash,
        )
        write_json(bundle_dir / "bundle.json", bundle)
        bundles.append(
            {
                "result_id": result["result_id"],
                "bundle_dir": str(bundle_dir),
                "bundle_json": str(bundle_dir / "bundle.json"),
                "replay_json": str(replay_path),
                "classification": result["classification"],
                "match_id": result["match_id"],
            }
        )

    proof_manifest = {
        "schema_version": "1.0",
        "status": floor["status"],
        "generated_at": utc_now_iso(),
        "query_hash": runtime.query_hash,
        "selected_result_count": len(selected),
        "near_miss_count": len(selected_near),
        "hard_floor": floor,
        "evidence_bundles": bundles,
        "reports": {
            "query_freeze": str(artifact_dir / "query-freeze.json"),
            "calibration": str(artifact_dir / "calibration-report.json"),
            "evaluation": str(artifact_dir / "evaluation-report.json"),
            "near_misses": str(artifact_dir / "near-misses.json"),
        },
        "feature_tables": {
            "accepted_candidates": str(feature_root / "accepted_candidates.parquet"),
            "near_misses": str(feature_root / "near_misses.parquet"),
        },
    }
    write_json(artifact_dir / "proof-pack-manifest.json", proof_manifest)
    return proof_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--feature-root", default=str(DEFAULT_FEATURE_ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_gate_c(
        config_path=Path(args.config),
        canonical_root=Path(args.canonical_root),
        raw_root=Path(args.raw_root),
        artifact_dir=Path(args.artifact_dir),
        evidence_root=Path(args.evidence_root),
        feature_root=Path(args.feature_root),
    )
    print(f"Wrote {Path(args.artifact_dir) / 'proof-pack-manifest.json'}")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "selected_result_count": manifest["selected_result_count"],
                "hard_floor": manifest["hard_floor"],
            },
            sort_keys=True,
        )
    )
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
