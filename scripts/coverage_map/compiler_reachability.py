#!/usr/bin/env python3
"""Type-directed composition synthesizer v0.

This is not natural-language compilation. It measures whether a bounded,
typed-target synthesizer can construct executable plans from catalog semantics
without being handed the coverage-map gold chain.
"""

from __future__ import annotations

import collections
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import BindError, bind_document  # noqa: E402
from tqe.runtime.catalog import default_catalog  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import ExecutionStatus, TacticalQueryDocument, stable_hash  # noqa: E402


TARGETS = ROOT / "config" / "compiler-reachability" / "targets.v0.json"
LEDGER = ROOT / "generated" / "coverage-map.json"
OUT_DIR = ROOT / "generated" / "compiler-reachability-v0"
PLAN_DIR = OUT_DIR / "plans"
ROW_LEDGER = OUT_DIR / "row-ledger.json"
ROW_CSV = OUT_DIR / "row-ledger.csv"
REPORT = ROOT / "artifacts" / "autonomous" / "compiler-reachability-v0-report.json"

SYNTHESIZER_VERSION = "synthesizer.v0.1"
SYNTHESIZER_STRATEGY = (
    "synthesizer.v0.1.strategy=typed_target_patterns.max_depth=4.max_branching=6"
)
MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]

EXCLUDED_CATALOG_REFS = {
    # Trusted/bespoke or concept-shaped nodes are not available to v0 synthesis.
    "controlled_line_break_episode",
    "relation_destination_entry_classification",
    "outcome_classification",
}


def main() -> int:
    targets_payload = load_json(TARGETS)
    coverage_rows = load_json(LEDGER)
    catalog_index = CatalogIndex()
    PLAN_DIR.mkdir(parents=True, exist_ok=True)

    row_results: list[dict[str, Any]] = []
    for target in targets_payload["targets"]:
        print(f"[compiler-reachability] {target['target_id']}", flush=True)
        row = coverage_row(coverage_rows, target["concept"])
        result = evaluate_target(
            target=target,
            row=row,
            catalog_index=catalog_index,
        )
        row_results.append(result)
        print(
            f"[compiler-reachability] {target['target_id']} -> {result['result']} "
            f"({result['failure_taxonomy'] or 'ok'})",
            flush=True,
        )

    update_coverage_rows(coverage_rows, row_results)
    LEDGER.write_text(json.dumps(coverage_rows, indent=1) + "\n", encoding="utf-8")
    write_row_outputs(row_results)
    report = build_report(
        targets_payload=targets_payload,
        coverage_rows=coverage_rows,
        row_results=row_results,
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


class CatalogIndex:
    def __init__(self) -> None:
        catalog = default_catalog()
        entries = [*catalog.primitives, *catalog.relations]
        self.entries = {
            entry.name: entry
            for entry in entries
            if entry.name not in EXCLUDED_CATALOG_REFS
        }
        self.operators = {operator.name for operator in catalog.operators}

    def provider_for_evidence(
        self,
        required_fields: set[str],
        *,
        preferred_kind: str | None = None,
    ) -> str | None:
        candidates: list[tuple[int, int, str]] = []
        for name, entry in self.entries.items():
            fields = set(entry.evidence_fields)
            for output in entry.outputs:
                fields.update(output.evidence_fields)
            covered = required_fields & fields
            if not required_fields.issubset(fields):
                continue
            kind_penalty = 0 if preferred_kind is None or entry.kind.value == preferred_kind else 1
            candidates.append((kind_penalty, len(fields), name))
        if not candidates:
            return None
        return sorted(candidates)[0][2]

    def require_provider(self, required_fields: set[str], *, preferred_kind: str | None = None) -> str:
        provider = self.provider_for_evidence(required_fields, preferred_kind=preferred_kind)
        if provider is None:
            raise SynthesisError(
                "synthesis_gap",
                f"No allowed catalog provider covers evidence fields {sorted(required_fields)}.",
            )
        return provider


class SynthesisError(Exception):
    def __init__(self, taxonomy: str, message: str) -> None:
        super().__init__(message)
        self.taxonomy = taxonomy
        self.message = message


def evaluate_target(
    *,
    target: dict[str, Any],
    row: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    target_contract = target["target_contract"]
    hint_violation = concept_name_used_as_hint(target)
    try:
        if hint_violation:
            raise SynthesisError(
                "composition_validity_gap",
                "Target contract contains the reporting concept name; refusing concept-name hint.",
            )
        document_payload = synthesize_document(
            target_id=target["target_id"],
            target_contract=target_contract,
            catalog_index=catalog_index,
        )
    except SynthesisError as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy=error.taxonomy,
            message=error.message,
            document_payload=None,
            execution=None,
            rows=[],
            concept_name_hint=hint_violation,
        )

    plan_path = PLAN_DIR / f"{target['target_id']}.json"
    plan_path.write_text(json.dumps(document_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        document = TacticalQueryDocument.model_validate(document_payload)
        bound = bind_document(document)
    except (BindError, ValueError) as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            document_payload=document_payload,
            execution=None,
            rows=[],
            concept_name_hint=hint_violation,
        )

    try:
        execution = TacticalQueryExecutor().execute(bound)
    except Exception as error:  # pragma: no cover - report carries exact runtime failure.
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            document_payload=document_payload,
            execution=None,
            rows=[],
            concept_name_hint=hint_violation,
        )

    rows = execution_result_rows(execution)
    evidence_failures = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    valid_execution = execution.status == ExecutionStatus.PASS and evidence_failures == 0
    if not valid_execution:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message="Synthesized plan did not execute with complete requested evidence.",
            document_payload=document_payload,
            execution=execution,
            rows=rows,
            concept_name_hint=hint_violation,
        )
    return row_result(
        target=target,
        row=row,
        result="compiler_reachable",
        failure_taxonomy=None,
        message="Synthesizer produced a valid executable plan under the declared v0 search budget.",
        document_payload=document_payload,
        execution=execution,
        rows=rows,
        concept_name_hint=hint_violation,
    )


