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
    BoundOperatorNode,
    BoundPlanNode,
    BoundPredicateNode,
    BoundQueryPlan,
    CapabilityCatalog,
    Cardinality,
    CatalogEntry,
    CatalogInput,
    CatalogOutput,
    ClassificationMode,
    CompositionOperatorSignature,
    DraftCatalogNode,
    DraftOperatorNode,
    DraftPredicateNode,
    DraftQueryPlan,
    EntityScope,
    MissingDataSemantics,
    NodeKind,
    OperatorInputDefinition,
    OperatorOutputDeclaration,
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
from tqe.runtime.operators import (
    OperatorImplementation,
    OperatorKey,
    build_operator_registry,
    declared_operator_signatures,
)


class BindError(ValueError):
    def __init__(self, issues: list[BindIssue]) -> None:
        self.issues = issues
        message = "; ".join(f"{issue.code} at {issue.path}: {issue.message}" for issue in issues)
        super().__init__(message)


HOST_RUNTIME_PARAMETER_DEFAULTS: dict[str, ParameterDefinition] = {
    "analysis_rate_hz": ParameterDefinition(
        name="analysis_rate_hz",
        payload_type=PayloadType.NUMBER,
        unit=Unit.HERTZ,
        required=False,
        default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.HERTZ, value=5),
        minimum=1.0,
        maximum=25.0,
        description="Host-owned analysis cadence injected when an authored recipe omits it.",
    ),
    "minimum_possession_seconds": ParameterDefinition(
        name="minimum_possession_seconds",
        payload_type=PayloadType.NUMBER,
        unit=Unit.SECOND,
        required=False,
        default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.SECOND, value=5.0),
        minimum=0.2,
        maximum=60.0,
        description="Host-owned minimum active-ball possession duration.",
    ),
    "maximum_analysis_gap_ms": ParameterDefinition(
        name="maximum_analysis_gap_ms",
        payload_type=PayloadType.NUMBER,
        unit=Unit.MILLISECOND,
        required=False,
        default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.MILLISECOND, value=250),
        minimum=40.0,
        maximum=2000.0,
        description="Host-owned maximum permitted gap in the analysis stream.",
    ),
    "minimum_outfield_players_per_team": ParameterDefinition(
        name="minimum_outfield_players_per_team",
        payload_type=PayloadType.NUMBER,
        unit=Unit.COUNT,
        required=False,
        default=TypedValue(payload_type=PayloadType.NUMBER, unit=Unit.COUNT, value=9),
        minimum=1.0,
        maximum=11.0,
        description="Host-owned tracking-quality floor for outfield players per team.",
    ),
}


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
    def __init__(
        self,
        catalog: CapabilityCatalog,
        *,
        composition_operator_signatures: dict[OperatorKey, CompositionOperatorSignature] | None = None,
        composition_operator_registry: dict[OperatorKey, OperatorImplementation] | None = None,
    ) -> None:
        self.catalog = catalog
        self.composition_operator_signatures = (
            composition_operator_signatures
            if composition_operator_signatures is not None
            else declared_operator_signatures()
        )
        self.composition_operator_registry = (
            composition_operator_registry
            if composition_operator_registry is not None
            else build_operator_registry({})
        )
        self.issues: list[BindIssue] = []
        self.catalog_outputs: dict[str, tuple[CatalogEntry | None, CatalogOutput]] = {}
        self.bound_nodes: list[BoundPlanNode] = []
        self.effective_max_temporal_horizon_seconds = (
            catalog.default_complexity_limits.max_temporal_horizon_seconds
        )

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
        self._validate_classifications(recipe, draft_plan)
        self._validate_anchor_source(draft_plan)
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
            "plan_status": draft_plan.status,
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
            "invocation_id": invocation.invocation_id,
            "match_ids": invocation.match_ids,
            "periods": invocation.periods,
            "perspective_team_role": invocation.perspective_team_role,
            "max_results": invocation.max_results,
            "execution_mode": invocation.execution_mode,
            "unknown_evidence_policy": draft_plan.unknown_evidence_policy,
            "classification_mode": draft_plan.classification_mode,
            "classification_rules": draft_plan.classification_rules,
            "anchor_source": draft_plan.anchor_source,
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
        trusted = self.catalog.default_complexity_limits
        for field_name in (
            "max_plan_nodes",
            "max_nesting_depth",
            "max_temporal_horizon_seconds",
            "max_returned_moments",
            "max_relations_per_anchor",
            "max_execution_cost",
        ):
            requested = getattr(limits, field_name)
            ceiling = getattr(trusted, field_name)
            if requested > ceiling:
                self._issue(
                    f"complexity_{field_name}_ceiling_exceeded",
                    f"{field_name}={requested} exceeds trusted ceiling {ceiling}",
                    f"draft_plan.complexity_limits.{field_name}",
                )

        effective_max_plan_nodes = min(limits.max_plan_nodes, trusted.max_plan_nodes)
        effective_max_nesting_depth = min(limits.max_nesting_depth, trusted.max_nesting_depth)
        effective_max_temporal_horizon_seconds = min(
            limits.max_temporal_horizon_seconds,
            trusted.max_temporal_horizon_seconds,
        )
        self.effective_max_temporal_horizon_seconds = effective_max_temporal_horizon_seconds
        effective_max_returned_moments = min(limits.max_returned_moments, trusted.max_returned_moments)
        effective_max_execution_cost = min(limits.max_execution_cost, trusted.max_execution_cost)

        if len(draft_plan.nodes) > effective_max_plan_nodes:
            self._issue(
                "complexity_nodes_exceeded",
                f"{len(draft_plan.nodes)} nodes exceeds max_plan_nodes={effective_max_plan_nodes}",
                "draft_plan.nodes",
            )
        if invocation.max_results > effective_max_returned_moments:
            self._issue(
                "complexity_results_exceeded",
                (
                    f"max_results={invocation.max_results} exceeds "
                    f"max_returned_moments={effective_max_returned_moments}"
                ),
                "default_invocation.max_results",
            )
        estimated_cost = len(draft_plan.nodes) * len(invocation.match_ids) * len(invocation.periods) * invocation.max_results
        if estimated_cost > effective_max_execution_cost:
            self._issue(
                "complexity_execution_cost_exceeded",
                (
                    f"estimated_execution_cost={estimated_cost} exceeds "
                    f"max_execution_cost={effective_max_execution_cost}"
                ),
                "draft_plan.complexity_limits.max_execution_cost",
            )
        depth = draft_plan_dependency_depth(draft_plan)
        if depth > effective_max_nesting_depth:
            self._issue(
                "complexity_nesting_depth_exceeded",
                f"dependency_depth={depth} exceeds max_nesting_depth={effective_max_nesting_depth}",
                "draft_plan.nodes",
            )
    def _resolve_parameters(
        self,
        recipe: RecipeDefinition,
        invocation: QueryInvocation,
    ) -> list[ResolvedParameter]:
        parameter_defs = {parameter.name: parameter for parameter in recipe.parameters}
        for name, parameter in HOST_RUNTIME_PARAMETER_DEFAULTS.items():
            parameter_defs.setdefault(name, parameter)
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
        if value.payload_type == PayloadType.NUMBER:
            numeric = float(value.value)
            if parameter.minimum is not None and numeric < parameter.minimum:
                self._issue(
                    "parameter_below_minimum",
                    f"parameter {parameter.name} must be >= {parameter.minimum}, got {numeric}",
                    path,
                )
            if parameter.maximum is not None and numeric > parameter.maximum:
                self._issue(
                    "parameter_above_maximum",
                    f"parameter {parameter.name} must be <= {parameter.maximum}, got {numeric}",
                    path,
                )
        if parameter.allowed_values is not None and str(value.value) not in set(parameter.allowed_values):
            self._issue(
                "parameter_value_not_allowed",
                (
                    f"parameter {parameter.name} must be one of "
                    f"{sorted(parameter.allowed_values)}, got {value.value}"
                ),
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
            elif isinstance(node, DraftOperatorNode):
                self._bind_operator_node(node, parameter_values, path)
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
        if not entry.executable:
            self._issue(
                "catalog_entry_not_executable",
                f"{node.catalog_ref}@{node.version} is not executable",
                f"{path}.catalog_ref",
            )
            return

        bound_inputs = self._bind_catalog_inputs(node=node, entry=entry, path=path)
        resolved_node_parameters: dict[str, TypedValue] = {}
        parameter_defs = {parameter.name: parameter for parameter in entry.parameters}
        for name in sorted(node.parameters):
            if name not in parameter_defs:
                self._issue(
                    "unknown_node_parameter",
                    f"{node.catalog_ref}@{node.version} does not accept parameter {name}",
                    f"{path}.parameters.{name}",
                )
        for name, parameter in sorted(parameter_defs.items()):
            argument = node.parameters.get(name)
            if argument is None:
                if parameter.default is None:
                    if parameter.required:
                        self._issue(
                            "missing_node_parameter",
                            f"{node.catalog_ref}@{node.version} requires parameter {name}",
                            f"{path}.parameters.{name}",
                        )
                    continue
                value = parameter.default
            else:
                value = self._resolve_argument(argument, parameter_values, f"{path}.parameters.{name}")
            if value is not None:
                self._validate_parameter_value(parameter, value, f"{path}.parameters.{name}")
                resolved_node_parameters[name] = value

        bound = BoundCatalogNode(
            kind=node.kind,
            node_id=node.node_id,
            catalog_ref=node.catalog_ref,
            version=node.version,
            inputs={name: reference for name, (reference, _) in bound_inputs.items()},
            input_types={name: output for name, (_, output) in bound_inputs.items()},
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

    def _bind_operator_node(
        self,
        node: DraftOperatorNode,
        parameter_values: dict[str, TypedValue],
        path: str,
    ) -> None:
        signature = self._find_composition_operator(node.operator.name, node.operator.version)
        if signature is None:
            self._issue(
                "operator_not_implemented",
                (
                    f"composition operator {node.operator.name}@{node.operator.version} "
                    "has no registered signature or implementation"
                ),
                f"{path}.operator",
            )
            return

        bound_inputs = self._bind_operator_inputs(node=node, signature=signature, path=path)
        resolved_node_parameters = self._bind_operator_parameters(
            node=node,
            signature=signature,
            parameter_values=parameter_values,
            path=path,
        )
        self._validate_operator_field_parameters(
            node=node,
            signature=signature,
            bound_inputs=bound_inputs,
            resolved_parameters=resolved_node_parameters,
            path=path,
        )
        self._validate_declared_join_constraints(
            signature=signature,
            resolved_parameters=resolved_node_parameters,
            path=path,
        )
        self._validate_aggregate_over_constraints(
            node=node,
            signature=signature,
            resolved_parameters=resolved_node_parameters,
            path=path,
        )
        outputs = self._bind_operator_outputs(node=node, signature=signature, path=path)
        if (signature.name, signature.version) not in self.composition_operator_registry:
            self._issue(
                "operator_not_implemented",
                (
                    f"composition operator {signature.name}@{signature.version} "
                    "has a signature but no registered implementation"
                ),
                f"{path}.operator",
            )
            return

        bound = BoundOperatorNode(
            node_id=node.node_id,
            operator=node.operator,
            operator_signature=signature,
            inputs={name: reference for name, (reference, _) in bound_inputs.items()},
            input_types={name: output for name, (_, output) in bound_inputs.items()},
            outputs=outputs,
            resolved_parameters=resolved_node_parameters,
        )
        self.bound_nodes.append(bound)
        for output in outputs:
            self.catalog_outputs[f"{node.node_id}.{output.name}"] = (None, output)

    def _bind_catalog_inputs(
        self,
        *,
        node: DraftCatalogNode,
        entry: CatalogEntry,
        path: str,
    ) -> dict[str, tuple[SignalRef, CatalogOutput]]:
        bound_inputs: dict[str, tuple[SignalRef, CatalogOutput]] = {}
        input_defs = {item.name: item for item in entry.inputs}

        for name in sorted(node.inputs):
            if name not in input_defs:
                self._issue(
                    "unknown_node_input",
                    f"{entry.name}@{entry.version} does not accept input {name}",
                    f"{path}.inputs.{name}",
                )

        for name, input_def in sorted(input_defs.items()):
            reference = node.inputs.get(name)
            if reference is None:
                if input_def.required:
                    self._issue(
                        "missing_node_input",
                        f"{entry.name}@{entry.version} requires input {name}",
                        f"{path}.inputs.{name}",
                    )
                continue
            resolved = self._resolve_signal(reference, f"{path}.inputs.{name}")
            if resolved is None:
                continue
            _, output = resolved
            self._validate_catalog_input(
                input_def=input_def,
                output=output,
                path=f"{path}.inputs.{name}",
            )
            bound_inputs[name] = (reference, output)
        return bound_inputs

    def _bind_operator_inputs(
        self,
        *,
        node: DraftOperatorNode,
        signature: CompositionOperatorSignature,
        path: str,
    ) -> dict[str, tuple[SignalRef, CatalogOutput]]:
        bound_inputs: dict[str, tuple[SignalRef, CatalogOutput]] = {}
        input_defs = {item.name: item for item in signature.inputs}

        for name in sorted(node.inputs):
            if name not in input_defs:
                self._issue(
                    "unknown_operator_input",
                    f"{signature.name}@{signature.version} does not accept input {name}",
                    f"{path}.inputs.{name}",
                )

        for name, input_def in sorted(input_defs.items()):
            reference = node.inputs.get(name)
            if reference is None:
                if input_def.required:
                    self._issue(
                        "missing_operator_input",
                        f"{signature.name}@{signature.version} requires input {name}",
                        f"{path}.inputs.{name}",
                    )
                continue
            resolved = self._resolve_signal(reference, f"{path}.inputs.{name}")
            if resolved is None:
                continue
            _, output = resolved
            self._validate_operator_input(
                input_def=input_def,
                output=output,
                path=f"{path}.inputs.{name}",
            )
            bound_inputs[name] = (reference, output)
        return bound_inputs

    def _bind_operator_parameters(
        self,
        *,
        node: DraftOperatorNode,
        signature: CompositionOperatorSignature,
        parameter_values: dict[str, TypedValue],
        path: str,
    ) -> dict[str, TypedValue]:
        resolved: dict[str, TypedValue] = {}
        parameter_defs = {parameter.name: parameter for parameter in signature.parameters}
        for name in sorted(node.parameters):
            if name not in parameter_defs:
                self._issue(
                    "unknown_operator_parameter",
                    f"{signature.name}@{signature.version} does not accept parameter {name}",
                    f"{path}.parameters.{name}",
                )
        for name, parameter in sorted(parameter_defs.items()):
            argument = node.parameters.get(name)
            if argument is None:
                if parameter.default is None:
                    if parameter.required:
                        self._issue(
                            "missing_operator_parameter",
                            f"{signature.name}@{signature.version} requires parameter {name}",
                            f"{path}.parameters.{name}",
                        )
                    continue
                value = parameter.default
            else:
                value = self._resolve_argument(argument, parameter_values, f"{path}.parameters.{name}")
            if value is not None:
                self._validate_parameter_value(parameter, value, f"{path}.parameters.{name}")
                resolved[name] = value
        return resolved

    def _validate_operator_field_parameters(
        self,
        *,
        node: DraftOperatorNode,
        signature: CompositionOperatorSignature,
        bound_inputs: dict[str, tuple[SignalRef, CatalogOutput]],
        resolved_parameters: dict[str, TypedValue],
        path: str,
    ) -> None:
        if not bound_inputs:
            return
        declared_fields: set[str] = set()
        for _, output in bound_inputs.values():
            declared_fields.add(output.name)
            declared_fields.update(output.evidence_fields)
        declared_fields.update({"match_id", "period"})
        for parameter in signature.parameters:
            if not parameter.name.endswith("_field"):
                continue
            value = resolved_parameters.get(parameter.name)
            if value is None:
                continue
            field_name = str(value.value)
            if field_name == "none":
                continue
            if field_name not in declared_fields:
                self._issue(
                    "operator_field_parameter_not_in_input",
                    (
                        f"{signature.name}@{signature.version} parameter {parameter.name} "
                        f"references field {field_name}, but no bound operator input declares it"
                    ),
                    f"{path}.parameters.{parameter.name}",
                )
        for parameter in signature.parameters:
            if not parameter.name.endswith("_fields"):
                continue
            value = resolved_parameters.get(parameter.name)
            if value is None:
                continue
            if value.payload_type != PayloadType.ENTITY_SET:
                continue
            for field_name in [str(item) for item in value.value]:
                if field_name == "none":
                    continue
                if field_name not in declared_fields:
                    self._issue(
                        "operator_field_parameter_not_in_input",
                        (
                            f"{signature.name}@{signature.version} parameter {parameter.name} "
                            f"references field {field_name}, but no bound operator input declares it"
                        ),
                        f"{path}.parameters.{parameter.name}",
                    )

    def _validate_declared_join_constraints(
        self,
        *,
        signature: CompositionOperatorSignature,
        resolved_parameters: dict[str, TypedValue],
        path: str,
    ) -> None:
        parameter_names = {parameter.name for parameter in signature.parameters}
        join_parameter_names = {
            "join_key",
            "same_team_perspective_required",
            "entity_identity_preserved_required",
            "frame_alignment_required",
            "unconstrained",
            "unconstrained_rationale",
        }
        if not join_parameter_names.issubset(parameter_names):
            return
        same_team_required = _resolved_bool(resolved_parameters, "same_team_perspective_required")
        entity_required = _resolved_bool(resolved_parameters, "entity_identity_preserved_required")
        frame_required = _resolved_bool(resolved_parameters, "frame_alignment_required")
        unconstrained = _resolved_bool(resolved_parameters, "unconstrained")
        rationale = _resolved_text(resolved_parameters, "unconstrained_rationale", "none")
        if not any((same_team_required, entity_required, frame_required)) and not unconstrained:
            self._issue(
                "operator_join_constraints_missing",
                "join composition must declare at least one enforced constraint or an unconstrained rationale",
                f"{path}.parameters",
            )
        if unconstrained and rationale == "none":
            self._issue(
                "operator_join_unconstrained_rationale_missing",
                "unconstrained join composition requires a rationale",
                f"{path}.parameters.unconstrained_rationale",
            )
        join_key = _resolved_text(resolved_parameters, "join_key", "")
        required_fields_by_key = {
            "same_anchor": ("left_anchor_id_field", "right_anchor_id_field"),
            "same_frame_window": ("left_frame_field", "right_frame_field"),
            "same_entity": ("left_entity_id_field", "right_entity_id_field"),
            "episode_overlap": (
                "left_start_frame_field",
                "left_end_frame_field",
                "right_start_frame_field",
                "right_end_frame_field",
            ),
        }
        for field_parameter in required_fields_by_key.get(join_key, ()):
            if _resolved_text(resolved_parameters, field_parameter, "none") == "none":
                self._issue(
                    "operator_join_key_field_missing",
                    f"{join_key} join requires declared {field_parameter}",
                    f"{path}.parameters.{field_parameter}",
                )
        if same_team_required:
            for field_parameter in ("left_team_role_field", "right_team_role_field"):
                if _resolved_text(resolved_parameters, field_parameter, "none") == "none":
                    self._issue(
                        "operator_join_constraint_field_missing",
                        f"same-team-perspective constraint requires declared {field_parameter}",
                        f"{path}.parameters.{field_parameter}",
                    )
        if entity_required:
            for field_parameter in ("left_entity_id_field", "right_entity_id_field"):
                if _resolved_text(resolved_parameters, field_parameter, "none") == "none":
                    self._issue(
                        "operator_join_constraint_field_missing",
                        f"entity-identity constraint requires declared {field_parameter}",
                        f"{path}.parameters.{field_parameter}",
                    )
        if frame_required:
            for field_parameter in ("left_frame_field", "right_frame_field"):
                if _resolved_text(resolved_parameters, field_parameter, "none") == "none":
                    self._issue(
                        "operator_join_constraint_field_missing",
                        f"frame-alignment constraint requires declared {field_parameter}",
                        f"{path}.parameters.{field_parameter}",
                    )

    def _validate_aggregate_over_constraints(
        self,
        *,
        node: DraftOperatorNode,
        signature: CompositionOperatorSignature,
        resolved_parameters: dict[str, TypedValue],
        path: str,
    ) -> None:
        if signature.name != "aggregate_over":
            return
        aggregation_kind = _resolved_text(resolved_parameters, "aggregation_kind")
        numeric_field = _resolved_text(resolved_parameters, "numeric_field", "none")
        if aggregation_kind == "count" and numeric_field != "none":
            self._issue(
                "operator_aggregate_count_numeric_field_forbidden",
                "aggregate_over count requires numeric_field=none",
                f"{path}.parameters.numeric_field",
            )
        if aggregation_kind in {"sum", "mean"} and numeric_field == "none":
            self._issue(
                "operator_aggregate_numeric_field_missing",
                f"aggregate_over {aggregation_kind} requires numeric_field",
                f"{path}.parameters.numeric_field",
            )
        same_team_required = _resolved_bool(resolved_parameters, "same_team_perspective_required")
        entity_required = _resolved_bool(resolved_parameters, "entity_identity_preserved_required")
        frame_required = _resolved_bool(resolved_parameters, "frame_alignment_required")
        if same_team_required and _resolved_text(resolved_parameters, "team_role_field", "none") == "none":
            self._issue(
                "operator_aggregate_team_role_field_missing",
                "same-team-perspective aggregate requires declared team_role_field",
                f"{path}.parameters.team_role_field",
            )
        if not any((same_team_required, entity_required, frame_required)):
            return
        population_ref = node.inputs.get("population")
        if population_ref is None:
            return
        upstream = next(
            (
                bound
                for bound in self.bound_nodes
                if isinstance(bound, BoundOperatorNode)
                and bound.node_id == population_ref.source_node_id
            ),
            None,
        )
        if upstream is None or upstream.operator.name != "typed_join":
            return
        required = {
            "same_team_perspective_required": same_team_required,
            "entity_identity_preserved_required": entity_required,
            "frame_alignment_required": frame_required,
        }
        for parameter_name, is_required in required.items():
            if not is_required:
                continue
            if not _resolved_bool(upstream.resolved_parameters, parameter_name):
                self._issue(
                    "operator_aggregate_constraint_not_inherited",
                    (
                        f"aggregate_over requires upstream typed_join to enforce "
                        f"{parameter_name}"
                    ),
                    f"{path}.parameters.{parameter_name}",
                )

    def _bind_operator_outputs(
        self,
        *,
        node: DraftOperatorNode,
        signature: CompositionOperatorSignature,
        path: str,
    ) -> list[CatalogOutput]:
        declared = {output.name: output for output in node.outputs}
        expected = {output.name: output for output in signature.outputs}
        for name in sorted(set(declared) - set(expected)):
            self._issue(
                "unknown_operator_output",
                f"{signature.name}@{signature.version} does not declare output {name}",
                f"{path}.outputs.{name}",
            )
        outputs: list[CatalogOutput] = []
        for name, output_def in sorted(expected.items()):
            output = declared.get(name)
            if output is None:
                self._issue(
                    "missing_operator_output",
                    f"{signature.name}@{signature.version} requires declared output {name}",
                    f"{path}.outputs.{name}",
                )
                continue
            self._validate_operator_output(
                output_def=output_def,
                output=output,
                path=f"{path}.outputs.{name}",
            )
            outputs.append(operator_output_to_catalog_output(output))
        return outputs

    def _validate_catalog_input(
        self,
        *,
        input_def: CatalogInput,
        output: CatalogOutput,
        path: str,
    ) -> None:
        if output.temporal_type != input_def.temporal_type:
            self._issue(
                "input_temporal_mismatch",
                (
                    f"input {input_def.name} expects {input_def.temporal_type.value}, "
                    f"got {output.temporal_type.value}"
                ),
                path,
            )
        if output.payload_type != input_def.payload_type:
            self._issue(
                "input_payload_mismatch",
                (
                    f"input {input_def.name} expects {input_def.payload_type.value}, "
                    f"got {output.payload_type.value}"
                ),
                path,
            )
        if output.cardinality != input_def.cardinality:
            self._issue(
                "input_cardinality_mismatch",
                (
                    f"input {input_def.name} expects {input_def.cardinality.value}, "
                    f"got {output.cardinality.value}"
                ),
                path,
            )
        if output.unit != input_def.unit:
            self._issue(
                "input_unit_mismatch",
                f"input {input_def.name} expects {input_def.unit.value}, got {output.unit.value}",
                path,
            )
        if output.entity_scope != input_def.entity_scope:
            self._issue(
                "input_entity_scope_mismatch",
                (
                    f"input {input_def.name} expects {input_def.entity_scope.value}, "
                    f"got {output.entity_scope.value}"
                ),
                path,
            )

    def _validate_operator_input(
        self,
        *,
        input_def: OperatorInputDefinition,
        output: CatalogOutput,
        path: str,
    ) -> None:
        if output.temporal_type != input_def.temporal_type:
            self._issue(
                "operator_input_temporal_mismatch",
                (
                    f"input {input_def.name} expects {input_def.temporal_type.value}, "
                    f"got {output.temporal_type.value}"
                ),
                path,
            )
        if output.payload_type != input_def.payload_type:
            self._issue(
                "operator_input_payload_mismatch",
                (
                    f"input {input_def.name} expects {input_def.payload_type.value}, "
                    f"got {output.payload_type.value}"
                ),
                path,
            )
        if output.cardinality != input_def.cardinality:
            self._issue(
                "operator_input_cardinality_mismatch",
                (
                    f"input {input_def.name} expects {input_def.cardinality.value}, "
                    f"got {output.cardinality.value}"
                ),
                path,
            )
        if output.unit != input_def.unit:
            self._issue(
                "operator_input_unit_mismatch",
                f"input {input_def.name} expects {input_def.unit.value}, got {output.unit.value}",
                path,
            )
        if output.entity_scope != input_def.entity_scope:
            self._issue(
                "operator_input_entity_scope_mismatch",
                (
                    f"input {input_def.name} expects {input_def.entity_scope.value}, "
                    f"got {output.entity_scope.value}"
                ),
                path,
            )

    def _validate_operator_output(
        self,
        *,
        output_def: OperatorOutputDeclaration,
        output: OperatorOutputDeclaration,
        path: str,
    ) -> None:
        if output.temporal_type != output_def.temporal_type:
            self._issue(
                "operator_output_temporal_mismatch",
                f"output {output_def.name} expects {output_def.temporal_type.value}, got {output.temporal_type.value}",
                path,
            )
        if output.payload_type != output_def.payload_type:
            self._issue(
                "operator_output_payload_mismatch",
                f"output {output_def.name} expects {output_def.payload_type.value}, got {output.payload_type.value}",
                path,
            )
        if output.cardinality != output_def.cardinality:
            self._issue(
                "operator_output_cardinality_mismatch",
                f"output {output_def.name} expects {output_def.cardinality.value}, got {output.cardinality.value}",
                path,
            )
        if output.unit != output_def.unit:
            self._issue(
                "operator_output_unit_mismatch",
                f"output {output_def.name} expects {output_def.unit.value}, got {output.unit.value}",
                path,
            )
        if output.entity_scope != output_def.entity_scope:
            self._issue(
                "operator_output_entity_scope_mismatch",
                f"output {output_def.name} expects {output_def.entity_scope.value}, got {output.entity_scope.value}",
                path,
            )
        if output.missing_data_semantics != output_def.missing_data_semantics:
            self._issue(
                "operator_output_missing_data_mismatch",
                (
                    f"output {output_def.name} expects {output_def.missing_data_semantics.value}, "
                    f"got {output.missing_data_semantics.value}"
                ),
                path,
            )

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
        if signature.name in {"exists", "count_at_least"} and not _has_anchor_evaluation_coverage(input_type):
            self._issue(
                "operator_requires_anchor_evaluations",
                (
                    f"{signature.name} only accepts declared anchor-evaluation outputs; "
                    f"got {node.input.source_node_id}.{node.input.output_name}"
                ),
                f"{path}.input",
            )
        if (
            signature.name == "count_at_least"
            and input_type.coverage is not None
            and input_type.coverage.count_field is None
        ):
            self._issue(
                "operator_requires_count_coverage",
                (
                    f"count_at_least requires a declared count_field on "
                    f"{node.input.source_node_id}.{node.input.output_name}"
                ),
                f"{path}.input",
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
            if (
                compare.payload_type == PayloadType.ENUM
                and input_type.allowed_values is not None
                and str(compare.value) not in set(input_type.allowed_values)
            ):
                self._issue(
                    "compare_value_not_allowed",
                    (
                        f"{node.input.source_node_id}.{node.input.output_name} allows "
                        f"{sorted(input_type.allowed_values)}, got {compare.value}"
                    ),
                    f"{path}.compare.value",
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
            seconds = _duration_seconds(duration)
            if (
                seconds is not None
                and seconds > self.effective_max_temporal_horizon_seconds
            ):
                self._issue(
                    "complexity_temporal_horizon_exceeded",
                    (
                        f"duration={seconds}s exceeds "
                        f"max_temporal_horizon_seconds={self.effective_max_temporal_horizon_seconds}"
                    ),
                    f"{path}.duration",
                )

    def _validate_classifications(
        self, recipe: RecipeDefinition, draft_plan: DraftQueryPlan
    ) -> None:
        predicate_ids = {
            node.node_id for node in draft_plan.nodes if isinstance(node, DraftPredicateNode)
        }
        labels = [rule.label for rule in draft_plan.classification_rules]
        recipe_labels = set(recipe.output_classifications)
        plan_labels = set(labels)
        if draft_plan.classification_mode == ClassificationMode.EXHAUSTIVE:
            if plan_labels != recipe_labels:
                self._issue(
                    "classification_label_mismatch",
                    "exhaustive plan classification labels must equal recipe output classifications",
                    "draft_plan.classification_rules",
                )
        elif not plan_labels.issubset(recipe_labels):
            self._issue(
                "classification_label_mismatch",
                "partial plan classification labels must be a subset of recipe output classifications",
                "draft_plan.classification_rules",
            )
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

    def _validate_anchor_source(self, draft_plan: DraftQueryPlan) -> None:
        if draft_plan.anchor_source is None:
            self._issue(
                "missing_anchor_source",
                "draft plan must designate an anchor source",
                "draft_plan.anchor_source",
            )
            return
        referenced = self._resolve_signal(draft_plan.anchor_source, "draft_plan.anchor_source")
        if referenced is None:
            return
        _, output = referenced
        if (
            output.temporal_type != TemporalContainer.EPISODE_SET
            or output.payload_type != PayloadType.ANCHOR_REF
            or output.cardinality != Cardinality.COLLECTION
        ):
            self._issue(
                "invalid_anchor_source",
                "anchor source must be an episode_set collection of anchor_ref records",
                "draft_plan.anchor_source",
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

    def _find_composition_operator(self, name: str, version: str) -> CompositionOperatorSignature | None:
        return self.composition_operator_signatures.get((name, version))

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


def draft_plan_dependency_depth(draft_plan: DraftQueryPlan) -> int:
    inputs_by_node: dict[str, list[str]] = {}
    node_ids = {node.node_id for node in draft_plan.nodes}
    for node in draft_plan.nodes:
        if isinstance(node, DraftCatalogNode):
            inputs_by_node[node.node_id] = [
                reference.source_node_id
                for reference in node.inputs.values()
                if reference.source_node_id in node_ids
            ]
        elif isinstance(node, DraftPredicateNode):
            inputs_by_node[node.node_id] = (
                [node.input.source_node_id]
                if node.input.source_node_id in node_ids
                else []
            )
        elif isinstance(node, DraftOperatorNode):
            inputs_by_node[node.node_id] = [
                reference.source_node_id
                for reference in node.inputs.values()
                if reference.source_node_id in node_ids
            ]

    visiting: set[str] = set()
    visited: dict[str, int] = {}

    def depth(node_id: str) -> int:
        if node_id in visited:
            return visited[node_id]
        if node_id in visiting:
            return len(inputs_by_node)
        visiting.add(node_id)
        parents = inputs_by_node.get(node_id, [])
        value = 1 + max((depth(parent) for parent in parents), default=0)
        visiting.remove(node_id)
        visited[node_id] = value
        return value

    return max((depth(node.node_id) for node in draft_plan.nodes), default=0)


def bind_document_from_path(path: Path) -> BoundQueryPlan:
    return bind_document(load_tactical_query_document(path))


def operator_output_to_catalog_output(output: OperatorOutputDeclaration) -> CatalogOutput:
    return CatalogOutput(
        name=output.name,
        temporal_type=output.temporal_type,
        payload_type=output.payload_type,
        cardinality=output.cardinality,
        unit=output.unit,
        entity_scope=output.entity_scope,
        missing_data_semantics=output.missing_data_semantics,
        evidence_fields=list(output.evidence_fields),
    )


def bind_document_json(path: Path) -> str:
    bound = bind_document_from_path(path)
    return json.dumps(model_payload(bound), indent=2, sort_keys=True) + "\n"


def bind_error_codes(error: BindError) -> set[str]:
    return {issue.code for issue in error.issues}


def validation_error_codes(error: ValidationError) -> set[str]:
    return {str(issue["type"]) for issue in error.errors()}


def _resolved_bool(
    parameters: dict[str, TypedValue],
    name: str,
    default: bool = False,
) -> bool:
    value = parameters.get(name)
    return default if value is None else bool(value.value)


def _resolved_text(
    parameters: dict[str, TypedValue],
    name: str,
    default: str = "",
) -> str:
    value = parameters.get(name)
    return default if value is None else str(value.value)


def _has_anchor_evaluation_coverage(output: CatalogOutput) -> bool:
    return (
        output.coverage is not None
        and output.name == "anchor_evaluations"
        and output.temporal_type == TemporalContainer.EPISODE_SET
        and output.cardinality == Cardinality.COLLECTION
        and output.entity_scope == EntityScope.ANCHOR
    )


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
