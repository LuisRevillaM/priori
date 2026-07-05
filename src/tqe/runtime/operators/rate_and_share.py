"""Interval-typed rates over declared subset populations."""

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


RATE_KINDS = ("rate", "share")
TRI_STATE_VALUES = ("PASS", "FAIL", "UNKNOWN")
RATE_EVIDENCE_FIELDS = [
    "rate_kind",
    "population_expression",
    "group_by_fields",
    "group_key",
    "numerator_status_field",
    "denominator_status_field",
    "subset_declaration",
    "constraint_opt_out_reason",
    "rate_status",
    "observed",
    "lower_bound",
    "upper_bound",
    "observed_denominator_count",
    "a_count",
    "b_count",
    "c_count",
    "d1_count",
    "d2_count",
    "e_count",
    "numerator_count_interval",
    "denominator_count_interval",
    "numerator_source_node_id",
    "numerator_source_output_name",
    "denominator_source_node_id",
    "denominator_source_output_name",
]
_BOUND_NOT_SUPPLIED = object()


RATE_AND_SHARE_SIGNATURE = CompositionOperatorSignature(
    name="rate_and_share",
    version="0.1.0",
    purpose=(
        "Compute interval-typed count rates from a joint numerator/denominator "
        "tri-state partition under a declared subset law."
    ),
    inputs=[
        OperatorInputDefinition(
            name="numerator",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
        OperatorInputDefinition(
            name="denominator",
            temporal_type=TemporalContainer.EPISODE_SET,
            payload_type=PayloadType.ANCHOR_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.ANCHOR,
        ),
    ],
    outputs=[
        OperatorOutputDeclaration(
            name="rate_records",
            temporal_type=TemporalContainer.RELATION_EPISODE_SET,
            payload_type=PayloadType.RELATION_REF,
            cardinality=Cardinality.COLLECTION,
            unit=Unit.NONE,
            entity_scope=EntityScope.RELATION,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=RATE_EVIDENCE_FIELDS,
        ),
    ],
    parameters=[
        ParameterDefinition(
            name="rate_kind",
            payload_type=PayloadType.ENUM,
            required=True,
            allowed_values=list(RATE_KINDS),
            description="R2-2 supports count rate and share only.",
        ),
        ParameterDefinition(
            name="population_expression",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Human-authored rate population expression echoed in evidence.",
        ),
        ParameterDefinition(
            name="group_by_fields",
            payload_type=PayloadType.ENTITY_SET,
            required=True,
            description="Declared record fields that define rate groups.",
        ),
        ParameterDefinition(
            name="numerator_status_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Tri-state PASS/FAIL/UNKNOWN field for numerator membership.",
        ),
        ParameterDefinition(
            name="denominator_status_field",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Tri-state PASS/FAIL/UNKNOWN field for denominator membership.",
        ),
        ParameterDefinition(
            name="subset_declaration",
            payload_type=PayloadType.ENUM,
            required=True,
            description="Declared subset law; numerator must add predicates over the denominator source.",
        ),
        ParameterDefinition(
            name="subset_predicate_fields",
            payload_type=PayloadType.ENTITY_SET,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENTITY_SET, value=[]),
            description="Predicate fields added by the numerator over the shared source relation.",
        ),
        ParameterDefinition(
            name="removed_denominator_predicate_fields",
            payload_type=PayloadType.ENTITY_SET,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENTITY_SET, value=[]),
            description="Must remain empty; non-empty values mean the numerator removed denominator predicates.",
        ),
        ParameterDefinition(
            name="share_key_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Declared partition key for share outputs.",
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
            description="Required declared reason when any rate lineage constraint is explicitly false.",
        ),
        ParameterDefinition(
            name="team_role_field",
            payload_type=PayloadType.ENUM,
            required=False,
            default=TypedValue(payload_type=PayloadType.ENUM, value="none"),
            description="Team-role field used when same-team perspective is required.",
        ),
    ],
    coverage_propagation_rule_id="rate_unknown_rows_to_joint_interval_bounds",
    witness_rule_id="rate_group_population_witnesses",
    limitations=[
        "rate_and_share never divides independent intervals; bounds come from the joint row partition.",
        "R2-2 supports count rates only; numeric sum/mean rates require a future field-domain mechanism.",
        "The numerator population must be declared as a same-source subset of the denominator population.",
        "A num PASS row with denominator FAIL or UNKNOWN raises because the evidence violates the subset law.",
        "Degenerate denominators emit a typed UNKNOWN rate instead of zero, NaN, or an omitted row.",
    ],
)


