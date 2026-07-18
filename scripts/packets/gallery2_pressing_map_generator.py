#!/usr/bin/env python3
"""Generate GALLERY-2's synthesized, bound pressing-map artifacts."""

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
from tqe.runtime.executor import TacticalQueryExecutor, parquet_rows, runtime_parameters  # noqa: E402
from tqe.runtime.ir import TacticalQueryDocument, stable_hash  # noqa: E402
from tqe.semantic_compiler.meaning_expression import (  # noqa: E402
    load_meaning_expression_from_path,
    load_pack_vocabulary,
)
from tqe.semantic_compiler.target_synthesis import synthesize_and_bind  # noqa: E402

OUT_DIR = Path("delivery/packets/gallery-2-pressing-map")
MEANING_PATH = OUT_DIR / "meaning-expression.json"
PLAN_PATH = OUT_DIR / "pressing_map_regain_thirds_v0.json"
TABLE_PATH = OUT_DIR / "pressing_map_regain_thirds_table.json"
TABLE_MD_PATH = OUT_DIR / "pressing_map_regain_thirds_table.md"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
AGGREGATE_TEMPLATE_PATH = Path(
    "delivery/packets/scp2-3-evidence/witness-plan/counterattack_initiation_v0.json"
)
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]
PERIOD_ORDER = ["firstHalf", "secondHalf"]
ZONE_ORDER = ["defensive_third", "middle_third", "final_third"]
ZONE_NODE_IDS = {zone: f"structured_zone_{zone}" for zone in ZONE_ORDER}
AGGREGATE_NODE_IDS = {
    "all": "aggregate_over_all_regains",
    **{zone: f"aggregate_over_{zone}" for zone in ZONE_ORDER},
}


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


def aggregate_template() -> dict[str, Any]:
    payload = load_json(AGGREGATE_TEMPLATE_PATH)
    document = payload["documents"]["home"]
    return copy.deepcopy(
        next(node for node in document["draft_plan"]["nodes"] if node.get("node_id") == "aggregate_over")
    )


def configured_aggregate(
    *,
    node_id: str,
    source_node_id: str,
    status_field: str,
    group_by_fields: list[str],
) -> dict[str, Any]:
    node = aggregate_template()
    node["node_id"] = node_id
    node["inputs"]["population"] = {
        "source_node_id": source_node_id,
        "output_name": "anchor_evaluations",
    }
    parameters = node["parameters"]
    parameters["population_expression"]["value"] = "observed regain anchors by perspective team"
    parameters["group_by_fields"]["value"] = group_by_fields
    parameters["status_field"]["value"] = status_field
    parameters["same_team_perspective_required"]["value"] = False
    parameters["entity_identity_preserved_required"]["value"] = False
    parameters["frame_alignment_required"]["value"] = False
    parameters["team_role_field"]["value"] = "none"
    parameters["constraint_opt_out_reason"]["value"] = (
        "transition_anchor already scopes records to one perspective; this count does not join "
        "entities or frames"
    )
    return node


