#!/usr/bin/env python3
"""Regenerate SCP2-1 meaning-expression round-trip evidence."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument  # noqa: E402
from tqe.semantic_compiler.meaning_expression import (  # noqa: E402
    load_meaning_expression_from_path,
    load_pack_vocabulary,
)
from tqe.semantic_compiler.target_synthesis import (  # noqa: E402
    synthesize_and_bind,
    target_file_payload,
    write_json,
)


PACKET_DIR = ROOT / "delivery" / "packets" / "scp2-1-roundtrip"
FIXTURE_DIR = PACKET_DIR / "meaning-expressions"
PLAN_DIR = PACKET_DIR / "plans"
REFUSAL_DIR = PACKET_DIR / "refusals"
EXECUTION_DIR = PACKET_DIR / "execution"
TARGETS_OUT = PACKET_DIR / "targets.v0.json"
REPORT_OUT = PACKET_DIR / "roundtrip-report.json"
LONG_RUN_THRESHOLD_SECONDS = 300.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live-execution", action="store_true")
    args = parser.parse_args()

    vocabulary = load_pack_vocabulary(ROOT / "generated" / "tactical-knowledge-pack.json")
    coverage_rows = json.loads((ROOT / "generated" / "coverage-map.json").read_text(encoding="utf-8"))
    accepted_targets: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "scp2_1_roundtrip_report.v0",
        "knowledge_pack": {
            "path": "generated/tactical-knowledge-pack.json",
            "sha256": vocabulary.pack_sha256,
            "primitive_count": len(vocabulary.primitive_names),
            "operator_count": len(vocabulary.operator_names),
            "gap_code_count": len(vocabulary.gap_codes),
        },
        "fixtures": [],
        "long_execution_threshold_seconds": LONG_RUN_THRESHOLD_SECONDS,
    }

    for fixture_path in sorted(FIXTURE_DIR.glob("*.json")):
        load_result = load_meaning_expression_from_path(fixture_path, vocabulary=vocabulary)
        fixture_record: dict[str, Any] = {
            "fixture": relative(fixture_path),
            "load_outcome": load_result.outcome,
        }
        if load_result.refusal is not None:
            refusal_payload = load_result.refusal.model_dump(mode="json")
            refusal_path = REFUSAL_DIR / f"{fixture_path.stem}.refusal.json"
            write_json(refusal_path, refusal_payload)
            fixture_record["refusal_path"] = relative(refusal_path)
            fixture_record["refusal"] = refusal_payload
            report["fixtures"].append(fixture_record)
            continue

        assert load_result.expression is not None
        expression = load_result.expression
        synthesized = synthesize_and_bind(expression, coverage_rows=coverage_rows)
        target = synthesized["target"]
        accepted_targets.append(target)
        plan_path = PLAN_DIR / f"{target['target_id']}.json"
        write_json(plan_path, synthesized["document"])
        fixture_record.update(
            {
                "expression_id": expression.expression_id,
                "target_id": target["target_id"],
                "concept": target["concept"],
                "target_path": relative(TARGETS_OUT),
                "plan_path": relative(plan_path),
                "document_hash": synthesized["document_hash"],
                "bind": synthesized["bind"],
                "build": synthesized["build"],
            }
        )
        ledger_row = next((row for row in coverage_rows if row.get("concept") == target["concept"]), None)
        if ledger_row and ledger_row.get("compiler_reachability_evidence"):
            expected = ledger_row["compiler_reachability_evidence"].get("document_hash")
            fixture_record["known_good_document_hash"] = expected
            fixture_record["known_good_document_hash_match"] = expected == synthesized["document_hash"]
        if target["concept"].startswith("scp2_1_") and not args.skip_live_execution:
            started = time.monotonic()
            execution_payload = execute_document(synthesized["document"])
            elapsed = time.monotonic() - started
            execution_path = EXECUTION_DIR / f"{target['target_id']}.execution.json"
            write_json(execution_path, execution_payload)
            fixture_record["execution_path"] = relative(execution_path)
            fixture_record["execution"] = {
                "status": execution_payload["status"],
                "result_count": execution_payload["result_count"],
                "elapsed_seconds": round(elapsed, 3),
                "exceeded_long_run_threshold": elapsed > LONG_RUN_THRESHOLD_SECONDS,
            }
        report["fixtures"].append(fixture_record)

    write_json(TARGETS_OUT, target_file_payload(accepted_targets))
    write_json(REPORT_OUT, report)
    print(json.dumps({"report": relative(REPORT_OUT), "target_count": len(accepted_targets)}, indent=2))
    return 0


def execute_document(document_payload: dict[str, Any]) -> dict[str, Any]:
    executor = TacticalQueryExecutor()
    if document_payload.get("schema_version") == "compiler_search_perspective_bundle.v1":
        role_payloads = document_payload["documents"]
    else:
        role_payloads = {"single": document_payload}
    roles: dict[str, Any] = {}
    total_rows = 0
    all_statuses: list[str] = []
    for role, payload in sorted(role_payloads.items()):
        document = TacticalQueryDocument.model_validate(payload)
        bound = bind_document(document)
        execution = executor.execute(bound)
        rows = execution_result_rows(execution)
        total_rows += len(rows)
        all_statuses.append(execution.status.value)
        roles[role] = {
            "status": execution.status.value,
            "result_count": len(rows),
            "provenance": execution.provenance,
            "rows": rows,
        }
    return {
        "status": "pass" if all(status == "pass" for status in all_statuses) else "fail",
        "result_count": total_rows,
        "roles": roles,
    }


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
