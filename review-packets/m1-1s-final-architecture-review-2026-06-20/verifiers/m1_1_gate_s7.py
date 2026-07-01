"""Verify M1.1S Gate S7: final architecture proof and packet readiness."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.executor import (
    execute_default_plan,
    execute_plan_from_path,
    execution_result_rows,
)
from tqe.verification.m1_1_gate_b import build_report as build_gate_b_report

S4_PLAN_PATH = Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json")
S6_PLAN_PATH = Path("config/query-plans/possession_corridor_availability.experimental.v1.json")
EXECUTOR_PATH = Path("src/tqe/runtime/executor.py")
REPORT_PATH = Path("artifacts/m1.1/gate-s7-verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pass_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "pass", "message": message, "details": details or {}}


def fail_check(check_id: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "status": "fail", "message": message, "details": details or {}}


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(validate_prior_gates())
    checks.extend(validate_m1_legacy_parity())
    checks.extend(validate_generic_plan_reproduction())
    checks.extend(validate_cache_independent_generic_reproduction())
    checks.extend(validate_source_coupling_boundaries())
    checks.extend(validate_external_packet_inputs_ready())

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.1S",
        "gate": "Gate_S7_parity_adapter_final_architecture_proof",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }
    write_json(REPORT_PATH, report)
    return report


def validate_prior_gates() -> list[dict[str, Any]]:
    required = {
        "s4": Path("artifacts/m1.1/gate-s4-verification-report.json"),
        "s5": Path("artifacts/m1.1/gate-s5-verification-report.json"),
        "s6": Path("artifacts/m1.1/gate-s6-verification-report.json"),
        "s3r": Path("artifacts/m1.1/gate-s3r-verification-report.json"),
    }
    reports: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    failing: dict[str, Any] = {}
    for name, path in required.items():
        if not path.exists():
            missing.append(str(path))
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        reports[name] = {"status": report.get("status"), "summary": report.get("summary")}
        if report.get("status") != "pass":
            failing[name] = reports[name]
    return [
        pass_check(
            "architecture.prior_s_gates_pass",
            "S3R, S4, S5, and S6 verification reports are passing",
            {"reports": reports},
        )
        if not missing and not failing
        else fail_check(
            "architecture.prior_s_gates_pass",
            "one or more required prior S-gate reports are missing or failing",
            {"missing": missing, "failing": failing, "reports": reports},
        )
    ]


def validate_m1_legacy_parity() -> list[dict[str, Any]]:
    gate_b = build_gate_b_report()
    _bound, execution = execute_default_plan()
    rows = execution_result_rows(execution)
    return [
        pass_check(
            "parity.explicit_legacy_path_exact",
            "M1 exact parity remains isolated behind the explicit legacy helper",
            {
                "gate_b_summary": gate_b.get("summary"),
                "result_count": len(rows),
                "trace_count": len(execution.predicate_traces),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
        if gate_b.get("status") == "pass"
        and len(rows) == 180
        and len(execution.predicate_traces) == 900
        and execution.provenance.get("compatibility_profile") == "legacy_m1_parity"
        else fail_check(
            "parity.explicit_legacy_path_exact",
            "M1 parity failed or did not use explicit legacy compatibility",
            {
                "gate_b_status": gate_b.get("status"),
                "gate_b_summary": gate_b.get("summary"),
                "result_count": len(rows),
                "trace_count": len(execution.predicate_traces),
                "compatibility_profile": execution.provenance.get("compatibility_profile"),
            },
        )
    ]


def validate_generic_plan_reproduction() -> list[dict[str, Any]]:
    s4_rows = execution_result_rows(execute_plan_from_path(S4_PLAN_PATH)[1])
    s6_rows = execution_result_rows(execute_plan_from_path(S6_PLAN_PATH)[1])
    return [
        pass_check(
            "architecture.generic_plans_reproduce",
            "S4 and S6 generic plans execute from canonical data with expected row counts",
            {
                "s4_count": len(s4_rows),
                "s6_count": len(s6_rows),
                "s4_labels": sorted({row["classification"] for row in s4_rows}),
                "s6_labels": sorted({row["classification"] for row in s6_rows}),
            },
        )
        if len(s4_rows) == 15
        and len(s6_rows) == 64
        and {row["classification"] for row in s6_rows} == {"PROGRESSIVE_CORRIDOR_AVAILABLE"}
        else fail_check(
            "architecture.generic_plans_reproduce",
            "S4 or S6 generic plan reproduction changed",
            {"s4_count": len(s4_rows), "s6_count": len(s6_rows)},
        )
    ]


def validate_cache_independent_generic_reproduction() -> list[dict[str, Any]]:
    baseline = {
        "s4": result_ids(execution_result_rows(execute_plan_from_path(S4_PLAN_PATH)[1])),
        "s6": result_ids(execution_result_rows(execute_plan_from_path(S6_PLAN_PATH)[1])),
    }
    temp_paths = [
        (Path("artifacts/m1.1"), Path("artifacts/m1.1.s7-cache-tmp")),
        (Path("generated"), Path("generated.s7-cache-tmp")),
    ]
    conflict = [str(tmp) for _src, tmp in temp_paths if tmp.exists()]
    if conflict:
        return [
            fail_check(
                "reproduction.generic_cache_independent",
                "temporary cache path already exists",
                {"conflicts": conflict},
            )
        ]
    moved: list[tuple[Path, Path]] = []
    try:
        for src, tmp in temp_paths:
            if src.exists():
                src.rename(tmp)
                moved.append((src, tmp))
        reproduced = {
            "s4": result_ids(execution_result_rows(execute_plan_from_path(S4_PLAN_PATH)[1])),
            "s6": result_ids(execution_result_rows(execute_plan_from_path(S6_PLAN_PATH)[1])),
        }
    finally:
        for src, tmp in reversed(moved):
            if tmp.exists() and not src.exists():
                tmp.rename(src)
    return [
        pass_check(
            "reproduction.generic_cache_independent",
            "generic S4 and S6 plans reproduce without generated/artifact caches",
            {"s4_count": len(baseline["s4"]), "s6_count": len(baseline["s6"])},
        )
        if baseline == reproduced
        else fail_check(
            "reproduction.generic_cache_independent",
            "generic plan result IDs changed when caches were unavailable",
            {
                "baseline": {key: len(value) for key, value in baseline.items()},
                "reproduced": {key: len(value) for key, value in reproduced.items()},
            },
        )
    ]


def validate_source_coupling_boundaries() -> list[dict[str, Any]]:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    experimental_predicate_ids = {
        "has_opposite_corridor",
        "destination_region_entered",
        "has_progressive_corridor",
    }
    approved_predicate_ids = {
        "wide_entry_threshold",
        "wide_entry_persists",
        "shift_threshold",
        "shift_persists",
        "not_stoppage",
    }
    generic_emit_body = function_body(source, "emit_generic_results_from_rules")
    generic_trace_body = function_body(source, "predicate_traces_from_declared_runtime_outputs")
    generic_bodies = "\n".join([generic_emit_body, generic_trace_body])
    generic_hits = sorted(
        item
        for item in approved_predicate_ids.union(experimental_predicate_ids)
        if item in generic_bodies
    )
    legacy_only_hits = sorted(
        item
        for item in experimental_predicate_ids
        if item in function_body(source, "experimental_predicate_traces_for_result")
    )
    return [
        pass_check(
            "architecture.generic_source_has_no_plan_predicate_ids",
            "generic result emission and generic trace construction contain no plan predicate IDs",
            {"checked_ids": sorted(approved_predicate_ids.union(experimental_predicate_ids))},
        )
        if not generic_hits
        else fail_check(
            "architecture.generic_source_has_no_plan_predicate_ids",
            "generic emission or trace source contains plan predicate IDs",
            {"hits": generic_hits},
        ),
        pass_check(
            "architecture.legacy_specific_literals_are_isolated",
            "remaining experimental predicate literals are isolated to legacy compatibility trace rewriting",
            {"legacy_only_hits": legacy_only_hits},
        )
        if legacy_only_hits == ["destination_region_entered", "has_opposite_corridor"]
        else fail_check(
            "architecture.legacy_specific_literals_are_isolated",
            "experimental predicate literals are missing or not isolated as expected",
            {"legacy_only_hits": legacy_only_hits},
        ),
    ]


def validate_external_packet_inputs_ready() -> list[dict[str, Any]]:
    required_paths = [
        Path("delivery/m1.1/STRUCTURAL_CORRECTIVE_SPEC.md"),
        Path("delivery/m1.1/status.yaml"),
        Path("delivery/ledger.jsonl"),
        Path("delivery/m1.1/reviews/gate-s4r-controller-review.md"),
        Path("delivery/m1.1/reviews/gate-s5-controller-review.md"),
        Path("delivery/m1.1/reviews/gate-s6-controller-review.md"),
        Path("docs/reviews/2026-06-20-m1-1s-gate-s4-external-review.md"),
        Path("config/query-plans/opposite_corridor_after_shift.experimental.v1.json"),
        Path("config/query-plans/possession_corridor_availability.experimental.v1.json"),
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    return [
        pass_check(
            "packet.inputs_ready",
            "source-of-truth files for external packet are present",
            {"path_count": len(required_paths)},
        )
        if not missing
        else fail_check(
            "packet.inputs_ready",
            "external packet source files are missing",
            {"missing": missing},
        )
    ]


def result_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["result_id"]) for row in rows]


def function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