@dataclass(frozen=True, init=False)
class RateIntervalResult:
    rate_kind: str
    population_expression: str
    group_key: dict[str, str]
    rate_status: str
    observed: float | None
    lower_bound: float | None
    upper_bound: float | None
    observed_denominator_count: int
    a_count: int
    b_count: int
    c_count: int
    d1_count: int
    d2_count: int
    e_count: int
    numerator_count_interval: dict[str, int]
    denominator_count_interval: dict[str, int]

    def __init__(
        self,
        *,
        rate_kind: str,
        population_expression: str,
        group_key: dict[str, str],
        a_count: int,
        b_count: int,
        c_count: int,
        d1_count: int,
        d2_count: int,
        e_count: int,
        observed: object = _BOUND_NOT_SUPPLIED,
        lower_bound: object = _BOUND_NOT_SUPPLIED,
        upper_bound: object = _BOUND_NOT_SUPPLIED,
    ) -> None:
        if (
            observed is not _BOUND_NOT_SUPPLIED
            or lower_bound is not _BOUND_NOT_SUPPLIED
            or upper_bound is not _BOUND_NOT_SUPPLIED
        ):
            raise ValueError("rate_and_share bounds are computed internally and cannot be supplied")
        if rate_kind not in set(RATE_KINDS):
            raise ValueError(f"unsupported rate_and_share rate_kind {rate_kind}")
        counts = {
            "a_count": int(a_count),
            "b_count": int(b_count),
            "c_count": int(c_count),
            "d1_count": int(d1_count),
            "d2_count": int(d2_count),
            "e_count": int(e_count),
        }
        if min(counts.values()) < 0:
            raise ValueError("rate_and_share partition counts must be non-negative")

        observed_denominator = counts["a_count"] + counts["b_count"]
        bound_denominator = (
            counts["a_count"]
            + counts["b_count"]
            + counts["c_count"]
            + counts["d1_count"]
            + counts["d2_count"]
        )
        rate_status, rate_observed, lower, upper = _rate_interval_from_partition(counts)
        _validate_rate_interval_order(
            observed=rate_observed,
            lower_bound=lower,
            upper_bound=upper,
        )
        numerator_interval = {
            "observed": counts["a_count"],
            "lower_bound": counts["a_count"],
            "upper_bound": counts["a_count"] + counts["c_count"] + counts["d2_count"],
            "unknown_count": counts["c_count"] + counts["d2_count"],
            "pass_count": counts["a_count"],
            "fail_count": counts["b_count"] + counts["d1_count"],
            "population_count": bound_denominator,
        }
        denominator_interval = {
            "observed": counts["a_count"] + counts["b_count"] + counts["c_count"],
            "lower_bound": counts["a_count"] + counts["b_count"] + counts["c_count"],
            "upper_bound": bound_denominator,
            "unknown_count": counts["d1_count"] + counts["d2_count"],
            "pass_count": counts["a_count"] + counts["b_count"] + counts["c_count"],
            "fail_count": counts["e_count"],
            "population_count": bound_denominator + counts["e_count"],
        }

        object.__setattr__(self, "rate_kind", rate_kind)
        object.__setattr__(self, "population_expression", population_expression)
        object.__setattr__(self, "group_key", group_key)
        object.__setattr__(self, "rate_status", rate_status)
        object.__setattr__(self, "observed", _compact_optional_number(rate_observed))
        object.__setattr__(self, "lower_bound", _compact_optional_number(lower))
        object.__setattr__(self, "upper_bound", _compact_optional_number(upper))
        object.__setattr__(self, "observed_denominator_count", observed_denominator)
        for name, value in counts.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "numerator_count_interval", numerator_interval)
        object.__setattr__(self, "denominator_count_interval", denominator_interval)


def _rate_interval_from_partition(
    counts: dict[str, int],
) -> tuple[str, float | None, float | None, float | None]:
    observed_denominator = counts["a_count"] + counts["b_count"]
    bound_denominator = (
        counts["a_count"]
        + counts["b_count"]
        + counts["c_count"]
        + counts["d1_count"]
        + counts["d2_count"]
    )
    if bound_denominator == 0:
        return "UNKNOWN", None, None, None
    observed = counts["a_count"] / observed_denominator if observed_denominator > 0 else None
    lower = counts["a_count"] / bound_denominator
    upper_denominator = counts["a_count"] + counts["b_count"] + counts["c_count"] + counts["d2_count"]
    upper = (
        (counts["a_count"] + counts["c_count"] + counts["d2_count"]) / upper_denominator
        if upper_denominator > 0
        else 0.0
    )
    return "PASS", observed, lower, upper


