"""Verify M1.1R Gate R2: typed runtime values and invocation semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows
from tqe.runtime.ir import ExecutionMode, ExecutionStatus

PLAN_PATH = Path("config/query-plans/ball_side_block_shift.ir.v1.json")
REPORT_PATH = Path("artifacts/m1.1/gate-r2-verification-report.json")


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
    bound = bind_document_from_path(PLAN_PATH)
    executor = TacticalQueryExecutor()

    execution = executor.execute(bound)
    rows = execution_result_rows(execution)
    checks.append(
        pass_check(
            "runtime.execute_mode",
            "execute mode runs the match executor",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "max_results": bound.max_results,
                "runtime_value_count": execution.provenance.get("runtime_value_count"),
            },
        )
        if execution.status == ExecutionStatus.PASS
        and len(rows) == bound.max_results
        and execution.provenance.get("execution_mode") == "execute"
        and int(execution.provenance.get("runtime_value_count", 0)) > 0
        else fail_check(
            "runtime.execute_mode",
            "execute mode did not produce a conforming execution",
            {
                "status": execution.status.value,
                "result_count": len(rows),
                "max_results": bound.max_results,
                "provenance": execution.provenance,
            },
        )
    )

    bind_only = executor.execute(bound.model_copy(update={"execution_mode": ExecutionMode.BIND_ONLY}))
    checks.append(
        pass_check("runtime.bind_only", "bind_only skips match execution")
        if bind_only.status == ExecutionStatus.NOT_STARTED
        and not bind_only.results
        and bind_only.provenance.get("skipped_reason") == "bind_only"
        else fail_check(
            "runtime.bind_only",
            "bind_only produced results or wrong status",
            {"status": bind_only.status.value, "result_count": len(bind_only.results), "provenance": bind_only.provenance},
        )
    )

    dry_run = executor.execute(bound.model_copy(update={"execution_mode": ExecutionMode.DRY_RUN}))
    checks.append(
        pass_check("runtime.dry_run", "dry_run validates without match results")
        if dry_run.status == ExecutionStatus.PASS
        and not dry_run.results
        and dry_run.provenance.get("skipped_reason") == "dry_run"
        else fail_check(
            "runtime.dry_run",
            "dry_run produced results or wrong status",
            {"status": dry_run.status.value, "result_count": len(dry_run.results), "provenance": dry_run.provenance},
        )
    )

    limited_bound = bound.model_copy(update={"max_results": 1})
    limited_first = executor.execute(limited_bound)
    limited_second = executor.execute(limited_bound)
    checks.append(
        pass_check(
            "runtime.max_results",
            "max_results truncates deterministically",
            {
                "result_id": limited_first.results[0].result_id if limited_first.results else None,
                "execution_id": limited_first.execution_id,
            },
        )
        if len(limited_first.results) == 1
        and [item.result_id for item in limited_first.results]
        == [item.result_id for item in limited_second.results]
        and limited_first.execution_id == limited_second.execution_id
        else fail_check(
            "runtime.max_results",
            "max_results is not honored deterministically",
            {
                "first_count": len(limited_first.results),
                "second_count": len(limited_second.results),
                "first_ids": [item.result_id for item in limited_first.results],
                "second_ids": [item.result_id for item in limited_second.results],
            },
        )
    )

    summary = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
        "not_ready": sum(1 for check in checks if check["status"] == "not_ready"),
    }
    return {
        "schema_version": "1.0",
        "milestone": "M1.1R",
        "gate": "Gate_R2_typed_runtime_values_invocation_semantics",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
    }


def main() -> int:
    report = build_report()
    write_json(REPORT_PATH, report)
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
