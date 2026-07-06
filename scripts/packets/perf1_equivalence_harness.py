#!/usr/bin/env python3
"""PERF-1 equivalence and timing evidence harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import (  # noqa: E402
    CACHE_SCHEMA_VERSION,
    TacticalQueryExecutor,
    execution_result_rows,
    runtime_code_epoch,
)
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402

EVIDENCE_ROOT = ROOT / "delivery" / "packets" / "perf-1-evidence" / "runs"
PACKET_PATH = ROOT / "delivery" / "packets" / "PERF-1-cold-ask-latency.md"
KEY_SCHEMA_PATH = ROOT / "delivery" / "packets" / "PERF-1-KEY-SCHEMA.md"
DEFAULT_WORKERS = 4
LONG_RUN_THRESHOLD_SECONDS = 300.0

DECLARED_PLAN_SET: list[dict[str, Any]] = [
    {
        "plan_set_id": "flagship_fragile_retention_rate",
        "kind": "flagship_committed_document",
        "path": "delivery/packets/r2-2-flagship/fragile_retention_rate_v0.json",
    },
    {
        "plan_set_id": "flagship_counterattack_initiation",
        "kind": "flagship_committed_document",
        "path": "delivery/packets/r2-4-flagship/counterattack_initiation_v0.json",
    },
    {
        "plan_set_id": "scp2_1_body_orientation_oov",
        "kind": "scp2_1_refusal_fixture",
        "path": "delivery/packets/scp2-1-roundtrip/meaning-expressions/body_orientation_oov.v0.json",
        "refusal_path": "delivery/packets/scp2-1-roundtrip/refusals/body_orientation_oov.v0.refusal.json",
    },
    {
        "plan_set_id": "scp2_1_fragile_possession_state_known",
        "kind": "scp2_1_committed_document",
        "path": "delivery/packets/scp2-1-roundtrip/plans/r1_5_fragile_possession_state_v0.json",
    },
    {
        "plan_set_id": "scp2_1_fragile_window_join_count_novel",
        "kind": "scp2_1_committed_document",
        "path": "delivery/packets/scp2-1-roundtrip/plans/scp2_1_fragile_window_join_count_v0.json",
    },
    {
        "plan_set_id": "novel_live_scp2_3_cold_document",
        "kind": "prior_live_synthesized_document",
        "source_response": (
            "delivery/packets/scp2-3-evidence/runs/"
            "2026-07-06T073846Z0000-06516dd4e3d5/film-room-cold-response.json"
        ),
        "document_pointer": "answer.document",
    },
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else "unknown"


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_once(path: Path, payload: dict[str, Any], metadata: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"evidence_metadata": metadata, **payload}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite evidence file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_run_dir(script_sha: str) -> Path:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    for index in range(10_000):
        candidate = EVIDENCE_ROOT / f"{timestamp}{index:04d}-{script_sha[:12]}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise RuntimeError("could not allocate unique PERF-1 evidence run directory")


def evidence_metadata(args: argparse.Namespace, *, run_dir: Path, script_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "perf1.evidence_metadata.v1",
        "produced_by": relative(Path(__file__).resolve()),
        "producing_script_sha256": script_sha,
        "run_started_at": utc_now(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_tree": git_value("rev-parse", "HEAD^{tree}"),
        "git_branch": git_value("branch", "--show-current"),
        "run_dir": relative(run_dir),
        "packet": {"path": relative(PACKET_PATH), "sha256": file_sha256(PACKET_PATH)},
        "key_schema": {"path": relative(KEY_SCHEMA_PATH), "sha256": file_sha256(KEY_SCHEMA_PATH)},
        "script_args": vars(args),
    }


def selected_plan_set(plan_set_ids: list[str]) -> list[dict[str, Any]]:
    if not plan_set_ids:
        return list(DECLARED_PLAN_SET)
    requested = set(plan_set_ids)
    selected = [record for record in DECLARED_PLAN_SET if record["plan_set_id"] in requested]
    missing = sorted(requested - {record["plan_set_id"] for record in selected})
    if missing:
        raise RuntimeError(f"unknown plan_set_id(s): {', '.join(missing)}")
    return selected


def document_payload(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "source_response" in record:
        source_path = ROOT / record["source_response"]
        response = read_json(source_path)
        payload = response["answer"]["document"]
        source = {
            "source_response": record["source_response"],
            "source_response_sha256": file_sha256(source_path),
            "source_response_stable_hash": stable_hash(response),
            "document_stable_hash": stable_hash(payload),
            "source_latency_breakdown_ms": response.get("latency_breakdown_ms", {}),
            "source_runtime_commit": response.get("answer", {}).get("provenance", {}).get("runtime_commit"),
            "source_runtime_tree": response.get("answer", {}).get("provenance", {}).get("tree"),
            "source_request_text": response.get("request_text"),
            "source_provider": response.get("provider"),
            "source_model": response.get("model"),
        }
        return payload, source
    path = ROOT / record["path"]
    payload = read_json(path)
    return payload, {
        "path": record["path"],
        "sha256": file_sha256(path),
        "stable_hash": stable_hash(payload),
    }


def role_documents(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if isinstance(payload.get("documents"), dict):
        return {str(role): document for role, document in sorted(payload["documents"].items())}
    return {"single": payload}


def bind_role(document: dict[str, Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    bound = bind_document(TacticalQueryDocument.model_validate(document))
    return bound, elapsed_ms(started)


def execute_variant(
    *,
    bound_plan: Any,
    variant: str,
    cache_root: Path | None,
    workers: int,
) -> tuple[Any, float]:
    started = time.perf_counter()
    executor = TacticalQueryExecutor(
        enable_node_cache=variant != "sequential",
        node_cache_root=cache_root,
        parallel_workers=1 if variant == "sequential" else workers,
    )
    execution = executor.execute(bound_plan)
    return execution, elapsed_ms(started)


def canonical_execution_payload(execution: Any) -> dict[str, Any]:
    return {
        "status": execution.status.value,
        "execution_id": execution.execution_id,
        "plan_hash": execution.plan_hash,
        "bound_plan_hash": execution.bound_plan_hash,
        "rows": execution_result_rows(execution),
        "predicate_traces": [
            trace.model_dump(mode="json", exclude_none=True)
            for trace in execution.predicate_traces
        ],
    }


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def cache_inventory(cache_root: Path) -> dict[str, Any]:
    files = sorted(path for path in cache_root.rglob("*.json") if path.is_file()) if cache_root.exists() else []
    return {
        "root": relative(cache_root),
        "entry_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "sample_entries": [relative(path) for path in files[:10]],
    }


def node_cache_summary(execution: Any) -> dict[str, Any]:
    return dict(execution.provenance.get("node_cache") or {})


def timing_record(
    *,
    plan_set_id: str,
    role: str,
    variant: str,
    bind_ms: float,
    external_execute_ms: float,
    execution: Any,
    source_latency_breakdown_ms: dict[str, Any] | None,
    long_run_threshold_seconds: float,
) -> dict[str, Any]:
    timing = dict(execution.timing_ms or {})
    duration_seconds = external_execute_ms / 1000.0
    return {
        "plan_set_id": plan_set_id,
        "role": role,
        "variant": variant,
        "hermes_ms": source_latency_breakdown_ms.get("hermes") if source_latency_breakdown_ms else None,
        "synthesis_ms": source_latency_breakdown_ms.get("synthesis") if source_latency_breakdown_ms else None,
        "bind_ms": bind_ms,
        "execute_external_ms": external_execute_ms,
        "execute_total_ms": timing.get("total_ms"),
        "period_execution_ms": timing.get("period_execution_ms"),
        "merge_apply_result_semantics_ms": timing.get("merge_apply_result_semantics_ms"),
        "period_count": len(timing.get("periods") or []),
        "result_count": len(execution.results),
        "trace_count": len(execution.predicate_traces),
        "status": execution.status.value,
        "node_cache": node_cache_summary(execution),
        "exceeded_long_run_threshold": duration_seconds > long_run_threshold_seconds,
        "long_run_threshold_seconds": long_run_threshold_seconds,
    }


def execute_plan_set(
    *,
    record: dict[str, Any],
    run_dir: Path,
    workers: int,
    long_run_threshold_seconds: float,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan_set_id = record["plan_set_id"]
    if record["kind"] == "scp2_1_refusal_fixture":
        refusal_path = ROOT / record["refusal_path"]
        fixture_path = ROOT / record["path"]
        refusal = read_json(refusal_path)
        fixture = read_json(fixture_path)
        return {
            "plan_set_id": plan_set_id,
            "kind": record["kind"],
            "outcome": "non_executable_refusal_fixture",
            "fixture": {"path": record["path"], "sha256": file_sha256(fixture_path), "stable_hash": stable_hash(fixture)},
            "refusal": {
                "path": record["refusal_path"],
                "sha256": file_sha256(refusal_path),
                "stable_hash": stable_hash(refusal),
                "gap_code": refusal.get("gap_code"),
                "missing_capability": refusal.get("missing_capability"),
                "outcome": refusal.get("outcome"),
            },
            "equivalence": "not_applicable_non_executable",
        }, []

    payload, source = document_payload(record)
    if "source_response" in source:
        write_json_once(
            run_dir / f"{plan_set_id}.document-record.json",
            {
                "schema_version": "perf1.prior_live_document_record.v1",
                "plan_set_id": plan_set_id,
                "source": source,
                "document": payload,
            },
            metadata,
        )

    roles: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    all_equivalent = True
    for role, document in role_documents(payload).items():
        print(f"PERF-1 {plan_set_id}/{role}: bind", flush=True)
        bound, bind_ms = bind_role(document)
        cache_root = run_dir / "node-cache" / plan_set_id / role

        variant_payloads: dict[str, dict[str, Any]] = {}
        variant_hashes: dict[str, str] = {}
        variant_bytes: dict[str, bytes] = {}
        variant_summaries: dict[str, Any] = {}

        for variant in ("sequential", "optimized_cold", "optimized_warm"):
            print(f"PERF-1 {plan_set_id}/{role}: {variant}", flush=True)
            execution, external_execute_ms = execute_variant(
                bound_plan=bound,
                variant=variant,
                cache_root=None if variant == "sequential" else cache_root,
                workers=workers,
            )
            payload_for_hash = canonical_execution_payload(execution)
            payload_bytes = canonical_json_bytes(payload_for_hash)
            variant_payloads[variant] = payload_for_hash
            variant_hashes[variant] = hashlib.sha256(payload_bytes).hexdigest()
            variant_bytes[variant] = payload_bytes
            variant_summaries[variant] = {
                "status": execution.status.value,
                "result_count": len(execution.results),
                "predicate_trace_count": len(execution.predicate_traces),
                "execution_id": execution.execution_id,
                "node_cache": node_cache_summary(execution),
                "execution_parallelism": execution.provenance.get("execution_parallelism", {}),
                "timing_ms": execution.timing_ms,
            }
            timing_rows.append(
                timing_record(
                    plan_set_id=plan_set_id,
                    role=role,
                    variant=variant,
                    bind_ms=bind_ms,
                    external_execute_ms=external_execute_ms,
                    execution=execution,
                    source_latency_breakdown_ms=source.get("source_latency_breakdown_ms"),
                    long_run_threshold_seconds=long_run_threshold_seconds,
                )
            )

        cold_equal = variant_bytes["sequential"] == variant_bytes["optimized_cold"]
        warm_equal = variant_bytes["sequential"] == variant_bytes["optimized_warm"]
        all_equivalent = all_equivalent and cold_equal and warm_equal
        roles.append(
            {
                "role": role,
                "bound_plan_hash": bound.bound_plan_hash,
                "plan_hash": bound.plan_hash,
                "canonical_payload_sha256": variant_hashes,
                "optimized_cold_byte_identical_to_sequential": cold_equal,
                "optimized_warm_byte_identical_to_sequential": warm_equal,
                "result_order_identical": result_order(variant_payloads["sequential"]) == result_order(variant_payloads["optimized_cold"]) == result_order(variant_payloads["optimized_warm"]),
                "trace_order_identical": trace_order(variant_payloads["sequential"]) == trace_order(variant_payloads["optimized_cold"]) == trace_order(variant_payloads["optimized_warm"]),
                "variant_summaries": variant_summaries,
                "cache_inventory": cache_inventory(cache_root),
            }
        )

    return {
        "plan_set_id": plan_set_id,
        "kind": record["kind"],
        "source": source,
        "role_count": len(roles),
        "roles": roles,
        "all_roles_byte_identical": all_equivalent,
        "equivalence_payload_definition": (
            "Canonical payload contains status, execution_id, plan hashes, execution_result_rows, "
            "and predicate traces. Runtime provenance and timing are excluded because cache/parallel "
            "execution intentionally change those measurements."
        ),
    }, timing_rows


def result_order(payload: dict[str, Any]) -> list[str]:
    return [str(row.get("result_id")) for row in payload["rows"]]


def trace_order(payload: dict[str, Any]) -> list[str]:
    return [stable_hash(trace) for trace in payload["predicate_traces"]]


def render_timing_table(metadata: dict[str, Any], timing_rows: list[dict[str, Any]]) -> str:
    columns = [
        "plan_set_id",
        "role",
        "variant",
        "hermes_ms",
        "synthesis_ms",
        "bind_ms",
        "execute_external_ms",
        "execute_total_ms",
        "period_execution_ms",
        "merge_apply_result_semantics_ms",
        "period_count",
        "result_count",
        "persistent_hits",
        "misses",
        "detected_never_served",
        "exceeded_long_run_threshold",
    ]
    lines = [
        "<!-- evidence_metadata: "
        + json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        + " -->",
        "# PERF-1 Timing Table",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in timing_rows:
        node_cache = row.get("node_cache") or {}
        values = {
            **row,
            "persistent_hits": node_cache.get("persistent_hits"),
            "misses": node_cache.get("misses"),
            "detected_never_served": node_cache.get("detected_never_served"),
        }
        lines.append("| " + " | ".join(render_cell(values.get(column)) for column in columns) + " |")
    lines.append("")
    return "\n".join(lines)


def render_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value).replace("|", "\\|")


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def run(args: argparse.Namespace) -> dict[str, Any]:
    script_path = Path(__file__).resolve()
    script_sha = file_sha256(script_path)
    run_dir = make_run_dir(script_sha)
    metadata = evidence_metadata(args, run_dir=run_dir, script_sha=script_sha)
    plan_set = selected_plan_set(args.plan_set)
    plan_results: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    started = time.perf_counter()

    for record in plan_set:
        plan_result, rows = execute_plan_set(
            record=record,
            run_dir=run_dir,
            workers=args.workers,
            long_run_threshold_seconds=args.long_run_threshold_seconds,
            metadata=metadata,
        )
        plan_results.append(plan_result)
        timing_rows.extend(rows)

    all_equivalent = all(
        result.get("all_roles_byte_identical", True)
        for result in plan_results
        if result.get("equivalence") != "not_applicable_non_executable"
    )
    payload = {
        "schema_version": "perf1.equivalence_evidence.v1",
        "acceptance": {
            "all_executable_roles_byte_identical": all_equivalent,
            "declared_plan_set_count": len(plan_set),
            "executable_plan_set_count": sum(
                1 for item in plan_results if item.get("equivalence") != "not_applicable_non_executable"
            ),
            "refusal_fixture_count": sum(
                1 for item in plan_results if item.get("equivalence") == "not_applicable_non_executable"
            ),
        },
        "cache_key_schema": {
            "node_cache_key_schema_version": CACHE_SCHEMA_VERSION,
            "runtime_code_epoch": runtime_code_epoch(),
            "upstream_lineage": "Merkle lineage: each node cache-key preimage carries input source node ids, output names, and upstream cache keys.",
            "entry_validation": "Persistent entries are self-describing and are detected-never-served on preimage or output hash mismatch.",
        },
        "parallel_period_execution_law": {
            "period_state_independence": (
                "Each period task builds a fresh PeriodState for one match_id/period, reads only "
                "that scope's canonical/raw files, and returns serializable rows/traces/progress. "
                "No PeriodState object is shared across workers."
            ),
            "deterministic_merge": (
                "Worker completion order is discarded. Results merge by bound_plan.match_ids order, "
                "then bound_plan.periods order, then the existing runtime result sort law."
            ),
        },
        "workers": args.workers,
        "long_run_threshold_seconds": args.long_run_threshold_seconds,
        "elapsed_ms": elapsed_ms(started),
        "declared_plan_set": plan_set,
        "plan_results": plan_results,
        "timing_rows": timing_rows,
    }
    write_json_once(run_dir / "perf1-equivalence.json", payload, metadata)
    write_text_once(run_dir / "perf1-timing-table.md", render_timing_table(metadata, timing_rows))
    print(json.dumps({"run_dir": relative(run_dir), "all_equivalent": all_equivalent}, indent=2, sort_keys=True))
    if not all_equivalent:
        raise RuntimeError("optimized execution was not byte-identical to sequential for all executable roles")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--plan-set", action="append", default=[], help="Run one declared plan_set_id; may repeat.")
    parser.add_argument("--long-run-threshold-seconds", type=float, default=LONG_RUN_THRESHOLD_SECONDS)
    args = parser.parse_args(argv)
    if args.workers < 1:
        raise RuntimeError("--workers must be >= 1")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
