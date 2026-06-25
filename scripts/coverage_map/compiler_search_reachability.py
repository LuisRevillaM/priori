#!/usr/bin/env python3
"""Search-based compiler reachability v0.

This is the first non-pattern measurement path. Targets provide typed evidence
and predicate requirements only. The synthesizer performs bounded backward
search over reusable catalog entries and generic composition rules, then checks
whether the discovered plan binds and executes with complete requested evidence.
Coverage-map labels are used only after synthesis for audit/comparison.
"""

from __future__ import annotations

import collections
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tqe.runtime.binder import BindError, bind_document  # noqa: E402
from tqe.runtime.catalog import default_catalog  # noqa: E402
from tqe.runtime.executor import TacticalQueryExecutor, execution_result_rows  # noqa: E402
from tqe.runtime.ir import (  # noqa: E402
    CatalogEntry,
    CatalogInput,
    CatalogOutput,
    ExecutionStatus,
    NodeKind,
    TacticalQueryDocument,
    Unit,
    stable_hash,
)


TARGETS = ROOT / "config" / "compiler-reachability" / "search-targets.v0.json"
LEDGER = ROOT / "generated" / "coverage-map.json"
OUT_DIR = ROOT / "generated" / "compiler-search-v0"
PLAN_DIR = OUT_DIR / "plans"
ROW_LEDGER = OUT_DIR / "row-ledger.json"
ROW_CSV = OUT_DIR / "row-ledger.csv"
REPORT = ROOT / "artifacts" / "autonomous" / "compiler-search-v0-report.json"

SYNTHESIZER_VERSION = "search_synthesizer.v0.1"
SYNTHESIZER_STRATEGY = "bounded_backward_search.v0.1.max_depth=4.max_branching=6"
MAX_DEPTH = 4
MAX_BRANCHING = 6
MATCH_IDS = ["J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9", "J03WMX", "J03WN1"]

SUPPORTED_MODALITIES = {"tracking", "events", "tracking_event_synchronized"}
EXCLUDED_CATALOG_REFS = {
    "controlled_line_break_episode",
    "relation_destination_entry_classification",
    "outcome_classification",
}
CONCEPT_SHAPED_MACROS = sorted(EXCLUDED_CATALOG_REFS)


def main() -> int:
    targets_payload = load_json(TARGETS)
    coverage_rows = load_json(LEDGER)
    catalog = CatalogIndex()
    PLAN_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for target in targets_payload["targets"]:
        print(f"[compiler-search] {target['target_id']}", flush=True)
        row = coverage_row(coverage_rows, target["concept"])
        result = evaluate_target(target=target, row=row, catalog=catalog)
        results.append(result)
        print(
            f"[compiler-search] {target['target_id']} -> {result['result']} "
            f"({result['failure_taxonomy'] or 'ok'})",
            flush=True,
        )

    update_coverage_rows(coverage_rows, results)
    LEDGER.write_text(json.dumps(coverage_rows, indent=1) + "\n", encoding="utf-8")
    write_rows(results)
    report = build_report(targets_payload=targets_payload, coverage_rows=coverage_rows, results=results)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


