#!/usr/bin/env python3
"""Generate the R2-2 CAR-0 retention-rate flagship artifacts."""

from __future__ import annotations

import argparse
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
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.operators.rate_and_share import (  # noqa: E402
    RATE_AND_SHARE_SIGNATURE,
    RateIntervalResult,
    _joint_partition_counts,
)


SOURCE_PLAN = Path("delivery/packets/r1-c-sweep/plans/r1_5_fragile_possession_state_v0.json")
SOURCE_AUDIT = Path("delivery/packets/r1-c-sweep/population-audit/audit.json")
R2_1_TABLE = Path("delivery/packets/r2-1-flagship/fragile_possession_state_denominator_table.json")
OUT_DIR = Path("delivery/packets/r2-2-flagship")
PLAN_PATH = OUT_DIR / "rate_and_share_car0_retention_v0.json"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
TABLE_JSON = OUT_DIR / "car0_retention_rate_table.json"
TABLE_MD = OUT_DIR / "car0_retention_rate_table.md"
RATE_NODE_ID = "rate_and_share_car0_retention"
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]
PERIOD_ORDER = {"firstHalf": 0, "secondHalf": 1}
IDENTITY_FIELDS = ["match_id", "period", "perspective_team_role"]
POPULATION_EXPRESSION = (
    "CAR-0 retained fragile-condition rate: final typed_join_status over right_status, "
    "per team perspective per match"
)
SUBSET_DECLARATION = (
    "typed_join_status PASS is the same-source retained subset of right_status PASS; "
    "the added predicate is the same-team retention window from the terminal CAR-0 join"
)


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


def rate_node_payload() -> dict[str, Any]:
    return {
        "kind": "operator",
        "node_id": RATE_NODE_ID,
        "operator": {"name": "rate_and_share", "version": "0.1.0"},
        "inputs": {
            "numerator": {"source_node_id": "typed_join_2", "output_name": "typed_join_records"},
            "denominator": {"source_node_id": "typed_join_2", "output_name": "typed_join_records"},
        },
        "parameters": {
            "rate_kind": {"payload_type": "enum", "value": "rate"},
            "population_expression": {"payload_type": "enum", "value": POPULATION_EXPRESSION},
            "group_by_fields": {"payload_type": "entity_set", "value": ["perspective_team_role", "match_id"]},
            "numerator_status_field": {"payload_type": "enum", "value": "typed_join_status"},
            "denominator_status_field": {"payload_type": "enum", "value": "right_status"},
            "subset_declaration": {"payload_type": "enum", "value": SUBSET_DECLARATION},
            "subset_predicate_fields": {"payload_type": "entity_set", "value": ["window_status"]},
            "removed_denominator_predicate_fields": {"payload_type": "entity_set", "value": []},
            "share_key_field": {"payload_type": "enum", "value": "none"},
            "same_team_perspective_required": {"payload_type": "boolean", "value": True},
            "entity_identity_preserved_required": {"payload_type": "boolean", "value": False},
            "frame_alignment_required": {"payload_type": "boolean", "value": True},
            "constraint_opt_out_reason": {
                "payload_type": "enum",
                "value": "entity identity is not part of the CAR-0 retention-rate denominator",
            },
            "team_role_field": {"payload_type": "enum", "value": "perspective_team_role"},
        },
        "outputs": [output.model_dump(mode="json") for output in RATE_AND_SHARE_SIGNATURE.outputs],
    }


def generate_plan_bundle(source_bundle: dict[str, Any]) -> dict[str, Any]:
    bundle = copy.deepcopy(source_bundle)
    bundle["target_id"] = "r2_2_rate_and_share_car0_retention_v0"
    for role, document in sorted(bundle["documents"].items()):
        declare_typed_join_identity_fields(document)
        document["draft_plan"]["nodes"].append(copy.deepcopy(rate_node_payload()))
        document["default_invocation"]["invocation_id"] = f"r2_2_rate_and_share_car0_retention_v0_{role}"
        document["default_invocation"]["max_results"] = 20
    return bundle


