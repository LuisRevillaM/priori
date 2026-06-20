"""Aggregate M1.1 verification state without overclaiming unfinished gates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.verification.m1_1_gate_a import build_report as build_gate_a_report
from tqe.verification.m1_1_gate_b import build_report as build_gate_b_report
from tqe.verification.m1_1_gate_c import build_report as build_gate_c_report
from tqe.verification.m1_1_gate_d import build_report as build_gate_d_report
from tqe.verification.m1_1_gate_e import build_report as build_gate_e_report
from tqe.verification.m1_1_gate_f import build_report as build_gate_f_report

REPORT_PATH = Path("artifacts/m1.1/verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    gate_a = build_gate_a_report()
    gate_b = build_gate_b_report()
    gate_c = build_gate_c_report(gate_b)
    gate_d = build_gate_d_report(gate_c)
    gate_e = build_gate_e_report(gate_d)
    gate_f = build_gate_f_report(gate_e)
    gate_reports = {
        "gate_a": gate_a,
        "gate_b": gate_b,
        "gate_c": gate_c,
        "gate_d": gate_d,
        "gate_e": gate_e,
        "gate_f": gate_f,
    }
    summary = {
        "pass": sum(report["summary"]["pass"] for report in gate_reports.values()),
        "fail": sum(report["summary"]["fail"] for report in gate_reports.values()),
        "not_ready": sum(report["summary"]["not_ready"] for report in gate_reports.values()),
    }
    aggregate = {
        "schema_version": "1.0",
        "milestone": "M1.1",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 and summary["not_ready"] == 0 else "not_ready",
        "summary": summary,
        "gate_reports": {
            name: {"status": report["status"], "summary": report["summary"]}
            for name, report in gate_reports.items()
        },
        "next_required": [],
    }
    write_json(REPORT_PATH, aggregate)
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps({"status": aggregate["status"], "summary": aggregate["summary"]}, sort_keys=True))
    return 0 if aggregate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
