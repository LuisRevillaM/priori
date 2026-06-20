"""Emit a machine-readable not-ready report for gates outside the active slice."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_report(gate: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "gate": gate,
        "generated_at": utc_now_iso(),
        "status": "fail",
        "summary": {"pass": 0, "fail": 0, "not_ready": 1},
        "checks": [
            {
                "id": f"{gate}.active_slice",
                "status": "not_ready",
                "message": f"{gate} is blocked until prior M1 promotion gates are accepted.",
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.gate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.report}")
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
