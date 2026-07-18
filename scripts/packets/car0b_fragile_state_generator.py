#!/usr/bin/env python3
"""Generate the certified CAR-0b fragile-state population table."""

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


SOURCE_PLAN = Path("delivery/packets/r1-c-sweep/plans/r1_5_fragile_possession_state_v0.json")
OUT_DIR = Path("delivery/packets/car-0b-fragile-state")
PLAN_PATH = OUT_DIR / "fragile_state_eligibility_v0.json"
TABLE_PATH = OUT_DIR / "fragile_state_population_table.json"
TABLE_MD_PATH = OUT_DIR / "fragile_state_population_table.md"
PROVENANCE_PATH = OUT_DIR / "provenance.json"
MATCH_ORDER = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]
ROLE_ORDER = ["home", "away"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_or_check(path: Path, payload: Any, *, check: bool) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != encoded:
            raise RuntimeError(f"byte reproduction failed: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded, encoding="utf-8")


def episode_node() -> dict[str, Any]:
    return {
        "kind": "primitive", "node_id": "fragile_carrier_episode",
        "catalog_ref": "fragile_carrier_episode", "version": "0.1.0",
        "inputs": {"pressure_evaluations": {
            "source_node_id": "pressure_on_carrier", "output_name": "anchor_evaluations"}},
        "parameters": {
            "observation_frame_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "pressure_frame_id", "kind": "frame"}},
            "onset_carrier_id_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "carrier_id", "kind": "entity"}},
            "possession_id_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "possession_id", "kind": "provenance"}},
            "pressure_status_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "pressure_status", "kind": "status"}},
            "carrier_control_status_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "controlled_reception_status", "kind": "status"}},
            "boundary_status_field": {"payload_type": "field_ref", "unit": "none", "value": {"field": "episode_boundary_status", "kind": "status"}},
            "same_episode_gap_tolerance_s": {"payload_type": "number", "unit": "second", "value": 0.4},
            "refractory_after_resolution_s": {"payload_type": "number", "unit": "second", "value": 1.0},
        },
    }


def eligibility_node() -> dict[str, Any]:
    return {
        "kind": "primitive", "node_id": "fragile_state_eligibility",
        "catalog_ref": "fragile_state_eligibility", "version": "0.1.0",
        "inputs": {"episodes": {
            "source_node_id": "fragile_carrier_episode", "output_name": "episodes"}},
    }


def build_bundle() -> dict[str, Any]:
    source = load_json(SOURCE_PLAN)
    bundle = {"schema_version": "car0b.fragile_state.plan_bundle.v1",
              "target_id": "car_0b_fragile_state_eligibility_v0",
              "perspective_team_roles": ROLE_ORDER, "documents": {}}
    for role in ROLE_ORDER:
        payload = copy.deepcopy(source["documents"][role])
        nodes = payload["draft_plan"]["nodes"]
        controlled = next(copy.deepcopy(n) for n in nodes if n.get("node_id") == "controlled_pass_episode_2")
        controlled["node_id"] = "controlled_pass_episode"
        pressure = next(copy.deepcopy(n) for n in nodes if n.get("node_id") == "pressure_on_carrier")
        pressure["inputs"]["anchors"]["source_node_id"] = "controlled_pass_episode"
        pressure["parameters"]["minimum_pressure_duration_seconds"]["value"] = 0.2
        predicate = {
            "kind": "predicate", "node_id": "eligible_predicate",
            "input": {"source_node_id": "fragile_state_eligibility", "output_name": "fragile_state_status"},
            "operator": {"name": "eq", "version": "1.0.0"},
            "compare": {"payload_type": "enum", "unit": "none", "value": "PASS"},
        }
        draft = payload["draft_plan"]
        draft.update({
            "plan_id": "car_0b_fragile_state_eligibility_v0",
            "recipe_id": "car_0b_fragile_state_eligibility_v0",
            "nodes": [controlled, pressure, episode_node(), eligibility_node(), predicate],
            "anchor_source": {"source_node_id": "fragile_state_eligibility",
                              "output_name": "eligibility_evaluations"},
            "classification_mode": "exhaustive",
            "classification_rules": [{"label": "CAR_0B_FRAGILE_STATE_ELIGIBLE",
                                      "predicate_ids": ["eligible_predicate"],
                                      "description": "Certified active-possession, unique-control, reused-pressure eligibility only."}],
            "requested_evidence": [
                {"alias": field, "field": field, "required": True,
                 "source": {"source_node_id": "fragile_state_eligibility",
                            "output_name": "eligibility_evaluations"}}
                for field in ("episode_id", "onset_frame_id", "onset_carrier_id",
                              "fragile_state_status", "fragile_state_reason",
                              "pressure_source_signature", "entry_dwell_seconds",
                              "same_episode_gap_tolerance_s")
            ],
        })
        payload["recipe"] = {
            "schema_version": "1.0", "recipe_id": "car_0b_fragile_state_eligibility_v0",
            "recipe_version": "0.1.0", "display_name": "CAR-0b Fragile-State Eligibility",
            "description": "Certifies fragile-state eligibility using active possession, unique carrier control, and reused pressure evidence.",
            "output_classifications": ["CAR_0B_FRAGILE_STATE_ELIGIBLE"],
            "allowed_claims": ["An onset episode met the declared possession, control, and certified pressure eligibility law."],
            "disallowed_claims": ["Eligibility measures continuity, value, ability, causation, decision quality, or replacement performance."],
            "limitations": ["Local numbers, support arrival, confinement, and escape geometry are not eligibility requirements.",
                            "Seven-match methodology demonstration only."],
            "parameters": [], "default_unknown_evidence_policy": "exclude_candidate",
        }
        payload["default_invocation"].update({
            "invocation_id": f"car_0b_fragile_state_eligibility_v0_{role}",
            "max_results": 100,
        })
        bundle["documents"][role] = payload
    return bundle


def execute(bundle: dict[str, Any], canonical_root: Path) -> list[dict[str, Any]]:
    executor = TacticalQueryExecutor(canonical_root=canonical_root)
    rows: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        document = TacticalQueryDocument.model_validate(copy.deepcopy(bundle["documents"][role]))
        bound = bind_document(document)
        params = runtime_parameters(bound)
        for match_id in bound.match_ids:
            evaluations: list[dict[str, Any]] = []
            pressure_candidates: list[dict[str, Any]] = []
            for period in bound.periods:
                state = executor._execute_period(
                    bound_plan=bound, match_id=match_id, period=period, params=params,
                    compatibility_profile=executor.compatibility_profile,
                )
                evaluations.extend(state.signals["fragile_state_eligibility"]["eligibility_evaluations"])
                pressure_candidates.extend(state.signals["pressure_on_carrier"]["anchor_evaluations"])
            statuses = collections.Counter(str(item["fragile_state_status"]) for item in evaluations)
            reasons = collections.Counter(str(item["fragile_state_reason"]) for item in evaluations)
            pressure_statuses = collections.Counter(str(item["pressure_status"]) for item in pressure_candidates)
            pressure_reasons = collections.Counter(
                f"{item['pressure_status']}:{item['pressure_reason']}" for item in pressure_candidates
            )
            total = len(evaluations)
            rows.append({
                "match_id": match_id, "team_role": role, "episode_population": total,
                "eligible_episode_count": statuses["PASS"], "fail_episode_count": statuses["FAIL"],
                "unknown_episode_count": statuses["UNKNOWN"],
                "pressure_candidate_population": len(pressure_candidates),
                "unknown_pressure_candidate_count": pressure_statuses["UNKNOWN"],
                "unknown_share": (0.0 if not pressure_candidates else
                                  pressure_statuses["UNKNOWN"] / len(pressure_candidates)),
                "status_counts": dict(sorted(statuses.items())),
                "reason_code_counts": dict(sorted(reasons.items())),
                "pressure_status_counts": dict(sorted(pressure_statuses.items())),
                "pressure_reason_code_counts": dict(sorted(pressure_reasons.items())),
                "episode_ids_hash": stable_hash(sorted(str(item["episode_id"]) for item in evaluations)),
            })
    return sorted(rows, key=lambda item: (MATCH_ORDER.index(item["match_id"]), ROLE_ORDER.index(item["team_role"])))


def render_markdown(table: dict[str, Any]) -> str:
    lines = ["# CAR-0b certified fragile-state population", "",
             "| Match | Team | Pressure candidates | Episodes | Eligible | Episode UNKNOWN | Coverage UNKNOWN share | Reasons |",
             "|---|---|---:|---:|---:|---:|---:|---|"]
    for row in table["rows"]:
        reasons = ", ".join(f"{key}={value}" for key, value in row["reason_code_counts"].items())
        lines.append(f"| `{row['match_id']}` | `{row['team_role']}` | {row['pressure_candidate_population']} | {row['episode_population']} | "
                     f"{row['eligible_episode_count']} | {row['unknown_episode_count']} | "
                     f"{row['unknown_share']:.4f} | {reasons} |")
    totals = table["totals"]
    lines.extend(["", "## Total", "",
                  f"- Pressure candidates: {totals['pressure_candidate_population']}",
                  f"- Coverage-UNKNOWN pressure candidates: {totals['unknown_pressure_candidate_count']}",
                  f"- Episode population: {totals['episode_population']}",
                  f"- Eligible: {totals['eligible_episode_count']}",
                  f"- UNKNOWN: {totals['unknown_episode_count']}",
                  "- No continuity outcome or player aggregation is computed.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-root", type=Path, default=Path("data/canonical/v1"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    bundle = build_bundle()
    rows = execute(bundle, args.canonical_root)
    totals = {
        key: sum(int(row[key]) for row in rows)
        for key in ("pressure_candidate_population", "unknown_pressure_candidate_count",
                    "episode_population", "eligible_episode_count", "fail_episode_count", "unknown_episode_count")
    }
    table = {"schema_version": "car0b.fragile_state.population.v1", "rows": rows,
             "totals": totals, "plan_hash": stable_hash(bundle),
             "population_definition": "deduplicated fragile carrier episodes; no optional context geometry required"}
    provenance = {"schema_version": "car0b.fragile_state.provenance.v1",
                  "generated_by": "scripts/packets/car0b_fragile_state_generator.py",
                  "plan_hash": stable_hash(bundle), "table_hash": stable_hash(table)}
    write_or_check(PLAN_PATH, bundle, check=args.check)
    write_or_check(TABLE_PATH, table, check=args.check)
    write_or_check(PROVENANCE_PATH, provenance, check=args.check)
    markdown = render_markdown(table)
    if args.check:
        if not TABLE_MD_PATH.is_file() or TABLE_MD_PATH.read_text(encoding="utf-8") != markdown:
            raise RuntimeError(f"byte reproduction failed: {TABLE_MD_PATH}")
    else:
        TABLE_MD_PATH.write_text(markdown, encoding="utf-8")
    print(json.dumps({"status": "reproduced" if args.check else "generated",
                      "totals": totals, **provenance}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
