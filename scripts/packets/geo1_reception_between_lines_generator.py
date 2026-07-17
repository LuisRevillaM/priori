#!/usr/bin/env python3
"""Generate GEO-1's certified reception-between-observed-lines recipe."""

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
from tqe.runtime.operators.aggregate_over import AGGREGATE_OVER_SIGNATURE  # noqa: E402
from tqe.runtime.operators.rate import (  # noqa: E402
    RATE_SIGNATURE,
    RateIntervalResult,
    _joint_partition_counts,
)
from tqe.semantic_compiler.meaning_expression import (  # noqa: E402
    load_meaning_expression_from_path,
    load_pack_vocabulary,
)
from tqe.semantic_compiler.target_synthesis import synthesize_and_bind  # noqa: E402


OUT_DIR = Path("delivery/packets/geo-1-reception-between-lines")
MEANING_PATH = OUT_DIR / "meaning-expression.json"
PLAN_PATH = OUT_DIR / "reception_between_observed_lines.v1.json"
TABLE_PATH = OUT_DIR / "reception_between_observed_lines_table.json"
TABLE_MD_PATH = OUT_DIR / "reception_between_observed_lines_table.md"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]
PERIOD_ORDER = ["firstHalf", "secondHalf"]
AGGREGATE_NODE_ID = "aggregate_between_lines_by_receiver"
RATE_NODE_ID = "rate_between_lines_by_receiver"
POPULATION_EXPRESSION = (
    "receptions between declared observed geometric line ranks 1 and 2, "
    "grouped by receiver_id over tracking-confirmed controlled receptions"
)
SUBSET_DECLARATION = (
    "between_observed_lines_status PASS is the same-row geometric subset of "
    "controlled_pass_status PASS at the aligned controlled reception frame"
)
OPT_OUT_REASON = (
    "between_observed_lines already preserves one shared perspective-team anchor, "
    "receiver, and aligned frame; aggregate_over and rate introduce no join"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_or_check(path: Path, payload: Any, *, check: bool) -> None:
    rendered = json_text(payload)
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            raise RuntimeError(f"byte reproduction failed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def enum(value: str) -> dict[str, Any]:
    return {"payload_type": "enum", "unit": "none", "value": value}


def boolean(value: bool) -> dict[str, Any]:
    return {"payload_type": "boolean", "unit": "none", "value": value}


def entity_set(values: list[str]) -> dict[str, Any]:
    return {"payload_type": "entity_set", "unit": "none", "value": values}


def field_ref(kind: str, field: str) -> dict[str, Any]:
    return {
        "payload_type": "field_ref",
        "unit": "none",
        "value": {"kind": kind, "field": field},
    }


def aggregate_node(source_node_id: str) -> dict[str, Any]:
    return {
        "kind": "operator",
        "node_id": AGGREGATE_NODE_ID,
        "operator": {"name": "aggregate_over", "version": "0.1.0"},
        "inputs": {
            "population": {
                "source_node_id": source_node_id,
                "output_name": "anchor_evaluations",
            }
        },
        "parameters": {
            "aggregation_kind": enum("count"),
            "population_expression": enum(POPULATION_EXPRESSION),
            "group_by_fields": entity_set(["receiver_id"]),
            "status_field": field_ref("status", "between_observed_lines_status"),
            "same_team_perspective_required": boolean(False),
            "entity_identity_preserved_required": boolean(False),
            "frame_alignment_required": boolean(False),
            "constraint_opt_out_reason": enum(OPT_OUT_REASON),
            "team_role_field": field_ref("entity", "team_role"),
        },
        "outputs": [output.model_dump(mode="json") for output in AGGREGATE_OVER_SIGNATURE.outputs],
    }


def rate_node(source_node_id: str) -> dict[str, Any]:
    source = {
        "source_node_id": source_node_id,
        "output_name": "anchor_evaluations",
    }
    return {
        "kind": "operator",
        "node_id": RATE_NODE_ID,
        "operator": {"name": "rate", "version": "0.1.0"},
        "inputs": {"numerator": source, "denominator": copy.deepcopy(source)},
        "parameters": {
            "rate_kind": enum("rate"),
            "population_expression": enum(POPULATION_EXPRESSION),
            "group_by_fields": entity_set(["receiver_id"]),
            "numerator_status_field": field_ref("status", "between_observed_lines_status"),
            "denominator_status_field": field_ref("status", "controlled_pass_status"),
            "subset_declaration": enum(SUBSET_DECLARATION),
            "subset_predicate_fields": entity_set(["between_observed_lines_status"]),
            "removed_denominator_predicate_fields": entity_set([]),
            "same_team_perspective_required": boolean(False),
            "entity_identity_preserved_required": boolean(False),
            "frame_alignment_required": boolean(False),
            "constraint_opt_out_reason": enum(OPT_OUT_REASON),
            "team_role_field": field_ref("entity", "team_role"),
        },
        "outputs": [output.model_dump(mode="json") for output in RATE_SIGNATURE.outputs],
    }


def synthesized_plan_bundle() -> tuple[dict[str, Any], dict[str, Any]]:
    loaded = load_meaning_expression_from_path(
        MEANING_PATH,
        vocabulary=load_pack_vocabulary(),
    )
    if loaded.expression is None:
        raise RuntimeError(f"GEO-1 meaning expression refused: {loaded.refusal}")
    synthesized = synthesize_and_bind(loaded.expression)
    bundle = copy.deepcopy(synthesized["document"])
    if bundle.get("schema_version") != "compiler_search_perspective_bundle.v1":
        raise RuntimeError("GEO-1 synthesis did not return the required perspective bundle")
    for role in ROLE_ORDER:
        document = bundle["documents"][role]
        nodes = document["draft_plan"]["nodes"]
        controlled = [node for node in nodes if node.get("catalog_ref") == "controlled_pass_episode"]
        line_models = [node for node in nodes if node.get("catalog_ref") == "multi_line_model"]
        between = [node for node in nodes if node.get("catalog_ref") == "between_observed_lines"]
        if len(controlled) != 1 or len(line_models) != 1 or len(between) != 1:
            raise RuntimeError(
                "standard envelope did not synthesize exactly one shared "
                "controlled_pass_episode -> multi_line_model -> between_observed_lines chain"
            )
        controlled_node = controlled[0]
        line_node = line_models[0]
        between_node = between[0]
        if controlled_node.get("parameters", {}).get("team_scope", {}).get("value") != "perspective_team":
            raise RuntimeError("GEO-1 controlled-pass source is not perspective-team scoped")
        if line_node["inputs"]["anchors"]["source_node_id"] != controlled_node["node_id"]:
            raise RuntimeError("GEO-1 line model does not use the shared controlled-pass anchors")
        if between_node["inputs"]["entity_anchors"]["source_node_id"] != controlled_node["node_id"]:
            raise RuntimeError("GEO-1 entity geometry does not use the shared controlled-pass anchors")
        if between_node["inputs"]["line_evaluations"]["source_node_id"] != line_node["node_id"]:
            raise RuntimeError("GEO-1 entity geometry does not use synthesized line evidence")
        predicates = [node for node in nodes if node.get("kind") == "predicate"]
        non_predicates = [node for node in nodes if node.get("kind") != "predicate"]
        document["draft_plan"]["nodes"] = [
            *non_predicates,
            aggregate_node(str(between_node["node_id"])),
            rate_node(str(between_node["node_id"])),
            *predicates,
        ]
        document["recipe"]["recipe_id"] = "reception_between_observed_lines_v1"
        document["draft_plan"]["recipe_id"] = "reception_between_observed_lines_v1"
        document["recipe"]["display_name"] = "Reception Between Observed Lines"
        document["recipe"]["allowed_claims"] = [
            "Signed receiver geometry between declared observed line ranks and interval rates over controlled receptions."
        ]
        document["recipe"]["limitations"] = [
            "Observed line ranks are geometric bands, never tactical role names or formation labels.",
            "The deepest observed line selector is geometric and is not legal offside.",
            "No intent, quality, optimality, causation, or assignment claim is made.",
        ]
        bind_document(TacticalQueryDocument.model_validate(copy.deepcopy(document)))
    return bundle, synthesized


def runtime_records(state: Any, node_id: str, output_name: str) -> list[dict[str, Any]]:
    value = state.runtime_values[node_id][output_name]
    return [dict(record) for record in value.records]


def compact_evaluation(record: dict[str, Any], *, role: str) -> dict[str, Any]:
    nearer = record.get("selected_nearer_line") or {}
    farther = record.get("selected_farther_line") or {}
    return {
        "anchor_frame_id": int(record["anchor_frame_id"]),
        "anchor_id": str(record["anchor_id"]),
        "audit_role": role,
        "between_observed_lines_reason": str(record["between_observed_lines_reason"]),
        "between_observed_lines_status": str(record["between_observed_lines_status"]),
        "controlled_pass_status": str(record["controlled_pass_status"]),
        "controlled_reception_frame_id": record.get("controlled_reception_frame_id"),
        "entity_frame_id": record.get("entity_frame_id"),
        "interline_gap_m": record.get("interline_gap_m"),
        "line_selector": str(record["line_selector"]),
        "match_id": str(record["match_id"]),
        "period": str(record["period"]),
        "player_track_coverage_row_ids": list(
            record.get("between_lines_player_track_coverage_row_ids") or []
        ),
        "player_track_coverage_status": record.get(
            "between_lines_player_track_coverage_status"
        ),
        "receiver_id": str(record["receiver_id"]),
        "selected_farther_line_id": farther.get("line_id"),
        "selected_farther_line_player_ids": list(farther.get("defender_ids") or []),
        "selected_nearer_line_id": nearer.get("line_id"),
        "selected_nearer_line_player_ids": list(nearer.get("defender_ids") or []),
        "signed_distance_to_farther_line_m": record.get(
            "signed_distance_to_farther_line_m"
        ),
        "signed_distance_to_nearer_line_m": record.get(
            "signed_distance_to_nearer_line_m"
        ),
        "team_role": str(record["team_role"]),
    }


def strip_source_records(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "source_records"}


def execute_population(
    *,
    plan_bundle: dict[str, Any],
    canonical_root: Path,
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    period_records: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    shared_cache: dict[str, dict[str, Any]] = {}
    for role in ROLE_ORDER:
        document = copy.deepcopy(plan_bundle["documents"][role])
        bound = bind_document(TacticalQueryDocument.model_validate(document))
        executor = TacticalQueryExecutor(
            canonical_root=canonical_root,
            raw_root=raw_root,
            shared_node_output_cache=shared_cache,
        )
        params = runtime_parameters(bound)
        for match_id in MATCH_ORDER:
            for period in PERIOD_ORDER:
                state = executor._execute_period(
                    bound_plan=bound,
                    match_id=match_id,
                    period=period,
                    params=params,
                    compatibility_profile=executor.compatibility_profile,
                )
                rows = runtime_records(
                    state,
                    "between_observed_lines",
                    "anchor_evaluations",
                )
                if any(str(row.get("team_role")) != role for row in rows):
                    raise RuntimeError("perspective-team scope leaked an opposite-team pass row")
                compact = [compact_evaluation(row, role=role) for row in rows]
                aggregate_records = [
                    strip_source_records(record)
                    for record in runtime_records(
                        state,
                        AGGREGATE_NODE_ID,
                        "aggregate_records",
                    )
                ]
                rate_records = [
                    strip_source_records(record)
                    for record in runtime_records(state, RATE_NODE_ID, "rate_records")
                ]
                _assert_operator_reconciliation(
                    compact,
                    aggregate_records=aggregate_records,
                    rate_records=rate_records,
                )
                period_records.append(
                    {
                        "aggregate_records": aggregate_records,
                        "audit_role": role,
                        "match_id": match_id,
                        "period": period,
                        "rate_records": rate_records,
                        "reason_counts": dict(
                            sorted(
                                collections.Counter(
                                    row["between_observed_lines_reason"] for row in compact
                                ).items()
                            )
                        ),
                        "source_record_count": len(compact),
                        "status_counts": _status_counts(compact),
                    }
                )
                evaluations.extend(compact)
    return period_records, evaluations


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = collections.Counter(
        str(record["between_observed_lines_status"]) for record in records
    )
    return {status: int(counts[status]) for status in ("PASS", "FAIL", "UNKNOWN")}


def _assert_operator_reconciliation(
    rows: list[dict[str, Any]],
    *,
    aggregate_records: list[dict[str, Any]],
    rate_records: list[dict[str, Any]],
) -> None:
    by_receiver: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_receiver.setdefault(str(row["receiver_id"]), []).append(row)
    aggregate_by_receiver = {
        str(record["group_key"]["receiver_id"]): record
        for record in aggregate_records
    }
    rate_by_receiver = {
        str(record["group_key"]["receiver_id"]): record for record in rate_records
    }
    if set(by_receiver) != set(aggregate_by_receiver) or set(by_receiver) != set(rate_by_receiver):
        raise RuntimeError("receiver groups differ across primitive, aggregate, and rate")
    for receiver_id, receiver_rows in by_receiver.items():
        aggregate = aggregate_by_receiver[receiver_id]
        rate = rate_by_receiver[receiver_id]
        expected_counts = _joint_partition_counts(
            records=receiver_rows,
            numerator_status_field="between_observed_lines_status",
            denominator_status_field="controlled_pass_status",
        )
        if int(aggregate["population_count"]) != len(receiver_rows):
            raise RuntimeError(f"aggregate population mismatch for receiver {receiver_id}")
        if any(int(rate[field]) != value for field, value in expected_counts.items()):
            raise RuntimeError(f"rate partition mismatch for receiver {receiver_id}")


def interval_payload(records: list[dict[str, Any]], *, group_key: dict[str, str]) -> dict[str, Any]:
    counts = _joint_partition_counts(
        records=records,
        numerator_status_field="between_observed_lines_status",
        denominator_status_field="controlled_pass_status",
    )
    result = RateIntervalResult(
        rate_kind="rate",
        population_expression=POPULATION_EXPRESSION,
        group_key=group_key,
        **counts,
    )
    return {
        "rate_status": result.rate_status,
        "observed": result.observed,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "observed_denominator_count": result.observed_denominator_count,
        "numerator_count_interval": result.numerator_count_interval,
        "denominator_count_interval": result.denominator_count_interval,
        **counts,
    }


def merged_rows(
    period_records: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    periods_by_key = {
        (str(record["audit_role"]), str(record["match_id"]), str(record["period"])): record
        for record in period_records
    }
    rows: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        for match_id in MATCH_ORDER:
            match_records = [
                record
                for record in evaluations
                if record["audit_role"] == role and record["match_id"] == match_id
            ]
            receiver_ids = sorted({str(record["receiver_id"]) for record in match_records})
            receiver_rates = [
                {
                    "receiver_id": receiver_id,
                    **interval_payload(
                        [
                            record
                            for record in match_records
                            if record["receiver_id"] == receiver_id
                        ],
                        group_key={"receiver_id": receiver_id},
                    ),
                }
                for receiver_id in receiver_ids
            ]
            rows.append(
                {
                    "audit_role": role,
                    "match_id": match_id,
                    "periods": [
                        periods_by_key[(role, match_id, period)]
                        for period in PERIOD_ORDER
                    ],
                    "receiver_rates": receiver_rates,
                    "source_record_count": len(match_records),
                    "status_counts": _status_counts(match_records),
                    **interval_payload(
                        match_records,
                        group_key={"audit_role": role, "match_id": match_id},
                    ),
                }
            )
    return rows


def build_table(
    *,
    plan_bundle: dict[str, Any],
    synthesized: dict[str, Any],
    period_records: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = merged_rows(period_records, evaluations)
    return {
        "definition": {
            "entity_frame_field": "controlled_reception_frame_id",
            "entity_id_field": "receiver_id",
            "farther_line_rank": 2,
            "line_boundary_buffer_m": 0.5,
            "line_selector": "declared_ranks",
            "minimum_interline_gap_m": 0.0,
            "nearer_line_rank": 1,
            "population_scope": "perspective_team tracking-confirmed controlled receptions",
        },
        "evaluation_record_count": len(evaluations),
        "evaluation_records": evaluations,
        "evaluation_records_hash": stable_hash(evaluations),
        "meaning_expression": str(MEANING_PATH),
        "meaning_expression_hash": stable_hash(load_json(MEANING_PATH)),
        "period_record_count": len(period_records),
        "period_records_hash": stable_hash(period_records),
        "plan": str(PLAN_PATH),
        "plan_hash": stable_hash(plan_bundle),
        "question": "How often does each receiver receive between declared observed lines?",
        "rows": rows,
        "schema_version": "geo1.reception_between_observed_lines.certified_table.v1",
        "synthesis": {
            "base_document_hash": synthesized["document_hash"],
            "bind": synthesized["bind"],
            "complete_plan_bound": True,
            "shared_anchor_chain": [
                "controlled_pass_episode",
                "multi_line_model",
                "between_observed_lines",
            ],
            "terminals": ["aggregate_over", "rate"],
        },
        "totals": {
            "source_record_count": len(evaluations),
            "status_counts": _status_counts(evaluations),
            **interval_payload(evaluations, group_key={"scope": "all_certified_rows"}),
        },
    }


def render_markdown(table: dict[str, Any]) -> str:
    lines = [
        "# GEO-1 certified reception-between-observed-lines table",
        "",
        f"Plan: `{PLAN_PATH}`",
        f"Plan hash: `{table['plan_hash']}`",
        "",
        "| Role | Match | Controlled rows | Between | Outside | Unknown | Observed rate | Lower | Upper | Receivers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table["rows"]:
        statuses = row["status_counts"]
        lines.append(
            f"| `{row['audit_role']}` | `{row['match_id']}` | {row['source_record_count']} | "
            f"{statuses['PASS']} | {statuses['FAIL']} | {statuses['UNKNOWN']} | "
            f"{_rate(row['observed'])} | {_rate(row['lower_bound'])} | "
            f"{_rate(row['upper_bound'])} | {len(row['receiver_rates'])} |"
        )
    totals = table["totals"]
    lines.extend(
        [
            "",
            "## Certified total",
            "",
            f"- Controlled-reception rows: {totals['source_record_count']}",
            f"- Between PASS: {totals['status_counts']['PASS']}",
            f"- Outside/minimum-gap FAIL: {totals['status_counts']['FAIL']}",
            f"- Evidence/buffer UNKNOWN: {totals['status_counts']['UNKNOWN']}",
            f"- Rate interval: {_rate(totals['lower_bound'])} to {_rate(totals['upper_bound'])}",
            "- Line labels: observed geometric ranks only; no tactical role or legal-offside claim.",
            "",
        ]
    )
    return "\n".join(lines)


def _rate(value: Any) -> str:
    return "UNKNOWN" if value is None else f"{float(value):.4f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", type=Path, default=Path("data/canonical/v1"))
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/idsse/figshare-28196177-v1"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    plan_bundle, synthesized = synthesized_plan_bundle()
    period_records, evaluations = execute_population(
        plan_bundle=plan_bundle,
        canonical_root=args.canonical_root,
        raw_root=args.raw_root,
    )
    table = build_table(
        plan_bundle=plan_bundle,
        synthesized=synthesized,
        period_records=period_records,
        evaluations=evaluations,
    )
    provenance = {
        "evaluation_records_hash": table["evaluation_records_hash"],
        "generated_by": "scripts/packets/geo1_reception_between_lines_generator.py",
        "meaning_expression_hash": table["meaning_expression_hash"],
        "period_records_hash": table["period_records_hash"],
        "plan_hash": table["plan_hash"],
        "schema_version": "geo1.reception_between_observed_lines.provenance.v1",
        "table_hash": stable_hash(table),
    }
    write_or_check(PLAN_PATH, plan_bundle, check=args.check)
    write_or_check(TABLE_PATH, table, check=args.check)
    write_or_check(PROVENANCE_PATH, provenance, check=args.check)
    markdown = render_markdown(table)
    if args.check:
        if not TABLE_MD_PATH.is_file() or TABLE_MD_PATH.read_text(encoding="utf-8") != markdown:
            raise RuntimeError(f"byte reproduction failed: {TABLE_MD_PATH}")
    else:
        TABLE_MD_PATH.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "evaluation_record_count": table["evaluation_record_count"],
                "plan_hash": table["plan_hash"],
                "status": "reproduced" if args.check else "generated",
                "status_counts": table["totals"]["status_counts"],
                "table_hash": provenance["table_hash"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