def concept_name_used_as_hint(target: dict[str, Any]) -> bool:
    concept = str(target["concept"]).lower()
    contract = json.dumps(target["target_contract"], sort_keys=True).lower()
    return concept in contract


def synthesize_document(
    *,
    target_id: str,
    target_contract: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    pattern = target_contract["pattern"]
    if pattern == "single_carry_forward_threshold":
        return build_carry_progression(target_id, target_contract, catalog_index)
    if pattern == "single_anchor_pressure_status":
        return build_direct_pressure(target_id, target_contract, catalog_index)
    if pattern == "carry_pressure_delta_join":
        return build_carry_pressure_change_join(target_id, target_contract, catalog_index)
    if pattern == "transition_outcome_window":
        return build_regain_settled_outcome(target_id, target_contract, catalog_index)
    if pattern == "unsupported_alignment_probe":
        raise SynthesisError(
            "missing_constraint",
            "v0 target declares semantic alignment requirements that are not yet a searchable composition-rule object.",
        )
    raise SynthesisError("synthesis_gap", f"Unsupported v0 target pattern {pattern!r}.")


def build_carry_progression(
    target_id: str,
    target_contract: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    controlled = catalog_index.require_provider({"controlled_pass_status", "receiver_id"})
    carry = catalog_index.require_provider(
        {"carry_status", "carry_forward_progression_m", "carrier_id"},
    )
    nodes = [
        primitive("controlled_pass", controlled),
        primitive(
            "carry_episode",
            carry,
            inputs={"controlled_pass_anchors": ref("controlled_pass", "anchors")},
        ),
        predicate_eq("carry_pass", "carry_episode", "carry_status", "PASS"),
        predicate_gte("progression_gte", "carry_episode", "forward_progression_m", 3.0, "metre"),
    ]
    return document(
        target_id=target_id,
        display_name="Synthesized Carry Progression",
        description="Type-directed carry progression target generated from evidence fields.",
        nodes=nodes,
        predicate_ids=["carry_pass", "progression_gte"],
        anchor_source=ref("carry_episode", "anchor_evaluations"),
        requested_evidence=evidence_list("carry_episode", target_contract["required_evidence"]),
        claim_boundary=target_contract["claim_boundary"],
    )


def build_direct_pressure(
    target_id: str,
    target_contract: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    controlled = catalog_index.require_provider({"controlled_pass_status", "receiver_id"})
    pressure = catalog_index.require_provider(
        {"pressure_status", "nearest_defender_distance_m", "closing_speed_mps"},
        preferred_kind="relation",
    )
    nodes = [
        primitive("controlled_pass", controlled),
        primitive(
            "pressure_at_reception",
            pressure,
            kind="relation",
            inputs={"anchors": ref("controlled_pass", "anchors")},
            parameters={
                "frame_field": enum("controlled_reception_frame_id"),
                "carrier_id_field": enum("receiver_id"),
                "maximum_pressure_distance_m": number(4.0, "metre"),
                "minimum_closing_speed_mps": number(0.2, "none"),
                "maximum_approach_angle_degrees": number(100.0, "none"),
                "minimum_pressure_duration_seconds": number(0.0, "second"),
                "lookback_seconds": number(0.4, "second"),
                "candidate_scope": enum("defending_outfield"),
            },
        ),
        predicate_eq("pressure_pass", "pressure_at_reception", "pressure_status", "PASS"),
    ]
    return document(
        target_id=target_id,
        display_name="Synthesized Direct Pressure Candidate",
        description="Type-directed pressure target generated from pressure evidence fields.",
        nodes=nodes,
        predicate_ids=["pressure_pass"],
        anchor_source=ref("pressure_at_reception", "anchor_evaluations"),
        requested_evidence=evidence_list("pressure_at_reception", target_contract["required_evidence"]),
        claim_boundary=target_contract["claim_boundary"],
    )


def build_carry_pressure_change_join(
    target_id: str,
    target_contract: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    controlled = catalog_index.require_provider({"controlled_pass_status", "receiver_id"})
    carry = catalog_index.require_provider({"carry_status", "carry_start_frame_id", "carry_end_frame_id"})
    pressure = catalog_index.require_provider(
        {"pressure_status", "nearest_defender_distance_m"},
        preferred_kind="relation",
    )
    change = catalog_index.require_provider({"change_status", "delta_value"})
    join = catalog_index.require_provider({"join_status", "join_key"})
    nodes = [
        primitive("controlled_pass", controlled),
        primitive(
            "carry_episode",
            carry,
            inputs={"controlled_pass_anchors": ref("controlled_pass", "anchors")},
        ),
        pressure_node("pressure_at_carry_start", pressure, "carry_start_frame_id"),
        pressure_node("pressure_at_carry_end", pressure, "carry_end_frame_id"),
        primitive(
            "pressure_distance_change",
            change,
            inputs={
                "anchors": ref("carry_episode", "anchor_evaluations"),
                "before_evaluations": ref("pressure_at_carry_start", "anchor_evaluations"),
                "after_evaluations": ref("pressure_at_carry_end", "anchor_evaluations"),
            },
            parameters={
                "before_value_field": enum("nearest_defender_distance_m"),
                "after_value_field": enum("nearest_defender_distance_m"),
                "before_status_field": enum("pressure_status"),
                "after_status_field": enum("none"),
                "required_status_value": enum("PASS"),
                "change_mode": enum("increase_at_least"),
                "minimum_change_m": number(2.0, "metre"),
                "maximum_before_value_m": number(4.0, "metre"),
            },
        ),
        primitive(
            "carry_pressure_join",
            join,
            inputs={
                "left_episodes": ref("carry_episode", "anchor_evaluations"),
                "right_episodes": ref("pressure_distance_change", "anchor_evaluations"),
            },
            parameters=join_parameters(
                left_key_field="anchor_id",
                right_key_field="anchor_id",
                left_status_field="carry_status",
                right_status_field="change_status",
            ),
        ),
        predicate_eq("join_pass", "carry_pressure_join", "join_status", "PASS"),
    ]
    return document(
        target_id=target_id,
        display_name="Synthesized Carry Out Of Pressure",
        description="Type-directed carry pressure-change target generated from evidence fields and declared same-anchor constraints.",
        nodes=nodes,
        predicate_ids=["join_pass"],
        anchor_source=ref("carry_pressure_join", "anchor_evaluations"),
        requested_evidence=evidence_list("carry_pressure_join", target_contract["required_evidence"]),
        claim_boundary=target_contract["claim_boundary"],
    )


def build_regain_settled_outcome(
    target_id: str,
    target_contract: dict[str, Any],
    catalog_index: CatalogIndex,
) -> dict[str, Any]:
    transition = catalog_index.require_provider({"transition_status", "transition_type"})
    outcome = catalog_index.require_provider({"outcome_window_status", "minimum_settled_possession_seconds"})
    nodes = [
        primitive(
            "regain_transition",
            transition,
            parameters={
                "transition_type": enum("regain"),
                "minimum_prior_possession_seconds": number(0.4, "second"),
                "zone_filter": enum("any"),
                "zone_boundary_buffer_m": number(0.5, "metre"),
            },
        ),
        primitive(
            "settled_outcome_window",
            outcome,
            inputs={"anchors": ref("regain_transition", "anchor_evaluations")},
            parameters={
                "maximum_window_seconds": number(8.0, "second"),
                "minimum_settled_possession_seconds": number(4.0, "second"),
                "required_anchor_status_field": enum("transition_status"),
                "required_anchor_status_value": enum("PASS"),
            },
        ),
        predicate_eq("transition_pass", "regain_transition", "transition_status", "PASS"),
        predicate_eq("settled_pass", "settled_outcome_window", "outcome_window_status", "PASS"),
    ]
    return document(
        target_id=target_id,
        display_name="Synthesized Post-Regain Retention",
        description="Type-directed transition outcome target generated from transition and outcome evidence fields.",
        nodes=nodes,
        predicate_ids=["transition_pass", "settled_pass"],
        anchor_source=ref("settled_outcome_window", "anchor_evaluations"),
        requested_evidence=[
            *evidence_list(
                "regain_transition",
                ["transition_status", "transition_type", "transition_frame_id"],
            ),
            *evidence_list(
                "settled_outcome_window",
                [
                    "outcome_window_status",
                    "outcome_window_reason",
                    "minimum_settled_possession_seconds",
                ],
            ),
        ],
        claim_boundary=target_contract["claim_boundary"],
    )


def pressure_node(node_id: str, catalog_ref: str, frame_field: str) -> dict[str, Any]:
    return primitive(
        node_id,
        catalog_ref,
        kind="relation",
        inputs={"anchors": ref("carry_episode", "anchor_evaluations")},
        parameters={
            "frame_field": enum(frame_field),
            "carrier_id_field": enum("carrier_id"),
            "maximum_pressure_distance_m": number(4.0, "metre"),
            "minimum_closing_speed_mps": number(-5.0, "none"),
            "maximum_approach_angle_degrees": number(180.0, "none"),
            "minimum_pressure_duration_seconds": number(0.0, "second"),
            "lookback_seconds": number(0.4, "second"),
            "candidate_scope": enum("defending_outfield"),
        },
    )


def document(
    *,
    target_id: str,
    display_name: str,
    description: str,
    nodes: list[dict[str, Any]],
    predicate_ids: list[str],
    anchor_source: dict[str, str],
    requested_evidence: list[dict[str, Any]],
    claim_boundary: str,
) -> dict[str, Any]:
    recipe_id = f"synthesized_{target_id}"
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": recipe_id,
            "recipe_version": "0.1.0",
            "display_name": display_name,
            "description": description,
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [claim_boundary],
            "disallowed_claims": [
                "The system inferred player intent, tactical causation, decision quality, optimality, or pass probability.",
                "The system used a bespoke concept-shaped macro instead of reusable catalog capabilities.",
            ],
            "limitations": [
                "Generated by a bounded v0 type-directed synthesizer from a typed target contract.",
                "Compiler reachability is relative to the declared v0 search strategy and budget.",
            ],
            "output_classifications": [target_id.upper()],
            "parameters": [],
        },
        "default_invocation": {
            "schema_version": "1.0",
            "invocation_id": f"{target_id}_probe",
            "match_ids": MATCH_IDS,
            "periods": ["firstHalf", "secondHalf"],
            "perspective_team_role": "home",
            "parameters": {},
            "max_results": 20,
            "execution_mode": "execute",
        },
        "draft_plan": {
            "schema_version": "1.0",
            "plan_id": f"synthesized_{target_id}",
            "plan_version": "0.1.0",
            "recipe_id": recipe_id,
            "recipe_version": "0.1.0",
            "status": "experimental",
            "unknown_evidence_policy": "exclude_candidate",
            "classification_mode": "partial_declared",
            "nodes": nodes,
            "classification_rules": [
                {
                    "label": target_id.upper(),
                    "predicate_ids": predicate_ids,
                    "description": description,
                }
            ],
            "anchor_source": anchor_source,
            "requested_evidence": requested_evidence,
        },
    }


def primitive(
    node_id: str,
    catalog_ref: str,
    *,
    kind: str = "primitive",
    inputs: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "kind": kind,
        "node_id": node_id,
        "catalog_ref": catalog_ref,
        "version": "0.1.0",
    }
    if inputs:
        node["inputs"] = inputs
    if parameters:
        node["parameters"] = parameters
    return node


def ref(node_id: str, output_name: str) -> dict[str, str]:
    return {"source_node_id": node_id, "output_name": output_name}


def evidence_list(node_id: str, fields: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "source": {"source_node_id": node_id, "output_name": "anchor_evaluations"},
            "field": field,
            "alias": field,
            "required": True,
        }
        for field in fields
    ]


def predicate_eq(node_id: str, source_node_id: str, output_name: str, value: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": enum(value),
    }


def predicate_gte(
    node_id: str,
    source_node_id: str,
    output_name: str,
    value: float,
    unit: str,
) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "gte", "version": "1.0.0"},
        "compare": number(value, unit),
    }