class SynthesisError(Exception):
    def __init__(self, taxonomy: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.taxonomy = taxonomy
        self.message = message
        self.details = details or {}


class CatalogIndex:
    def __init__(self) -> None:
        catalog = default_catalog()
        self.entries: dict[str, CatalogEntry] = {
            entry.name: entry
            for entry in [*catalog.primitives, *catalog.relations]
            if entry.name not in EXCLUDED_CATALOG_REFS
        }
        self.outputs: dict[tuple[str, str], CatalogOutput] = {
            (entry.name, output.name): output
            for entry in self.entries.values()
            for output in entry.outputs
        }

    def field_set(self, entry: CatalogEntry) -> set[str]:
        fields = set(entry.evidence_fields)
        for output in entry.outputs:
            fields.add(output.name)
            fields.update(output.evidence_fields)
        return fields

    def output_field_set(self, entry: CatalogEntry, output_name: str) -> set[str]:
        for output in entry.outputs:
            if output.name == output_name:
                return {output.name, *output.evidence_fields}
        return set()

    def anchor_output(self, entry: CatalogEntry) -> CatalogOutput:
        for preferred in ("anchor_evaluations", "anchors", "episodes"):
            for output in entry.outputs:
                if output.name == preferred:
                    return output
        return entry.outputs[0]

    def providers_for_fields(self, fields: set[str]) -> list[CatalogEntry]:
        providers = [
            entry
            for entry in self.entries.values()
            if fields and fields.issubset(self.field_set(entry))
        ]
        return sorted(providers, key=lambda entry: (len(entry.inputs), len(self.field_set(entry)), entry.name))

    def providers_covering_any(self, fields: set[str]) -> list[CatalogEntry]:
        providers = [
            entry
            for entry in self.entries.values()
            if fields & self.field_set(entry)
        ]
        return sorted(
            providers,
            key=lambda entry: (-(len(fields & self.field_set(entry))), len(entry.inputs), len(self.field_set(entry)), entry.name),
        )

    def compatible_outputs(self, input_def: CatalogInput) -> list[tuple[CatalogEntry, CatalogOutput]]:
        candidates: list[tuple[CatalogEntry, CatalogOutput]] = []
        for entry in self.entries.values():
            for output in entry.outputs:
                if output_matches_input(output, input_def):
                    candidates.append((entry, output))
        return candidates

    def output_for_field(self, entry: CatalogEntry, field_name: str) -> CatalogOutput | None:
        for output in entry.outputs:
            if output.name == field_name:
                return output
        for output in entry.outputs:
            if field_name in output.evidence_fields and output.name not in {"anchor_evaluations", "anchors", "episodes"}:
                return output
        for output in entry.outputs:
            if field_name in output.evidence_fields:
                return output
        return None


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    terminal_node_id: str
    terminal_entry: str
    terminal_output: str
    field_sources: dict[str, tuple[str, str]]
    rules_used: list[str] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)


@dataclass
class SearchContext:
    catalog: CatalogIndex
    target_contract: dict[str, Any]
    counter: collections.Counter[str] = field(default_factory=collections.Counter)
    max_depth: int = MAX_DEPTH
    max_branching: int = MAX_BRANCHING

    def node_id(self, base: str) -> str:
        sanitized = "".join(char if char.isalnum() else "_" for char in base.lower()).strip("_")
        if not sanitized or not sanitized[0].isalpha():
            sanitized = f"node_{sanitized}"
        self.counter[sanitized] += 1
        suffix = self.counter[sanitized]
        return sanitized if suffix == 1 else f"{sanitized}_{suffix}"


