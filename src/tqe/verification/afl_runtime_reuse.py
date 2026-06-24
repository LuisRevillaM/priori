"""AFL runtime reuse and progress hardening verifier.

This is a scaling gate, not a football-semantics gate. It proves the executor
can reuse identical catalog-node outputs inside one execution without changing
results, traces, evidence, or execution status, and that long runs emit
deterministic progress events.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document
from tqe.runtime.executor import TacticalQueryExecutor
from tqe.runtime.ir import QueryExecution, TacticalQueryDocument, stable_hash
from tqe.verification.afl_one_touch_pass_chain import one_touch_pass_chain_document


REPORT_PATH = Path("artifacts/autonomous/afl-runtime-reuse-progress-report.json")


def runtime_reuse_document() -> dict[str, Any]:
    payload = copy.deepcopy(one_touch_pass_chain_document())
    nodes = payload["draft_plan"]["nodes"]
    terminal = next(node for node in nodes if node["node_id"] == "terminal_controlled_pass")
    duplicate = copy.deepcopy(terminal)
    duplicate["node_id"] = "terminal_controlled_pass_duplicate_for_cache_gate"
    nodes.insert(nodes.index(terminal) + 1, duplicate)
    return payload


def verify_runtime_reuse() -> dict[str, Any]:
    document_payload = runtime_reuse_document()
    bound_plan = bind_document(TacticalQueryDocument.model_validate(document_payload))
    cache_events: list[dict[str, Any]] = []
    cached = TacticalQueryExecutor(
        enable_node_cache=True,
        progress_callback=cache_events.append,
    ).execute(bound_plan)
    uncached = TacticalQueryExecutor(enable_node_cache=False).execute(bound_plan)

    cached_payload = semantic_execution_payload(cached)
    uncached_payload = semantic_execution_payload(uncached)
    cached_hash = stable_hash(cached_payload)
    uncached_hash = stable_hash(uncached_payload)
    cached_cache = cached.provenance.get("node_cache") or {}
    uncached_cache = uncached.provenance.get("node_cache") or {}
    cached_progress = cached.provenance.get("progress_events") or []
    findings: list[dict[str, str]] = []

    if cached_hash != uncached_hash:
        findings.append(
            {
                "code": "cache_changed_semantic_payload",
                "message": "Cache-enabled and cache-disabled executions produced different semantic payloads.",
                "path": "semantic_hash",
            }
        )
    if int(cached_cache.get("hits") or 0) <= 0:
        findings.append(
            {
                "code": "cache_hit_not_observed",
                "message": "The duplicate-node gate did not observe a cache hit.",
                "path": "cached.provenance.node_cache.hits",
            }
        )
    if int(cached_cache.get("misses") or 0) <= 0:
        findings.append(
            {
                "code": "cache_miss_not_observed",
                "message": "The cache-enabled run did not record cache misses.",
                "path": "cached.provenance.node_cache.misses",
            }
        )
    if int(uncached_cache.get("disabled") or 0) <= 0:
        findings.append(
            {
                "code": "cache_disabled_not_observed",
                "message": "The cache-disabled run did not record disabled catalog-node execution.",
                "path": "uncached.provenance.node_cache.disabled",
            }
        )
    if not cached_progress or cached.provenance.get("progress_event_count") != len(cached_progress):
        findings.append(
            {
                "code": "progress_events_missing",
                "message": "The cache-enabled execution did not carry deterministic progress events.",
                "path": "cached.provenance.progress_events",
            }
        )
    if not any(event.get("event") == "node_complete" and event.get("cache_status") == "hit" for event in cached_progress):
        findings.append(
            {
                "code": "progress_cache_hit_missing",
                "message": "Progress events did not expose the observed cache hit.",
                "path": "cached.provenance.progress_events",
            }
        )
    if cache_events != cached_progress:
        findings.append(
            {
                "code": "callback_progress_mismatch",
                "message": "Progress callback events did not match execution provenance events.",
                "path": "progress_callback",
            }
        )

    report = {
        "schema_version": "afl.runtime_reuse_progress.v1",
        "milestone": "AFL-09B runtime reuse and progress hardening",
        "status": "PASS" if not findings else "FAIL",
        "plan": {
            "plan_id": bound_plan.plan_id,
            "bound_plan_hash": bound_plan.bound_plan_hash,
            "duplicate_node": "terminal_controlled_pass_duplicate_for_cache_gate",
            "match_count": len(bound_plan.match_ids),
            "period_count": len(bound_plan.periods),
        },
        "semantic_comparison": {
            "cached_hash": cached_hash,
            "uncached_hash": uncached_hash,
            "same_semantic_payload": cached_hash == uncached_hash,
            "result_count": len(cached.results),
            "predicate_trace_count": len(cached.predicate_traces),
        },
        "cached_execution": {
            "execution_id": cached.execution_id,
            "status": cached.status.value,
            "runtime_trace_hash": cached.provenance.get("runtime_trace_hash"),
            "node_cache": cached_cache,
            "progress_event_count": cached.provenance.get("progress_event_count"),
        },
        "uncached_execution": {
            "execution_id": uncached.execution_id,
            "status": uncached.status.value,
            "runtime_trace_hash": uncached.provenance.get("runtime_trace_hash"),
            "node_cache": uncached_cache,
            "progress_event_count": uncached.provenance.get("progress_event_count"),
        },
        "checks": {
            "cache_on_off_semantic_payload_identical": cached_hash == uncached_hash,
            "cache_hit_observed": int(cached_cache.get("hits") or 0) > 0,
            "cache_disabled_path_observed": int(uncached_cache.get("disabled") or 0) > 0,
            "progress_events_recorded": bool(cached_progress),
            "progress_callback_matches_provenance": cache_events == cached_progress,
            "progress_exposes_cache_hit": any(
                event.get("event") == "node_complete" and event.get("cache_status") == "hit"
                for event in cached_progress
            ),
        },
        "findings": findings,
    }
    return report


def semantic_execution_payload(execution: QueryExecution) -> dict[str, Any]:
    return {
        "execution_id": execution.execution_id,
        "status": execution.status.value,
        "results": [result.model_dump(mode="json") for result in execution.results],
        "predicate_traces": [
            trace.model_dump(mode="json", exclude_none=True)
            for trace in execution.predicate_traces
        ],
        "runtime_trace_hash": execution.provenance.get("runtime_trace_hash"),
        "runtime_result_count": execution.provenance.get("runtime_result_count"),
        "runtime_value_count": execution.provenance.get("runtime_value_count"),
        "requested_evidence_failure_count": execution.provenance.get(
            "requested_evidence_failure_count"
        ),
        "unknown_trace_count": execution.provenance.get("unknown_trace_count"),
    }


def main() -> None:
    report = verify_runtime_reuse()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
