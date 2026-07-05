"""Interval-typed aggregation over declared evidence populations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tqe.runtime.ir import (
    Cardinality,
    CompositionOperatorSignature,
    EntityScope,
    MissingDataSemantics,
    OperatorInputDefinition,
    OperatorOutputDeclaration,
    ParameterDefinition,
    PayloadType,
    TemporalContainer,
    TypedValue,
    Unit,
    stable_hash,
)
from tqe.runtime.values import RuntimeValue


AGGREGATION_KINDS = ("count",)
TRI_STATE_VALUES = ("PASS", "FAIL", "UNKNOWN")
AGGREGATE_EVIDENCE_FIELDS = [
    "aggregation_kind",
    "population_expression",
    "group_by_fields",
    "group_key",
    "status_field",
    "constraint_opt_out_reason",
    "observed",
    "lower_bound",
    "upper_bound",
    "unknown_count",
    "population_count",
    "pass_count",
    "fail_count",
    "source_node_id",
    "source_output_name",
]
_BOUND_NOT_SUPPLIED = object()


AGGREGATE_OVER_SIGNATURE = CompositionOperatorSignature(
    name="aggregate_over",
    version="0.1.0",
    purpose=(
        "Aggregate a declared anchor-level evidence population into interval-typed "
        "group results with UNKNOWN rows carried into bounds."
    ),
    inputs=[
        OperatorInputDefinition(
            name="population",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="aggregate_records",
            temporal_type=TemporalContainer.RELATION_EPISODE_SET,
            payload_type=PayloadType.RELATION_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.RELATION,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=AGGREGATE_EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="aggregation_kind",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(AGGREGATION_KINDS),
            description="Aggregation operation to perform over the declared population. R2-1 supports count only.",
        ),
        ParameterDefinition(
            name="population_expression",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Human-authored denominator expression echoed in aggregate evidence.",
        ),
        ParameterDefinition(
            name="group_by_fields",
            payload_type=PayloadType.ENTITY_SET,
            required=True,
            description="Declared record fields that define aggregate groups.",
        ),
        ParameterDefinition(
            name="status_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Tri-state PASS/FAIL/UNKNOWN field partitioning the population.",
        ),
        ParameterDefinition(
            name="same_team_perspective_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=True),
            description="Require upstream population lineage to have enforced same-team perspective.",
        ),
        ParameterDefinition(
            name="entity_identity_preserved_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=True),
            description="Require upstream population lineage to have enforced entity identity.",
        ),
        ParameterDefinition(
            name="frame_alignment_required",
            payload_type=PayloadType.BOOLEAN,
            required=False,
            default=TypedValue(payload_type=PayloadType.BOOLEAN, value=True),
            description="Require upstream population lineage to have enforced frame alignment.",
        ),
        ParameterDefinition(
            name="constraint_opt_out_reason",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Required declared reason when any aggregate lineage constraint is explicitly false.",
        ),
        ParameterDefinition(
            name="team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Team-role field used when same-team perspective is required.",
        ),
    ],
    coverage_propagation_rule_id="aggregate_unknown_rows_to_interval_bounds",
    witness_rule_id="aggregate_group_population_witnesses",
    limitations=[
        "aggregate_over never emits point-only results; bounds remain present even when collapsed.",
        "UNKNOWN rows are never silently dropped; they move the upper bound for count.",
        (
            "R2-1 intentionally excludes sum and mean: bounding numeric aggregates over UNKNOWN rows "
            "requires a declared field-domain mechanism before unobserved contributions can be bounded."
        ),
        "The construction guarantee is enforced at interval construction; persisted artifacts are attested by provenance hashes.",
        "Denominator expressions are authored parameters and are echoed in each output record.",
    ],
)


@dataclass(frozen=True, init=False)
class AggregateIntervalResult:
    aggregation_kind: str
    population_expression: str
    group_key: dict[str, str]
    observed: float
    lower_bound: float
    upper_bound: float
    unknown_count: int
    population_count: int
    pass_count: int
    fail_count: int

    def __init__(
        self,
        *,
        aggregation_kind: str,
        population_expression: str,
        group_key: dict[str, str],
        pass_count: int,
        fail_count: int,
        unknown_count: int,
        lower_bound: object = _BOUND_NOT_SUPPLIED,
        upper_bound: object = _BOUND_NOT_SUPPLIED,
    ) -> None:
        if lower_bound is not _BOUND_NOT_SUPPLIED or upper_bound is not _BOUND_NOT_SUPPLIED:
            raise ValueError("aggregate_over bounds are computed internally and cannot be supplied")
        if aggregation_kind not in set(AGGREGATION_KINDS):
            raise ValueError(f"unsupported aggregate_over aggregation_kind {aggregation_kind}")
        if min(int(pass_count), int(fail_count), int(unknown_count)) < 0:
            raise ValueError("aggregate_over count partitions must be non-negative")
        population_count = int(pass_count) + int(fail_count) + int(unknown_count)
        observed, lower, upper = _count_interval(
            pass_count=int(pass_count),
            unknown_count=int(unknown_count),
        )
        _validate_interval_order(
            observed=observed,
            lower_bound=lower,
            upper_bound=upper,
        )
        object.__setattr__(self, "aggregation_kind", aggregation_kind)
        object.__setattr__(self, "population_expression", population_expression)
        object.__setattr__(self, "group_key", group_key)
        object.__setattr__(self, "observed", _compact_number(observed))
        object.__setattr__(self, "lower_bound", _compact_number(lower))
        object.__setattr__(self, "upper_bound", _compact_number(upper))
        object.__setattr__(self, "unknown_count", int(unknown_count))
        object.__setattr__(self, "population_count", population_count)
        object.__setattr__(self, "pass_count", int(pass_count))
        object.__setattr__(self, "fail_count", int(fail_count))


def execute_aggregate_over(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    population = inputs.get("population")
    records = _runtime_records(population)
    group_by_fields = _parameter_entity_set(parameters, "group_by_fields")
    status_field = _parameter_enum(parameters, "status_field")
    aggregation_kind = _parameter_enum(parameters, "aggregation_kind")
    population_expression = _parameter_enum(parameters, "population_expression")
    constraint_opt_out_reason = _parameter_enum(parameters, "constraint_opt_out_reason", "none")
    if aggregation_kind != "count":
        raise ValueError("aggregate_over R2-1 supports aggregation_kind=count only")

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("aggregate_over population records must be objects")
        key_values = []
        for field in group_by_fields:
            if field == "perspective_team_role":
                if "perspective_team_role" not in record:
                    raise ValueError("aggregate_over perspective_team_role missing from source record")
                key_values.append(str(record["perspective_team_role"]))
                continue
            if field not in record:
                raise ValueError(f"aggregate_over group_by field {field} missing from source record")
            key_values.append(str(record[field]))
        groups.setdefault(tuple(key_values), []).append(record)

    source_ref = node.inputs["population"]
    aggregate_records = []
    for key, group_records in sorted(groups.items()):
        group_key = {field: value for field, value in zip(group_by_fields, key, strict=True)}
        pass_count = 0
        fail_count = 0
        unknown_count = 0
        for record in group_records:
            status = _tri_state(record, status_field)
            if status == "PASS":
                pass_count += 1
            elif status == "FAIL":
                fail_count += 1
            else:
                unknown_count += 1
        result = AggregateIntervalResult(
            aggregation_kind=aggregation_kind,
            population_expression=population_expression,
            group_key=group_key,
            pass_count=pass_count,
            fail_count=fail_count,
            unknown_count=unknown_count,
        )
        aggregate_records.append(
            _result_record(
                result,
                state=state,
                group_by_fields=group_by_fields,
                status_field=status_field,
                constraint_opt_out_reason=constraint_opt_out_reason,
                source_node_id=source_ref.source_node_id,
                source_output_name=source_ref.output_name,
                source_records=group_records,
            )
        )
    state.signals[node.node_id] = {
        "aggregate_records": aggregate_records,
        "aggregate_records_records": aggregate_records,
    }


def _result_record(
    result: AggregateIntervalResult,
    *,
    state: Any,
    group_by_fields: list[str],
    status_field: str,
    constraint_opt_out_reason: str,
    source_node_id: str,
    source_output_name: str,
    source_records: list[dict[str, Any]],
) -> dict[str, Any]:
    frame_ids = [
        int(record["anchor_frame_id"])
        for record in source_records
        if isinstance(record.get("anchor_frame_id"), int)
    ]
    open_frame_id = min(frame_ids) if frame_ids else 0
    close_frame_id = max(frame_ids) if frame_ids else open_frame_id
    relation_id = stable_hash(
        {
            "operator": "aggregate_over",
            "match_id": str(state.match_id),
            "period": str(state.period),
            "population_expression": result.population_expression,
            "aggregation_kind": result.aggregation_kind,
            "group_key": result.group_key,
        }
    )[:16]
    return {
        "relation_id": relation_id,
        "match_id": str(state.match_id),
        "period": str(state.period),
        "open_frame_id": open_frame_id,
        "close_frame_id": close_frame_id,
        "aggregation_kind": result.aggregation_kind,
        "population_expression": result.population_expression,
        "group_by_fields": list(group_by_fields),
        "group_key": result.group_key,
        "status_field": status_field,
        "constraint_opt_out_reason": constraint_opt_out_reason,
        "observed": result.observed,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "unknown_count": result.unknown_count,
        "population_count": result.population_count,
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "source_node_id": source_node_id,
        "source_output_name": source_output_name,
        "source_record_count": len(source_records),
        "source_records": source_records,
    }


def _runtime_records(value: RuntimeValue | None) -> list[dict[str, Any]]:
    if value is None:
        raise ValueError("aggregate_over missing population input")
    if value.records:
        if not all(isinstance(item, dict) for item in value.records):
            raise ValueError("aggregate_over population records must be objects")
        return value.records
    if isinstance(value.value, list):
        if not all(isinstance(item, dict) for item in value.value):
            raise ValueError("aggregate_over population value must be a list of objects")
        return value.value
    raise ValueError("aggregate_over population input is malformed")


def _count_interval(*, pass_count: int, unknown_count: int) -> tuple[float, float, float]:
    observed = float(pass_count)
    lower = float(pass_count)
    upper = float(pass_count + unknown_count)
    return observed, lower, upper


def _validate_interval_order(
    *,
    observed: float | None,
    lower_bound: float,
    upper_bound: float,
) -> None:
    if observed is not None and not (lower_bound <= observed <= upper_bound):
        raise ValueError("aggregate_over interval invariant requires lower_bound <= observed <= upper_bound")
    if lower_bound > upper_bound:
        raise ValueError("aggregate_over interval invariant requires lower_bound <= upper_bound")


def _tri_state(record: dict[str, Any], status_field: str) -> str:
    raw = record.get(status_field)
    status = "UNKNOWN" if raw is None else str(raw)
    if status not in set(TRI_STATE_VALUES):
        raise ValueError(f"aggregate_over status_field {status_field} must be PASS/FAIL/UNKNOWN")
    return status


def _parameter_enum(parameters: dict[str, TypedValue], name: str, default: str | None = None) -> str:
    value = parameters.get(name)
    if value is None:
        if default is None:
            raise ValueError(f"aggregate_over missing parameter {name}")
        return default
    return str(value.value)


def _parameter_entity_set(parameters: dict[str, TypedValue], name: str) -> list[str]:
    value = parameters.get(name)
    if value is None or not isinstance(value.value, list):
        raise ValueError(f"aggregate_over missing entity-set parameter {name}")
    fields = [str(item) for item in value.value]
    if not fields:
        raise ValueError("aggregate_over group_by_fields must be non-empty")
    return fields


def _compact_number(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value
