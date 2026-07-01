/* eslint-disable */
// Generated from Pydantic TacticalQuerySchemaBundle.
// schema_sha256: ef278b28b4b2d31f9b7730af3135302c5aea377111ee92b744b90c92c32dcd7a

export type TemporalContainer = 'scalar' | 'frame_signal' | 'episode_set' | 'relation_episode_set';
export type PayloadType = 'boolean' | 'number' | 'enum' | 'anchor_ref' | 'entity_ref' | 'team_ref' | 'region_ref' | 'point' | 'entity_set' | 'relation_ref';
export type Cardinality = 'single' | 'per_player' | 'per_team' | 'collection';
export type Unit = 'none' | 'metre' | 'second' | 'millisecond' | 'frame' | 'fraction' | 'hertz' | 'count';
export type EntityScope = 'none' | 'anchor' | 'ball' | 'player' | 'team' | 'match' | 'possession' | 'frame' | 'relation';
export type MissingDataSemantics = 'unknown' | 'quality_fail' | 'not_applicable';
export type UnknownEvidencePolicy = 'exclude_candidate' | 'include_with_warning' | 'invalidate_execution';
export type ExecutionMode = 'bind_only' | 'dry_run' | 'execute';
export type PlanStatus = 'approved' | 'experimental';

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface TypedValue {
  payload_type: PayloadType;
  value: JsonValue;
  unit?: Unit;
}

export interface ParameterRef {
  kind: 'parameter';
  name: string;
}

export type TypedArgument = TypedValue | ParameterRef;

export interface ParameterDefinition {
  name: string;
  payload_type: PayloadType;
  unit?: Unit;
  required?: boolean;
  default?: TypedValue;
  minimum?: number;
  maximum?: number;
  allowed_values?: string[];
  description: string;
}

export interface QueryInvocation {
  schema_version: '1.0';
  invocation_id: string;
  match_ids: string[];
  periods: Array<'firstHalf' | 'secondHalf'>;
  perspective_team_role: 'home' | 'away';
  parameters?: Record<string, TypedValue>;
  max_results: number;
  execution_mode?: ExecutionMode;
}

export interface EvaluationTarget {
  schema_version: '1.0';
  target_id: string;
  match_id: string;
  period: 'firstHalf' | 'secondHalf';
  approximate_time_ms: number;
  search_radius_ms: number;
}

export interface SignalRef {
  source_node_id: string;
  output_name: string;
}

export interface OperatorRef {
  name: string;
  version: string;
}

export interface EvidenceRequest {
  source: SignalRef;
  field: string;
}

export interface DraftCatalogNode {
  kind: 'primitive' | 'relation';
  node_id: string;
  catalog_ref: string;
  version: string;
  inputs?: Record<string, SignalRef>;
  parameters?: Record<string, TypedArgument>;
}

export interface DraftPredicateNode {
  kind: 'predicate';
  node_id: string;
  input: SignalRef;
  operator: OperatorRef;
  compare?: TypedArgument;
  duration?: TypedArgument;
  required_cardinality?: Cardinality;
  required_entity_scope?: EntityScope;
}

export type DraftPlanNode = DraftCatalogNode | DraftPredicateNode;

export interface ClassificationRule {
  label: string;
  predicate_ids: string[];
  description: string;
}

export interface ComplexityLimits {
  max_plan_nodes: number;
  max_nesting_depth: number;
  max_temporal_horizon_seconds: number;
  max_returned_moments: number;
  max_relations_per_anchor: number;
  max_execution_cost: number;
}

export interface DraftQueryPlan {
  schema_version: '1.0';
  plan_id: string;
  plan_version: string;
  recipe_id: string;
  recipe_version: string;
  status: PlanStatus;
  unknown_evidence_policy: UnknownEvidencePolicy;
  classification_mode: 'exhaustive' | 'partial_declared';
  nodes: DraftPlanNode[];
  classification_rules: ClassificationRule[];
  requested_evidence?: EvidenceRequest[];
  complexity_limits?: ComplexityLimits;
}

export interface RecipeDefinition {
  schema_version: '1.0';
  recipe_id: string;
  recipe_version: string;
  display_name: string;
  description: string;
  parameters?: ParameterDefinition[];
  default_unknown_evidence_policy: UnknownEvidencePolicy;
  allowed_claims?: string[];
  disallowed_claims?: string[];
  limitations?: string[];
  output_classifications: string[];
}

export interface TacticalQueryDocument {
  schema_version: '1.0';
  recipe: RecipeDefinition;
  default_invocation: QueryInvocation;
  draft_plan: DraftQueryPlan;
}

export interface BoundQueryPlan {
  schema_version: '1.0';
  plan_id: string;
  plan_version: string;
  plan_status: PlanStatus;
  recipe_id: string;
  recipe_version: string;
  invocation_id: string;
  match_ids: string[];
  periods: Array<'firstHalf' | 'secondHalf'>;
  perspective_team_role: 'home' | 'away';
  max_results: number;
  execution_mode: ExecutionMode;
  unknown_evidence_policy: UnknownEvidencePolicy;
  plan_hash: string;
  bound_plan_hash: string;
}

export interface QueryExecution {
  schema_version: '1.0';
  execution_id: string;
  status: 'not_started' | 'pass' | 'fail' | 'incomplete';
  plan_hash: string;
  bound_plan_hash: string;
}
