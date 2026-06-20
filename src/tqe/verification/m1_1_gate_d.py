"""Verify M1.1 Gate D: dynamic geometric relation proof."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tqe.runtime.catalog import default_catalog
from tqe.runtime.executor import DEFAULT_CANONICAL_ROOT, execution_result_rows, execute_default_plan
from tqe.runtime.relations import (
    CorridorConfig,
    evaluate_geometric_progressive_corridors,
    point_segment_distance,
    write_visual_review_svgs,
)
from tqe.verification.m1_1_gate_c import build_report as build_gate_c_report

RELATION_REPORT = Path("artifacts/m1.1/relation-validation-report.json")
VISUAL_REVIEW_DIR = Path("artifacts/m1.1/relation-visual-review")
VERIFY_REPORT = Path("artifacts/m1.1/gate-d-verification-report.json")

REQUIRED_EPISODE_FIELDS = {
    "relation_id",
    "open_frame_id",
    "open_confirm_frame_id",
    "close_frame_id",
    "duration_seconds",
    "minimum_clearance_m",
    "target_player_id",
    "destination_side",
    "destination_region",
    "destination_lane",
    "limiting_defender_id",
    "source_open_point",
    "target_open_point",
    "source_close_point",
    "target_close_point",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report(gate_c_report: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    gate_c = gate_c_report or build_gate_c_report()
    checks.append(
        pass_check("gate_c.precondition", "Gate C verifier passes")
        if gate_c["status"] == "pass"
        else fail_check("gate_c.precondition", "Gate C must pass before Gate D")
    )

    _bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    relation_report = evaluate_geometric_progressive_corridors(results=rows)
    visual_artifacts = write_visual_review_svgs(
        relation_report["visual_review_cases"],
        VISUAL_REVIEW_DIR,
    )
    relation_report = {
        **relation_report,
        "generated_at": utc_now_iso(),
        "visual_review_artifacts": visual_artifacts,
    }
    write_json(RELATION_REPORT, relation_report)

    checks.extend(validate_catalog_contract())
    checks.extend(validate_relation_breadth(relation_report))
    checks.extend(validate_episode_shape(relation_report))
    checks.extend(validate_reconstructable_geometry(relation_report))
    checks.extend(validate_visual_review_cases(relation_report))
    checks.extend(validate_unknown_invalid_controls(relation_report))
    checks.extend(validate_no_forbidden_claim_surface(relation_report))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_D_dynamic_relation_proof",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            "relation_validation_report": str(RELATION_REPORT),
            "visual_review_dir": str(VISUAL_REVIEW_DIR),
        },
        "checks": checks,
    }
    write_json(VERIFY_REPORT, report)
    return report


def validate_catalog_contract() -> list[dict[str, Any]]:
    catalog = default_catalog()
    relation = next(
        (
            entry
            for entry in catalog.relations
            if entry.name == "geometric_progressive_corridor" and entry.version == "0.1.0"
        ),
        None,
    )
    if relation is None:
        return [fail_check("relation.catalog_entry", "geometric_progressive_corridor@0.1.0 is missing")]
    evidence = set(relation.evidence_fields) | set(relation.outputs[0].evidence_fields)
    missing = sorted(REQUIRED_EPISODE_FIELDS - evidence)
    return [
        pass_check("relation.catalog_entry", "geometric_progressive_corridor@0.1.0 is cataloged"),
        pass_check("relation.catalog_evidence", "relation catalog exposes required evidence fields")
        if not missing
        else fail_check(
            "relation.catalog_evidence",
            "relation catalog is missing required evidence fields",
            {"missing": missing},
        ),
    ]


def validate_relation_breadth(report: dict[str, Any]) -> list[dict[str, Any]]:
    summary = report["summary"]
    return [
        pass_check(
            "relation.episode_count",
            "geometric corridor emits several real episodes",
            {"episode_count": summary["episode_count"]},
        )
        if summary["episode_count"] >= 20
        else fail_check(
            "relation.episode_count",
            "too few geometric corridor episodes were derived",
            {"episode_count": summary["episode_count"]},
        ),
        pass_check(
            "relation.match_span",
            "relation episodes span multiple Fortuna evaluation matches",
            {"by_match": summary["by_match"]},
        )
        if summary["match_count_with_episode"] >= 3
        else fail_check(
            "relation.match_span",
            "relation episodes do not span enough evaluation matches",
            {"by_match": summary["by_match"]},
        ),
    ]


def validate_episode_shape(report: dict[str, Any]) -> list[dict[str, Any]]:
    config = CorridorConfig(**report["config"])
    malformed: list[dict[str, Any]] = []
    for episode in report["episodes"]:
        missing = REQUIRED_EPISODE_FIELDS - set(episode)
        if missing:
            malformed.append({"relation_id": episode.get("relation_id"), "missing": sorted(missing)})
            continue
        if (
            episode["status"] != "PASS"
            or float(episode["duration_seconds"]) < config.open_after_frames / config.analysis_rate_hz
            or float(episode["minimum_clearance_m"]) < config.minimum_clearance_m
            or int(episode["open_frame_id"]) > int(episode["close_frame_id"])
            or int(episode["open_confirm_frame_id"]) < int(episode["open_frame_id"])
        ):
            malformed.append({"relation_id": episode.get("relation_id"), "reason": "invalid_values"})
    return [
        pass_check("relation.episode_shape", "every relation episode has reproducible evidence fields")
        if not malformed
        else fail_check(
            "relation.episode_shape",
            "one or more relation episodes have missing or invalid evidence",
            {"sample": malformed[:10]},
        )
    ]


def validate_reconstructable_geometry(report: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    positions_cache: dict[tuple[str, str], Any] = {}
    players = pq.ParquetFile(DEFAULT_CANONICAL_ROOT / "players.parquet").read().to_pandas()
    for episode in report["episodes"]:
        match_id = str(episode["match_id"])
        period = str(episode["period"])
        positions = cached_positions(positions_cache, match_id, period)
        for frame_key, source_key, target_key in (
            ("open_frame_id", "source_open_point", "target_open_point"),
            ("close_frame_id", "source_close_point", "target_close_point"),
        ):
            frame = positions[positions.frame_id == int(episode[frame_key])]
            ball = frame[frame.entity_type == "ball"]
            target = frame[frame.entity_id == episode["target_player_id"]]
            if ball.empty or target.empty:
                failures.append({"relation_id": episode["relation_id"], "field": frame_key})
                continue
            if not point_matches(ball.iloc[0], episode[source_key]) or not point_matches(target.iloc[0], episode[target_key]):
                failures.append({"relation_id": episode["relation_id"], "field": f"{frame_key}.points"})
        minimum_clearance, limiting_defender_id = recompute_episode_clearance(positions, players, episode)
        if abs(round(minimum_clearance, 3) - float(episode["minimum_clearance_m"])) > 0.001:
            failures.append({"relation_id": episode["relation_id"], "field": "minimum_clearance_m"})
        if limiting_defender_id != episode["limiting_defender_id"]:
            failures.append({"relation_id": episode["relation_id"], "field": "limiting_defender_id"})

    return [
        pass_check(
            "relation.geometry_reconstructable",
            "all relation episodes reconstruct from canonical positions",
            {"episode_count": len(report["episodes"])},
        )
        if not failures
        else fail_check(
            "relation.geometry_reconstructable",
            "relation episode evidence does not reconstruct from canonical positions",
            {"failure_count": len(failures), "sample": failures[:10]},
        )
    ]


def validate_visual_review_cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    case_types = {case["case_type"] for case in report["visual_review_cases"]}
    required = {"positive", "negative", "flicker_boundary"}
    svg_failures = [
        artifact
        for artifact in report["visual_review_artifacts"]
        if not Path(artifact["path"]).exists()
        or "<line" not in Path(artifact["path"]).read_text(encoding="utf-8")
    ]
    return [
        pass_check("relation.visual_case_types", "visual review cases include positives, negatives, and flicker boundaries")
        if required.issubset(case_types)
        else fail_check(
            "relation.visual_case_types",
            "visual review cases do not cover required case types",
            {"case_types": sorted(case_types)},
        ),
        pass_check("relation.visual_artifacts", "visual review SVG artifacts were generated")
        if not svg_failures
        else fail_check(
            "relation.visual_artifacts",
            "one or more visual review SVG artifacts are missing or malformed",
            {"failures": svg_failures},
        ),
    ]


def validate_unknown_invalid_controls(report: dict[str, Any]) -> list[dict[str, Any]]:
    states = [item["state"]["status"] for item in report["unknown_invalid_controls"]]
    reasons = [item["state"].get("reason") for item in report["unknown_invalid_controls"]]
    return [
        pass_check("relation.unknown_invalid_states", "UNKNOWN and INVALID relation states are explicit")
        if "UNKNOWN" in states and "INVALID" in states and all(reasons)
        else fail_check(
            "relation.unknown_invalid_states",
            "UNKNOWN or INVALID relation controls are missing",
            {"states": states, "reasons": reasons},
        )
    ]


def validate_no_forbidden_claim_surface(report: dict[str, Any]) -> list[dict[str, Any]]:
    forbidden_episode_keys = {
        "pass_probability",
        "expected_completion",
        "best_decision",
        "optimality",
        "missed_opportunity",
        "intent",
    }
    offending = [
        sorted(forbidden_episode_keys & set(episode))
        for episode in report["episodes"]
        if forbidden_episode_keys & set(episode)
    ]
    return [
        pass_check("relation.no_optimality_claims", "relation episodes expose geometry only, not pass quality or optimality claims")
        if not offending and len(report.get("disallowed_claims", [])) >= 4
        else fail_check(
            "relation.no_optimality_claims",
            "relation report exposes forbidden pass-quality or optimality fields",
            {"offending": offending[:10]},
        )
    ]


def cached_positions(cache: dict[tuple[str, str], Any], match_id: str, period: str) -> Any:
    key = (match_id, period)
    if key not in cache:
        path = DEFAULT_CANONICAL_ROOT / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
        cache[key] = pq.ParquetFile(path).read(
            columns=["frame_id", "team_role", "entity_id", "entity_type", "x_m", "y_m"]
        ).to_pandas()
    return cache[key]


def point_matches(row: Any, point: dict[str, float]) -> bool:
    return abs(round(float(row.x_m), 3) - float(point["x_m"])) <= 0.001 and abs(
        round(float(row.y_m), 3) - float(point["y_m"])
    ) <= 0.001


def recompute_episode_clearance(positions: Any, players: Any, episode: dict[str, Any]) -> tuple[float, str | None]:
    frame_ids = range(int(episode["open_frame_id"]), int(episode["close_frame_id"]) + 1, 5)
    minimum_clearance = float("inf")
    limiting_defender_id: str | None = None
    defending_role = "away" if episode["perspective_team_role"] == "home" else "home"
    defending_outfield = set(
        players[
            (players.match_id == episode["match_id"])
            & (players.team_role == defending_role)
            & (~players.is_goalkeeper)
        ].player_id.astype(str)
    )
    for frame_id in frame_ids:
        frame = positions[positions.frame_id == frame_id]
        ball = frame[frame.entity_type == "ball"]
        target = frame[frame.entity_id == episode["target_player_id"]]
        defenders = frame[
            (frame.entity_type == "player")
            & (frame.team_role == defending_role)
            & (frame.entity_id.astype(str).isin(defending_outfield))
        ]
        if ball.empty or target.empty:
            continue
        source = ball.iloc[0]
        destination = target.iloc[0]
        for defender in defenders.itertuples(index=False):
            clearance = point_segment_distance(
                float(defender.x_m),
                float(defender.y_m),
                float(source.x_m),
                float(source.y_m),
                float(destination.x_m),
                float(destination.y_m),
            )
            if clearance < minimum_clearance:
                minimum_clearance = clearance
                limiting_defender_id = str(defender.entity_id)
    return minimum_clearance, limiting_defender_id


def main() -> int:
    report = build_report()
    print(f"Wrote {VERIFY_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