def validate_plan_bundle(plan_bundle: dict[str, Any]) -> None:
    for document_payload in sorted(plan_bundle["documents"].values(), key=lambda item: item["default_invocation"]["invocation_id"]):
        bind_document(TacticalQueryDocument.model_validate(copy.deepcopy(document_payload)))


def audit_period_records(audit: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in audit["rows"]:
        key = (str(record["audit_role"]), str(record["match_id"]), str(record["period"]))
        grouped.setdefault(key, []).append(record)

    period_records: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        for match_id in MATCH_ORDER:
            for period in PERIOD_ORDER:
                source_records = grouped[(role, match_id, period)]
                counts = _joint_partition_counts(
                    records=source_records,
                    numerator_status_field="typed_join_status",
                    denominator_status_field="right_status",
                )
                group_key = {"perspective_team_role": role, "match_id": match_id}
                interval = RateIntervalResult(
                    rate_kind="rate",
                    population_expression=POPULATION_EXPRESSION,
                    group_key=group_key,
                    **counts,
                )
                period_records.append(
                    {
                        "audit_role": role,
                        "match_id": match_id,
                        "period": period,
                        "rate_kind": "rate",
                        "population_expression": POPULATION_EXPRESSION,
                        "group_by_fields": ["perspective_team_role", "match_id"],
                        "group_key": group_key,
                        "numerator_status_field": "typed_join_status",
                        "denominator_status_field": "right_status",
                        "subset_declaration": SUBSET_DECLARATION,
                        "rate_status": interval.rate_status,
                        "observed": interval.observed,
                        "lower_bound": interval.lower_bound,
                        "upper_bound": interval.upper_bound,
                        "observed_denominator_count": interval.observed_denominator_count,
                        "source_record_count": len(source_records),
                        **counts,
                    }
                )
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
                "rate_kind": record["rate_kind"],
                "population_expression": record["population_expression"],
                "group_by_fields": record["group_by_fields"],
                "group_key": {
                    "perspective_team_role": record["audit_role"],
                    "match_id": record["match_id"],
                },
                "numerator_status_field": record["numerator_status_field"],
                "denominator_status_field": record["denominator_status_field"],
                "subset_declaration": record["subset_declaration"],
                "a_count": 0,
                "b_count": 0,
                "c_count": 0,
                "d1_count": 0,
                "d2_count": 0,
                "e_count": 0,
                "periods": [],
            },
        )
        for field in ("a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count"):
            row[field] += int(record[field])
        row["periods"].append(
            {
                "period": record["period"],
                "rate_status": record["rate_status"],
                "observed": record["observed"],
                "lower_bound": record["lower_bound"],
                "upper_bound": record["upper_bound"],
                "observed_denominator_count": int(record["observed_denominator_count"]),
                "a_count": int(record["a_count"]),
                "b_count": int(record["b_count"]),
                "c_count": int(record["c_count"]),
                "d1_count": int(record["d1_count"]),
                "d2_count": int(record["d2_count"]),
                "e_count": int(record["e_count"]),
                "source_record_count": int(record["source_record_count"]),
            }
        )
    rows = []
    for role in ROLE_ORDER:
        for match_id in MATCH_ORDER:
            row = by_key[(role, match_id)]
            interval = RateIntervalResult(
                rate_kind="rate",
                population_expression=row["population_expression"],
                group_key=row["group_key"],
                a_count=row["a_count"],
                b_count=row["b_count"],
                c_count=row["c_count"],
                d1_count=row["d1_count"],
                d2_count=row["d2_count"],
                e_count=row["e_count"],
            )
            row["rate_status"] = interval.rate_status
            row["observed"] = interval.observed
            row["lower_bound"] = interval.lower_bound
            row["upper_bound"] = interval.upper_bound
            row["observed_denominator_count"] = interval.observed_denominator_count
            row["numerator_count_interval"] = interval.numerator_count_interval
            row["denominator_count_interval"] = interval.denominator_count_interval
            row["source_record_count"] = interval.denominator_count_interval["population_count"]
            row["periods"].sort(key=lambda item: PERIOD_ORDER[item["period"]])
            rows.append(row)
    return rows


