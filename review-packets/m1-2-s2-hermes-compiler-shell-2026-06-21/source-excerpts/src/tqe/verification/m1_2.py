"""Aggregate verifier for M1.2 active gates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqe.verification import m1_2_gate_s0, m1_2_gate_s1, m1_2_gate_s2

REPORT_PATH = Path("artifacts/m1.2/verification-report.json")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_report() -> dict[str, Any]:
    s0 = m1_2_gate_s0.build_report()
    s1 = m1_2_gate_s1.build_report()
    s2 = m1_2_gate_s2.build_report()
    checks = [
        {"id": "m1_2.s0", "status": s0["status"], "summary": s0["summary"]},
        {"id": "m1_2.s1", "status": s1["status"], "summary": s1["summary"]},
        {"id": "m1_2.s2", "status": s2["status"], "summary": s2["summary"]},
    ]
    summary = {
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] != "pass"),
    }
    report = {
        "schema_version": "1.0",
        "milestone": "M1.2",
        "scope": "S0_S1_S2_hermes_workshop",
        "generated_at": utc_now_iso(),
        "status": "pass" if summary["fail"] == 0 else "fail",
        "summary": summary,
        "checks": checks,
        "reports": {
            "s0": str(m1_2_gate_s0.REPORT_PATH),
            "s1": str(m1_2_gate_s1.REPORT_PATH),
            "s2": str(m1_2_gate_s2.REPORT_PATH),
        },
    }
    write_json(REPORT_PATH, report)
    return report


def main() -> None:
    report = build_report()
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