def execute_rate_and_share(
    *,
    state: Any,
    node: Any,
    inputs: dict[str, RuntimeValue],
    parameters: dict[str, TypedValue],
) -> None:
    numerator = inputs.get("numerator")
    denominator = inputs.get("denominator")
    numerator_records = _runtime_records(numerator)
    denominator_records = _runtime_records(denominator)
    _validate_shared_source_records(numerator_records, denominator_records)

    rate_kind = _parameter_enum(parameters, "rate_kind")
    if rate_kind not in set(RATE_KINDS):
        raise ValueError(f"rate_and_share unsupported rate_kind {rate_kind}")
    group_by_fields = _parameter_entity_set(parameters, "group_by_fields")
    numerator_status_field = _parameter_enum(parameters, "numerator_status_field")
    denominator_status_field = _parameter_enum(parameters, "denominator_status_field")
    population_expression = _parameter_enum(parameters, "population_expression")
    subset_declaration = _parameter_enum(parameters, "subset_declaration")
    constraint_opt_out_reason = _parameter_enum(parameters, "constraint_opt_out_reason", "none")
    share_key_field = _parameter_enum(parameters, "share_key_field", "none")
    if rate_kind == "share" and share_key_field == "none":
        raise ValueError("rate_and_share share outputs require share_key_field")

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for record in denominator_records:
        if not isinstance(record, dict):
            raise ValueError("rate_and_share population records must be objects")
        key_values = []
        for field in group_by_fields:
            if field not in record:
                raise ValueError(f"rate_and_share group_by field {field} missing from source record")
            key_values.append(str(record[field]))
        groups.setdefault(tuple(key_values), []).append(record)

    source_ref = node.inputs["denominator"]
    numerator_ref = node.inputs["numerator"]
    rate_records = []
    for key, group_records in sorted(groups.items()):
        group_key = {field: value for field, value in zip(group_by_fields, key, strict=True)}
        result = RateIntervalResult(
            rate_kind=rate_kind,
            population_expression=population_expression,
            group_key=group_key,
            **_joint_partition_counts(
                records=group_records,
                numerator_status_field=numerator_status_field,
                denominator_status_field=denominator_status_field,
            ),
        )
        rate_records.append(
            _result_record(
                result,
                state=state,
                group_by_fields=group_by_fields,
                numerator_status_field=numerator_status_field,
                denominator_status_field=denominator_status_field,
                subset_declaration=subset_declaration,
                constraint_opt_out_reason=constraint_opt_out_reason,
                numerator_source_node_id=numerator_ref.source_node_id,
                numerator_source_output_name=numerator_ref.output_name,
                denominator_source_node_id=source_ref.source_node_id,
                denominator_source_output_name=source_ref.output_name,
                source_records=group_records,
            )
        )
    if rate_kind == "share":
        _assert_share_observed_sum(rate_records=rate_records, share_key_field=share_key_field)
    state.signals[node.node_id] = {
        "rate_records": rate_records,
        "rate_records_records": rate_records,
    }


def _joint_partition_counts(
    *,
    records: list[dict[str, Any]],
    numerator_status_field: str,
    denominator_status_field: str,
) -> dict[str, int]:
    counts = {
        "a_count": 0,
        "b_count": 0,
        "c_count": 0,
        "d1_count": 0,
        "d2_count": 0,
        "e_count": 0,
    }
    for record in records:
        numerator_status = _tri_state(record, numerator_status_field)
        denominator_status = _tri_state(record, denominator_status_field)
        if denominator_status == "FAIL":
            if numerator_status == "PASS":
                raise ValueError("rate_and_share subset invariant violated: numerator PASS with denominator FAIL")
            counts["e_count"] += 1
            continue
        if denominator_status == "UNKNOWN":
            if numerator_status == "PASS":
                raise ValueError("rate_and_share subset invariant violated: numerator PASS with denominator UNKNOWN")
            if numerator_status == "FAIL":
                counts["d1_count"] += 1
            else:
                counts["d2_count"] += 1
            continue
        if numerator_status == "PASS":
            counts["a_count"] += 1
        elif numerator_status == "FAIL":
            counts["b_count"] += 1
        else:
            counts["c_count"] += 1
    return counts