def synthesized_plan_bundle() -> tuple[dict[str, Any], dict[str, Any]]:
    vocabulary = load_pack_vocabulary()
    loaded = load_meaning_expression_from_path(MEANING_PATH, vocabulary=vocabulary)
    if loaded.expression is None:
        raise RuntimeError(f"GALLERY-2 meaning expression refused: {loaded.refusal}")
    synthesized = synthesize_and_bind(
        loaded.expression,
        coverage_rows=load_json(Path("generated/coverage-map.json")),
    )
    bundle = copy.deepcopy(synthesized["document"])
    if bundle.get("schema_version") != "compiler_search_perspective_bundle.v1":
        raise RuntimeError("GALLERY-2 synthesis did not return the required perspective bundle")
    for role in ROLE_ORDER:
        document = bundle["documents"][role]
        draft = document["draft_plan"]
        base = next(node for node in draft["nodes"] if node.get("catalog_ref") == "transition_anchor")
        base["parameters"]["zone_filter"]["value"] = "any"
        base["parameters"]["zone_boundary_buffer_m"]["value"] = 0.5
        zone_nodes: list[dict[str, Any]] = []
        for zone in ZONE_ORDER:
            node = {
                "catalog_ref": "structured_zone",
                "inputs": {
                    "anchors": {
                        "source_node_id": str(base["node_id"]),
                        "output_name": "anchor_evaluations",
                    }
                },
                "kind": "primitive",
                "node_id": ZONE_NODE_IDS[zone],
                "parameters": {
                    "frame_field": {
                        "payload_type": "enum",
                        "unit": "none",
                        "value": "anchor_frame_id",
                    },
                    "zone_boundary_buffer_m": {
                        "payload_type": "number",
                        "unit": "metre",
                        "value": 0.5,
                    },
                    "zone_name": {
                        "payload_type": "enum",
                        "unit": "none",
                        "value": zone,
                    },
                },
                "version": "0.1.0",
            }
            zone_nodes.append(node)
        aggregate_nodes = [
            configured_aggregate(
                node_id=AGGREGATE_NODE_IDS["all"],
                source_node_id=str(base["node_id"]),
                status_field="transition_status",
                group_by_fields=["new_team_role"],
            ),
            *[
                configured_aggregate(
                    node_id=AGGREGATE_NODE_IDS[zone],
                    source_node_id=ZONE_NODE_IDS[zone],
                    status_field="zone_status",
                    group_by_fields=["zone_name"],
                )
                for zone in ZONE_ORDER
            ],
        ]
        predicate_nodes = [node for node in draft["nodes"] if node.get("kind") == "predicate"]
        non_predicate_nodes = [node for node in draft["nodes"] if node.get("kind") != "predicate"]
        draft["nodes"] = [*non_predicate_nodes, *zone_nodes, *aggregate_nodes, *predicate_nodes]
        document["recipe"]["allowed_claims"] = [
            "Observed regain counts by perspective team and registered orientation-aware pitch third."
        ]
        document["recipe"]["limitations"] = [
            "A regain is an observed possession-role change from transition_anchor; it does not prove pressing intent.",
            "Locations within 0.5 m of a third boundary remain UNKNOWN rather than being forced into a third.",
        ]
        bind_document(TacticalQueryDocument.model_validate(copy.deepcopy(document)))
    return bundle, synthesized


def runtime_records(state: Any, node_id: str, output_name: str) -> list[dict[str, Any]]:
    value = state.runtime_values[node_id][output_name]
    return [dict(record) for record in value.records]


def team_names(canonical_root: Path) -> dict[tuple[str, str], str]:
    rows = parquet_rows(canonical_root / "teams.parquet")
    return {
        (str(row["match_id"]), str(row["team_role"])): str(row["team_name"])
        for row in rows.to_dict("records")
    }


