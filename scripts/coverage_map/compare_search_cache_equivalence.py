#!/usr/bin/env python3
"""Compare compiler-search runs with and without cross-target execution reuse."""

from __future__ import annotations

import collections
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_LEDGER = ROOT / os.environ.get(
    "TQE_SEARCH_BASELINE_ROW_LEDGER",
    "generated/compiler-search-bare-atlas/search-run-no-shared/row-ledger.json",
)
CACHED_LEDGER = ROOT / os.environ.get(
    "TQE_SEARCH_CACHED_ROW_LEDGER",
    "generated/compiler-search-bare-atlas/search-run-shared/row-ledger.json",
)
REPORT = ROOT / os.environ.get(
    "TQE_SEARCH_CACHE_EQUIVALENCE_REPORT",
    "artifacts/autonomous/compiler-search-cache-equivalence-report.json",
)

NON_SEMANTIC_ROW_KEYS = {
    "execution_node_cache",
    "plan_path",
}


def main() -> int:
    baseline = load_json(BASELINE_LEDGER)
    cached = load_json(CACHED_LEDGER)
    findings: list[dict[str, Any]] = []

    baseline_by_id = {row["target_id"]: row for row in baseline}
    cached_by_id = {row["target_id"]: row for row in cached}
    if set(baseline_by_id) != set(cached_by_id):
        findings.append(
            {
                "code": "target_set_mismatch",
                "baseline_only": sorted(set(baseline_by_id) - set(cached_by_id)),
                "cached_only": sorted(set(cached_by_id) - set(baseline_by_id)),
            }
        )

    compared = 0
    for target_id in sorted(set(baseline_by_id) & set(cached_by_id)):
        compared += 1
        left = semantic_row(baseline_by_id[target_id])
        right = semantic_row(cached_by_id[target_id])
        if left != right:
            findings.append(
                {
                    "code": "semantic_row_mismatch",
                    "target_id": target_id,
                    "baseline": left,
                    "cached": right,
                }
            )

    baseline_cache = cache_totals(baseline)
    cached_cache = cache_totals(cached)
    if cached_cache.get("shared_hits", 0) <= 0:
        findings.append(
            {
                "code": "shared_cache_not_exercised",
                "message": "Cached run produced no shared cache hits.",
                "cached_node_cache": cached_cache,
            }
        )
    if baseline_cache.get("shared_hits", 0) != 0:
        findings.append(
            {
                "code": "baseline_shared_cache_exercised",
                "message": "Baseline no-shared run unexpectedly produced shared cache hits.",
                "baseline_node_cache": baseline_cache,
            }
        )

    report = {
        "schema_version": "compiler_search_cache_equivalence.v0",
        "status": "PASS" if not findings else "FAIL",
        "claim": (
            "Cross-target shared catalog-node execution reuse preserves compiler-search semantic "
            "row results on the compared sample."
        ),
        "scope": {
            "atlas_wide": False,
            "natural_language": False,
            "compares_final_query_results": True,
            "compares_provider_chains": True,
            "compares_runtime_trace_hashes": True,
            "ignores_non_semantic_plan_paths": True,
            "cache_on_off_equivalence": True,
        },
        "summary": {
            "compared_target_count": compared,
            "baseline_node_cache": baseline_cache,
            "cached_node_cache": cached_cache,
        },
        "inputs": {
            "baseline_row_ledger": relative_path(BASELINE_LEDGER),
            "cached_row_ledger": relative_path(CACHED_LEDGER),
        },
        "findings": findings,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def semantic_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(row.items())
        if key not in NON_SEMANTIC_ROW_KEYS
    }


def cache_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    totals: collections.Counter[str] = collections.Counter()
    for row in rows:
        cache = row.get("execution_node_cache")
        if not isinstance(cache, dict):
            continue
        for key in ("hits", "local_hits", "shared_hits", "misses", "disabled", "bypassed"):
            totals[key] += int(cache.get(key) or 0)
    return dict(sorted(totals.items()))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