def _result_record(
    result: RateIntervalResult,
    *,
    state: Any,
    group_by_fields: list[str],
    numerator_status_field: str,
    denominator_status_field: str,
    subset_declaration: str,
    constraint_opt_out_reason: str,
    numerator_source_node_id: str,
    numerator_source_output_name: str,
    denominator_source_node_id: str,
    denominator_source_output_name: str,
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
            "operator": "rate_and_share",
            "match_id": str(state.match_id),
            "period": str(state.period),
            "population_expression": result.population_expression,
            "rate_kind": result.rate_kind,
            "group_key": result.group_key,
        }
    )[:16]
    return {
        "relation_id": relation_id,
        "match_id": str(state.match_id),
        "period": str(state.period),
        "open_frame_id": open_frame_id,
        "close_frame_id": close_frame_id,
        "rate_kind": result.rate_kind,
        "population_expression": result.population_expression,
        "group_by_fields": list(group_by_fields),
        "group_key": result.group_key,
        "numerator_status_field": numerator_status_field,
        "denominator_status_field": denominator_status_field,
        "subset_declaration": subset_declaration,
        "constraint_opt_out_reason": constraint_opt_out_reason,
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
        "numerator_source_node_id": numerator_source_node_id,
        "numerator_source_output_name": numerator_source_output_name,
        "denominator_source_node_id": denominator_source_node_id,
        "denominator_source_output_name": denominator_source_output_name,
        "source_record_count": len(source_records),
    }


def _runtime_records(value: RuntimeValue | None) -> list[dict[str, Any]]:
    if value is None:
        raise ValueError("rate_and_share missing population input")
    if value.records:
        if not all(isinstance(item, dict) for item in value.records):
            raise ValueError("rate_and_share population records must be objects")
        return value.records
    if isinstance(value.value, list):
        if not all(isinstance(item, dict) for item in value.value):
            raise ValueError("rate_and_share population value must be a list of objects")
        return value.value
    raise ValueError("rate_and_share population input is malformed")


def _validate_shared_source_records(
    numerator_records: list[dict[str, Any]],
    denominator_records: list[dict[str, Any]],
) -> None:
    if len(numerator_records) != len(denominator_records):
        raise ValueError("rate_and_share numerator and denominator source rows must be identical")
    for numerator_record, denominator_record in zip(numerator_records, denominator_records, strict=True):
        if _record_identity(numerator_record) != _record_identity(denominator_record):
            raise ValueError("rate_and_share numerator and denominator source rows must be identical")


def _record_identity(record: dict[str, Any]) -> str:
    for field in ("anchor_id", "witness_anchor_record_hash", "left_record_hash"):
        value = record.get(field)
        if value is not None:
            return str(value)
    return stable_hash(record)


def _validate_rate_interval_order(
    *,
    observed: float | None,
    lower_bound: float | None,
    upper_bound: float | None,
) -> None:
    if lower_bound is None or upper_bound is None:
        return
    if observed is not None and not (lower_bound <= observed <= upper_bound):
        raise ValueError("rate_and_share interval invariant requires lower_bound <= observed <= upper_bound")
    if lower_bound > upper_bound:
        raise ValueError("rate_and_share interval invariant requires lower_bound <= upper_bound")


def _assert_share_observed_sum(
    *,
    rate_records: list[dict[str, Any]],
    share_key_field: str,
) -> None:
    sums: dict[tuple[tuple[str, str], ...], float] = {}
    for record in rate_records:
        if record.get("rate_status") == "UNKNOWN" or record.get("observed") is None:
            continue
        group_key = record.get("group_key")
        if not isinstance(group_key, dict) or share_key_field not in group_key:
            raise ValueError("rate_and_share share records must carry the declared share_key_field")
        base_key = tuple(sorted((key, str(value)) for key, value in group_key.items() if key != share_key_field))
        sums[base_key] = sums.get(base_key, 0.0) + float(record["observed"])
    for base_key, observed_sum in sums.items():
        if abs(observed_sum - 1.0) > 1e-9:
            raise ValueError(f"rate_and_share share observed values must sum to 1 for {dict(base_key)}")


def _tri_state(record: dict[str, Any], status_field: str) -> str:
    raw = record.get(status_field)
    status = "UNKNOWN" if raw is None else str(raw)
    if status not in set(TRI_STATE_VALUES):
        raise ValueError(f"rate_and_share status_field {status_field} must be PASS/FAIL/UNKNOWN")
    return status


def _parameter_enum(parameters: dict[str, TypedValue], name: str, default: str | None = None) -> str:
    value = parameters.get(name)
    if value is None:
        if default is None:
            raise ValueError(f"rate_and_share missing parameter {name}")
        return default
    return str(value.value)


def _parameter_entity_set(parameters: dict[str, TypedValue], name: str) -> list[str]:
    value = parameters.get(name)
    if value is None or not isinstance(value.value, list):
        raise ValueError(f"rate_and_share missing entity-set parameter {name}")
    fields = [str(item) for item in value.value]
    if not fields:
        raise ValueError("rate_and_share group_by_fields must be non-empty")
    return fields


def _compact_optional_number(value: float | None) -> float | int | None:
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value
