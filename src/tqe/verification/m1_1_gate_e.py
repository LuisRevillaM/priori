"""Verify M1.1 Gate E: no-code experimental composition proof."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from tqe.runtime.executor import (
    DEFAULT_CANONICAL_ROOT,
    FRAME_RATE_HZ,
    execute_plan_from_path,
    execution_result_rows,
    summarize_results,
)
from tqe.runtime.ir import BoundCatalogNode, BoundPredicateNode, NodeKind, PlanStatus
from tqe.verification.m1_1_gate_d import build_report as build_gate_d_report

PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
RESULTS_REPORT = Path("artifacts/m1.1/experimental-query-results.json")
EVIDENCE_ROOT = Path("artifacts/m1.1/experimental-evidence")
BUNDLE_MANIFEST = Path("artifacts/m1.1/experimental-evidence-manifest.json")
VERIFY_REPORT = Path("artifacts/m1.1/gate-e-verification-report.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")

REQUIRED_RESULT_FIELDS = {
    "plan_status",
    "base_result_id",
    "relation_id",
    "relation_open_frame_id",
    "relation_open_confirm_frame_id",
    "relation_close_frame_id",
    "relation_duration_seconds",
    "relation_target_player_id",
    "relation_minimum_clearance_m",
    "destination_region",
    "destination_side",
    "destination_lane",
    "destination_entry_frame_id",
    "replay_start_frame_id",
    "replay_end_frame_id",
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


def build_report(gate_d_report: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    gate_d = gate_d_report or build_gate_d_report()
    checks.append(
        pass_check("gate_d.precondition", "Gate D verifier passes")
        if gate_d["status"] == "pass"
        else fail_check("gate_d.precondition", "Gate D must pass before Gate E")
    )

    bound, execution = execute_plan_from_path(PLAN_PATH)
    rows = execution_result_rows(execution)
    trace_payload = [
        trace.model_dump(mode="json", exclude_none=True) for trace in execution.predicate_traces
    ]
    bundle_manifest = write_evidence_bundles(rows)

    result_report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_E_no_code_composition",
        "generated_at": utc_now_iso(),
        "status": "pass",
        "plan_path": str(PLAN_PATH),
        "plan_id": bound.plan_id,
        "plan_version": bound.plan_version,
        "plan_status": bound.plan_status.value,
        "recipe_id": bound.recipe_id,
        "recipe_version": bound.recipe_version,
        "plan_hash": bound.plan_hash,
        "bound_plan_hash": bound.bound_plan_hash,
        "execution_id": execution.execution_id,
        "execution_status": execution.status.value,
        "execution_provenance": execution.provenance,
        "cache_policy": {
            "precomputed_results_used": False,
            "precomputed_artifacts_ignored": True,
            "execution_source": "external_plan_file_plus_canonical_parquet",
        },
        "result_summary": summarize_results(rows),
        "predicate_trace_count": len(trace_payload),
        "predicate_trace_hash": execution.provenance["runtime_trace_hash"],
        "evidence_manifest": str(BUNDLE_MANIFEST),
        "results": rows,
    }
    write_json(RESULTS_REPORT, result_report)

    checks.extend(validate_plan_contract(bound))
    checks.extend(validate_execution_output(bound, execution, rows, trace_payload))
    checks.extend(validate_no_code_architecture())
    checks.extend(validate_evidence_bundles(rows, bundle_manifest))
    checks.extend(validate_experimental_status(result_report, bundle_manifest))
    checks.extend(validate_no_forbidden_claim_surface(rows, result_report))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_E_no_code_composition",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "plan_status": bound.plan_status.value,
        "artifacts": {
            "plan": str(PLAN_PATH),
            "experimental_query_results": str(RESULTS_REPORT),
            "evidence_root": str(EVIDENCE_ROOT),
            "evidence_manifest": str(BUNDLE_MANIFEST),
        },
        "checks": checks,
    }
    write_json(VERIFY_REPORT, report)
    return report


def validate_plan_contract(bound: Any) -> list[dict[str, Any]]:
    relation_nodes = [
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode)
        and node.kind == NodeKind.RELATION
        and node.catalog_ref == "geometric_progressive_corridor"
    ]
    destination_nodes = [
        node
        for node in bound.nodes
        if isinstance(node, BoundCatalogNode)
        and node.kind == NodeKind.PRIMITIVE
        and node.catalog_ref == "relation_destination_entry_classification"
    ]
    predicate_ids = {
        node.node_id for node in bound.nodes if isinstance(node, BoundPredicateNode)
    }
    return [
        pass_check("plan.external_file", "experimental plan file exists", {"path": str(PLAN_PATH)})
        if PLAN_PATH.exists()
        else fail_check("plan.external_file", "experimental plan file is missing"),
        pass_check("plan.status", "bound plan status is experimental")
        if bound.plan_status == PlanStatus.EXPERIMENTAL
        else fail_check("plan.status", "bound plan is not experimental", {"plan_status": bound.plan_status}),
        pass_check("plan.relation_node", "plan composes geometric_progressive_corridor as a relation node")
        if len(relation_nodes) == 1
        else fail_check(
            "plan.relation_node",
            "plan must contain one geometric_progressive_corridor relation node",
            {"count": len(relation_nodes)},
        ),
        pass_check("plan.destination_entry_node", "plan composes destination-entry classification as a catalog primitive")
        if len(destination_nodes) == 1
        else fail_check(
            "plan.destination_entry_node",
            "plan must contain one relation_destination_entry_classification primitive",
            {"count": len(destination_nodes)},
        ),
        pass_check("plan.predicates", "plan declares relation and destination predicates")
        if {"has_opposite_corridor", "destination_region_entered"}.issubset(predicate_ids)
        else fail_check(
            "plan.predicates",
            "plan is missing expected composition predicates",
            {"predicate_ids": sorted(predicate_ids)},
        ),
    ]


def validate_execution_output(
    bound: Any,
    execution: Any,
    rows: list[dict[str, Any]],
    traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_class = Counter(str(row["classification"]) for row in rows)
    by_match = Counter(str(row["match_id"]) for row in rows)
    malformed = [
        {
            "result_id": row.get("result_id"),
            "missing": sorted(REQUIRED_RESULT_FIELDS - set(row)),
        }
        for row in rows
        if REQUIRED_RESULT_FIELDS - set(row)
    ]
    bad_relation_rows = [
        row["result_id"]
        for row in rows
        if row["destination_side"] == row["ball_side"]
        or float(row["relation_duration_seconds"]) < 0.8
        or int(row["relation_open_frame_id"]) > int(row["relation_close_frame_id"])
    ]
    trace_result_ids = {
        str(trace.get("source_evidence", {}).get("result_id", "")) for trace in traces
    }
    result_ids = {str(row["result_id"]) for row in rows}
    return [
        pass_check(
            "execution.external_plan_loaded",
            "runtime loaded and executed the external plan file",
            {"plan_path": str(PLAN_PATH), "execution_id": execution.execution_id},
        )
        if execution.provenance.get("plan_id") == bound.plan_id
        else fail_check("execution.external_plan_loaded", "execution provenance did not retain plan identity"),
        pass_check(
            "execution.result_breadth",
            "experimental composition yields real results across multiple matches",
            {"count": len(rows), "by_match": dict(sorted(by_match.items()))},
        )
        if len(rows) >= 20 and len(by_match) >= 3
        else fail_check(
            "execution.result_breadth",
            "experimental composition did not yield enough match-spanning results",
            {"count": len(rows), "by_match": dict(sorted(by_match.items()))},
        ),
        pass_check(
            "execution.classification_breadth",
            "experimental results classify both destination-entry outcomes",
            {"by_classification": dict(sorted(by_class.items()))},
        )
        if {"DESTINATION_ENTERED", "CORRIDOR_PERSISTED_NO_DESTINATION_ENTRY"}.issubset(by_class)
        else fail_check(
            "execution.classification_breadth",
            "experimental results did not include both outcome classes",
            {"by_classification": dict(sorted(by_class.items()))},
        ),
        pass_check("execution.result_shape", "every experimental result carries relation and destination evidence")
        if not malformed
        else fail_check(
            "execution.result_shape",
            "experimental results are missing required evidence",
            {"sample": malformed[:10]},
        ),
        pass_check(
            "execution.opposite_persistent_corridor",
            "every result uses an opposite-side corridor that persists for the configured minimum",
        )
        if not bad_relation_rows
        else fail_check(
            "execution.opposite_persistent_corridor",
            "one or more results failed the opposite-side/persistence contract",
            {"sample_result_ids": bad_relation_rows[:10]},
        ),
        pass_check("execution.result_traces", "experimental predicate traces reference final result IDs")
        if result_ids.issubset(trace_result_ids)
        else fail_check(
            "execution.result_traces",
            "one or more experimental results lack final-result predicate traces",
            {"missing_result_ids": sorted(result_ids - trace_result_ids)[:10]},
        ),
    ]


def validate_no_code_architecture() -> list[dict[str, Any]]:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    import_hits: list[dict[str, Any]] = []
    branch_hits: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("tqe.query"):
                    import_hits.append({"line": node.lineno, "module": alias.name})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("tqe.query"):
                import_hits.append({"line": node.lineno, "module": module})
        elif isinstance(node, ast.If):
            names = {child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)}
            attrs = {child.attr for child in ast.walk(node.test) if isinstance(child, ast.Attribute)}
            hit = sorted((names | attrs) & {"query_id", "recipe_id", "plan_id"})
            if hit:
                branch_hits.append({"line": node.lineno, "names": hit})

    detector_hits = []
    for path in Path("src/tqe/query").glob("*.py"):
        if path.name == "__init__.py":
            continue
        if "opposite" in path.name or "corridor" in path.name:
            detector_hits.append(str(path))
        text = path.read_text(encoding="utf-8")
        if "opposite_corridor_after_shift" in text:
            detector_hits.append(str(path))

    return [
        pass_check("architecture.executor_no_recipe_imports", "executor does not import recipe modules")
        if not import_hits
        else fail_check(
            "architecture.executor_no_recipe_imports",
            "executor imports recipe modules",
            {"import_hits": import_hits},
        ),
        pass_check("architecture.no_query_id_branch", "executor has no query/recipe/plan ID conditionals")
        if not branch_hits
        else fail_check(
            "architecture.no_query_id_branch",
            "executor branches on query/recipe/plan identity",
            {"branch_hits": branch_hits},
        ),
        pass_check("architecture.no_new_python_detector", "no Python detector was added for the experimental plan")
        if not detector_hits
        else fail_check(
            "architecture.no_new_python_detector",
            "experimental detector code appeared under src/tqe/query",
            {"detector_hits": sorted(set(detector_hits))},
        ),
    ]


def write_evidence_bundles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    table_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        result_id = str(row["result_id"])
        bundle_dir = EVIDENCE_ROOT / result_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        replay_path = bundle_dir / "replay.json"
        bundle_path = bundle_dir / "bundle.json"
        replay = replay_from_canonical(row, table_cache)
        write_json(replay_path, replay)
        bundle = {
            "schema_version": "1.0",
            "bundle_id": result_id,
            "generated_at": utc_now_iso(),
            "status": "pass",
            "plan_status": "experimental",
            "result_id": result_id,
            "classification": row["classification"],
            "query": {
                "query_id": row["query_id"],
                "query_version": row["query_version"],
                "query_hash": row["query_hash"],
            },
            "relation": {
                "relation_id": row["relation_id"],
                "relation_version": row["relation_version"],
                "open_frame_id": row["relation_open_frame_id"],
                "open_confirm_frame_id": row["relation_open_confirm_frame_id"],
                "close_frame_id": row["relation_close_frame_id"],
                "duration_seconds": row["relation_duration_seconds"],
                "target_player_id": row["relation_target_player_id"],
                "destination_region": row["destination_region"],
                "destination_side": row["destination_side"],
                "destination_lane": row["destination_lane"],
                "minimum_clearance_m": row["relation_minimum_clearance_m"],
                "limiting_defender_id": row["relation_limiting_defender_id"],
                "source_open_point": row["source_open_point"],
                "target_open_point": row["target_open_point"],
                "source_close_point": row["source_close_point"],
                "target_close_point": row["target_close_point"],
            },
            "destination_entry": {
                "entered": row["classification"] == "DESTINATION_ENTERED",
                "frame_id": row["destination_entry_frame_id"],
                "point": row["destination_entry_point"],
                "horizon_seconds": row["destination_entry_horizon_seconds"],
            },
            "base_result": {
                "base_result_id": row["base_result_id"],
                "source_classification": row["source_classification"],
                "wide_entry_frame_id": row["wide_entry_frame_id"],
                "anchor_frame_id": row["anchor_frame_id"],
                "ball_side": row["ball_side"],
                "signed_shift_metres": row["signed_shift_metres"],
            },
            "replay_reference": {"path": str(replay_path), "format": "static_json_frames"},
            "disallowed_claims": [
                "No pass probability is inferred.",
                "No optimality or decision-quality claim is emitted.",
                "No player intent, causation, or missed-opportunity claim is emitted.",
                "No match video is used.",
            ],
        }
        write_json(bundle_path, bundle)
        entries.append(
            {
                "result_id": result_id,
                "bundle_dir": str(bundle_dir),
                "bundle_json": str(bundle_path),
                "replay_json": str(replay_path),
                "classification": row["classification"],
                "match_id": row["match_id"],
                "plan_status": "experimental",
            }
        )

    manifest = {
        "schema_version": "1.0",
        "status": "pass",
        "generated_at": utc_now_iso(),
        "plan_status": "experimental",
        "bundle_count": len(entries),
        "evidence_bundles": entries,
    }
    write_json(BUNDLE_MANIFEST, manifest)
    return manifest


def replay_from_canonical(
    row: dict[str, Any],
    table_cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    match_id = str(row["match_id"])
    period = str(row["period"])
    orientation_path = DEFAULT_CANONICAL_ROOT / "orientation.parquet"
    start_frame_id = int(row["replay_start_frame_id"])
    end_frame_id = int(row["replay_end_frame_id"])
    tables = cached_period_tables(match_id, period, table_cache)
    frames_path = tables["frames_path"]
    positions_path = tables["positions_path"]
    frames_table = tables["frames"]
    positions_table = tables["positions"]

    frame_rows = frames_table[
        (frames_table.frame_id >= start_frame_id) & (frames_table.frame_id <= end_frame_id)
    ].sort_values("frame_id")
    position_rows = positions_table[
        (positions_table.frame_id >= start_frame_id)
        & (positions_table.frame_id <= end_frame_id)
    ].sort_values(["frame_id", "team_role", "entity_type", "entity_id"])

    positions_by_frame: dict[int, list[dict[str, Any]]] = {}
    for entity in position_rows.itertuples(index=False):
        positions_by_frame.setdefault(int(entity.frame_id), []).append(
            {
                "team_id": str(entity.team_id),
                "team_role": str(entity.team_role),
                "entity_id": str(entity.entity_id),
                "entity_type": str(entity.entity_type),
                "x_m": round(float(entity.x_m), 3),
                "y_m": round(float(entity.y_m), 3),
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": utc_now_iso(),
        "plan_status": "experimental",
        "result_id": row["result_id"],
        "match_id": match_id,
        "period": period,
        "frame_rate_hz": FRAME_RATE_HZ,
        "analysis_rate_hz": row["analysis_rate_hz"],
        "start_frame_id": start_frame_id,
        "end_frame_id": end_frame_id,
        "canonical_sources": {
            "frames": str(frames_path),
            "positions": str(positions_path),
            "orientation": str(orientation_path),
            "frames_sha256": tables["frames_sha256"],
            "positions_sha256": tables["positions_sha256"],
            "orientation_sha256": tables["orientation_sha256"],
        },
        "frames": [
            {
                "frame_id": int(frame.frame_id),
                "timestamp_utc": str(frame.timestamp_utc),
                "entities": positions_by_frame.get(int(frame.frame_id), []),
            }
            for frame in frame_rows.itertuples(index=False)
        ],
    }


def cached_period_tables(
    match_id: str,
    period: str,
    table_cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = (match_id, period)
    if key not in table_cache:
        frames_path = DEFAULT_CANONICAL_ROOT / "frames" / f"match_id={match_id}" / f"period={period}.parquet"
        positions_path = DEFAULT_CANONICAL_ROOT / "positions" / f"match_id={match_id}" / f"period={period}.parquet"
        table_cache[key] = {
            "frames_path": frames_path,
            "positions_path": positions_path,
            "frames": pq.ParquetFile(frames_path).read().to_pandas(),
            "positions": pq.ParquetFile(positions_path).read().to_pandas(),
            "frames_sha256": sha256_file(frames_path),
            "positions_sha256": sha256_file(positions_path),
            "orientation_sha256": sha256_file(DEFAULT_CANONICAL_ROOT / "orientation.parquet"),
        }
    return table_cache[key]


def validate_evidence_bundles(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    bundle_by_result = {entry["result_id"]: entry for entry in manifest["evidence_bundles"]}
    failures: list[dict[str, Any]] = []
    for row in rows:
        entry = bundle_by_result.get(str(row["result_id"]))
        if entry is None:
            failures.append({"result_id": row["result_id"], "reason": "missing_manifest_entry"})
            continue
        bundle_path = Path(entry["bundle_json"])
        replay_path = Path(entry["replay_json"])
        if not bundle_path.exists() or not replay_path.exists():
            failures.append({"result_id": row["result_id"], "reason": "missing_bundle_file"})
            continue
        bundle = read_json(bundle_path)
        replay = read_json(replay_path)
        required_frames = {
            int(row["wide_entry_frame_id"]),
            int(row["anchor_frame_id"]),
            int(row["relation_open_frame_id"]),
            int(row["relation_close_frame_id"]),
        }
        if row["destination_entry_frame_id"] is not None:
            required_frames.add(int(row["destination_entry_frame_id"]))
        replay_frame_ids = {int(frame["frame_id"]) for frame in replay.get("frames", [])}
        if (
            bundle.get("plan_status") != "experimental"
            or replay.get("plan_status") != "experimental"
            or bundle.get("result_id") != row["result_id"]
            or not replay.get("frames")
            or not required_frames.issubset(replay_frame_ids)
        ):
            failures.append(
                {
                    "result_id": row["result_id"],
                    "reason": "invalid_bundle_contract",
                    "missing_frames": sorted(required_frames - replay_frame_ids),
                }
            )

    return [
        pass_check(
            "evidence.bundles",
            "every experimental result has a replay and evidence bundle",
            {"bundle_count": manifest["bundle_count"]},
        )
        if not failures and manifest["bundle_count"] == len(rows)
        else fail_check(
            "evidence.bundles",
            "one or more experimental evidence bundles are missing or invalid",
            {"failure_count": len(failures), "sample": failures[:10]},
        )
    ]


def validate_experimental_status(
    result_report: dict[str, Any],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = result_report["results"]
    bad_rows = [row["result_id"] for row in rows if row.get("plan_status") != "experimental"]
    bad_bundles = [
        entry["result_id"]
        for entry in manifest["evidence_bundles"]
        if entry.get("plan_status") != "experimental"
    ]
    return [
        pass_check("status.result_report", "experimental status is explicit in the result report")
        if result_report.get("plan_status") == "experimental"
        else fail_check("status.result_report", "result report does not declare experimental status"),
        pass_check("status.every_result", "experimental status is explicit on every result")
        if not bad_rows
        else fail_check(
            "status.every_result",
            "one or more results lack experimental status",
            {"sample_result_ids": bad_rows[:10]},
        ),
        pass_check("status.bundle_manifest", "experimental status is explicit in the evidence manifest")
        if manifest.get("plan_status") == "experimental" and not bad_bundles
        else fail_check(
            "status.bundle_manifest",
            "bundle manifest does not consistently declare experimental status",
            {"sample_result_ids": bad_bundles[:10]},
        ),
    ]


def validate_no_forbidden_claim_surface(
    rows: list[dict[str, Any]],
    result_report: dict[str, Any],
) -> list[dict[str, Any]]:
    forbidden_fields = {
        "pass_probability",
        "optimality",
        "decision_quality",
        "player_intent",
        "causation",
        "missed_opportunity",
        "video",
    }
    hits = []
    for row in rows:
        overlap = sorted(forbidden_fields & set(row))
        if overlap:
            hits.append({"result_id": row["result_id"], "fields": overlap})
    cache_policy = result_report.get("cache_policy", {})
    return [
        pass_check("claims.no_forbidden_fields", "result evidence exposes no optimality/video/probability fields")
        if not hits
        else fail_check(
            "claims.no_forbidden_fields",
            "forbidden claim fields appeared in result evidence",
            {"sample": hits[:10]},
        ),
        pass_check("cache_policy.fresh_execution", "verifier ignored precomputed result artifacts")
        if cache_policy.get("precomputed_results_used") is False
        and cache_policy.get("precomputed_artifacts_ignored") is True
        else fail_check(
            "cache_policy.fresh_execution",
            "result report does not prove precomputed artifacts were ignored",
            {"cache_policy": cache_policy},
        ),
    ]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report = build_report()
    print(f"Wrote {VERIFY_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