def compact_moment(
    record: dict[str, Any],
    *,
    role: str,
    team_name: str,
    zone_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    located = [
        zone
        for zone in ZONE_ORDER
        if str(zone_records[zone].get("zone_status") or "") == "PASS"
    ]
    if len(located) > 1:
        raise RuntimeError(f"registered thirds overlap at anchor {record.get('anchor_id')}: {located}")
    zone = located[0] if located else None
    zone_record = zone_records[zone] if zone else zone_records["middle_third"]
    return {
        "anchor_frame_id": int(record["anchor_frame_id"]),
        "anchor_id": str(record["anchor_id"]),
        "attacking_direction": record.get("attacking_direction"),
        "audit_role": role,
        "end_frame_id": int(record["end_frame_id"]),
        "location_status": "PASS" if zone else "UNKNOWN",
        "match_id": str(record["match_id"]),
        "new_team_role": str(record["new_team_role"]),
        "period": str(record["period"]),
        "regain_status": str(record["transition_status"]),
        "start_frame_id": int(record["start_frame_id"]),
        "team_name": team_name,
        "transition_match_time_ms": record.get("transition_match_time_ms"),
        "transition_reason": str(record["transition_reason"]),
        "zone_ball_x_m": zone_record.get("zone_ball_x_m"),
        "zone_ball_y_m": zone_record.get("zone_ball_y_m"),
        "zone_name": zone,
        "zone_normalized_ball_x_m": zone_record.get("zone_normalized_ball_x_m"),
        "zone_reason": str(zone_record.get("zone_reason") or "location_not_resolved"),
    }


def execute_population(
    *,
    plan_bundle: dict[str, Any],
    canonical_root: Path,
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    names = team_names(canonical_root)
    period_records: list[dict[str, Any]] = []
    moments: list[dict[str, Any]] = []
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
                overall = runtime_records(state, "transition_anchor", "anchor_evaluations")
                by_zone = {
                    zone: {
                        str(record["anchor_id"]): record
                        for record in runtime_records(state, ZONE_NODE_IDS[zone], "anchor_evaluations")
                    }
                    for zone in ZONE_ORDER
                }
                period_moments: list[dict[str, Any]] = []
                for record in overall:
                    anchor_id = str(record["anchor_id"])
                    if any(anchor_id not in by_zone[zone] for zone in ZONE_ORDER):
                        raise RuntimeError(f"zone execution omitted regain anchor {anchor_id}")
                    period_moments.append(
                        compact_moment(
                            record,
                            role=role,
                            team_name=names[(match_id, role)],
                            zone_records={zone: by_zone[zone][anchor_id] for zone in ZONE_ORDER},
                        )
                    )
                third_counts = {
                    zone: sum(moment["zone_name"] == zone for moment in period_moments)
                    for zone in ZONE_ORDER
                }
                location_unknown_count = sum(moment["zone_name"] is None for moment in period_moments)
                if sum(third_counts.values()) + location_unknown_count != len(overall):
                    raise RuntimeError("thirds do not reconcile to the observed regain population")
                aggregates = {
                    key: [
                        {
                            field: value
                            for field, value in aggregate.items()
                            if field != "source_records"
                        }
                        for aggregate in runtime_records(state, node_id, "aggregate_records")
                    ]
                    for key, node_id in AGGREGATE_NODE_IDS.items()
                }
                period_records.append(
                    {
                        "aggregates": aggregates,
                        "audit_role": role,
                        "location_unknown_count": location_unknown_count,
                        "match_id": match_id,
                        "period": period,
                        "population_count": len(overall),
                        "regain_pass_count": sum(
                            str(record.get("transition_status")) == "PASS" for record in overall
                        ),
                        "regain_unknown_count": sum(
                            str(record.get("transition_status")) == "UNKNOWN" for record in overall
                        ),
                        "team_name": names[(match_id, role)],
                        "third_counts": third_counts,
                    }
                )
                moments.extend(period_moments)
    return period_records, moments


def merged_rows(period_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for record in period_records:
        key = (str(record["audit_role"]), str(record["match_id"]))
        row = rows.setdefault(
            key,
            {
                "audit_role": key[0],
                "location_unknown_count": 0,
                "match_id": key[1],
                "periods": [],
                "population_count": 0,
                "team_name": record["team_name"],
                "third_counts": {zone: 0 for zone in ZONE_ORDER},
            },
        )
        period = copy.deepcopy(record)
        row["periods"].append(period)
        row["population_count"] += int(record["population_count"])
        row["location_unknown_count"] += int(record["location_unknown_count"])
        for zone in ZONE_ORDER:
            row["third_counts"][zone] += int(record["third_counts"][zone])
    return [rows[(role, match)] for role in ROLE_ORDER for match in MATCH_ORDER]


def build_table(
    *,
    plan_bundle: dict[str, Any],
    synthesized: dict[str, Any],
    period_records: list[dict[str, Any]],
    moments: list[dict[str, Any]],
) -> dict[str, Any]:
    located = sum(moment["location_status"] == "PASS" for moment in moments)
    unknown = len(moments) - located
    totals = {
        "a_count": located,
        "b_count": 0,
        "c_count": unknown,
        "d1_count": 0,
        "d2_count": 0,
        "e_count": 0,
        "location_unknown_count": unknown,
        "population_count": len(moments),
        "rate_lower_bound": located / len(moments) if moments else 0.0,
        "rate_observed": 1.0 if located else 0.0,
        "rate_upper_bound": 1.0,
        "third_counts": {
            zone: sum(moment["zone_name"] == zone for moment in moments)
            for zone in ZONE_ORDER
        },
        "unknown_count": unknown,
    }
    return {
        "fallback_rung": "a_thirds",
        "meaning_expression": str(MEANING_PATH),
        "meaning_expression_hash": stable_hash(load_json(MEANING_PATH)),
        "moment_record_count": len(moments),
        "moment_records": moments,
        "moment_records_hash": stable_hash(moments),
        "period_record_count": len(period_records),
        "period_records_hash": stable_hash(period_records),
        "plan": str(PLAN_PATH),
        "plan_hash": stable_hash(plan_bundle),
        "question": "Where does each team win the ball back?",
        "rows": merged_rows(period_records),
        "schema_version": "gallery_2_pressing_map_table.v1",
        "synthesis": {
            "base_document_hash": synthesized["document_hash"],
            "bind": synthesized["bind"],
            "registered_zone_filters": ZONE_ORDER,
            "registry_modified": False,
        },
        "totals": totals,
    }


def markdown_table(table: dict[str, Any]) -> str:
    lines = [
        "# GALLERY-2 certified pressing-map table",
        "",
        "Fallback rung: **(a) orientation-aware thirds**.",
        "",
        "| Team | Match | Defensive third | Middle third | Attacking third | Location unknown | Total |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in table["rows"]:
        thirds = row["third_counts"]
        lines.append(
            f"| {row['team_name']} | {row['match_id']} | {thirds['defensive_third']} | "
            f"{thirds['middle_third']} | {thirds['final_third']} | "
            f"{row['location_unknown_count']} | {row['population_count']} |"
        )
    totals = table["totals"]
    lines.extend(
        [
            "",
            f"Observed regain records: **{totals['population_count']:,}**.",
            f"Location-UNKNOWN boundary/missing records: **{totals['location_unknown_count']:,}**.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", type=Path, default=Path("data/canonical/v1"))
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/idsse/figshare-28196177-v1"),
    )
    parser.add_argument("--check", action="store_true", help="execute and byte-compare committed artifacts")
    args = parser.parse_args()

    plan_bundle, synthesized = synthesized_plan_bundle()
    period_records, moments = execute_population(
        plan_bundle=plan_bundle,
        canonical_root=args.canonical_root,
        raw_root=args.raw_root,
    )
    table = build_table(
        plan_bundle=plan_bundle,
        synthesized=synthesized,
        period_records=period_records,
        moments=moments,
    )
    provenance = {
        "fallback_rung": "a_thirds",
        "meaning_expression_hash": stable_hash(load_json(MEANING_PATH)),
        "moment_records_hash": table["moment_records_hash"],
        "period_records_hash": table["period_records_hash"],
        "plan_hash": table["plan_hash"],
        "population_count": table["totals"]["population_count"],
        "registry_modified": False,
        "schema_version": "gallery_2_pressing_map_provenance.v1",
        "table_hash": stable_hash(table),
    }
    write_or_check(PLAN_PATH, plan_bundle, check=args.check)
    write_or_check(TABLE_PATH, table, check=args.check)
    write_or_check(PROVENANCE_PATH, provenance, check=args.check)
    markdown = markdown_table(table)
    if args.check:
        if not TABLE_MD_PATH.is_file() or TABLE_MD_PATH.read_text(encoding="utf-8") != markdown:
            raise RuntimeError(f"byte reproduction failed: {TABLE_MD_PATH}")
    else:
        TABLE_MD_PATH.write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "fallback_rung": "a_thirds",
                "location_unknown_count": table["totals"]["location_unknown_count"],
                "moment_record_count": len(moments),
                "plan_hash": table["plan_hash"],
                "population_count": table["totals"]["population_count"],
                "status": "reproduced" if args.check else "generated",
                "table_hash": provenance["table_hash"],
                "third_counts": table["totals"]["third_counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
