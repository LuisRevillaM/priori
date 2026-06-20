"""Gate C verification for the M1 tactical proof pack."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from tqe.query.ball_side_block_shift import (
    FRAME_RATE_HZ,
    PERIODS,
    BallSideBlockShiftQueryV1,
    has_persistent_shift,
    load_query_runtime,
    stream_ball_state,
)

DEFAULT_CONFIG_PATH = Path("config/queries/ball_side_block_shift.v1.yaml")
DEFAULT_ARTIFACT_DIR = Path("artifacts/m1/gate-c")
DEFAULT_CANONICAL_ROOT = Path("data/canonical/v1")
DEFAULT_RAW_ROOT = Path("data/raw/idsse/figshare-28196177-v1")
DEFAULT_GOLD_SET_PATH = Path("docs/queries/ball-side-block-shift/semantic-gold-set.v1.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def check(status: str, check_id: str, message: str, evidence: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"id": check_id, "status": status, "message": message}
    if evidence is not None:
        result["evidence"] = evidence
    return result


def load_json(path: Path) -> dict[str, Any] | list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    return pq.ParquetFile(path).read(columns=columns).to_pandas()


def validate_artifact_set(artifact_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    required = (
        "query-freeze.json",
        "query-schema.json",
        "calibration-report.json",
        "evaluation-report.json",
        "accepted-results.json",
        "near-misses.json",
        "proof-pack-manifest.json",
        "replay-proof-report.json",
    )
    for name in required:
        path = artifact_dir / name
        if not path.exists():
            checks.append(check("fail", f"gate_c_artifact.{name}.exists", f"{name} is missing.", str(path)))
            continue
        checks.append(check("pass", f"gate_c_artifact.{name}.exists", f"{name} exists.", str(path)))
        try:
            payload = load_json(path)
        except json.JSONDecodeError as exc:
            checks.append(
                check("fail", f"gate_c_artifact.{name}.valid_json", f"Invalid JSON: {exc}", str(path))
            )
            continue
        if isinstance(payload, dict) and "status" in payload:
            checks.append(
                check(
                    "pass" if payload.get("status") == "pass" else "fail",
                    f"gate_c_artifact.{name}.status",
                    f"{name} reports status=pass.",
                    str(path),
                )
            )
    return checks


def validate_query_freeze(config_path: Path, artifact_dir: Path) -> list[dict[str, Any]]:
    runtime = load_query_runtime(config_path)
    freeze_path = artifact_dir / "query-freeze.json"
    if not freeze_path.exists():
        return [check("fail", "query_freeze.exists", "Query freeze artifact is missing.", str(freeze_path))]
    freeze = load_json(freeze_path)
    if not isinstance(freeze, dict):
        return [check("fail", "query_freeze.object", "Query freeze must be a JSON object.", str(freeze_path))]
    checks = [
        check(
            "pass" if freeze.get("query_hash") == runtime.query_hash else "fail",
            "query_freeze.hash",
            "Query freeze hash matches the local frozen config.",
            str(freeze_path),
        ),
        check(
            "pass" if freeze.get("canonical_config") == runtime.canonical_config else "fail",
            "query_freeze.config",
            "Frozen canonical config matches the local config file.",
            str(config_path),
        ),
        check(
            "pass" if freeze.get("calibration_match_id") == runtime.config.calibration_match_id else "fail",
            "query_freeze.calibration_match",
            "Calibration match is recorded.",
        ),
        check(
            "pass" if freeze.get("evaluation_match_ids") == runtime.config.evaluation_match_ids else "fail",
            "query_freeze.evaluation_matches",
            "Evaluation matches are recorded in frozen order.",
        ),
    ]
    schema_path = artifact_dir / "query-schema.json"
    if schema_path.exists():
        schema = load_json(schema_path)
        checks.append(
            check(
                "pass"
                if isinstance(schema, dict)
                and schema.get("title") == BallSideBlockShiftQueryV1.model_json_schema().get("title")
                else "fail",
                "query_schema.model",
                "Query schema is generated from the Pydantic model.",
                str(schema_path),
            )
        )
    return checks


def hard_floor_checks(artifact_dir: Path) -> list[dict[str, Any]]:
    report_path = artifact_dir / "evaluation-report.json"
    if not report_path.exists():
        return [check("fail", "evaluation_report.exists", "Evaluation report is missing.", str(report_path))]
    report = load_json(report_path)
    if not isinstance(report, dict):
        return [check("fail", "evaluation_report.object", "Evaluation report must be an object.", str(report_path))]
    selected = report.get("selected_results", [])
    if not isinstance(selected, list):
        return [check("fail", "evaluation_report.selected_results", "Selected results must be a list.")]
    by_class = Counter(str(item.get("classification")) for item in selected if isinstance(item, dict))
    by_match = Counter(str(item.get("match_id")) for item in selected if isinstance(item, dict))
    max_match_share = max(by_match.values()) / len(selected) if selected else 1.0
    non_switched = by_class.get("RETAINED_NO_SWITCH", 0) + by_class.get("LOST_BEFORE_SWITCH", 0)
    return [
        check("pass" if len(selected) >= 8 else "fail", "hard_floor.accepted_count", "At least 8 accepted results are selected."),
        check("pass" if len(by_match) >= 3 else "fail", "hard_floor.match_span", "Accepted results span at least 3 evaluation matches."),
        check("pass" if by_class.get("SWITCHED", 0) >= 2 else "fail", "hard_floor.switched", "At least 2 accepted results are SWITCHED."),
        check("pass" if non_switched >= 2 else "fail", "hard_floor.non_switched", "At least 2 accepted results are non-switched outcomes."),
        check("pass" if max_match_share <= 0.60 else "fail", "hard_floor.match_concentration", "No match contributes more than 60 percent."),
        check(
            "pass" if all(item.get("quality_status") != "fail" for item in selected if isinstance(item, dict)) else "fail",
            "hard_floor.quality",
            "No selected result has quality_status=fail.",
        ),
    ]


def selected_results(artifact_dir: Path) -> list[dict[str, Any]]:
    report = load_json(artifact_dir / "evaluation-report.json")
    if not isinstance(report, dict):
        return []
    selected = report.get("selected_results", [])
    return [item for item in selected if isinstance(item, dict)]


def outfield_players(canonical_root: Path, match_id: str, team_role: str) -> set[str]:
    players = read_parquet(canonical_root / "players.parquet")
    selected = players[
        (players.match_id == match_id) & (players.team_role == team_role) & (~players.is_goalkeeper)
    ]
    return set(selected.player_id.astype(str))


def verify_result_predicate(
    *,
    result: dict[str, Any],
    config: BallSideBlockShiftQueryV1,
    canonical_root: Path,
    raw_root: Path,
) -> list[dict[str, Any]]:
    match_id = str(result["match_id"])
    period = str(result["period"])
    result_id = str(result["result_id"])
    checks: list[dict[str, Any]] = []
    if period not in PERIODS:
        return [check("fail", f"predicate.{result_id}.period", f"Unexpected period {period}.")]

    positions_path = canonical_root / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
    pos = read_parquet(
        positions_path,
        ["frame_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
    )
    ball = (
        pos[pos.entity_type == "ball"][["frame_id", "x_m", "y_m"]]
        .sort_values("frame_id")
        .reset_index(drop=True)
    )
    state = stream_ball_state(raw_root / match_id / "tracking.xml", period)
    full_frame = ball.merge(state, on="frame_id").sort_values("frame_id").reset_index(drop=True)
    step = FRAME_RATE_HZ // config.analysis_rate_hz
    frame = full_frame.iloc[::step].reset_index(drop=True)
    frame_ids = frame.frame_id.to_numpy(dtype=np.int64)
    gaps_ms = np.diff(frame_ids) / FRAME_RATE_HZ * 1000.0
    checks.append(
        check(
            "pass" if not len(gaps_ms) or float(np.max(gaps_ms)) <= config.maximum_analysis_gap_ms else "fail",
            f"predicate.{result_id}.analysis_gap",
            "Analysis stream gap stays within the frozen maximum.",
        )
    )

    by_frame_index = {int(frame_id): index for index, frame_id in enumerate(frame_ids)}
    required_ids = (
        "possession_start_frame_id",
        "possession_end_frame_id",
        "wide_entry_frame_id",
        "anchor_frame_id",
        "outcome_frame_id",
    )
    missing_ids = [name for name in required_ids if int(result[name]) not in by_frame_index]
    checks.append(
        check(
            "pass" if not missing_ids else "fail",
            f"predicate.{result_id}.analysis_frame_ids",
            "Result predicate frames are present in the 5 Hz analysis stream.",
        )
    )
    if missing_ids:
        return checks

    possession = frame.possession_team_role.to_numpy(dtype=object)
    alive = frame.ball_alive.to_numpy(dtype=bool)
    ball_y = frame.y_m.to_numpy(dtype=float)
    start_idx = by_frame_index[int(result["possession_start_frame_id"])]
    end_idx = by_frame_index[int(result["possession_end_frame_id"])]
    entry_idx = by_frame_index[int(result["wide_entry_frame_id"])]
    anchor_idx = by_frame_index[int(result["anchor_frame_id"])]
    outcome_idx = by_frame_index[int(result["outcome_frame_id"])]

    segment_ok = bool(
        end_idx > start_idx
        and np.all(possession[start_idx : end_idx + 1] == config.perspective_team_role)
        and np.all(alive[start_idx : end_idx + 1])
        and (end_idx - start_idx + 1) >= int(round(config.minimum_possession_seconds * config.analysis_rate_hz))
    )
    checks.append(
        check(
            "pass" if segment_ok else "fail",
            f"predicate.{result_id}.possession_segment",
            "Possession segment recomputes from raw ball state.",
        )
    )

    dwell_frames = int(round(config.minimum_wide_dwell_seconds * config.analysis_rate_hz))
    prior_frames = int(round(2.0 * config.analysis_rate_hz))
    side_sign = 1 if ball_y[entry_idx] >= 0 else -1
    wide = np.abs(ball_y) > config.wide_y_threshold_m
    prior_start = max(0, entry_idx - prior_frames)
    wide_ok = bool(
        wide[entry_idx]
        and not wide[entry_idx - 1]
        and entry_idx + dwell_frames <= len(wide)
        and np.all(wide[entry_idx : entry_idx + dwell_frames])
        and np.any(np.abs(ball_y[prior_start:entry_idx]) < config.central_y_threshold_m)
    )
    checks.append(
        check(
            "pass" if wide_ok else "fail",
            f"predicate.{result_id}.wide_entry",
            "Wide entry and prior central predicate recompute.",
        )
    )

    defending_role = "away" if config.perspective_team_role == "home" else "home"
    defenders = pos[
        (pos.entity_type == "player")
        & (pos.team_role == defending_role)
        & (pos.entity_id.astype(str).isin(outfield_players(canonical_root, match_id, defending_role)))
    ]
    defender_count = defenders.groupby("frame_id").entity_id.nunique()
    defender_centroid_y = defenders.groupby("frame_id").y_m.mean().sort_index()
    baseline = defender_centroid_y.loc[
        (defender_centroid_y.index >= int(result["baseline_start_frame_id"]))
        & (defender_centroid_y.index <= int(result["baseline_end_frame_id"]))
    ]
    baseline_y = float(baseline.mean()) if not baseline.empty else math.nan
    checks.append(
        check(
            "pass" if abs(round(baseline_y, 3) - float(result["baseline_defensive_centroid_y_m"])) <= 0.001 else "fail",
            f"predicate.{result_id}.baseline_centroid",
            "Baseline defensive centroid recomputes within tolerance.",
        )
    )

    search_frames = int(round(config.shift_search_window_seconds * config.analysis_rate_hz))
    search_ids = frame_ids[entry_idx : min(end_idx + 1, entry_idx + search_frames)]
    search_series = defender_centroid_y.loc[defender_centroid_y.index.isin(search_ids)]
    signed_shift = side_sign * (search_series - baseline_y)
    recomputed_shift = float(signed_shift.max()) if not signed_shift.empty else math.nan
    recomputed_anchor = int(signed_shift.idxmax()) if not signed_shift.empty else -1
    persistence_frames = int(round(config.minimum_shift_persistence_seconds * config.analysis_rate_hz))
    persistent = has_persistent_shift(signed_shift, config.minimum_shift_metres, persistence_frames)
    enough_defenders = bool(
        defender_count.loc[
            (defender_count.index >= int(result["baseline_start_frame_id"]))
            & (defender_count.index <= int(search_ids[-1]))
        ].min()
        >= config.minimum_outfield_players_per_team
    )
    checks.extend(
        [
            check(
                "pass" if recomputed_anchor == int(result["anchor_frame_id"]) else "fail",
                f"predicate.{result_id}.anchor",
                "Anchor frame recomputes from maximum signed defensive shift.",
            ),
            check(
                "pass" if abs(round(recomputed_shift, 3) - float(result["signed_shift_metres"])) <= 0.001 else "fail",
                f"predicate.{result_id}.signed_shift",
                "Signed defensive shift recomputes within tolerance.",
            ),
            check(
                "pass" if persistent and recomputed_shift >= config.minimum_shift_metres else "fail",
                f"predicate.{result_id}.shift_threshold",
                "Shift magnitude and persistence meet frozen thresholds.",
            ),
            check(
                "pass" if enough_defenders else "fail",
                f"predicate.{result_id}.defender_count",
                "Minimum defending outfield player count is present.",
            ),
        ]
    )

    horizon_frames = int(round(config.outcome_horizon_seconds * config.analysis_rate_hz))
    retain_frames = int(round(config.retained_after_switch_seconds * config.analysis_rate_hz))
    outcome_y = ball_y[anchor_idx : anchor_idx + horizon_frames]
    outcome_possession = possession[anchor_idx : anchor_idx + horizon_frames]
    outcome_alive = alive[anchor_idx : anchor_idx + horizon_frames]
    opposite = np.where(side_sign * outcome_y <= -config.opposite_y_threshold_m)[0]
    loss = np.where((outcome_possession != config.perspective_team_role) & outcome_alive)[0]
    dead = np.where(~outcome_alive)[0]
    first_dead = int(dead[0]) if len(dead) else None
    first_loss = int(loss[0]) if len(loss) else None
    first_switch = int(opposite[0]) if len(opposite) else None
    if first_dead is not None and (
        first_switch is None or first_dead < first_switch
    ) and (first_loss is None or first_dead < first_loss):
        classification = "STOPPAGE"
        outcome_offset = first_dead
    elif first_switch is not None:
        end = min(len(outcome_possession), first_switch + retain_frames)
        retained = end - first_switch >= retain_frames and np.all(
            (outcome_possession[first_switch:end] == config.perspective_team_role)
            & outcome_alive[first_switch:end]
        )
        if retained:
            classification = "SWITCHED"
            outcome_offset = first_switch
        elif first_loss is not None:
            classification = "LOST_BEFORE_SWITCH"
            outcome_offset = first_loss
        else:
            classification = "RETAINED_NO_SWITCH"
            outcome_offset = len(outcome_y) - 1
    elif first_loss is not None:
        classification = "LOST_BEFORE_SWITCH"
        outcome_offset = first_loss
    else:
        classification = "RETAINED_NO_SWITCH"
        outcome_offset = len(outcome_y) - 1
    recomputed_outcome_frame = int(frame_ids[min(anchor_idx + outcome_offset, len(frame_ids) - 1)])
    checks.extend(
        [
            check(
                "pass" if classification == result["classification"] else "fail",
                f"predicate.{result_id}.classification",
                "Outcome classification recomputes from raw ball state.",
            ),
            check(
                "pass" if recomputed_outcome_frame == int(result["outcome_frame_id"]) else "fail",
                f"predicate.{result_id}.outcome_frame",
                "Outcome frame recomputes from outcome classification.",
            ),
        ]
    )
    return checks


def validate_replay_bundle(
    *,
    result: dict[str, Any],
    artifact_dir: Path,
    canonical_cache: dict[Path, pd.DataFrame],
) -> list[dict[str, Any]]:
    result_id = str(result["result_id"])
    manifest = load_json(artifact_dir / "proof-pack-manifest.json")
    if not isinstance(manifest, dict):
        return [check("fail", f"bundle.{result_id}.manifest", "Proof manifest is invalid.")]
    bundles = {
        str(item.get("result_id")): item
        for item in manifest.get("evidence_bundles", [])
        if isinstance(item, dict)
    }
    bundle_record = bundles.get(result_id)
    if bundle_record is None:
        return [check("fail", f"bundle.{result_id}.exists", "Selected result has no evidence bundle.")]

    bundle_path = Path(str(bundle_record["bundle_json"]))
    replay_path = Path(str(bundle_record["replay_json"]))
    checks = [
        check("pass" if bundle_path.exists() else "fail", f"bundle.{result_id}.bundle_json.exists", "bundle.json exists.", str(bundle_path)),
        check("pass" if replay_path.exists() else "fail", f"bundle.{result_id}.replay_json.exists", "replay.json exists.", str(replay_path)),
    ]
    if not bundle_path.exists() or not replay_path.exists():
        return checks
    bundle = load_json(bundle_path)
    replay = load_json(replay_path)
    if not isinstance(bundle, dict) or not isinstance(replay, dict):
        checks.append(check("fail", f"bundle.{result_id}.json_shape", "Bundle and replay must be JSON objects."))
        return checks

    checks.extend(
        [
            check(
                "pass" if bundle.get("result_id") == result_id and bundle.get("status") == "pass" else "fail",
                f"bundle.{result_id}.contract",
                "Bundle references the selected result and reports pass.",
                str(bundle_path),
            ),
            check(
                "pass"
                if int(replay.get("start_frame_id", -1)) == int(result["replay_start_frame_id"])
                and int(replay.get("end_frame_id", -1)) == int(result["replay_end_frame_id"])
                else "fail",
                f"bundle.{result_id}.replay_window",
                "Replay window matches the selected result.",
                str(replay_path),
            ),
        ]
    )

    source_path = Path(str(replay["canonical_sources"]["positions"]))
    if source_path not in canonical_cache:
        canonical_cache[source_path] = read_parquet(
            source_path,
            ["frame_id", "team_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"],
        )
    canonical = canonical_cache[source_path]
    start = int(replay["start_frame_id"])
    end = int(replay["end_frame_id"])
    window = canonical[(canonical.frame_id >= start) & (canonical.frame_id <= end)].copy()
    expected: dict[tuple[int, str], tuple[str, str, str, float, float]] = {}
    for row in window.itertuples(index=False):
        expected[(int(row.frame_id), str(row.entity_id))] = (
            str(row.team_id),
            str(row.team_role),
            str(row.entity_type),
            round(float(row.x_m), 3),
            round(float(row.y_m), 3),
        )
    seen: set[tuple[int, str]] = set()
    mismatch_count = 0
    entity_count = 0
    for frame in replay.get("frames", []):
        frame_id = int(frame["frame_id"])
        for entity in frame.get("entities", []):
            key = (frame_id, str(entity["entity_id"]))
            seen.add(key)
            entity_count += 1
            expected_row = expected.get(key)
            if expected_row is None:
                mismatch_count += 1
                continue
            if (
                str(entity["team_id"]) != expected_row[0]
                or str(entity["team_role"]) != expected_row[1]
                or str(entity["entity_type"]) != expected_row[2]
                or abs(float(entity["x_m"]) - expected_row[3]) > 0.001
                or abs(float(entity["y_m"]) - expected_row[4]) > 0.001
            ):
                mismatch_count += 1
    checks.extend(
        [
            check(
                "pass" if entity_count > 0 else "fail",
                f"bundle.{result_id}.replay_nonempty",
                "Replay contains entity observations.",
                str(replay_path),
            ),
            check(
                "pass" if mismatch_count == 0 and seen == set(expected) else "fail",
                f"bundle.{result_id}.replay_canonical_parity",
                "Replay coordinates and identities match canonical positions exactly after rounding.",
                str(replay_path),
            ),
        ]
    )
    return checks


def validate_feature_tables(artifact_dir: Path) -> list[dict[str, Any]]:
    manifest_path = artifact_dir / "proof-pack-manifest.json"
    if not manifest_path.exists():
        return [check("fail", "features.manifest", "Proof pack manifest is missing.")]
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return [check("fail", "features.manifest_shape", "Proof pack manifest must be an object.")]
    checks: list[dict[str, Any]] = []
    feature_tables = manifest.get("feature_tables", {})
    for name, raw_path in feature_tables.items():
        path = Path(str(raw_path))
        if not path.exists():
            checks.append(check("fail", f"features.{name}.exists", f"{name} feature table is missing.", str(path)))
            continue
        rows = pq.ParquetFile(path).metadata.num_rows
        checks.append(
            check(
                "pass" if rows > 0 else "fail",
                f"features.{name}.rows",
                f"{name} feature table has rows.",
                str(path),
            )
        )
    return checks


def validate_semantic_gold_set(gold_set_path: Path, expected_query_hash: str) -> list[dict[str, Any]]:
    if not gold_set_path.exists():
        return [check("fail", "semantic_gold.exists", "Semantic gold set is missing.", str(gold_set_path))]
    try:
        payload = load_json(gold_set_path)
    except json.JSONDecodeError as exc:
        return [check("fail", "semantic_gold.valid_json", f"Invalid JSON: {exc}", str(gold_set_path))]
    if not isinstance(payload, dict):
        return [check("fail", "semantic_gold.object", "Semantic gold set must be a JSON object.", str(gold_set_path))]

    reviewed = payload.get("reviewed_moments", [])
    categories = {
        str(item.get("category"))
        for item in reviewed
        if isinstance(item, dict) and item.get("category") is not None
    }
    expected_categories = {
        "clear_positive",
        "borderline_accepted",
        "clear_negative_excluded",
        "threshold_near_miss",
    }
    checks = [
        check(
            "pass" if payload.get("query_hash") == expected_query_hash else "fail",
            "semantic_gold.query_hash",
            "Semantic gold set is bound to the frozen query hash.",
            str(gold_set_path),
        ),
        check(
            "pass" if isinstance(reviewed, list) and len(reviewed) >= 15 else "fail",
            "semantic_gold.reviewed_count",
            "Semantic gold set has at least 15 reviewed moment cases.",
            str(gold_set_path),
        ),
        check(
            "pass" if expected_categories.issubset(categories) else "fail",
            "semantic_gold.categories",
            "Semantic gold set covers positives, borderline accepted cases, excluded negatives, and threshold near misses.",
            str(gold_set_path),
        ),
        check(
            "pass" if len(payload.get("data_quality_failure_controls", [])) >= 2 else "fail",
            "semantic_gold.data_quality_controls",
            "Semantic gold set defines data-quality failure controls.",
            str(gold_set_path),
        ),
        check(
            "pass" if len(payload.get("allowed_claims", [])) >= 3 else "fail",
            "semantic_gold.allowed_claims",
            "Semantic gold set records allowed claims.",
            str(gold_set_path),
        ),
        check(
            "pass" if len(payload.get("disallowed_claims", [])) >= 3 else "fail",
            "semantic_gold.disallowed_claims",
            "Semantic gold set records disallowed claims.",
            str(gold_set_path),
        ),
    ]
    return checks


def build_report(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
    gold_set_path: Path = DEFAULT_GOLD_SET_PATH,
) -> dict[str, Any]:
    runtime = load_query_runtime(config_path)
    checks: list[dict[str, Any]] = []
    checks.extend(validate_artifact_set(artifact_dir))
    checks.extend(validate_query_freeze(config_path, artifact_dir))
    checks.extend(hard_floor_checks(artifact_dir))
    checks.extend(validate_feature_tables(artifact_dir))
    checks.extend(validate_semantic_gold_set(gold_set_path, runtime.query_hash))

    canonical_cache: dict[Path, pd.DataFrame] = {}
    for result in selected_results(artifact_dir):
        checks.extend(
            verify_result_predicate(
                result=result,
                config=runtime.config,
                canonical_root=canonical_root,
                raw_root=raw_root,
            )
        )
        checks.extend(
            validate_replay_bundle(
                result=result,
                artifact_dir=artifact_dir,
                canonical_cache=canonical_cache,
            )
        )

    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
        "not_ready": sum(1 for item in checks if item["status"] == "not_ready"),
    }
    status = "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail"
    return {
        "schema_version": "1.0",
        "gate": "Gate C - Tactical Proof",
        "generated_at": utc_now_iso(),
        "status": status,
        "artifact_dir": str(artifact_dir),
        "canonical_root": str(canonical_root),
        "raw_root": str(raw_root),
        "semantic_gold_set": str(gold_set_path),
        "summary": summary,
        "checks": checks,
        "next_required": [] if status == "pass" else ["Fix failing tactical proof checks before accepting M1."],
    }


def write_report(report: dict[str, Any], artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / "verification-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--gold-set", default=str(DEFAULT_GOLD_SET_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        config_path=Path(args.config),
        artifact_dir=Path(args.artifact_dir),
        canonical_root=Path(args.canonical_root),
        raw_root=Path(args.raw_root),
        gold_set_path=Path(args.gold_set),
    )
    report_path = write_report(report, Path(args.artifact_dir))
    print(f"Wrote {report_path}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
