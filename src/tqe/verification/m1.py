"""Aggregate M1 verification without overclaiming unfinished gates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.verification.gate_a import build_report as build_gate_a_report
from tqe.verification.gate_a import write_report as write_gate_a_report
from tqe.verification.gate_b import build_report as build_gate_b_report
from tqe.verification.gate_b import write_report as write_gate_b_report
from tqe.verification.gate_c import build_report as build_gate_c_report
from tqe.verification.gate_c import write_report as write_gate_c_report


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    gate_a = build_gate_a_report()
    write_gate_a_report(gate_a)
    gate_b = build_gate_b_report()
    write_gate_b_report(gate_b)
    gate_c = build_gate_c_report()
    write_gate_c_report(gate_c)

    reports = {"gate_a": gate_a, "gate_b": gate_b, "gate_c": gate_c}
    status = "pass" if all(report["status"] == "pass" for report in reports.values()) else "fail"
    aggregate = {
        "schema_version": "1.0",
        "milestone": "M1",
        "generated_at": utc_now_iso(),
        "status": status,
        "gate_reports": {
            name: {"status": report["status"], "summary": report["summary"]}
            for name, report in reports.items()
        },
        "next_required": [
            "Fix failing gate verification before accepting M1.",
        ]
        if status != "pass"
        else [],
    }
    report_path = Path("artifacts/m1/verification-report.json")
    write_json(report_path, aggregate)
    print(f"Wrote {report_path}")
    print(json.dumps({"status": aggregate["status"], "gate_reports": aggregate["gate_reports"]}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