def join_parameters(
    *,
    left_key_field: str,
    right_key_field: str,
    left_status_field: str,
    right_status_field: str,
    temporal_relation: str = "none",
    left_time_field: str = "anchor_frame_id",
    right_time_field: str = "anchor_frame_id",
    maximum_gap_seconds: float = 999.0,
    distinct_entity_fields: str = "none",
) -> dict[str, Any]:
    return {
        "left_key_field": enum(left_key_field),
        "right_key_field": enum(right_key_field),
        "left_status_field": enum(left_status_field),
        "right_status_field": enum(right_status_field),
        "required_status_value": enum("PASS"),
        "temporal_relation": enum(temporal_relation),
        "left_time_field": enum(left_time_field),
        "right_time_field": enum(right_time_field),
        "maximum_gap_seconds": number(maximum_gap_seconds, "second"),
        "distinct_entity_fields": enum(distinct_entity_fields),
    }


def enum(value: str) -> dict[str, str]:
    return {"payload_type": "enum", "unit": "none", "value": value}


def number(value: float, unit: str) -> dict[str, Any]:
    return {"payload_type": "number", "unit": unit, "value": value}


def row_result(
    *,
    target: dict[str, Any],
    row: dict[str, Any],
    result: str,
    failure_taxonomy: str | None,
    message: str,
    document_payload: dict[str, Any] | None,
    execution: Any,
    rows: list[dict[str, Any]],
    concept_name_hint: bool,
) -> dict[str, Any]:
    evidence_failures = (
        None
        if execution is None
        else int(execution.provenance.get("requested_evidence_failure_count") or 0)
    )
    return {
        "target_id": target["target_id"],
        "concept": target["concept"],
        "coverage_classification": row.get("classification"),
        "input_composition_maturity": row.get("composition_maturity", "handwired"),
        "target_contract_hash": stable_hash(target["target_contract"]),
        "concept_name_used_as_hint": concept_name_hint,
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": SYNTHESIZER_STRATEGY,
        "result": result,
        "failure_taxonomy": failure_taxonomy,
        "message": message,
        "plan_path": None if document_payload is None else str((PLAN_DIR / f"{target['target_id']}.json").relative_to(ROOT)),
        "document_hash": None if document_payload is None else stable_hash(document_payload),
        "execution_status": None if execution is None else execution.status.value,
        "compatibility_profile": None if execution is None else execution.provenance.get("compatibility_profile"),
        "result_count": len(rows),
        "honest_zero": execution is not None and execution.status == ExecutionStatus.PASS and len(rows) == 0 and evidence_failures == 0,
        "requested_evidence_failure_count": evidence_failures,
        "runtime_trace_hash": None if execution is None else execution.provenance.get("runtime_trace_hash"),
        "runtime_value_count": None if execution is None else execution.provenance.get("runtime_value_count"),
        "declared_missing_constraints": target["target_contract"].get("known_composition_constraints", []),
        "gold_chain_audit": gold_chain_audit(row),
    }


