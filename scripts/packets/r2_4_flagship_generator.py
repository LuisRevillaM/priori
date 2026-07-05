#!/usr/bin/env python3
"""Generate the R2-4 counterattack initiation flagship artifacts."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import bind_document  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, canonical_data_manifest_hash, runtime_parameters, utc_now_iso  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.runtime.operators.rate import RateIntervalResult  # noqa: E402
from tqe.semantic_compiler.meaning_expression import load_meaning_expression_from_path, load_pack_vocabulary  # noqa: E402
from tqe.semantic_compiler.target_synthesis import synthesize_and_bind  # noqa: E402

OUT_DIR = Path("delivery/packets/r2-4-flagship")
MEANING_EXPRESSION = OUT_DIR / "meaning-expressions" / "counterattack_initiation_sequence_rate.v0.json"
PLAN_PATH = OUT_DIR / "counterattack_initiation_v0.json"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
TABLE_JSON = OUT_DIR / "counterattack_initiation_table.json"
TABLE_MD = OUT_DIR / "counterattack_initiation_table.md"
LOCAL_SIDECAR = OUT_DIR / "run-sidecar.local.json"
RATE_NODE_ID = "rate"
SEQUENCE_NODE_ID = "sequence_pattern"
AGGREGATE_NODE_ID = "aggregate_over"
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]
PERIOD_ORDER = {"firstHalf": 0, "secondHalf": 1}
POPULATION_EXPRESSION = "counterattack initiation completed chains over regain starts"
SUBSET_DECLARATION = (
    "chain_status PASS is the completed-chain subset of stage_1_status PASS regain starts "
    "from the same sequence_pattern source records"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_ready(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): json_ready(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [json_ready(value) for value in payload]
    if isinstance(payload, tuple):
        return [json_ready(value) for value in payload]
    return payload


def synthesized_plan_bundle() -> tuple[dict[str, Any], dict[str, Any]]:
    vocabulary = load_pack_vocabulary()
    load_result = load_meaning_expression_from_path(MEANING_EXPRESSION, vocabulary=vocabulary)
    if load_result.expression is None:
        raise RuntimeError(f"R2-4 meaning expression refused: {load_result.refusal}")
    synthesized = synthesize_and_bind(load_result.expression, coverage_rows=load_json(Path("generated/coverage-map.json")))
    return synthesized["document"], synthesized


def validate_plan_bundle(plan_bundle: dict[str, Any]) -> None:
    for role in ROLE_ORDER:
        bind_document(TacticalQueryDocument.model_validate(copy.deepcopy(plan_bundle["documents"][role])))


def execute_period_outputs(
    *,
    plan_bundle: dict[str, Any],
    canonical_root: Path,
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    period_records: list[dict[str, Any]] = []
    timings: list[dict[str, Any]] = []
    shared_cache: dict[str, dict[str, Any]] = {}
    for role in ROLE_ORDER:
        document_payload = copy.deepcopy(plan_bundle["documents"][role])
        bound = bind_document(TacticalQueryDocument.model_validate(document_payload))
        params = runtime_parameters(bound)
        executor = TacticalQueryExecutor(
            canonical_root=canonical_root,
            raw_root=raw_root,
            shared_node_output_cache=shared_cache,
        )
        for match_id in MATCH_ORDER:
            for period in PERIOD_ORDER:
                started = time.monotonic()
                state = executor._execute_period(
                    bound_plan=bound,
                    match_id=match_id,
                    period=period,
                    params=params,
                    compatibility_profile=executor.compatibility_profile,
                )
                elapsed = round(time.monotonic() - started, 3)
                sequence_records = records_for(state, SEQUENCE_NODE_ID, "chain_records")
                aggregate_records = records_for(state, AGGREGATE_NODE_ID, "aggregate_records")
                rate_records = records_for(state, RATE_NODE_ID, "rate_records")
                aggregate_record = aggregate_records[0] if aggregate_records else empty_aggregate_record(role, match_id, period)
                rate_record = rate_records[0] if rate_records else empty_rate_record(role, match_id, period)
                period_records.append(
                    {
                        "audit_role": role,
                        "match_id": match_id,
                        "period": period,
                        "sequence_record_count": len(sequence_records),
                        "aggregate": strip_source_records(aggregate_record),
                        "rate": strip_source_records(rate_record),
                    }
                )
                timings.append(
                    {
                        "audit_role": role,
                        "match_id": match_id,
                        "period": period,
                        "elapsed_seconds": elapsed,
                        "sequence_record_count": len(sequence_records),
                    }
                )
    return period_records, timings


def records_for(state: Any, node_id: str, output_name: str) -> list[dict[str, Any]]:
    runtime_value = state.runtime_values[node_id][output_name]
    return [dict(record) for record in runtime_value.records]


def strip_source_records(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "source_records"}


def empty_aggregate_record(role: str, match_id: str, period: str) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "period": period,
        "aggregation_kind": "count",
        "population_expression": "counterattack initiation chains by team and match",
        "group_by_fields": ["team_role", "match_id"],
        "group_key": {"team_role": role, "match_id": match_id},
        "status_field": "chain_status",
        "observed": 0,
        "lower_bound": 0,
        "upper_bound": 0,
        "unknown_count": 0,
        "population_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "source_record_count": 0,
    }


def empty_rate_record(role: str, match_id: str, period: str) -> dict[str, Any]:
    result = RateIntervalResult(
        rate_kind="rate",
        population_expression=POPULATION_EXPRESSION,
        group_key={"team_role": role, "match_id": match_id},
        a_count=0,
        b_count=0,
        c_count=0,
        d1_count=0,
        d2_count=0,
        e_count=0,
    )
    return rate_record_from_interval(result, match_id=match_id, period=period)


def rate_record_from_interval(result: RateIntervalResult, *, match_id: str, period: str) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "period": period,
        "rate_kind": result.rate_kind,
        "population_expression": result.population_expression,
        "group_by_fields": ["team_role", "match_id"],
        "group_key": result.group_key,
        "numerator_status_field": "chain_status",
        "denominator_status_field": "stage_1_status",
        "subset_declaration": SUBSET_DECLARATION,
        "rate_status": result.rate_status,
        "observed": result.observed,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "observed_denominator_count": result.observed_denominator_count,
        "a_count": result.a_count,
        "b_count": result.b_count,
        "c_count": result.c_count,
        "d1_count": result.d1_count,
        "d2_count": result.d2_count,
        "e_count": result.e_count,
        "numerator_count_interval": result.numerator_count_interval,
        "denominator_count_interval": result.denominator_count_interval,
    }


def merged_rows(period_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for period_record in period_records:
        role = period_record["audit_role"]
        match_id = period_record["match_id"]
        key = (role, match_id)
        aggregate = period_record["aggregate"]
        rate = period_record["rate"]
        row = by_key.setdefault(
            key,
            {
                "audit_role": role,
                "match_id": match_id,
                "group_key": {"team_role": role, "match_id": match_id},
                "periods": [],
                "observed": 0,
                "lower_bound": 0,
                "upper_bound": 0,
                "unknown_count": 0,
                "population_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "a_count": 0,
                "b_count": 0,
                "c_count": 0,
                "d1_count": 0,
                "d2_count": 0,
                "e_count": 0,
            },
        )
        for field in ("observed", "lower_bound", "upper_bound", "unknown_count", "population_count", "pass_count", "fail_count"):
            row[field] += int(aggregate[field])
        for field in ("a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count"):
            row[field] += int(rate[field])
        row["periods"].append(
            {
                "period": period_record["period"],
                "sequence_record_count": int(period_record["sequence_record_count"]),
                "aggregate": aggregate,
                "rate": rate,
            }
        )
    rows: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        for match_id in MATCH_ORDER:
            row = by_key[(role, match_id)]
            chain_count_interval = {
                "observed": row["observed"],
                "lower_bound": row["lower_bound"],
                "upper_bound": row["upper_bound"],
                "unknown_count": row["unknown_count"],
                "population_count": row["population_count"],
                "pass_count": row["pass_count"],
                "fail_count": row["fail_count"],
            }
            interval = RateIntervalResult(
                rate_kind="rate",
                population_expression=POPULATION_EXPRESSION,
                group_key=row["group_key"],
                a_count=row["a_count"],
                b_count=row["b_count"],
                c_count=row["c_count"],
                d1_count=row["d1_count"],
                d2_count=row["d2_count"],
                e_count=row["e_count"],
            )
            row.update(rate_record_from_interval(interval, match_id=match_id, period="all"))
            row["chain_count_interval"] = chain_count_interval
            row["denominator_reconciliation"] = {
                "chain_population_matches_rate_denominator": row["population_count"] == row["denominator_count_interval"]["population_count"],
                "completed_chain_count_matches_rate_a": row["pass_count"] == row["a_count"],
            }
            row["periods"].sort(key=lambda item: PERIOD_ORDER[item["period"]])
            rows.append(row)
    return rows


def table_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        field: sum(int(row["chain_count_interval"][field]) for row in rows)
        for field in (
            "observed",
            "lower_bound",
            "upper_bound",
            "unknown_count",
            "population_count",
            "pass_count",
            "fail_count",
        )
    }
    totals.update(
        {
            field: sum(int(row[field]) for row in rows)
            for field in ("a_count", "b_count", "c_count", "d1_count", "d2_count", "e_count")
        }
    )
    interval = RateIntervalResult(
        rate_kind="rate",
        population_expression=POPULATION_EXPRESSION,
        group_key={"scope": "all_role_match_rows"},
        a_count=totals["a_count"],
        b_count=totals["b_count"],
        c_count=totals["c_count"],
        d1_count=totals["d1_count"],
        d2_count=totals["d2_count"],
        e_count=totals["e_count"],
    )
    totals["rate_status"] = interval.rate_status
    totals["rate_observed"] = interval.observed
    totals["rate_lower_bound"] = interval.lower_bound
    totals["rate_upper_bound"] = interval.upper_bound
    totals["observed_denominator_count"] = interval.observed_denominator_count
    return totals


def table_payload(
    *,
    plan_bundle: dict[str, Any],
    synthesized: dict[str, Any],
    period_records: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = merged_rows(period_records)
    totals = table_totals(rows)
    return {
        "schema_version": "r2_4_counterattack_initiation_table.v1",
        "question": "After a regain, does the team progress the ball by carry and keep it with a controlled pass?",
        "meaning_expression": str(MEANING_EXPRESSION),
        "meaning_expression_hash": stable_hash(load_json(MEANING_EXPRESSION)),
        "plan": str(PLAN_PATH),
        "plan_hash": stable_hash(plan_bundle),
        "synthesized_sequence_rate_document_hash": synthesized["document_hash"],
        "sequence_node_id": SEQUENCE_NODE_ID,
        "aggregate_node_id": AGGREGATE_NODE_ID,
        "rate_node_id": RATE_NODE_ID,
        "match_order": MATCH_ORDER,
        "role_order": ROLE_ORDER,
        "rows": rows,
        "totals": totals,
        "period_record_count": len(period_records),
        "period_records_hash": stable_hash(period_records),
        "denominator_reconciliation": {
            "all_14_chain_populations_match_rate_denominators": all(
                row["denominator_reconciliation"]["chain_population_matches_rate_denominator"] for row in rows
            ),
            "all_14_completed_chain_counts_match_rate_a": all(
                row["denominator_reconciliation"]["completed_chain_count_matches_rate_a"] for row in rows
            ),
        },
    }


def format_rate(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return f"{float(value):.3f}"


def render_markdown(table: dict[str, Any]) -> str:
    lines = [
        "# R2-4 Flagship Counterattack Initiation",
        "",
        f"Plan: `{table['plan']}`",
        f"Plan hash: `{table['plan_hash']}`",
        "",
        "| Role | Match | Chains | Lower | Upper | Population | Unknown | Rate | Rate Lower | Rate Upper | A | B | C | D1 | D2 | E |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table["rows"]:
        lines.append(
            f"| `{row['audit_role']}` | `{row['match_id']}` | {row['chain_count_interval']['pass_count']} | {row['chain_count_interval']['lower_bound']} | {row['chain_count_interval']['upper_bound']} | "
            f"{row['chain_count_interval']['population_count']} | {row['chain_count_interval']['unknown_count']} | {format_rate(row['observed'])} | "
            f"{format_rate(row['lower_bound'])} | {format_rate(row['upper_bound'])} | {row['a_count']} | {row['b_count']} | "
            f"{row['c_count']} | {row['d1_count']} | {row['d2_count']} | {row['e_count']} |"
        )
    totals = table["totals"]
    reconciliation = table["denominator_reconciliation"]
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- Completed chains (A / pass_count): {totals['a_count']}",
            f"- Chain population rows: {totals['population_count']}",
            f"- Unknown chain rows: {totals['unknown_count']}",
            f"- Rate interval: {format_rate(totals['rate_observed'])} [{format_rate(totals['rate_lower_bound'])}, {format_rate(totals['rate_upper_bound'])}]",
            "",
            "## Denominator Reconciliation",
            "",
            f"- All 14 chain populations match rate denominators: {reconciliation['all_14_chain_populations_match_rate_denominators']}",
            f"- All 14 completed-chain counts match rate A counts: {reconciliation['all_14_completed_chain_counts_match_rate_a']}",
        ]
    )
    return "\n".join(lines) + "\n"


def write_artifacts(*, canonical_root: Path, raw_root: Path, long_threshold_seconds: float) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    plan_bundle, synthesized = synthesized_plan_bundle()
    validate_plan_bundle(plan_bundle)
    write_json(PLAN_PATH, plan_bundle)
    period_records, timings = execute_period_outputs(
        plan_bundle=plan_bundle,
        canonical_root=canonical_root,
        raw_root=raw_root,
    )
    table = table_payload(plan_bundle=plan_bundle, synthesized=synthesized, period_records=period_records)
    write_json(TABLE_JSON, table)
    TABLE_MD.write_text(render_markdown(table), encoding="utf-8")
    provenance = {
        "schema_version": "r2_4_flagship_provenance.v1",
        "generated_by": "scripts/packets/r2_4_flagship_generator.py",
        "meaning_expression": str(MEANING_EXPRESSION),
        "meaning_expression_hash": stable_hash(load_json(MEANING_EXPRESSION)),
        "synthesized_sequence_rate_document_hash": synthesized["document_hash"],
        "flagship_plan": str(PLAN_PATH),
        "flagship_plan_hash": stable_hash(plan_bundle),
        "table": str(TABLE_JSON),
        "table_hash": stable_hash(table),
        "canonical_manifest_hash": canonical_data_manifest_hash(canonical_root),
        "period_record_count": len(period_records),
        "period_records_hash": table["period_records_hash"],
        "long_execution_threshold_seconds": long_threshold_seconds,
    }
    write_json(PROVENANCE_PATH, provenance)
    elapsed = round(time.monotonic() - started, 3)
    sidecar = {
        "schema_version": "r2_4_flagship_run_sidecar.local.v1",
        "generated_at": utc_now_iso(),
        "elapsed_seconds": elapsed,
        "long_execution": elapsed > long_threshold_seconds,
        "canonical_root": str(canonical_root),
        "raw_root": str(raw_root),
        "period_timings": timings,
    }
    write_json(LOCAL_SIDECAR, sidecar)
    return {
        "plan_hash": stable_hash(plan_bundle),
        "table_hash": stable_hash(table),
        "rows": len(table["rows"]),
        "period_records": len(period_records),
        "elapsed_seconds": elapsed,
        "long_execution": elapsed > long_threshold_seconds,
        "totals": table["totals"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical-root",
        default=os.environ.get("TQE_DATA_ROOT", "data/canonical/v1"),
        help="Canonical parquet root used for execution.",
    )
    parser.add_argument(
        "--raw-root",
        default=os.environ.get("TQE_RAW_ROOT", "data/raw/idsse/figshare-28196177-v1"),
        help="Raw IDSSE root used for execution.",
    )
    parser.add_argument("--long-threshold-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    summary = write_artifacts(
        canonical_root=Path(args.canonical_root),
        raw_root=Path(args.raw_root),
        long_threshold_seconds=float(args.long_threshold_seconds),
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
