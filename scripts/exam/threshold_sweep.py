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

from tqe.runtime.executor import TacticalQueryExecutor  # noqa: E402
from tqe.semantic_compiler import meaning_expression as me  # noqa: E402
from tqe.semantic_compiler import target_synthesis as ts  # noqa: E402


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


def rate_summary(execution: Any) -> dict[str, Any]:
    rows = []
    for result in execution.results:
        evidence = getattr(result, "evidence", None) or {}
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
    return {"status": execution.status.value, "result_count": len(execution.results), "rate_rows": rows}


def run(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(Path(args.expression).read_text())
    grid = [float(v) for v in args.grid.split(",")]
    run_dir = ROOT / "delivery/packets/exam-1-evidence/runs" / f"{utc_stamp()}-{script_sha256()[:12]}"
    cache_root = Path(args.cache_root) if args.cache_root else None

    points: list[dict[str, Any]] = []
    for value in grid:
        mutated, hits = set_parameter(raw, args.parameter, value)
        if hits == 0:
            raise RuntimeError(f"parameter {args.parameter} not found in expression")
        expression = me.MeaningExpressionV0.model_validate(mutated)
        refusal = me.first_vocabulary_refusal(
            expression=expression, vocabulary=me.load_pack_vocabulary()
        )
        if refusal is not None:
            points.append({"value": value, "outcome": "refusal", "refusal": refusal.model_dump(mode="json")})
            continue
        started = time.perf_counter()
        bound = ts.synthesize_and_bind(expression=expression)
        synth_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        executor = TacticalQueryExecutor(enable_node_cache=True, node_cache_root=cache_root, parallel_workers=args.workers)
        execution = executor.execute(bound.bound_plan)
        exec_ms = (time.perf_counter() - started) * 1000.0
        points.append(
            {
                "value": value,
                "outcome": "executed",
                "parameter_occurrences_set": hits,
                "document_hash": bound.document_hash,
                "synthesis_ms": round(synth_ms, 3),
                "execution_ms": round(exec_ms, 3),
                "summary": rate_summary(execution),
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
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--grid", required=True, help="comma-separated values")
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(args)))


if __name__ == "__main__":
    main()