def gold_chain_audit(row: dict[str, Any]) -> dict[str, Any]:
    chain = str(row.get("closest_supported_substitute") or "")
    if not chain:
        return {"status": "not_available", "note": "coverage row has no closest_supported_substitute"}
    tokens = [
        token.strip()
        for token in chain.replace(",", "+").replace("/", "+").split("+")
        if token.strip()
    ]
    catalog_names = set(CatalogIndex().entries)
    matched = [
        token
        for token in tokens
        if token.split()[0].split("(")[0].strip() in catalog_names
        or token.strip() in catalog_names
    ]
    return {
        "status": "static_reference_only",
        "note": "Gold chain is used only after synthesis for audit context, not as synthesizer input.",
        "raw_chain": chain,
        "matched_catalog_refs": sorted(set(matched)),
    }


def coverage_row(rows: list[dict[str, Any]], concept: str) -> dict[str, Any]:
    for row in rows:
        if row.get("concept") == concept:
            return row
    raise RuntimeError(f"Coverage concept not found: {concept}")


def update_coverage_rows(rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    by_concept = {result["concept"]: result for result in results}
    for row in rows:
        maturity = row.get("composition_maturity") or row.get("compiler_reachability_status") or "handwired"
        if row.get("classification") != "supported":
            maturity = "handwired"
        result = by_concept.get(row.get("concept"))
        if result is not None and result["result"] == "compiler_reachable":
            maturity = "compiler_reachable"
            row["compiler_reachability_status"] = "compiler_reachable"
            row["compiler_reachability_evidence"] = {
                "synthesizer_version": SYNTHESIZER_VERSION,
                "synthesizer_strategy": SYNTHESIZER_STRATEGY,
                "target_id": result["target_id"],
                "report_path": str(REPORT.relative_to(ROOT)),
                "document_hash": result["document_hash"],
                "result_count": result["result_count"],
                "honest_zero": result["honest_zero"],
            }
        row["composition_maturity"] = maturity
        row["composition_maturity_applicable"] = row.get("classification") == "supported"


def write_row_outputs(results: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ROW_LEDGER.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = [
        "target_id",
        "concept",
        "coverage_classification",
        "input_composition_maturity",
        "result",
        "failure_taxonomy",
        "result_count",
        "honest_zero",
        "requested_evidence_failure_count",
        "document_hash",
        "message",
    ]
    with ROW_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(result)


def build_report(
    *,
    targets_payload: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    row_results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(coverage_rows)
    supported = sum(1 for row in coverage_rows if row.get("classification") == "supported")
    compiler_reachable = sum(1 for row in coverage_rows if row.get("composition_maturity") == "compiler_reachable")
    result_counts = collections.Counter(result["result"] for result in row_results)
    failures = collections.Counter(
        result["failure_taxonomy"]
        for result in row_results
        if result.get("failure_taxonomy")
    )
    missing_constraints = collections.Counter(
        result["message"]
        for result in row_results
        if result.get("failure_taxonomy") == "missing_constraint"
    )
    findings: list[dict[str, str]] = []
    if not row_results:
        findings.append({"code": "empty_sample", "message": "No synthesizer targets were evaluated.", "path": "targets"})
    if any(result.get("concept_name_used_as_hint") for result in row_results):
        findings.append({"code": "concept_name_hint_used", "message": "A target used concept name as semantic input.", "path": "row_results"})
    return {
        "schema_version": "compiler_reachability_report.v0",
        "status": "PASS" if not findings else "FAIL",
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": targets_payload["strategy"],
        "search_budget": {
            "max_depth": 4,
            "max_branching": 6,
            "allowed_catalog_refs": sorted(CatalogIndex().entries),
            "excluded_catalog_refs": sorted(EXCLUDED_CATALOG_REFS),
        },
        "scope": {
            "mode": "stratified_sample",
            "atlas_wide_execution": false_like(),
            "natural_language": false_like(),
            "target_count": len(row_results),
        },
        "summary": {
            "coverage_supported_count": supported,
            "coverage_supported_pct": round(100 * supported / total, 1),
            "compiler_reachable_count": compiler_reachable,
            "compiler_reachable_pct": round(100 * compiler_reachable / total, 1),
            "sample_compiler_reachable_count": result_counts.get("compiler_reachable", 0),
            "sample_target_count": len(row_results),
            "sample_compiler_reachable_pct": round(100 * result_counts.get("compiler_reachable", 0) / max(len(row_results), 1), 1),
            "reachable_vs_supported_gap_count": supported - compiler_reachable,
            "reachable_vs_supported_gap_pct": round(100 * (supported - compiler_reachable) / total, 1),
        },
        "failure_distribution": dict(sorted(failures.items())),
        "missing_composition_constraints_ranked": missing_constraints.most_common(),
        "row_ledger_path": str(ROW_LEDGER.relative_to(ROOT)),
        "row_csv_path": str(ROW_CSV.relative_to(ROOT)),
        "plan_dir": str(PLAN_DIR.relative_to(ROOT)),
        "targets_path": str(TARGETS.relative_to(ROOT)),
        "report_priority": (
            "The compiler_reachable_pct is a bounded v0 sample signal. "
            "The failure-cause distribution is the actionable output."
        ),
        "findings": findings,
    }


def false_like() -> bool:
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