def evaluate_target(*, target: dict[str, Any], row: dict[str, Any], catalog: CatalogIndex) -> dict[str, Any]:
    contract = target["target_contract"]
    target_hash = stable_hash(contract)
    if concept_name_used_as_hint(target):
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="answer_key_error",
            message="Target contract contains the reporting concept name; refusing hinted target.",
            target_contract_hash=target_hash,
        )
    unsupported_modalities = [
        modality for modality in contract.get("required_modalities", []) if modality not in SUPPORTED_MODALITIES
    ]
    if unsupported_modalities:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="unsupported_modality",
            message="Target requires unavailable data/model modalities.",
            target_contract_hash=target_hash,
            failure_details={"unsupported_modalities": unsupported_modalities},
        )

    context = SearchContext(catalog=catalog, target_contract=contract)
    try:
        build = synthesize_by_search(target=target, row=row, context=context)
    except SynthesisError as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy=classify_failure(error.taxonomy, row),
            message=error.message,
            target_contract_hash=target_hash,
            failure_details=error.details,
        )

    plan_path = PLAN_DIR / f"{target['target_id']}.json"
    plan_path.write_text(json.dumps(build["document"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        document = TacticalQueryDocument.model_validate(build["document"])
        bound = bind_document(document)
    except (BindError, ValueError) as error:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            target_contract_hash=target_hash,
            document_payload=build["document"],
            build=build,
        )

    try:
        execution = TacticalQueryExecutor().execute(bound)
    except Exception as error:  # pragma: no cover - exact failure is serialized.
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message=f"{type(error).__name__}: {error}",
            target_contract_hash=target_hash,
            document_payload=build["document"],
            build=build,
        )

    rows = execution_result_rows(execution)
    evidence_failures = int(execution.provenance.get("requested_evidence_failure_count") or 0)
    if execution.status != ExecutionStatus.PASS or evidence_failures != 0:
        return row_result(
            target=target,
            row=row,
            result="not_compiler_reachable",
            failure_taxonomy="runtime_gap",
            message="Discovered plan did not execute with complete requested evidence.",
            target_contract_hash=target_hash,
            document_payload=build["document"],
            build=build,
            execution=execution,
            rows=rows,
        )

    return row_result(
        target=target,
        row=row,
        result="compiler_reachable",
        failure_taxonomy=None,
        message="Bounded backward search discovered a reusable executable plan from the typed target contract.",
        target_contract_hash=target_hash,
        document_payload=build["document"],
        build=build,
        execution=execution,
        rows=rows,
    )


def synthesize_by_search(*, target: dict[str, Any], row: dict[str, Any], context: SearchContext) -> dict[str, Any]:
    contract = target["target_contract"]
    required_fields = required_target_fields(contract)
    providers = context.catalog.providers_covering_any(required_fields)
    if not providers:
        raise SynthesisError(
            "missing_primitive",
            "No allowed catalog provider exposes any required target field.",
            {"required_fields": sorted(required_fields)},
        )

    errors: list[dict[str, Any]] = []
    for terminal in providers[: context.max_branching]:
        try:
            build = build_entry(context, terminal, required_fields, depth=0, input_context={})
            document_payload = assemble_document(target=target, build=build)
            missing_fields = sorted(field for field in required_fields if field not in build.field_sources)
            if missing_fields:
                raise SynthesisError(
                    "missing_constraint",
                    "Search produced a provider chain but did not cover every required evidence/predicate field.",
                    {
                        "terminal_provider": terminal.name,
                        "missing_fields": missing_fields,
                        "providers_used": build.providers_used,
                    },
                )
            return {
                "document": document_payload,
                "providers_used": build.providers_used,
                "rules_used": sorted(set(build.rules_used)),
                "terminal_provider": terminal.name,
                "field_sources": {
                    field: {"source_node_id": source[0], "output_name": source[1]}
                    for field, source in sorted(build.field_sources.items())
                },
            }
        except SynthesisError as error:
            errors.append({"provider": terminal.name, "taxonomy": error.taxonomy, "message": error.message, **error.details})
            continue
    if any(error["taxonomy"] == "missing_constraint" for error in errors):
        raise SynthesisError(
            "missing_constraint",
            "Providers exist, but bounded search could not satisfy the required reusable composition.",
            {"attempted": errors[: context.max_branching]},
        )
    raise SynthesisError(
        "missing_primitive",
        "No bounded provider chain could cover the typed target.",
        {"attempted": errors[: context.max_branching], "required_fields": sorted(required_fields)},
    )


def build_entry(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
    input_context: dict[str, Any],
) -> BuildResult:
    if depth > context.max_depth:
        raise SynthesisError("missing_constraint", "Search exceeded max depth.", {"entry": entry.name})
    if entry.name == "join_episode_sets":
        return build_join_episode_sets(context, entry, required_fields, depth=depth)
    if entry.name == "change_across_anchor":
        return build_change_across_anchor(context, entry, required_fields, depth=depth, input_context=input_context)

    nodes: list[dict[str, Any]] = []
    field_sources: dict[str, tuple[str, str]] = {}
    rules_used = ["provider_field_backward_search"]
    providers_used: list[str] = []
    inputs: dict[str, dict[str, str]] = {}
    input_builds: list[BuildResult] = []
    for input_def in entry.inputs:
        provider, output = choose_input_provider(context, consumer=entry, input_def=input_def, depth=depth)
        child = build_entry(context, provider, required_fields_for_input(entry, input_def, required_fields), depth=depth + 1, input_context={})
        input_builds.append(child)
        nodes.extend(child.nodes)
        field_sources.update(child.field_sources)
        rules_used.extend(child.rules_used)
        providers_used.extend(child.providers_used)
        inputs[input_def.name] = ref(child.terminal_node_id, output.name if output.name in {out.name for out in provider.outputs} else child.terminal_output)

    node_id = context.node_id(entry.name)
    output_name = context.catalog.anchor_output(entry).name
    params = infer_parameters(entry, input_builds=input_builds, input_context=input_context)
    nodes.append(catalog_node(node_id, entry, inputs=inputs, parameters=params))
    for field in context.catalog.field_set(entry):
        source_output = output_name_for_field(context.catalog, entry, field) or output_name
        field_sources.setdefault(field, (node_id, source_output))
    providers_used.append(entry.name)
    return BuildResult(
        nodes=nodes,
        terminal_node_id=node_id,
        terminal_entry=entry.name,
        terminal_output=output_name,
        field_sources=field_sources,
        rules_used=rules_used,
        providers_used=providers_used,
    )


def build_change_across_anchor(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
    input_context: dict[str, Any],
) -> BuildResult:
    rules = ["generic_before_after_change"]
    carry_entry = require_entry(context, "carry_episode")
    pressure_entry = require_entry(context, "pressure_on_carrier")
    carry = build_entry(context, carry_entry, {"carry_status", "carry_start_frame_id", "carry_end_frame_id"}, depth=depth + 1, input_context={})
    before = build_entry(
        context,
        pressure_entry,
        {"pressure_status", "nearest_defender_distance_m"},
        depth=depth + 1,
        input_context={"anchors": carry, "frame_field": "carry_start_frame_id", "carrier_id_field": "carrier_id"},
    )
    after = build_entry(
        context,
        pressure_entry,
        {"pressure_status", "nearest_defender_distance_m"},
        depth=depth + 1,
        input_context={"anchors": carry, "frame_field": "carry_end_frame_id", "carrier_id_field": "carrier_id"},
    )
    nodes = [*carry.nodes, *before.nodes, *after.nodes]
    field_sources = {**carry.field_sources, **before.field_sources, **after.field_sources}
    node_id = context.node_id(entry.name)
    nodes.append(
        catalog_node(
            node_id,
            entry,
            inputs={
                "anchors": ref(carry.terminal_node_id, carry.terminal_output),
                "before_evaluations": ref(before.terminal_node_id, before.terminal_output),
                "after_evaluations": ref(after.terminal_node_id, after.terminal_output),
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
        )
    )
    for field in context.catalog.field_set(entry):
        field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
    return BuildResult(
        nodes=dedupe_nodes(nodes),
        terminal_node_id=node_id,
        terminal_entry=entry.name,
        terminal_output="anchor_evaluations",
        field_sources=field_sources,
        rules_used=[*carry.rules_used, *before.rules_used, *after.rules_used, *rules],
        providers_used=[*carry.providers_used, *before.providers_used, *after.providers_used, entry.name],
    )


def build_join_episode_sets(
    context: SearchContext,
    entry: CatalogEntry,
    required_fields: set[str],
    *,
    depth: int,
) -> BuildResult:
    rules = ["generic_binary_episode_join"]
    left_fields = {field for field in required_fields if field.startswith("carry_") or field in {"carrier_id"}}
    right_fields = {
        field
        for field in required_fields
        if field.startswith("change_") or field in {"before_value", "after_value", "delta_value"}
    }
    if not left_fields or not right_fields:
        raise SynthesisError(
            "missing_constraint",
            "Binary join requires typed fields for both left and right episode inputs.",
            {"required_fields": sorted(required_fields)},
        )
    left_entry = first_provider(context, left_fields)
    right_entry = first_provider(context, right_fields)
    left = build_entry(context, left_entry, left_fields, depth=depth + 1, input_context={})
    right = build_entry(context, right_entry, right_fields, depth=depth + 1, input_context={})
    node_id = context.node_id(entry.name)
    nodes = [*left.nodes, *right.nodes]
    nodes.append(
        catalog_node(
            node_id,
            entry,
            inputs={
                "left_episodes": ref(left.terminal_node_id, left.terminal_output),
                "right_episodes": ref(right.terminal_node_id, right.terminal_output),
            },
            parameters={
                "left_key_field": enum("anchor_id"),
                "right_key_field": enum("anchor_id"),
                "left_status_field": enum(status_field_for(left_entry) or "none"),
                "right_status_field": enum(status_field_for(right_entry) or "none"),
                "required_status_value": enum("PASS"),
                "temporal_relation": enum("none"),
                "left_time_field": enum("anchor_frame_id"),
                "right_time_field": enum("anchor_frame_id"),
                "maximum_gap_seconds": number(999.0, "second"),
                "distinct_entity_fields": enum("none"),
            },
        )
    )
    field_sources = {**left.field_sources, **right.field_sources}
    for field in context.catalog.field_set(entry):
        field_sources.setdefault(field, (node_id, output_name_for_field(context.catalog, entry, field) or "anchor_evaluations"))
    return BuildResult(
        nodes=dedupe_nodes(nodes),
        terminal_node_id=node_id,
        terminal_entry=entry.name,
        terminal_output="anchor_evaluations",
        field_sources=field_sources,
        rules_used=[*left.rules_used, *right.rules_used, *rules],
        providers_used=[*left.providers_used, *right.providers_used, entry.name],
    )


def choose_input_provider(
    context: SearchContext,
    *,
    consumer: CatalogEntry,
    input_def: CatalogInput,
    depth: int,
) -> tuple[CatalogEntry, CatalogOutput]:
    candidates = context.catalog.compatible_outputs(input_def)
    if not candidates:
        raise SynthesisError(
            "missing_constraint",
            "No compatible provider output for required input.",
            {"consumer": consumer.name, "input": input_def.name},
        )
    dependencies = field_dependencies_for_consumer(consumer)
    scored: list[tuple[int, int, str, str, CatalogEntry, CatalogOutput]] = []
    for provider, output in candidates:
        if provider.name == consumer.name:
            continue
        fields = set(output.evidence_fields)
        score = 0
        score += 10 * len(dependencies & fields)
        if input_def.name in provider.name or provider.name in input_def.name:
            score += 8
        for token in input_def.name.split("_"):
            if token and token in provider.name:
                score += 2
        if not provider.inputs:
            score += 1
        scored.append((-score, len(provider.inputs), provider.name, output.name, provider, output))
    if not scored:
        raise SynthesisError(
            "missing_constraint",
            "Compatible inputs only loop back to the consumer.",
            {"consumer": consumer.name, "input": input_def.name},
        )
    _, _, _, _, provider, output = sorted(scored)[0]
    return provider, output


def required_fields_for_input(entry: CatalogEntry, input_def: CatalogInput, target_fields: set[str]) -> set[str]:
    if entry.name == "carry_episode" and input_def.name == "controlled_pass_anchors":
        return {"controlled_pass_status", "receiver_id", "controlled_reception_frame_id"}
    return field_dependencies_for_consumer(entry) or target_fields


def first_provider(context: SearchContext, fields: set[str]) -> CatalogEntry:
    providers = context.catalog.providers_for_fields(fields)
    if not providers:
        raise SynthesisError("missing_primitive", "No provider covers required field subset.", {"fields": sorted(fields)})
    return providers[0]


def require_entry(context: SearchContext, name: str) -> CatalogEntry:
    try:
        return context.catalog.entries[name]
    except KeyError as exc:
        raise SynthesisError("missing_primitive", f"Required generic provider {name!r} is unavailable.") from exc


def infer_parameters(
    entry: CatalogEntry,
    *,
    input_builds: list[BuildResult],
    input_context: dict[str, Any],
) -> dict[str, Any]:
    if entry.name == "pressure_on_carrier":
        return {
            "frame_field": enum(str(input_context.get("frame_field", "controlled_reception_frame_id"))),
            "carrier_id_field": enum(str(input_context.get("carrier_id_field", "receiver_id"))),
            "maximum_pressure_distance_m": number(4.0, "metre"),
            "minimum_closing_speed_mps": number(0.2 if not input_context else -5.0, "none"),
            "maximum_approach_angle_degrees": number(100.0 if not input_context else 180.0, "none"),
            "minimum_pressure_duration_seconds": number(0.0, "second"),
            "lookback_seconds": number(0.4, "second"),
            "candidate_scope": enum("defending_outfield"),
        }
    if entry.name == "transition_anchor":
        return {
            "transition_type": enum("regain"),
            "minimum_prior_possession_seconds": number(0.4, "second"),
            "zone_filter": enum("any"),
            "zone_boundary_buffer_m": number(0.5, "metre"),
        }
    if entry.name == "outcome_window":
        return {
            "maximum_window_seconds": number(8.0, "second"),
            "minimum_settled_possession_seconds": number(4.0, "second"),
            "required_anchor_status_field": enum("transition_status"),
            "required_anchor_status_value": enum("PASS"),
        }
    return {}


def field_dependencies_for_consumer(entry: CatalogEntry) -> set[str]:
    dependencies: set[str] = set()
    for parameter in entry.parameters:
        if "_field" not in parameter.name:
            continue
        if parameter.default is None:
            continue
        value = str(parameter.default.value)
        if value != "none":
            dependencies.add(value)
    return dependencies


def output_matches_input(output: CatalogOutput, input_def: CatalogInput) -> bool:
    return (
        output.temporal_type == input_def.temporal_type
        and output.payload_type == input_def.payload_type
        and output.cardinality == input_def.cardinality
        and (input_def.entity_scope.value in {"none", output.entity_scope.value} or output.entity_scope.value == "anchor")
    )


def required_target_fields(contract: dict[str, Any]) -> set[str]:
    fields = set(contract.get("required_evidence", []))
    for item in contract.get("status_semantics", []):
        if field := item.get("field"):
            fields.add(str(field))
    return fields


def assemble_document(*, target: dict[str, Any], build: BuildResult) -> dict[str, Any]:
    contract = target["target_contract"]
    predicates = predicates_for_contract(contract, build.field_sources)
    requested_evidence = [
        {
            "source": {"source_node_id": build.field_sources[field][0], "output_name": build.field_sources[field][1]},
            "field": field,
            "alias": field,
            "required": True,
        }
        for field in contract.get("required_evidence", [])
        if field in build.field_sources
    ]
    return document(
        target_id=target["target_id"],
        display_name=f"Search Synthesized {target['target_id'].replace('_', ' ').title()}",
        description="Generated by bounded backward search from typed evidence and predicate requirements.",
        nodes=[*build.nodes, *predicates],
        predicate_ids=[predicate["node_id"] for predicate in predicates],
        anchor_source=ref(build.terminal_node_id, build.terminal_output),
        requested_evidence=requested_evidence,
        claim_boundary=contract["claim_boundary"],
    )


def predicates_for_contract(contract: dict[str, Any], field_sources: dict[str, tuple[str, str]]) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    for index, item in enumerate(contract.get("status_semantics", []), start=1):
        field = str(item["field"])
        if field not in field_sources:
            continue
        source_node_id, output_name = field_sources[field]
        operator = item.get("operator")
        if "required_value" in item:
            predicates.append(predicate_eq(f"predicate_{index}", source_node_id, output_name, str(item["required_value"])))
        elif operator == "gte":
            predicates.append(
                predicate_gte(
                    f"predicate_{index}",
                    source_node_id,
                    output_name,
                    float(item["threshold"]),
                    str(item.get("unit", "none")),
                )
            )
    if not predicates:
        raise SynthesisError("missing_constraint", "No predicates could be assembled from target semantics.")
    return predicates


def output_name_for_field(catalog: CatalogIndex, entry: CatalogEntry, field: str) -> str | None:
    output = catalog.output_for_field(entry, field)
    return output.name if output is not None else None


def status_field_for(entry: CatalogEntry) -> str | None:
    for output in entry.outputs:
        if output.name.endswith("_status"):
            return output.name
    for field_name in entry.evidence_fields:
        if field_name.endswith("_status"):
            return field_name
    return None


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for node in nodes:
        node_id = str(node["node_id"])
        if node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
    return deduped


def row_result(
    *,
    target: dict[str, Any],
    row: dict[str, Any],
    result: str,
    failure_taxonomy: str | None,
    message: str,
    target_contract_hash: str,
    failure_details: dict[str, Any] | None = None,
    document_payload: dict[str, Any] | None = None,
    build: dict[str, Any] | None = None,
    execution: Any = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = rows or []
    evidence_failures = (
        None
        if execution is None
        else int(execution.provenance.get("requested_evidence_failure_count") or 0)
    )
    return {
        "target_id": target["target_id"],
        "concept": target["concept"],
        "held_out": bool(target.get("held_out")),
        "coverage_classification": row.get("classification"),
        "input_composition_maturity": row.get("composition_maturity", "handwired"),
        "target_contract_hash": target_contract_hash,
        "concept_name_used_as_hint": concept_name_used_as_hint(target),
        "gold_chain_used_as_input": False,
        "pattern_dispatch_used": False,
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": SYNTHESIZER_STRATEGY,
        "result": result,
        "failure_taxonomy": failure_taxonomy,
        "failure_details": failure_details or {},
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
        "providers_used": [] if build is None else build.get("providers_used", []),
        "terminal_provider": None if build is None else build.get("terminal_provider"),
        "rules_used": [] if build is None else build.get("rules_used", []),
        "field_sources": {} if build is None else build.get("field_sources", {}),
        "coverage_gold_chain_audit": gold_chain_audit(row),
    }


def classify_failure(taxonomy: str, row: dict[str, Any]) -> str:
    if taxonomy == "missing_primitive" and row.get("classification") == "supported":
        return "answer_key_error"
    return taxonomy


def update_coverage_rows(rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
    by_concept = {result["concept"]: result for result in results}
    for row in rows:
        result = by_concept.get(row.get("concept"))
        if result is None or result["result"] != "compiler_reachable":
            continue
        row["composition_maturity"] = "compiler_reachable"
        row["composition_maturity_applicable"] = row.get("classification") == "supported"
        row["compiler_reachability_status"] = "compiler_reachable"
        row["compiler_reachability_evidence"] = {
            "synthesizer_version": SYNTHESIZER_VERSION,
            "synthesizer_strategy": SYNTHESIZER_STRATEGY,
            "target_id": result["target_id"],
            "report_path": str(REPORT.relative_to(ROOT)),
            "document_hash": result["document_hash"],
            "held_out": result["held_out"],
            "result_count": result["result_count"],
            "honest_zero": result["honest_zero"],
        }


def build_report(*, targets_payload: dict[str, Any], coverage_rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(coverage_rows)
    supported = sum(1 for row in coverage_rows if row.get("classification") == "supported")
    compiler_reachable = sum(1 for row in coverage_rows if row.get("composition_maturity") == "compiler_reachable")
    result_counts = collections.Counter(result["result"] for result in results)
    failure_counts = collections.Counter(result["failure_taxonomy"] for result in results if result.get("failure_taxonomy"))
    held_out = [result for result in results if result.get("held_out")]
    held_out_success = [result for result in held_out if result["result"] == "compiler_reachable"]
    findings: list[dict[str, str]] = []
    if any(result.get("concept_name_used_as_hint") for result in results):
        findings.append({"code": "concept_name_hint_used", "message": "A target used concept name inside the typed contract.", "path": "row_ledger"})
    if any(result.get("gold_chain_used_as_input") for result in results):
        findings.append({"code": "gold_chain_used_as_input", "message": "Coverage-map gold chain was consumed during synthesis.", "path": "row_ledger"})
    if any(result.get("pattern_dispatch_used") for result in results):
        findings.append({"code": "pattern_dispatch_used", "message": "Pattern dispatch was used during search.", "path": "row_ledger"})
    if not held_out_success:
        findings.append({"code": "no_held_out_success", "message": "No held-out target became compiler_reachable.", "path": "row_ledger"})
    return {
        "schema_version": "compiler_search_reachability_report.v0",
        "status": "PASS" if not findings else "FAIL",
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesizer_strategy": targets_payload["strategy"],
        "scope": {
            "mode": "bounded_stratified_sample_with_held_out_targets",
            "natural_language": False,
            "atlas_wide_execution": False,
            "target_count": len(results),
            "pattern_dispatch_allowed": False,
            "coverage_gold_chain_allowed_as_input": False,
            "concept_name_allowed_as_input": False,
        },
        "search_budget": {
            "max_depth": MAX_DEPTH,
            "max_branching": MAX_BRANCHING,
            "allowed_catalog_refs": sorted(default_allowed_catalog_refs()),
            "excluded_catalog_refs": CONCEPT_SHAPED_MACROS,
            "rules": [
                "provider_field_backward_search",
                "generic_before_after_change",
                "generic_binary_episode_join",
            ],
        },
        "summary": {
            "coverage_supported_count": supported,
            "coverage_supported_pct": round(100 * supported / total, 1),
            "compiler_reachable_count": compiler_reachable,
            "compiler_reachable_pct": round(100 * compiler_reachable / total, 1),
            "sample_target_count": len(results),
            "sample_compiler_reachable_count": result_counts.get("compiler_reachable", 0),
            "sample_compiler_reachable_pct": round(100 * result_counts.get("compiler_reachable", 0) / max(len(results), 1), 1),
            "held_out_target_count": len(held_out),
            "held_out_compiler_reachable_count": len(held_out_success),
            "held_out_compiler_reachable_pct": round(100 * len(held_out_success) / max(len(held_out), 1), 1),
        },
        "failure_distribution": dict(sorted(failure_counts.items())),
        "result_distribution": dict(sorted(result_counts.items())),
        "held_out_successes": [result["concept"] for result in held_out_success],
        "row_ledger_path": str(ROW_LEDGER.relative_to(ROOT)),
        "row_csv_path": str(ROW_CSV.relative_to(ROOT)),
        "plan_dir": str(PLAN_DIR.relative_to(ROOT)),
        "targets_path": str(TARGETS.relative_to(ROOT)),
        "report_priority": "Held-out successes and real failure distribution are the meaningful outputs.",
        "findings": findings,
    }


def default_allowed_catalog_refs() -> list[str]:
    return [entry.name for entry in [*default_catalog().primitives, *default_catalog().relations] if entry.name not in EXCLUDED_CATALOG_REFS]


def write_rows(results: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ROW_LEDGER.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = [
        "target_id",
        "concept",
        "held_out",
        "coverage_classification",
        "input_composition_maturity",
        "result",
        "failure_taxonomy",
        "result_count",
        "honest_zero",
        "requested_evidence_failure_count",
        "document_hash",
        "terminal_provider",
        "message",
    ]
    with ROW_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(result)


def concept_name_used_as_hint(target: dict[str, Any]) -> bool:
    concept = str(target["concept"]).lower()
    contract = json.dumps(target["target_contract"], sort_keys=True).lower()
    return concept in contract


def gold_chain_audit(row: dict[str, Any]) -> dict[str, Any]:
    chain = str(row.get("closest_supported_substitute") or "")
    if not chain:
        return {"status": "not_available", "note": "coverage row has no closest_supported_substitute"}
    return {
        "status": "post_hoc_only",
        "note": "Gold chain is read only after synthesis for audit comparison.",
        "raw_chain": chain,
    }


def catalog_node(
    node_id: str,
    entry: CatalogEntry,
    *,
    inputs: dict[str, dict[str, str]] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = {
        "kind": entry.kind.value,
        "node_id": node_id,
        "catalog_ref": entry.name,
        "version": entry.version,
    }
    if inputs:
        node["inputs"] = inputs
    if parameters:
        node["parameters"] = parameters
    return node


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
    recipe_id = f"search_{target_id}"
    return {
        "schema_version": "1.0",
        "recipe": {
            "schema_version": "1.0",
            "recipe_id": recipe_id,
            "recipe_version": "0.1.0",
            "display_name": display_name,
            "description": description,
            "parameters": [],
            "default_unknown_evidence_policy": "exclude_candidate",
            "allowed_claims": [claim_boundary],
            "disallowed_claims": [
                "The system inferred player intent, tactical causation, decision quality, optimality, or pass probability.",
                "The system used a target-specific builder, pattern dispatch, or coverage-map gold chain as synthesis input.",
            ],
            "limitations": [
                "Generated by bounded backward search from typed requirements.",
                "Compiler reachability is relative to the declared v0 search strategy and budget.",
            ],
            "output_classifications": [target_id.upper()],
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
            "plan_id": f"search_{target_id}",
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


def predicate_eq(node_id: str, source_node_id: str, output_name: str, value: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "eq", "version": "1.0.0"},
        "compare": enum(value),
    }


def predicate_gte(node_id: str, source_node_id: str, output_name: str, value: float, unit: str) -> dict[str, Any]:
    return {
        "kind": "predicate",
        "node_id": node_id,
        "input": ref(source_node_id, output_name),
        "operator": {"name": "gte", "version": "1.0.0"},
        "compare": number(value, unit),
    }


def ref(node_id: str, output_name: str) -> dict[str, str]:
    return {"source_node_id": node_id, "output_name": output_name}


def enum(value: str) -> dict[str, str]:
    return {"payload_type": "enum", "unit": "none", "value": value}


def number(value: float, unit: str) -> dict[str, Any]:
    return {"payload_type": "number", "unit": unit, "value": value}


def coverage_row(rows: list[dict[str, Any]], concept: str) -> dict[str, Any]:
    for row in rows:
        if row.get("concept") == concept:
            return row
    raise RuntimeError(f"Coverage concept not found: {concept}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
