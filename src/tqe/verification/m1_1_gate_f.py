"""Verify M1.1 Gate F: developer inspector and reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.inspector.m1_1 import (
    INSPECTOR_DATA,
    INSPECTOR_HTML,
    INSPECTOR_MANIFEST,
    build_inspector_artifacts,
)
from tqe.verification.m1_1_gate_e import build_report as build_gate_e_report

VERIFY_REPORT = Path("artifacts/m1.1/gate-f-verification-report.json")
GATE_E_REPORT = Path("artifacts/m1.1/gate-e-verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report(gate_e_report: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    gate_e = gate_e_report or existing_gate_e_report_or_build()
    checks.append(
        pass_check("gate_e.precondition", "Gate E verifier passes")
        if gate_e["status"] == "pass"
        else fail_check("gate_e.precondition", "Gate E must pass before Gate F")
    )

    manifest = build_inspector_artifacts()
    data = read_json(INSPECTOR_DATA)
    html = INSPECTOR_HTML.read_text(encoding="utf-8")

    checks.extend(validate_artifacts(manifest))
    checks.extend(validate_html_controls(html))
    checks.extend(validate_data_contract(data))
    checks.extend(validate_plan_results(data))
    checks.extend(validate_non_match_tester(data))
    checks.extend(validate_replay_reuse(data))
    checks.extend(validate_generic_shape(data))

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "gate": "Gate_F_developer_inspector_reports",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "artifacts": {
            "inspector_html": str(INSPECTOR_HTML),
            "inspector_data": str(INSPECTOR_DATA),
            "inspector_manifest": str(INSPECTOR_MANIFEST),
        },
        "checks": checks,
    }
    write_json(VERIFY_REPORT, report)
    return report


def existing_gate_e_report_or_build() -> dict[str, Any]:
    if GATE_E_REPORT.exists():
        report = read_json(GATE_E_REPORT)
        if report.get("status") == "pass":
            return report
    return build_gate_e_report()


def validate_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [
        Path(str(manifest["html"])),
        Path(str(manifest["data_json"])),
        Path(str(manifest["data_js"])),
        INSPECTOR_MANIFEST,
    ]
    missing = [str(path) for path in paths if not path.exists() or path.stat().st_size == 0]
    return [
        pass_check(
            "inspector.artifacts",
            "inspector HTML, data JSON, data JS, and manifest exist",
            {"paths": [str(path) for path in paths]},
        )
        if not missing
        else fail_check("inspector.artifacts", "inspector artifact files are missing", {"missing": missing}),
        pass_check("inspector.manifest_status", "inspector manifest reports pass")
        if manifest.get("status") == "pass"
        else fail_check("inspector.manifest_status", "inspector manifest did not report pass"),
    ]


def validate_html_controls(html: str) -> list[dict[str, Any]]:
    required_tokens = {
        "plan selector": 'id="planSelect"',
        "result list": 'id="resultRows"',
        "coordinate replay canvas": 'id="pitchCanvas"',
        "frame slider": 'id="frameSlider"',
        "predicate trace": 'id="traceRows"',
        "non-match tester": 'id="nonMatchSelect"',
        "raw evidence": 'id="rawEvidence"',
        "data script": "./inspector-data.js",
    }
    missing = [label for label, token in required_tokens.items() if token not in html]
    return [
        pass_check("inspector.html_controls", "inspector exposes all required developer controls")
        if not missing
        else fail_check(
            "inspector.html_controls",
            "inspector HTML is missing required controls",
            {"missing": missing},
        )
    ]


def validate_data_contract(data: dict[str, Any]) -> list[dict[str, Any]]:
    contract = data.get("inspector_contract", {})
    required = {
        "plan_selector",
        "validation_visible",
        "result_list",
        "coordinate_replay",
        "predicate_trace",
        "non_match_tester",
        "raw_evidence_values",
        "generic_result_shape",
        "reuses_existing_replay_bundles",
    }
    missing = sorted(key for key in required if contract.get(key) is not True)
    reports = data.get("validation_reports", [])
    failed_reports = [report for report in reports if report.get("status") != "pass"]
    return [
        pass_check("inspector.contract", "inspector data declares every Gate F capability")
        if not missing
        else fail_check("inspector.contract", "inspector contract is missing capabilities", {"missing": missing}),
        pass_check("inspector.validation_reports", "validation reports are visible and passing")
        if len(reports) >= 5 and not failed_reports
        else fail_check(
            "inspector.validation_reports",
            "validation reports are missing or failing",
            {"failed": failed_reports, "report_count": len(reports)},
        ),
    ]


def validate_plan_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    plans = data.get("plans", [])
    plan_ids = {plan.get("plan_id") for plan in plans}
    plan_failures: list[dict[str, Any]] = []
    for plan in plans:
        results = plan.get("results", [])
        validation = plan.get("validation", [])
        if not results or any(item.get("status") != "pass" for item in validation):
            plan_failures.append({"plan_id": plan.get("plan_id"), "reason": "empty_or_invalid_plan"})
            continue
        for result in results:
            if (
                not result.get("raw_evidence")
                or not result.get("predicate_traces")
                or not result.get("bundle", {}).get("raw")
                or not result.get("replay", {}).get("frames")
            ):
                plan_failures.append(
                    {
                        "plan_id": plan.get("plan_id"),
                        "result_id": result.get("result_id"),
                        "reason": "missing_inspection_surface",
                    }
                )
                break
    return [
        pass_check(
            "inspector.plan_selector_data",
            "approved and experimental plans are both available to the selector",
            {"plan_ids": sorted(str(item) for item in plan_ids)},
        )
        if {"ball_side_block_shift_ir_v1", "opposite_corridor_after_shift_experimental_v1"}.issubset(plan_ids)
        else fail_check(
            "inspector.plan_selector_data",
            "plan selector data is missing an expected plan",
            {"plan_ids": sorted(str(item) for item in plan_ids)},
        ),
        pass_check("inspector.results", "every plan exposes result rows, replay, traces, and raw evidence")
        if not plan_failures
        else fail_check(
            "inspector.results",
            "one or more plans/results lack required inspection surfaces",
            {"sample": plan_failures[:10]},
        ),
    ]


def validate_non_match_tester(data: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations = data.get("non_match_evaluations", [])
    statuses = {item.get("status") for item in evaluations}
    failures = [
        item
        for item in evaluations
        if not item.get("raw_evaluation")
        or ("failed_predicates" not in item and item.get("status") != "NO_COMPATIBLE_ANCHOR")
    ]
    return [
        pass_check("inspector.non_match_statuses", "non-match tester includes failure and no-anchor cases")
        if {"NON_MATCH", "NO_COMPATIBLE_ANCHOR"}.issubset(statuses)
        else fail_check(
            "inspector.non_match_statuses",
            "non-match tester lacks required statuses",
            {"statuses": sorted(str(status) for status in statuses)},
        ),
        pass_check("inspector.non_match_raw", "non-match tester exposes raw engine evaluations")
        if not failures
        else fail_check(
            "inspector.non_match_raw",
            "non-match tester is missing raw evaluations",
            {"sample": failures[:5]},
        ),
    ]


def validate_replay_reuse(data: dict[str, Any]) -> list[dict[str, Any]]:
    families = {
        result.get("replay", {}).get("source_artifact_family")
        for plan in data.get("plans", [])
        for result in plan.get("results", [])
    }
    paths = [
        str(result.get("replay", {}).get("path", ""))
        for plan in data.get("plans", [])
        for result in plan.get("results", [])
    ]
    missing_frames = [
        result.get("result_id")
        for plan in data.get("plans", [])
        for result in plan.get("results", [])
        if result.get("replay", {}).get("frame_count", 0) <= 0
    ]
    return [
        pass_check(
            "inspector.replay_reuse",
            "inspector reuses existing M1 and M1.1 replay bundles",
            {"families": sorted(str(item) for item in families)},
        )
        if {"m1_proof_pack", "m1_1_experimental_proof_pack"}.issubset(families)
        and any(path.startswith("artifacts/m1/evidence/") for path in paths)
        and any(path.startswith("artifacts/m1.1/experimental-evidence/") for path in paths)
        else fail_check(
            "inspector.replay_reuse",
            "inspector did not reuse expected replay bundle families",
            {"families": sorted(str(item) for item in families), "sample_paths": paths[:10]},
        ),
        pass_check("inspector.replay_frames", "coordinate replay frames are present for all results")
        if not missing_frames
        else fail_check(
            "inspector.replay_frames",
            "one or more results have empty replay frames",
            {"sample_result_ids": missing_frames[:10]},
        ),
    ]


def validate_generic_shape(data: dict[str, Any]) -> list[dict[str, Any]]:
    plans = data.get("plans", [])
    key_sets = {
        plan.get("plan_id"): set(plan.get("result_schema_keys", []))
        for plan in plans
    }
    approved = key_sets.get("ball_side_block_shift_ir_v1", set())
    experimental = key_sets.get("opposite_corridor_after_shift_experimental_v1", set())
    raw_union = set(data.get("result_key_union", []))
    return [
        pass_check(
            "inspector.generic_result_shape",
            "inspector carries a raw evidence union instead of fixed result shape panels",
            {"union_key_count": len(raw_union)},
        )
        if len(raw_union) >= 20
        and bool(approved)
        and bool(experimental)
        and bool(experimental - approved)
        and bool(approved - experimental)
        else fail_check(
            "inspector.generic_result_shape",
            "inspector data looks tied to one result shape",
            {
                "union_key_count": len(raw_union),
                "approved_only_count": len(approved - experimental),
                "experimental_only_count": len(experimental - approved),
            },
        )
    ]


def main() -> int:
    report = build_report()
    print(f"Wrote {VERIFY_REPORT}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
