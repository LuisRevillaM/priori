"""Generated M1.1 Gate A schema and catalog artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tqe.runtime.catalog import default_catalog
from tqe.runtime.ir import (
    CapabilityCatalog,
    Cardinality,
    EntityScope,
    ExecutionMode,
    MissingDataSemantics,
    PayloadType,
    PlanStatus,
    TacticalQuerySchemaBundle,
    TemporalContainer,
    Unit,
    UnknownEvidencePolicy,
    canonical_json,
    stable_hash,
)

GENERATED_DIR = Path("generated")
SCHEMA_PATH = GENERATED_DIR / "tactical-query-plan.schema.json"
TYPES_PATH = GENERATED_DIR / "tactical-query-plan.types.ts"
CATALOG_PATH = GENERATED_DIR / "capability-catalog.json"


def schema_payload() -> dict[str, Any]:
    schema = TacticalQuerySchemaBundle.model_json_schema()
    schema["$id"] = "https://priori.local/schemas/tactical-query-plan.v1.json"
    schema["title"] = "Tactical Query IR v1 Schema Bundle"
    return schema


def catalog_payload(catalog: CapabilityCatalog | None = None) -> dict[str, Any]:
    return (catalog or default_catalog()).model_dump(mode="json", exclude_none=True)


def typescript_types_payload(schema: dict[str, Any] | None = None) -> str:
    schema = schema or schema_payload()
    schema_hash = stable_hash(schema)
    return "\n".join(
        [
            "/* eslint-disable */",
            "// Generated from Pydantic TacticalQuerySchemaBundle.",
            f"// schema_sha256: {schema_hash}",
            "",
            enum_type("TemporalContainer", TemporalContainer),
            enum_type("PayloadType", PayloadType),
            enum_type("Cardinality", Cardinality),
            enum_type("Unit", Unit),
            enum_type("EntityScope", EntityScope),
            enum_type("MissingDataSemantics", MissingDataSemantics),
            enum_type("UnknownEvidencePolicy", UnknownEvidencePolicy),
            enum_type("ExecutionMode", ExecutionMode),
            enum_type("PlanStatus", PlanStatus),
            "",
            "export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };",
            "",
            "export interface TypedValue {",
            "  payload_type: PayloadType;",
            "  value: JsonValue;",
            "  unit?: Unit;",
            "}",
            "",
            "export interface ParameterRef {",
            "  kind: 'parameter';",
            "  name: string;",
            "}",
            "",
            "export type TypedArgument = TypedValue | ParameterRef;",
            "",
            "export interface ParameterDefinition {",
            "  name: string;",
            "  payload_type: PayloadType;",
            "  unit?: Unit;",
            "  required?: boolean;",
            "  default?: TypedValue;",
            "  description: string;",
            "}",
            "",
            "export interface QueryInvocation {",
            "  schema_version: '1.0';",
            "  invocation_id: string;",
            "  match_ids: string[];",
            "  periods: Array<'firstHalf' | 'secondHalf'>;",
            "  perspective_team_role: 'home' | 'away';",
            "  parameters?: Record<string, TypedValue>;",
            "  max_results: number;",
            "  execution_mode?: ExecutionMode;",
            "}",
            "",
            "export interface SignalRef {",
            "  source_node_id: string;",
            "  output_name: string;",
            "}",
            "",
            "export interface OperatorRef {",
            "  name: string;",
            "  version: string;",
            "}",
            "",
            "export interface EvidenceRequest {",
            "  source: SignalRef;",
            "  field: string;",
            "}",
            "",
            "export interface DraftCatalogNode {",
            "  kind: 'primitive' | 'relation';",
            "  node_id: string;",
            "  catalog_ref: string;",
            "  version: string;",
            "  parameters?: Record<string, TypedArgument>;",
            "}",
            "",
            "export interface DraftPredicateNode {",
            "  kind: 'predicate';",
            "  node_id: string;",
            "  input: SignalRef;",
            "  operator: OperatorRef;",
            "  compare?: TypedArgument;",
            "  duration?: TypedArgument;",
            "  required_cardinality?: Cardinality;",
            "  required_entity_scope?: EntityScope;",
            "}",
            "",
            "export type DraftPlanNode = DraftCatalogNode | DraftPredicateNode;",
            "",
            "export interface ClassificationRule {",
            "  label: string;",
            "  predicate_ids: string[];",
            "  description: string;",
            "}",
            "",
            "export interface ComplexityLimits {",
            "  max_plan_nodes: number;",
            "  max_nesting_depth: number;",
            "  max_temporal_horizon_seconds: number;",
            "  max_returned_moments: number;",
            "  max_relations_per_anchor: number;",
            "  max_execution_cost: number;",
            "}",
            "",
            "export interface DraftQueryPlan {",
            "  schema_version: '1.0';",
            "  plan_id: string;",
            "  plan_version: string;",
            "  recipe_id: string;",
            "  recipe_version: string;",
            "  status: PlanStatus;",
            "  unknown_evidence_policy: UnknownEvidencePolicy;",
            "  classification_mode: 'exhaustive' | 'partial_declared';",
            "  nodes: DraftPlanNode[];",
            "  classification_rules: ClassificationRule[];",
            "  requested_evidence?: EvidenceRequest[];",
            "  complexity_limits?: ComplexityLimits;",
            "}",
            "",
            "export interface RecipeDefinition {",
            "  schema_version: '1.0';",
            "  recipe_id: string;",
            "  recipe_version: string;",
            "  display_name: string;",
            "  description: string;",
            "  parameters?: ParameterDefinition[];",
            "  default_unknown_evidence_policy: UnknownEvidencePolicy;",
            "  allowed_claims?: string[];",
            "  disallowed_claims?: string[];",
            "  limitations?: string[];",
            "  output_classifications: string[];",
            "}",
            "",
            "export interface TacticalQueryDocument {",
            "  schema_version: '1.0';",
            "  recipe: RecipeDefinition;",
            "  default_invocation: QueryInvocation;",
            "  draft_plan: DraftQueryPlan;",
            "}",
            "",
            "export interface BoundQueryPlan {",
            "  schema_version: '1.0';",
            "  plan_id: string;",
            "  plan_version: string;",
            "  recipe_id: string;",
            "  recipe_version: string;",
            "  invocation_id: string;",
            "  match_ids: string[];",
            "  periods: Array<'firstHalf' | 'secondHalf'>;",
            "  perspective_team_role: 'home' | 'away';",
            "  unknown_evidence_policy: UnknownEvidencePolicy;",
            "  plan_hash: string;",
            "  bound_plan_hash: string;",
            "}",
            "",
            "export interface QueryExecution {",
            "  schema_version: '1.0';",
            "  execution_id: string;",
            "  status: 'not_started' | 'pass' | 'fail' | 'incomplete';",
            "  plan_hash: string;",
            "  bound_plan_hash: string;",
            "}",
            "",
        ]
    )


def write_generated_artifacts(root: Path = Path(".")) -> dict[str, str]:
    schema = schema_payload()
    catalog = catalog_payload()
    typescript = typescript_types_payload(schema)
    outputs = {
        root / SCHEMA_PATH: canonical_json(schema) + "\n",
        root / CATALOG_PATH: canonical_json(catalog) + "\n",
        root / TYPES_PATH: typescript,
    }
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {str(path): stable_hash(content) for path, content in outputs.items()}


def expected_generated_artifacts() -> dict[str, str]:
    schema = schema_payload()
    catalog = catalog_payload()
    typescript = typescript_types_payload(schema)
    return {
        str(SCHEMA_PATH): canonical_json(schema) + "\n",
        str(CATALOG_PATH): canonical_json(catalog) + "\n",
        str(TYPES_PATH): typescript,
    }


def enum_type(name: str, enum_cls: type) -> str:
    values = " | ".join(f"'{member.value}'" for member in enum_cls)
    return f"export type {name} = {values};"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
