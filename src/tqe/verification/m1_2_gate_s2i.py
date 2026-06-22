"""Verify M1.2 S2I-A Tactical Knowledge Pack artifacts."""

from __future__ import annotations

from pathlib import Path

from tqe.workshop.knowledge_pack import (
    PACK_JSON_PATH,
    PACK_MD_PATH,
    verify_tactical_knowledge_pack,
    write_json,
    write_tactical_knowledge_pack,
)
from tqe.workshop.m1_2 import utc_now_iso


REPORT_PATH = Path("artifacts/m1.2/gate-s2i-verification-report.json")


def main() -> None:
    pack = write_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    checks = verify_tactical_knowledge_pack(PACK_JSON_PATH, PACK_MD_PATH)
    report = {
        "schema_version": "1.0",
        "gate": "S2I_A_tactical_knowledge_pack",
        "generated_at": utc_now_iso(),
        "knowledge_pack_path": str(PACK_JSON_PATH),
        "knowledge_pack_markdown_path": str(PACK_MD_PATH),
        "knowledge_pack_sha256": pack["knowledge_pack_sha256"],
        "checks": checks,
        "passed": all(item["ok"] for item in checks),
    }
    write_json(REPORT_PATH, report)
    passed = sum(1 for item in checks if item["ok"])
    failed = len(checks) - passed
    print(f"S2I-A verification: {passed} passed, {failed} failed")
    print(f"Report: {REPORT_PATH}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
