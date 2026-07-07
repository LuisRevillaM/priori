"""EXAM-1 E1: threshold sensitivity sweeps (director-authored).

Sweeps one declared numeric parameter of a committed meaning
expression across a grid, running every point through the real
synthesize -> certify -> execute path with the node cache on, and
publishes the sensitivity curve with the honest interval at every
point. R-AZ layout: runs/<timestamp>-<script sha12>/, self-stamped,
overwrite-refusing.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tqe.semantic_compiler import meaning_expression as me  # noqa: E402
from tqe.semantic_compiler.target_synthesis import synthesize_and_bind  # noqa: E402
from tqe.workshop.app_service import film_room_answer_from_document  # noqa: E402


def script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ0000")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")


def set_parameter(raw: dict[str, Any], target: str, value: float) -> tuple[dict[str, Any], int]:
    """Set every occurrence of the named numeric parameter/field; return copy + hit count."""
    mutated = copy.deepcopy(raw)
    hits = 0

    def walk(obj: Any) -> None:
        nonlocal hits
        if isinstance(obj, dict):
            if obj.get("name") == target and isinstance(obj.get("value"), (int, float)):
                obj["value"] = value
                hits += 1
            if obj.get("field") == target and isinstance(obj.get("value"), (int, float)):
                obj["value"] = value
                hits += 1
            for key, child in obj.items():
                if key == target and isinstance(child, (int, float)) and not isinstance(child, bool):
                    obj[key] = value
                    hits += 1
                else:
                    walk(child)
        elif isinstance(obj, list):
            for child in obj:
                walk(child)

    walk(mutated)
    return mutated, hits


def rate_summary_from_payload(execution: dict[str, Any]) -> dict[str, Any]:
    rows = []
    inner = execution.get("execution", execution) if isinstance(execution.get("execution"), dict) else execution
    for result in inner.get("results", []) or []:
        evidence = result.get("evidence") if isinstance(result, dict) else None
        if not isinstance(evidence, dict):
            evidence = result if isinstance(result, dict) else {}
        if isinstance(evidence, dict) and any(k in evidence for k in ("observed", "lower_bound", "a_count")):
            rows.append(
                {
                    k: evidence.get(k)
                    for k in (
                        "group_key", "observed", "lower_bound", "upper_bound",
                        "a_count", "b_count", "c_count", "d1_count", "d2_count",
                        "e_count", "unknown_count", "population_count",
                    )
                }
            )
    return {
        "role": execution.get("role"),
        "status": inner.get("execution_status", inner.get("status")),
        "result_count": inner.get("total_result_count", len(inner.get("results", []) or [])),
        "requested_evidence_failure_count": inner.get("requested_evidence_failure_count"),
        "rate_rows": rows,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(Path(args.expression).read_text())
    grid = [float(v) for v in args.grid.split(",")]
    run_dir = ROOT / "delivery/packets/exam-1-evidence/runs" / f"{utc_stamp()}-{script_sha256()[:12]}"

    points: list[dict[str, Any]] = []
    for value in grid:
        mutated = raw
        hits = 0
        for target in args.parameter.split(","):
            mutated, target_hits = set_parameter(mutated, target.strip(), value)
            if target_hits == 0:
                raise RuntimeError(f"parameter {target} not found in expression")
            hits += target_hits
        expression = me.MeaningExpressionV0.model_validate(mutated)
        refusal = me.first_vocabulary_refusal(
            expression=expression, vocabulary=me.load_pack_vocabulary()
        )
        if refusal is not None:
            points.append({"value": value, "outcome": "refusal", "refusal": refusal.model_dump(mode="json")})
            continue
        started = time.perf_counter()
        synthesized = synthesize_and_bind(expression)
        synth_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        answer = film_room_answer_from_document(
            synthesized["document"],
            expression_payload=mutated,
            expression_hash=None,
            synthesized_document_hash=str(synthesized["document_hash"]),
            output_root=Path(args.output_root),
        )
        exec_ms = (time.perf_counter() - started) * 1000.0
        points.append(
            {
                "value": value,
                "outcome": "executed",
                "parameter_occurrences_set": hits,
                "document_hash": str(synthesized["document_hash"]),
                "synthesis_ms": round(synth_ms, 3),
                "execution_ms": round(exec_ms, 3),
                "interval_metric": answer.get("interval_metric"),
                "moment_total_count": answer.get("moment_total_count"),
                "evidence_rows_kind": answer.get("evidence_rows_kind"),
            }
        )

    payload = {
        "evidence_metadata": {
            "producing_script": "scripts/exam/threshold_sweep.py",
            "producing_script_sha256": script_sha256(),
            "run_started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "expression": args.expression,
            "parameter": args.parameter,
            "grid": grid,
        },
        "points": points,
    }
    write_json(run_dir / f"sweep-{args.parameter}.json", payload)
    return {"run_dir": str(run_dir), "points": len(points)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expression", required=True)
    parser.add_argument("--parameter", required=True, help="comma-separated coherent set: every listed parameter/field is set to the value (e.g. operator param + its describing clause field)")
    parser.add_argument("--grid", required=True, help="comma-separated values")
    parser.add_argument("--output-root", default="artifacts/exam-output")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(args)))


if __name__ == "__main__":
    main()