def r2_1_reconciliation(rows: list[dict[str, Any]], r2_1_table: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    r2_1_by_key = {
        (row["audit_role"], row["match_id"]): row
        for row in r2_1_table["rows"]
    }
    per_row = []
    for row in rows:
        r2_1 = r2_1_by_key[(row["audit_role"], row["match_id"])]
        per_row.append(
            {
                "audit_role": row["audit_role"],
                "match_id": row["match_id"],
                "rate_source_record_count": row["source_record_count"],
                "r2_1_population_count": int(r2_1["population_count"]),
                "rate_a_count": row["a_count"],
                "r2_1_pass_count": int(r2_1["pass_count"]),
                "rate_num_status_field": row["numerator_status_field"],
                "r2_1_status_field": "typed_join_status",
                "source_population_matches": row["source_record_count"] == int(r2_1["population_count"]),
                "retained_fragile_pass_count_matches": row["a_count"] == int(r2_1["pass_count"]),
            }
        )
    totals = table_totals(rows)
    r2_1_totals = r2_1_table["totals"]
    reconciliation = {
        "r2_1_table": str(R2_1_TABLE),
        "r2_1_table_hash": stable_hash(r2_1_table),
        "same_14_role_match_rows": set(r2_1_by_key) == {
            (row["audit_role"], row["match_id"]) for row in rows
        },
        "rate_source_record_count": totals["source_record_count"],
        "r2_1_population_count": int(r2_1_totals["population_count"]),
        "rate_a_count": totals["a_count"],
        "r2_1_pass_count": int(r2_1_totals["pass_count"]),
        "all_14_source_populations_match_r2_1": all(item["source_population_matches"] for item in per_row),
        "all_14_retained_fragile_pass_counts_match_r2_1": all(
            item["retained_fragile_pass_count_matches"] for item in per_row
        ),
    }
    return reconciliation, per_row


def table_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    fields = ["a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count", "source_record_count"]
    totals = {field: sum(int(row[field]) for row in rows) for field in fields}
    totals["observed_denominator_count"] = sum(int(row["observed_denominator_count"]) for row in rows)
    totals["denominator_pass_count"] = sum(int(row["denominator_count_interval"]["pass_count"]) for row in rows)
    totals["denominator_unknown_count"] = sum(int(row["denominator_count_interval"]["unknown_count"]) for row in rows)
    totals["denominator_upper_bound"] = sum(int(row["denominator_count_interval"]["upper_bound"]) for row in rows)
    totals["numerator_upper_bound"] = sum(int(row["numerator_count_interval"]["upper_bound"]) for row in rows)
    return totals


def table_payload(
    plan_bundle: dict[str, Any],
    period_records: list[dict[str, Any]],
    r2_1_table: dict[str, Any],
) -> dict[str, Any]:
    rows = merged_rows(period_records)
    reconciliation, per_row = r2_1_reconciliation(rows, r2_1_table)
    return {
        "schema_version": "r2_2_flagship_car0_retention_rate_table.v1",
        "plan": str(PLAN_PATH),
        "plan_hash": stable_hash(plan_bundle),
        "rate_node_id": RATE_NODE_ID,
        "question": "When a team's possession turns fragile, how often do they keep the ball anyway?",
        "numerator": "typed_join_status PASS: retained final CAR-0 fragile state",
        "denominator": "right_status PASS/UNKNOWN over the same typed_join_2 source relation",
        "rows": rows,
        "totals": table_totals(rows),
        "r2_1_reconciliation": reconciliation,
        "per_row_r2_1_reconciliation": per_row,
        "period_record_count": len(period_records),
        "period_records_hash": stable_hash(period_records),
    }


def _format_rate(value: float | int | None) -> str:
    if value is None:
        return "UNKNOWN"
    return f"{float(value):.3f}"


def render_markdown(table: dict[str, Any]) -> str:
    totals = table["totals"]
    reconciliation = table["r2_1_reconciliation"]
    lines = [
        "# R2-2 Flagship CAR-0 Retention Rate Table",
        "",
        f"Plan: `{PLAN_PATH}`",
        f"Plan hash: `{table['plan_hash']}`",
        f"R2-1 denominator table: `{R2_1_TABLE}`",
        "",
        "| Role | Match | Rate | Lower | Upper | A | B | C | D1 | D2 | E | Known Den | Source Rows |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table["rows"]:
        lines.append(
            f"| `{row['audit_role']}` | `{row['match_id']}` | {_format_rate(row['observed'])} | "
            f"{_format_rate(row['lower_bound'])} | {_format_rate(row['upper_bound'])} | "
            f"{row['a_count']} | {row['b_count']} | {row['c_count']} | {row['d1_count']} | "
            f"{row['d2_count']} | {row['e_count']} | {row['observed_denominator_count']} | "
            f"{row['source_record_count']} |"
        )
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- A retained fragile rows: {totals['a_count']}",
            f"- B known non-retained rows inside known denominator: {totals['b_count']}",
            f"- C numerator-UNKNOWN rows inside known denominator: {totals['c_count']}",
            f"- D1 denominator-UNKNOWN / numerator-FAIL rows: {totals['d1_count']}",
            f"- D2 denominator-UNKNOWN / numerator-UNKNOWN rows: {totals['d2_count']}",
            f"- E denominator-FAIL rows excluded from the rate: {totals['e_count']}",
            f"- Source rows: {totals['source_record_count']}",
            "",
            "## R2-1 Denominator Reconciliation",
            "",
            f"- Same 14 role-match rows: {reconciliation['same_14_role_match_rows']}",
            (
                "- Source population count matches R2-1: "
                f"{reconciliation['rate_source_record_count']} == {reconciliation['r2_1_population_count']}"
            ),
            (
                "- A count matches R2-1 typed_join_status PASS count: "
                f"{reconciliation['rate_a_count']} == {reconciliation['r2_1_pass_count']}"
            ),
            (
                "- All 14 source populations match R2-1: "
                f"{reconciliation['all_14_source_populations_match_r2_1']}"
            ),
            (
                "- All 14 retained fragile PASS counts match R2-1: "
                f"{reconciliation['all_14_retained_fragile_pass_counts_match_r2_1']}"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_artifacts() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_bundle = load_json(SOURCE_PLAN)
    source_audit = load_json(SOURCE_AUDIT)
    r2_1_table = load_json(R2_1_TABLE)
    plan_bundle = generate_plan_bundle(source_bundle)
    write_json(PLAN_PATH, plan_bundle)
    validate_plan_bundle(plan_bundle)
    provenance = {
        "schema_version": "r2_2_flagship_provenance.v1",
        "generated_by": "scripts/packets/r2_2_flagship_generator.py",
        "generated_from": str(SOURCE_PLAN),
        "generated_from_hash": stable_hash(source_bundle),
        "source_population_audit": str(SOURCE_AUDIT),
        "source_population_audit_hash": stable_hash(source_audit),
        "flagship_plan": str(PLAN_PATH),
        "flagship_plan_hash": stable_hash(plan_bundle),
        "rate_node_id": RATE_NODE_ID,
        "r2_1_denominator_table": str(R2_1_TABLE),
        "r2_1_denominator_table_hash": stable_hash(r2_1_table),
    }
    write_json(PROVENANCE_PATH, provenance)
    period_records = audit_period_records(source_audit)
    table = table_payload(plan_bundle, period_records, r2_1_table)
    write_json(TABLE_JSON, table)
    TABLE_MD.write_text(render_markdown(table), encoding="utf-8")
    return {
        "plan_hash": stable_hash(plan_bundle),
        "rows": len(table["rows"]),
        "totals": table["totals"],
        "reconciled_source_populations": table["r2_1_reconciliation"]["all_14_source_populations_match_r2_1"],
        "reconciled_pass_counts": table["r2_1_reconciliation"]["all_14_retained_fragile_pass_counts_match_r2_1"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(write_artifacts(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
