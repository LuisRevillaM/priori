#!/usr/bin/env python3
"""SEAM-1 R-AZ evidence producer.

Writes a fresh, overwrite-refusing run directory with script hash, timestamp,
git identity, focused-test output, denominator equivalence, refusal evidence,
and payload-contract evidence.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tqe.semantic_compiler.meaning_expression import load_meaning_expression_result, load_pack_vocabulary  # noqa: E402
from tqe.workshop.app_service import film_room_interval_metric, film_room_interval_metric_from_evidence  # noqa: E402
from tqe.workshop.m1_2 import rank_result  # noqa: E402

TABLE_PATH = ROOT / "delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_table.json"
EXPRESSION_PATH = (
    ROOT / "delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json"
)
DOC_PATH = ROOT / "docs/EXECUTION_PAYLOAD_CONTRACT.md"
EVIDENCE_ROOT = ROOT / "delivery/packets/seam-1-evidence/runs"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ0000")


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def metadata() -> dict[str, Any]:
    script = Path(__file__).resolve()
    return {
        "schema_version": "seam1.evidence_metadata.v1",
        "producing_script": str(script.relative_to(ROOT)),
        "producing_script_sha256": file_sha256(script),
        "run_started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(args: list[str], *, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {output_path}")
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    output_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return {
        "command": args,
        "returncode": completed.returncode,
        "output_path": str(output_path.relative_to(ROOT)),
    }


def runtime_rows_from_certified_table(table: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {**period_record["rate"], "audit_role": row["audit_role"]}
        for row in table["rows"]
        for period_record in row["periods"]
        if isinstance(period_record.get("rate"), dict)
    ]


def numeric_refusal_payload() -> dict[str, Any]:
    payload = read_json(EXPRESSION_PATH)
    mutated = copy.deepcopy(payload)
    for clause in mutated["meaning_clauses"]:
        if clause.get("field") == "carry_forward_progression_m":
            clause["value"] = 8.0
    result = load_meaning_expression_result(mutated, vocabulary=load_pack_vocabulary())
    return {
        "mutation": "meaning_clauses carry_forward_progression_m value 3.0 -> 8.0; executable parameter remains 3.0",
        "outcome": result.outcome,
        "refusal": result.refusal.model_dump(mode="json") if result.refusal else None,
    }


def payload_contract_probe() -> dict[str, Any]:
    ranked = rank_result(
        {
            "result_id": "seam1-contract-probe",
            "classification": "UNKNOWN",
            "match_id": "J03WOY",
            "period": "firstHalf",
            "anchor_frame_id": 100,
            "requested_evidence": {},
        },
        rank=1,
    )
    return {
        "ranked_response": ranked,
        "doc_path": str(DOC_PATH.relative_to(ROOT)),
        "doc_sha256": file_sha256(DOC_PATH),
        "moment_total_count_definition": (
            "number of distinct Film Room moment rows assembled for replay/overlay display; "
            "not the rate denominator and not a population count"
        ),
    }


def build_evidence(run_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    table = read_json(TABLE_PATH)
    certified_metric = film_room_interval_metric(table)
    runtime_metric = film_room_interval_metric_from_evidence(runtime_rows_from_certified_table(table))
    count_fields = ("a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count", "population_count")
    counts_equal = bool(
        certified_metric
        and runtime_metric
        and all(certified_metric["source"].get(field) == runtime_metric["source"].get(field) for field in count_fields)
    )
    focused_tests = run_command(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_film_room_app",
            "tests.test_scp2_1_meaning_to_target.SCP2MeaningToTargetTests.test_numeric_meaning_clause_must_match_executable_parameter_value",
            "-v",
        ],
        output_path=run_dir / "focused-tests.txt",
    )
    return {
        "evidence_metadata": meta,
        "root_cause": (
            "Before SEAM-1, Film Room's runtime interval fallback read rate evidence from returned chain-result rows, "
            "so result ordering/result_limit could select one chain-group denominator while the certified path used "
            "the full declared R2-4 per-regain partition."
        ),
        "denominator_declaration": {
            "ratified_question": "per-regain rate",
            "declared_denominator_status_field": "stage_1_status",
            "declared_denominator_label": "per regain start",
            "table_path": str(TABLE_PATH.relative_to(ROOT)),
            "table_sha256": file_sha256(TABLE_PATH),
        },
        "certified_runtime_equivalence": {
            "certified_metric": certified_metric,
            "runtime_metric_from_declared_partitions": runtime_metric,
            "count_fields": list(count_fields),
            "counts_equal": counts_equal,
            "cache_provenance": (
                "This evidence script does not consult the execution cache; it compares committed certified partitions "
                "to the same declared rate partition shape consumed from runtime requested-evidence source summaries."
            ),
        },
        "numeric_clause_parameter_refusal": numeric_refusal_payload(),
        "payload_contract": payload_contract_probe(),
        "focused_tests": focused_tests,
    }


def main() -> None:
    meta = metadata()
    run_dir = EVIDENCE_ROOT / f"{utc_stamp()}-{meta['producing_script_sha256'][:12]}"
    if run_dir.exists():
        raise RuntimeError(f"refusing to reuse evidence directory: {run_dir}")
    run_dir.mkdir(parents=True)
    evidence = build_evidence(run_dir, meta)
    write_json(run_dir / "seam1-evidence.json", evidence)
    print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), "focused_tests": evidence["focused_tests"]}, sort_keys=True))


if __name__ == "__main__":
    main()
