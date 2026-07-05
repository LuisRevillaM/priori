#!/usr/bin/env python3
"""Generate the R2-1 aggregate_over flagship artifacts."""

from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, runtime_parameters  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.operators.aggregate_over import (  # noqa: E402
    AGGREGATE_OVER_SIGNATURE,
    AggregateIntervalResult,
)


SOURCE_PLAN = Path("delivery/packets/r1-c-sweep/plans/r1_5_fragile_possession_state_v0.json")
SEALED_AUDIT = Path("delivery/packets/r1-c-sweep/population-audit/audit.json")
OUT_DIR = Path("delivery/packets/r2-1-flagship")
PLAN_PATH = OUT_DIR / "aggregate_over_fragile_possession_state_v0.json"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
TABLE_JSON = OUT_DIR / "fragile_possession_state_denominator_table.json"
TABLE_MD = OUT_DIR / "fragile_possession_state_denominator_table.md"
CANONICAL_ROOT = Path("data/canonical/v1")
AGGREGATE_NODE_ID = "aggregate_over_fragile_possession_state"
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]
PERIOD_ORDER = {"firstHalf": 0, "secondHalf": 1}
IDENTITY_FIELDS = ["match_id", "period", "perspective_team_role"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def declare_typed_join_identity_fields(document: dict[str, Any]) -> None:
    for node in document["draft_plan"]["nodes"]:
        if node.get("node_id") != "typed_join_2":
            continue
        for output in node.get("outputs", []):
            evidence_fields = output.setdefault("evidence_fields", [])
            for field in reversed(IDENTITY_FIELDS):
                if field not in evidence_fields:
                    evidence_fields.insert(0, field)


def aggregate_node_payload() -> dict[str, Any]:
    return {
        "kind": "operator",
        "node_id": AGGREGATE_NODE_ID,
        "operator": {"name": "aggregate_over", "version": "0.1.0"},
        "inputs": {
            "population": {"source_node_id": "typed_join_2", "output_name": "typed_join_records"},
        },
        "parameters": {
            "aggregation_kind": {"payload_type": "enum", "value": "count"},
            "population_expression": {
                "payload_type": "enum",
                "value": "fragile_possession_state typed_join rows per team perspective per match",
            },
            "group_by_fields": {"payload_type": "entity_set", "value": ["perspective_team_role", "match_id"]},
            "status_field": {"payload_type": "enum", "value": "typed_join_status"},
            "same_team_perspective_required": {"payload_type": "boolean", "value": True},
            "entity_identity_preserved_required": {"payload_type": "boolean", "value": False},
            "frame_alignment_required": {"payload_type": "boolean", "value": True},
            "constraint_opt_out_reason": {
                "payload_type": "enum",
                "value": "entity identity is not part of the CAR-0 count denominator",
            },
            "team_role_field": {"payload_type": "enum", "value": "perspective_team_role"},
        },
        "outputs": [output.model_dump(mode="json") for output in AGGREGATE_OVER_SIGNATURE.outputs],
    }


def generate_plan_bundle(source_bundle: dict[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(source_bundle)
    bundle["target_id"] = "r2_1_aggregate_over_fragile_possession_state_v0"
    for role, document in sorted(bundle["documents"].items()):
        declare_typed_join_identity_fields(document)
        document["draft_plan"]["nodes"].append(copy.deepcopy(aggregate_node_payload()))
        document["default_invocation"]["invocation_id"] = (
            f"r2_1_aggregate_over_fragile_possession_state_v0_{role}"
        )
        document["default_invocation"]["max_results"] = 20
    return bundle


def execute_period_records(plan_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor(canonical_root=CANONICAL_ROOT)
    period_records: list[dict[str, Any]] = []
    for role, document_payload in sorted(plan_bundle["documents"].items()):
        document = TacticalQueryDocument.model_validate(copy.deepcopy(document_payload))
        bound = bind_document(document)
        params = runtime_parameters(bound)
        for match_id in bound.match_ids:
            for period in bound.periods:
                state = executor._execute_period(  # noqa: SLF001 - evidence artifact needs aggregate records.
                    bound_plan=bound,
                    match_id=match_id,
                    period=period,
                    params=params,
                    compatibility_profile=executor.compatibility_profile,
                )
                aggregate_records = state.signals[AGGREGATE_NODE_ID]["aggregate_records"]
                if len(aggregate_records) != 1:
                    raise RuntimeError(f"{role} {match_id} {period} emitted {len(aggregate_records)} aggregate rows")
                record = aggregate_records[0]
                if record["group_key"]["perspective_team_role"] != role:
                    raise RuntimeError(f"{role} {match_id} {period} perspective group mismatch")
                if record["group_key"]["match_id"] != match_id:
                    raise RuntimeError(f"{role} {match_id} {period} match group mismatch")
                period_records.append({"audit_role": role, **record})
    return period_records


def merged_rows(period_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in period_records:
        key = (record["audit_role"], record["match_id"])
        row = by_key.setdefault(
            key,
            {
                "audit_role": record["audit_role"],
                "match_id": record["match_id"],
                "aggregation_kind": record["aggregation_kind"],
                "population_expression": record["population_expression"],
                "group_by_fields": record["group_by_fields"],
                "group_key": {
                    "perspective_team_role": record["audit_role"],
                    "match_id": record["match_id"],
                },
                "pass_count": 0,
                "fail_count": 0,
                "unknown_count": 0,
                "periods": [],
            },
        )
        row["pass_count"] += int(record["pass_count"])
        row["fail_count"] += int(record["fail_count"])
        row["unknown_count"] += int(record["unknown_count"])
        row["periods"].append(
            {
                "period": record["period"],
                "observed": int(record["observed"]),
                "lower_bound": int(record["lower_bound"]),
                "upper_bound": int(record["upper_bound"]),
                "unknown_count": int(record["unknown_count"]),
                "population_count": int(record["population_count"]),
                "pass_count": int(record["pass_count"]),
                "fail_count": int(record["fail_count"]),
            }
        )
    rows = []
    for role in ROLE_ORDER:
        for match_id in MATCH_ORDER:
            row = by_key[(role, match_id)]
            interval = AggregateIntervalResult(
                aggregation_kind="count",
                population_expression=row["population_expression"],
                group_key=row["group_key"],
                pass_count=row["pass_count"],
                fail_count=row["fail_count"],
                unknown_count=row["unknown_count"],
            )
            row["observed"] = interval.observed
            row["lower_bound"] = interval.lower_bound
            row["upper_bound"] = interval.upper_bound
            row["population_count"] = interval.population_count
            row["periods"].sort(key=lambda item: PERIOD_ORDER[item["period"]])
            rows.append(row)
    return rows


def sealed_reconciliation(rows: list[dict[str, Any]], audit: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sealed_by_key: dict[tuple[str, str], collections.Counter[str]] = {}
    for role_summary in audit["summary"]["role_summaries"]:
        role = role_summary["role"]
        for period in role_summary["periods"]:
            sealed_by_key.setdefault((role, period["match_id"]), collections.Counter()).update(
                period["status_distribution"]
            )
    per_row = []
    for row in rows:
        sealed = sealed_by_key[(row["audit_role"], row["match_id"])]
        sealed_population = sum(int(value) for value in sealed.values())
        per_row.append(
            {
                "audit_role": row["audit_role"],
                "match_id": row["match_id"],
                "aggregate_pass_count": row["pass_count"],
                "sealed_pass_count": int(sealed.get("PASS", 0)),
                "aggregate_fail_count": row["fail_count"],
                "sealed_fail_count": int(sealed.get("FAIL", 0)),
                "aggregate_unknown_count": row["unknown_count"],
                "sealed_unknown_count": int(sealed.get("UNKNOWN", 0)),
                "aggregate_population_count": row["population_count"],
                "sealed_population_count": sealed_population,
                "matches": (
                    row["pass_count"] == int(sealed.get("PASS", 0))
                    and row["fail_count"] == int(sealed.get("FAIL", 0))
                    and row["unknown_count"] == int(sealed.get("UNKNOWN", 0))
                    and row["population_count"] == sealed_population
                ),
            }
        )
    totals = table_totals(rows)
    sealed_status = audit["summary"]["status_distributions"]["typed_join_status"]
    reconciliation = {
        "sealed_audit": str(SEALED_AUDIT),
        "sealed_audit_hash": stable_hash(audit),
        "sealed_total_rows": audit["summary"]["total_rows"],
        "sealed_pass_rows": int(sealed_status["PASS"]),
        "sealed_fail_rows": int(sealed_status["FAIL"]),
        "sealed_unknown_rows": int(sealed_status["UNKNOWN"]),
        "aggregate_total_rows": totals["population_count"],
        "aggregate_observed_pass_rows": totals["observed"],
        "aggregate_lower_bound_sum": totals["lower_bound"],
        "aggregate_upper_bound_sum": totals["upper_bound"],
        "aggregate_fail_rows": totals["fail_count"],
        "aggregate_unknown_rows": totals["unknown_count"],
        "all_14_rows_match_sealed_status_counts": all(item["matches"] for item in per_row),
    }
    return reconciliation, per_row


def table_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "observed": sum(int(row["observed"]) for row in rows),
        "lower_bound": sum(int(row["lower_bound"]) for row in rows),
        "upper_bound": sum(int(row["upper_bound"]) for row in rows),
        "unknown_count": sum(int(row["unknown_count"]) for row in rows),
        "population_count": sum(int(row["population_count"]) for row in rows),
        "pass_count": sum(int(row["pass_count"]) for row in rows),
        "fail_count": sum(int(row["fail_count"]) for row in rows),
    }


def table_payload(plan_bundle: dict[str, Any], period_records: list[dict[str, Any]], audit: dict[str, Any]) -> dict[str, Any]:
    rows = merged_rows(period_records)
    reconciliation, per_row = sealed_reconciliation(rows, audit)
    return {
        "schema_version": "r2_1_flagship_denominator_table.v1",
        "plan": str(PLAN_PATH),
        "plan_hash": stable_hash(plan_bundle),
        "aggregate_node_id": AGGREGATE_NODE_ID,
        "denominator": "fragile_possession_state typed_join rows per team perspective per match",
        "rows": rows,
        "totals": table_totals(rows),
        "reconciliation": reconciliation,
        "per_row_reconciliation": per_row,
        "period_record_count": len(period_records),
        "period_records_hash": stable_hash(period_records),
    }


def render_markdown(table: dict[str, Any]) -> str:
    totals = table["totals"]
    reconciliation = table["reconciliation"]
    lines = [
        "# R2-1 Flagship Denominator Table",
        "",
        f"Plan: `{PLAN_PATH}`",
        f"Plan hash: `{table['plan_hash']}`",
        f"Sealed audit: `{SEALED_AUDIT}`",
        "",
        "| Role | Match | Observed PASS | Lower | Upper | UNKNOWN | Population | FAIL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table["rows"]:
        lines.append(
            f"| `{row['audit_role']}` | `{row['match_id']}` | {row['observed']} | {row['lower_bound']} | "
            f"{row['upper_bound']} | {row['unknown_count']} | {row['population_count']} | {row['fail_count']} |"
        )
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- Observed PASS/lower bound: {totals['observed']}",
            f"- Upper bound: {totals['upper_bound']}",
            f"- UNKNOWN rows: {totals['unknown_count']}",
            f"- FAIL rows: {totals['fail_count']}",
            f"- Population rows: {totals['population_count']}",
            "",
            "## Sealed Audit Reconciliation",
            "",
            f"- Sealed PASS rows: {reconciliation['sealed_pass_rows']}",
            f"- Sealed FAIL rows: {reconciliation['sealed_fail_rows']}",
            f"- Sealed UNKNOWN rows: {reconciliation['sealed_unknown_rows']}",
            f"- Sealed total rows: {reconciliation['sealed_total_rows']}",
            (
                "- All 14 role-match rows match sealed status counts: "
                f"{reconciliation['all_14_rows_match_sealed_status_counts']}"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_artifacts() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_bundle = load_json(SOURCE_PLAN)
    audit = load_json(SEALED_AUDIT)
    plan_bundle = generate_plan_bundle(source_bundle)
    write_json(PLAN_PATH, plan_bundle)
    provenance = {
        "schema_version": "r2_1_flagship_provenance.v1",
        "generated_by": "scripts/packets/r2_1_flagship_generator.py",
        "generated_from": str(SOURCE_PLAN),
        "generated_from_hash": stable_hash(source_bundle),
        "flagship_plan": str(PLAN_PATH),
        "flagship_plan_hash": stable_hash(plan_bundle),
        "aggregate_node_id": AGGREGATE_NODE_ID,
        "sealed_audit": str(SEALED_AUDIT),
        "sealed_audit_hash": stable_hash(audit),
    }
    write_json(PROVENANCE_PATH, provenance)
    period_records = execute_period_records(plan_bundle)
    table = table_payload(plan_bundle, period_records, audit)
    write_json(TABLE_JSON, table)
    TABLE_MD.write_text(render_markdown(table), encoding="utf-8")
    return {
        "plan_hash": stable_hash(plan_bundle),
        "rows": len(table["rows"]),
        "totals": table["totals"],
        "reconciled": table["reconciliation"]["all_14_rows_match_sealed_status_counts"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(write_artifacts(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
