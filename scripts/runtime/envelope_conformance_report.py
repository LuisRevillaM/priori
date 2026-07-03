"""Run shadow capability-envelope conformance over representative plans."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Any

from tqe.runtime.binder import bind_document_from_path
from tqe.runtime.envelope import (
    check_envelope_conformance,
    catalog_entry_for_bound_node,
    legacy_envelope_from_runtime_values,
)
from tqe.runtime.executor import TacticalQueryExecutor, runtime_parameters
from tqe.runtime.ir import BoundCatalogNode

DEFAULT_PLANS = (
    Path("config/query-plans/high_bypass_completed_pass.experimental.v1.json"),
    Path("config/query-plans/q6_throw_in_first_action_under_pressure.experimental.v1.json"),
)
DEFAULT_OUTPUT = Path("artifacts/check-runs/envelope-conformance-report.json")


def report_for_plan(
    plan_path: Path,
    *,
    match_id: str | None,
    period: str | None,
) -> dict[str, Any]:
    bound = bind_document_from_path(plan_path)
    selected_match = match_id or bound.match_ids[0]
    selected_period = period or bound.periods[0]
    executor = TacticalQueryExecutor()
    state = executor._execute_period(
        bound_plan=bound,
        match_id=selected_match,
        period=selected_period,
        params=runtime_parameters(bound),
    )

    findings: list[dict[str, Any]] = []
    counts = Counter()
    for node in bound.nodes:
        if not isinstance(node, BoundCatalogNode):
            continue
        raw_outputs = state.signals.get(node.node_id)
        runtime_values = state.runtime_values.get(node.node_id)
        if not isinstance(raw_outputs, dict) or runtime_values is None:
            continue
        entry = catalog_entry_for_bound_node(node)
        envelope = legacy_envelope_from_runtime_values(
            capability_name=node.catalog_ref,
            node_id=node.node_id,
            raw_outputs=raw_outputs,
            runtime_values=runtime_values,
        )
        conformance = check_envelope_conformance(catalog_entry=entry, envelope=envelope)
        counts[node.catalog_ref] += conformance.finding_count
        findings.extend(
            {
                "capability": finding.capability_name,
                "node_id": finding.node_id,
                "output_name": finding.output_name,
                "code": finding.code,
                "message": finding.message,
            }
            for finding in conformance.findings
        )

    return {
        "plan": str(plan_path),
        "match_id": selected_match,
        "period": selected_period,
        "finding_count": len(findings),
        "findings_count_by_capability": dict(sorted(counts.items())),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="append", type=Path, default=None)
    parser.add_argument("--match-id")
    parser.add_argument("--period")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    os.environ["TQE_ENVELOPE_CONFORMANCE"] = "warn"
    logging.getLogger("tqe.runtime.envelope").setLevel(logging.ERROR)
    plan_paths = tuple(args.plan or DEFAULT_PLANS)
    reports = [
        report_for_plan(plan_path, match_id=args.match_id, period=args.period)
        for plan_path in plan_paths
    ]
    totals = Counter()
    for report in reports:
        totals.update(report["findings_count_by_capability"])
    payload = {
        "schema_version": "f2_0.envelope_conformance_report.v1",
        "mode": "warn",
        "plan_count": len(reports),
        "finding_count": sum(report["finding_count"] for report in reports),
        "findings_count_by_capability": dict(sorted(totals.items())),
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
