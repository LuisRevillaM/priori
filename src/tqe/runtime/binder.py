"""Deterministic binder for Tactical Query IR v1."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import (
    BindIssue,
    BoundCatalogNode,
    BoundPlanNode,
    BoundPredicateNode,
    BoundQueryPlan,
    CapabilityCatalog,
    Cardinality,
    CatalogEntry,
    CatalogOutput,
    ClassificationMode,
    DraftCatalogNode,
    DraftPredicateNode,
    DraftQueryPlan,
    EntityScope,
    MissingDataSemantics,
    NodeKind,
    OperatorSignature,
    ParameterDefinition,
    ParameterRef,
    PayloadType,
    QueryInvocation,
    RecipeDefinition,
    ResolvedParameter,
    SignalRef,
    TacticalQueryDocument,
    TemporalContainer,
    TypedArgument,
    TypedValue,
    Unit,
    model_payload,
    stable_hash,
)


class BindError(ValueError):
    def __init__(self, issues: list[BindIssue]) -> None:
        self.issues = issues
        message = "; ".join(f"{issue.code} at {issue.path}: {issue.message}" for issue in issues)
        super().__init__(message)


def load_tactical_query_document(path: Path) -> TacticalQueryDocument:
    return TacticalQueryDocument.model_validate_json(path.read_text(encoding="utf-8"))


def bind_document(
    document: TacticalQueryDocument,
    *,
    catalog: CapabilityCatalog | None = None,
) -> BoundQueryPlan:
    return bind_plan(
        recipe=document.recipe,
        invocation=document.default_invocation,
        draft_plan=document.draft_plan,
        catalog=catalog,
    )


def bind_plan(
    *,
    recipe: RecipeDefinition,
    invocation: QueryInvocation,
    draft_plan: DraftQueryPlan,
    catalog: CapabilityCatalog | None = None,
) -> BoundQueryPlan:
    binder = Binder(catalog or default_catalog())
    return binder.bind(recipe=recipe, invocation=invocation, draft_plan=draft_plan)


class Binder:
    def __init__(self, catalog: CapabilityCatalog) -> None:
        self.catalog = catalog
        self.issues: list[BindIssue] = []
        self.catalog_outputs: dict[str, tuple[CatalogEntry | None, CatalogOutput]] = {}
        self.bound_nodes: list[BoundPlanNode] = []

    def bind(
        self,
        *,
        recipe: RecipeDefinition,
        invocation: QueryInvocation,
        draft_plan: DraftQueryPlan,
    ) -> BoundQueryPlan:
        self._validate_document_identity(recipe, draft_plan)
        self._validate_complexity(invocation, draft_plan)
        resolved_parameters = self._resolve_parameters(recipe, invocation)
        self._bind_nodes(draft_plan, resolved_parameters)
        self._validate_classifications(draft_plan)
        self._validate_evidence_requests(draft_plan)

        if self.issues:
            raise BindError(self.issues)

        plan_hash = stable_hash(
            {
                "recipe": model_payload(recipe),
                "draft_plan": model_payload(draft_plan),
            }
        )
        bound_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "plan_id": draft_plan.plan_id,
            "plan_version": draft_plan.plan_version,
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
            "invocation_id": invocation.invocation_id,
            "match_ids": invocation.match_ids,
            "periods": invocation.periods,
            "perspective_team_role": invocation.perspective_team_role,
            "unknown_evidence_policy": draft_plan.unknown_evidence_policy,
            "classification_mode": draft_plan.classification_mode,
            "classification_rules": draft_plan.classification_rules,
            "requested_evidence": draft_plan.requested_evidence,
            "complexity_limits": draft_plan.complexity_limits,
            "resolved_parameters": sorted(resolved_parameters, key=lambda item: item.name),
            "nodes": self.bound_nodes,
            "plan_hash": plan_hash,
            "bound_plan_hash": "",
        }
        bound_hash = stable_hash(bound_payload)
        return BoundQueryPlan.model_validate({**bound_payload, "bound_plan_hash": bound_hash})

    def _issue(self, code: str, message: str, path: str) -> None:
        self.issues.append(BindIssue(code=code, message=message, path=path))

    def _validate_document_identity(
        self, recipe: RecipeDefinition, draft_plan: DraftQueryPlan
    ) -> None:
        if draft_plan.recipe_id != recipe.recipe_id:
            self._issue(
                "recipe_id_mismatch",
                f"draft plan references {draft_plan.recipe_id}, recipe is {recipe.recipe_id}",
                "draft_plan.recipe_id",
            )
        if draft_plan.recipe_version != recipe.recipe_version:
            self._issue(
                "recipe_version_mismatch",
                (
                    f"draft plan references {draft_plan.recipe_version}, "
                    f"recipe is {recipe.recipe_version}"
                ),
                "draft_plan.recipe_version",
            )
        if draft_plan.unknown_evidence_policy is None:
            self._issue(
                "missing_unknown_evidence_policy",
                "unknown-evidence policy must be declared",
                "draft_plan.unknown_evidence_policy",
            )

    def _validate_complexity(
        self, invocation: QueryInvocation, draft_plan: DraftQueryPlan
    ) -> None:
        limits = draft_plan.complexity_limits
        if len(draft_plan.nodes) > limits.max_plan_nodes:
            self._issue(
                "complexity_nodes_exceeded",
                f"{len(draft_plan.nodes)} nodes exceeds max_plan_nodes={limits.max_plan_nodes}",
                "draft_plan.nodes",
            )
        if invocation.max_results > limits.max_returned_moments:
            self._issue(
                "complexity_results_exceeded",
                (
                    f"max_results={invocation.max_results} exceeds "
                    f"max_returned_moments={limits.max_returned_moments}"
                ),
                "default_invocation.max_results",
            )
        for index, node in enumerate(draft_plan.nodes):
            if isinstance(node, DraftPredicateNode):
                if isinstance(node.duration, TypedValue) and node.duration.payload_type == PayloadType.NUMBER:
                    seconds = _duration_seconds(node.duration)
                    if seconds is not None and seconds > limits.max_temporal_horizon_seconds:
                        self._issue(
                            "complexity_temporal_horizon_exceeded",
                            (
                                f"duration={seconds}s exceeds "
                                f"max_temporal_horizon_seconds={limits.max_temporal_horizon_seconds}"
                            ),
                            f"draft_plan.nodes[{index}].duration",
                        )

    def _resolve_parameters(
        self,
        recipe: RecipeDefinition,
        invocation: QueryInvocation,
    ) -> list[ResolvedParameter]:
        parameter_defs = {parameter.name: parameter for parameter in recipe.parameters}
        resolved: list[ResolvedParameter] = []

        for name in invocation.parameters:
            if name not in parameter_defs:
                self._issue(
                    "unknown_parameter",
                    f"invocation supplies unknown parameter {name}",
                    f"default_invocation.parameters.{name}",
                )

        for name, parameter in sorted(parameter_defs.items()):
            value = invocation.parameters.get(name)
            source = "invocation"
            if value is None:
                if parameter.default is None:
                    self._issue(
                        "missing_required_parameter",
                        f"parameter {name} is required",
                        f"default_invocation.parameters.{name}",
                    )
                    continue
                value = parameter.default
                source = "default"
            self._validate_parameter_value(parameter, value, f"default_invocation.parameters.{name}")
            resolved.append(ResolvedParameter(name=name, value=value, source=source))

        return resolved

    def _validate_parameter_value(
        self, parameter: ParameterDefinition, value: TypedValue, path: str
    ) -> None:
        if value.payload_type != parameter.payload_type:
            self._issue(
                "parameter_payload_mismatch",
                (
                    f"parameter {parameter.name} expects {parameter.payload_type.value}, "
                    f"got {value.payload_type.value}"
                ),
                path,
            )
        if value.unit != parameter.unit:
            self._issue(
                "parameter_unit_mismatch",
                f"parameter {parameter.name} expects {parameter.unit.value}, got {value.unit.value}",
                path,
            )

    def _bind_nodes(
        self,
        draft_plan: DraftQueryPlan,
        resolved_parameters: list[ResolvedParameter],
    ) -> None:
        parameter_values = {item.name: item.value for item in resolved_parameters}
        seen_ids: set[str] = set()

        for index, node in enumerate(draft_plan.nodes):
            path = f"draft_plan.nodes[{index}]"
            if node.node_id in seen_ids:
                self._issue("duplicate_node_id", f"duplicate node_id {node.node_id}", path)
                continue
            seen_ids.add(node.node_id)

            if isinstance(node, DraftCatalogNode):
                self._bind_catalog_node(node, parameter_values, path)
            elif isinstance(node, DraftPredicateNode):
                self._bind_predicate_node(node, parameter_values, path)
            else:
                self._issue("unsupported_node_type", f"unsupported node {node}", path)

    def _bind_catalog_node(
        self,
        node: DraftCatalogNode,
        parameter_values: dict[str, TypedValue],
        path: str,
    ) -> None:
        entry = self._find_catalog_entry(node.kind, node.catalog_ref, node.version)
        if entry is None:
            self._issue(
                "unknown_catalog_ref",
                f"{node.kind.value} {node.catalog_ref}@{node.version} is not in the catalog",
                f"{path}.catalog_ref",
            )
            return

        resolved_node_parameters: dict[str, TypedValue] = {}
        for name, argument in sorted(node.parameters.items()):
            value = self._resolve_argument(argument, parameter_values, f"{path}.parameters.{name}")
            if value is not None:
                resolved_node_parameters[name] = value

        bound = BoundCatalogNode(
            kind=node.kind,
            node_id=node.node_id,
            catalog_ref=node.catalog_ref,
            version=node.version,
            outputs=deepcopy(entry.outputs),
            resolved_parameters=resolved_node_parameters,
        )
        self.bound_nodes.append(bound)
        for output in entry.outputs:
            self.catalog_outputs[f"{node.node_id}.{output.name}"] = (entry, output)

    def _bind_predicate_node(
        self,
        node: DraftPredicateNode,
        parameter_values: dict[str, TypedValue],
        path: str,
    ) -> None:
        referenced = self._resolve_signal(node.input, f"{path}.input")
        signature = self._find_operator(node.operator.name, node.operator.version)
        if signature is None:
            self._issue(
                "unknown_operator",
                f"operator {node.operator.name}@{node.operator.version} is not in the catalog",
                f"{path}.operator",
            )
            return
        if referenced is None:
            return

        _, input_type = referenced
        compare = self._resolve_optional_argument(node.compare, parameter_values, f"{path}.compare")
        duration = self._resolve_optional_argument(
            node.duration,
            parameter_values,
            f"{path}.duration",
        )
        self._validate_operator_application(
            signature=signature,
            input_type=input_type,
            compare=compare,
            duration=duration,
            node=node,
            path=path,
        )

        output = CatalogOutput(
            name="predicate",
            temporal_type=signature.output_temporal_type,
            payload_type=signature.output_payload_type,
            cardinality=signature.output_cardinality,
            unit=signature.output_unit,
            entity_scope=input_type.entity_scope,
            missing_data_semantics=MissingDataSemantics.UNKNOWN,
            evidence_fields=[
                "predicate_status",
                "predicate_value",
                "predicate_threshold",
                "predicate_unit",
            ],
        )
        bound = BoundPredicateNode(
            node_id=node.node_id,
            input=node.input,
            input_type=input_type,
            operator=node.operator,
            operator_signature=signature,
            compare=compare,
            duration=duration,
            output=output,
        )
        self.bound_nodes.append(bound)
        self.catalog_outputs[f"{node.node_id}.{output.name}"] = (None, output)

    def _validate_operator_application(
        self,
        *,
        signature: OperatorSignature,
        input_type: CatalogOutput,
        compare: TypedValue | None,
        duration: TypedValue | None,
        node: DraftPredicateNode,
        path: str,
    ) -> None:
        if input_type.temporal_type not in signature.input_temporal_types:
            self._issue(
                "operator_temporal_mismatch",
                (
                    f"{signature.name} does not accept {input_type.temporal_type.value}; "
                    f"allowed={','.join(item.value for item in signature.input_temporal_types)}"
                ),
                f"{path}.input",
            )
        if input_type.payload_type not in signature.input_payload_types:
            self._issue(
                "operator_payload_mismatch",
                (
                    f"{signature.name} does not accept {input_type.payload_type.value}; "
                    f"allowed={','.join(item.value for item in signature.input_payload_types)}"
                ),
                f"{path}.input",
            )
        if input_type.cardinality not in signature.input_cardinalities:
            self._issue(
                "operator_cardinality_mismatch",
                (
                    f"{signature.name} does not accept {input_type.cardinality.value}; "
                    f"allowed={','.join(item.value for item in signature.input_cardinalities)}"
                ),
                f"{path}.input",
            )
        if node.required_cardinality is not None and input_type.cardinality != node.required_cardinality:
            self._issue(
                "required_cardinality_mismatch",
                (
                    f"node requires {node.required_cardinality.value}, "
                    f"input is {input_type.cardinality.value}"
                ),
                f"{path}.required_cardinality",
            )
        if node.required_entity_scope is not None and input_type.entity_scope != node.required_entity_scope:
            self._issue(
                "required_entity_scope_mismatch",
                (
                    f"node requires {node.required_entity_scope.value}, "
                    f"input is {input_type.entity_scope.value}"
                ),
                f"{path}.required_entity_scope",
            )
        if signature.compare_required and compare is None:
            self._issue(
                "missing_compare_value",
                f"{signature.name} requires a typed compare value",
                f"{path}.compare",
            )
        if not signature.compare_required and compare is not None:
            self._issue(
                "unexpected_compare_value",
                f"{signature.name} does not accept a compare value",
                f"{path}.compare",
            )
        if compare is not None:
            if compare.payload_type not in signature.compare_payload_types:
                self._issue(
                    "compare_payload_mismatch",
                    (
                        f"{signature.name} does not accept compare payload "
                        f"{compare.payload_type.value}"
                    ),
                    f"{path}.compare",
                )
            if signature.compare_unit_must_match and compare.unit != input_type.unit:
                self._issue(
                    "unit_mismatch",
                    (
                        f"{signature.name} compares {input_type.unit.value} to "
                        f"{compare.unit.value}"
                    ),
                    f"{path}.compare.unit",
                )
        if signature.duration_required and duration is None:
            self._issue(
                "missing_duration",
                f"{signature.name} requires a duration",
                f"{path}.duration",
            )
        if not signature.duration_required and duration is not None:
            self._issue(
                "unexpected_duration",
                f"{signature.name} does not accept a duration",
                f"{path}.duration",
            )
        if duration is not None:
            if duration.payload_type != PayloadType.NUMBER:
                self._issue(
                    "duration_payload_mismatch",
                    "duration must be a number",
                    f"{path}.duration",
                )
            if duration.unit not in {Unit.SECOND, Unit.MILLISECOND, Unit.FRAME}:
                self._issue(
                    "duration_unit_mismatch",
                    f"duration unit must be second, millisecond, or frame; got {duration.unit.value}",
                    f"{path}.duration.unit",
                )

    def _validate_classifications(self, draft_plan: DraftQueryPlan) -> None:
        predicate_ids = {
            node.node_id for node in draft_plan.nodes if isinstance(node, DraftPredicateNode)
        }
        labels = [rule.label for rule in draft_plan.classification_rules]
        if len(set(labels)) != len(labels):
            self._issue(
                "duplicate_classification_label",
                "classification labels must be unique",
                "draft_plan.classification_rules",
            )
        if draft_plan.classification_mode not in {
            ClassificationMode.EXHAUSTIVE,
            ClassificationMode.PARTIAL_DECLARED,
        }:
            self._issue(
                "classification_mode_unsupported",
                "classification mode must be exhaustive or partial_declared",
                "draft_plan.classification_mode",
            )
        for index, rule in enumerate(draft_plan.classification_rules):
            for predicate_id in rule.predicate_ids:
                if predicate_id not in predicate_ids:
                    self._issue(
                        "unknown_classification_predicate",
                        f"classification {rule.label} references unknown predicate {predicate_id}",
                        f"draft_plan.classification_rules[{index}].predicate_ids",
                    )

    def _validate_evidence_requests(self, draft_plan: DraftQueryPlan) -> None:
        for index, request in enumerate(draft_plan.requested_evidence):
            referenced = self._resolve_signal(
                request.source,
                f"draft_plan.requested_evidence[{index}].source",
            )
            if referenced is None:
                continue
            entry, output = referenced
            allowed = set(output.evidence_fields)
            if entry is not None:
                allowed.update(entry.evidence_fields)
            if request.field not in allowed:
                self._issue(
                    "unsupported_evidence_field",
                    (
                        f"{request.field} is not available on "
                        f"{request.source.source_node_id}.{request.source.output_name}"
                    ),
                    f"draft_plan.requested_evidence[{index}].field",
                )

    def _find_catalog_entry(
        self,
        kind: NodeKind,
        name: str,
        version: str,
    ) -> CatalogEntry | None:
        entries = self.catalog.primitives if kind == NodeKind.PRIMITIVE else self.catalog.relations
        for entry in entries:
            if entry.name == name and entry.version == version:
                return entry
        return None

    def _find_operator(self, name: str, version: str) -> OperatorSignature | None:
        for signature in self.catalog.operators:
            if signature.name == name and signature.version == version:
                return signature
        return None

    def _resolve_signal(
        self,
        reference: SignalRef,
        path: str,
    ) -> tuple[CatalogEntry | None, CatalogOutput] | None:
        key = f"{reference.source_node_id}.{reference.output_name}"
        resolved = self.catalog_outputs.get(key)
        if resolved is None:
            self._issue(
                "unresolved_temporal_reference",
                f"no bound output exists for {key}",
                path,
            )
            return None
        return resolved

    def _resolve_optional_argument(
        self,
        argument: TypedArgument | None,
        parameters: dict[str, TypedValue],
        path: str,
    ) -> TypedValue | None:
        if argument is None:
            return None
        return self._resolve_argument(argument, parameters, path)

    def _resolve_argument(
        self,
        argument: TypedArgument,
        parameters: dict[str, TypedValue],
        path: str,
    ) -> TypedValue | None:
        if isinstance(argument, TypedValue):
            return argument
        if isinstance(argument, ParameterRef):
            value = parameters.get(argument.name)
            if value is None:
                self._issue(
                    "unresolved_parameter_reference",
                    f"parameter {argument.name} is not resolved",
                    path,
                )
            return value
        self._issue("unsupported_argument", f"unsupported argument {argument}", path)
        return None


def bind_document_from_path(path: Path) -> BoundQueryPlan:
    return bind_document(load_tactical_query_document(path))


def bind_document_json(path: Path) -> str:
    bound = bind_document_from_path(path)
    return json.dumps(model_payload(bound), indent=2, sort_keys=True) + "\n"


def bind_error_codes(error: BindError) -> set[str]:
    return {issue.code for issue in error.issues}


def validation_error_codes(error: ValidationError) -> set[str]:
    return {str(issue["type"]) for issue in error.errors()}


def _duration_seconds(value: TypedValue) -> float | None:
    if value.payload_type != PayloadType.NUMBER:
        return None
    if value.unit == Unit.SECOND:
        return float(value.value)
    if value.unit == Unit.MILLISECOND:
        return float(value.value) / 1000.0
    if value.unit == Unit.FRAME:
        return None
    return None
