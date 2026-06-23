import type {
  BootstrapResponse as GeneratedBootstrapResponse,
  ConfirmationResponse as GeneratedConfirmationResponse,
  ErrorResponse as GeneratedErrorResponse,
  ExecutionProgressResponse as GeneratedExecutionProgressResponse,
  ExecutionResponse as GeneratedExecutionResponse,
  InspectResultResponse as GeneratedInspectResultResponse,
  InspectTimestampResponse as GeneratedInspectTimestampResponse,
  InterpretResponse as GeneratedInterpretResponse,
  MatchLibraryResponse as GeneratedMatchLibraryResponse,
  PlanResponse as GeneratedPlanResponse,
  SubmitValidateResponse as GeneratedSubmitValidateResponse
} from "./generated/api-types";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonObject = { [key: string]: JsonValue };

export type RecipeSummary = {
  recipe_id: string;
  recipe_version: string;
  state: "APPROVED" | "EXPERIMENTAL" | "USER_SAVED" | "DEPRECATED";
  display_name: string;
  description: string;
  allowed_claims: string[];
  disallowed_claims: string[];
  limitations: string[];
  output_classifications: string[];
};

export type Preset = {
  preset_id: "approved_block_shift" | "experimental_corridor" | "experimental_high_bypass";
  label: string;
  recipe: RecipeSummary;
  plan_hash: string;
};

export type TeamBrand = {
  team_id?: string | null;
  team_name: string;
  short_name: string;
  abbreviation: string;
  logo_url?: string | null;
  logo_source?: string | null;
  primary_color?: string | null;
  secondary_color?: string | null;
};

export type MatchSummary = {
  match_id: string;
  match_title: string;
  home_team: string;
  away_team: string;
  home_team_brand: TeamBrand;
  away_team_brand: TeamBrand;
  result?: string | null;
  match_day?: string | null;
  kickoff_time_utc?: string | null;
};

export type MatchLibraryResponse = Omit<GeneratedMatchLibraryResponse, "matches"> & {
  ok: true;
  perspective_team: string;
  perspective_team_brand: TeamBrand;
  default_match_ids: string[];
  matches: MatchSummary[];
};

export type BootstrapResponse = Omit<GeneratedBootstrapResponse, "presets" | "capabilities"> & {
  presets: Preset[];
  capabilities: {
    primitive_count: number;
    relation_count: number;
    operator_count: number;
    tools: string[];
    execute_tool_description: JsonObject;
  };
};

export type InterpretStatus =
  | "PLAN_INTERPRETED"
  | "CLARIFICATION_REQUIRED"
  | "CAPABILITY_GAP"
  | "MODEL_UNAVAILABLE";

export type ProvenanceSource =
  | "REVIEWED_RECIPE"
  | "MANUAL_PRESET"
  | "HERMES_RECIPE_SELECTION"
  | "HERMES_NOVEL_COMPOSITION"
  | "HERMES_EXPERIMENTAL_UNVERIFIED"
  | "DETERMINISTIC_REPAIR"
  | "CAPABILITY_GAP"
  | "MODEL_UNAVAILABLE";

export type InterpretResponse = Omit<GeneratedInterpretResponse, "recipe" | "plan_document" | "capability_gaps"> & {
  ok: true;
  status: InterpretStatus;
  provenance_source: ProvenanceSource;
  query?: string | null;
  message?: string | null;
  source?: string | null;
  model_session_id?: string | null;
  recipe?: RecipeSummary | null;
  plan_document?: JsonObject | null;
  plan_hash?: string | null;
  recipe_id?: string | null;
  draft_plan_hash?: string | null;
  clarification_questions?: string[] | null;
  clarification_codes?: string[] | null;
  capability_gaps?: Array<{ concept: string; reason: string }> | null;
  manual_available?: boolean | null;
  repair_applied?: boolean;
  fallback_reason?: string | null;
};

export type SubmitValidateResponse = Omit<GeneratedSubmitValidateResponse, "submit" | "validation"> & {
  ok: true;
  submit: JsonObject;
  validation: {
    ok: boolean;
    draft_plan_id: string;
    bound_plan_id?: string | null;
    plan_id?: string | null;
    recipe_id?: string | null;
    plan_status?: string | null;
    bound_plan_hash?: string | null;
    execution_profile?: string | null;
    issues: JsonObject[];
  };
};

export type ConfirmationResponse = Omit<GeneratedConfirmationResponse, "confirmation"> & {
  ok: true;
  confirmation: {
    ok: boolean;
    bound_plan_id: string;
    execution_authorization_id: string;
  };
};

export type ResultRow = {
  rank: number;
  result_id: string;
  classification: string;
  match_id: string;
  period: string;
  anchor_frame_id: number;
  match_time_ms?: number | null;
  requested_evidence: Record<string, JsonValue>;
};

export type ExecutionProgressResponse = GeneratedExecutionProgressResponse & {
  ok: true;
  cache_key: string;
  cache_status: "HIT" | "MISS";
  message: string;
  stages: string[];
};

export type ExecutionResponse = Omit<GeneratedExecutionResponse, "execution" | "cache"> & {
  ok: true;
  cache: ExecutionProgressResponse;
  execution: {
    ok: boolean;
    execution_id: string;
    execution_status: string;
    execution_complete: boolean;
    requested_evidence_failure_count: number;
    requested_evidence_failures: JsonObject[];
    bound_plan_id: string;
    plan_id: string;
    plan_status: string;
    compatibility_profile: string;
    draft_plan_hash: string;
    total_result_count: number;
    returned_result_count: number;
    results: ResultRow[];
    trace_count: number;
    bound_plan_hash: string;
  };
};

export type ReplayEntity = {
  team_id: string;
  team_role: string;
  entity_id: string;
  entity_type: string;
  x_m: number;
  y_m: number;
};

export type ReplayFrame = {
  frame_id: number;
  timestamp_utc?: string | null;
  entities: ReplayEntity[];
};

export type ReplayPayload = {
  schema_version: string;
  replay_window_id: string;
  source_kind: "result" | "target";
  source_id: string;
  match_id: string;
  period: string;
  frame_rate_hz: number;
  start_frame_id: number;
  end_frame_id: number;
  anchor_frame_id: number;
  generated_at: string;
  canonical_sources: Record<string, string>;
  pitch: {
    length_m: number;
    width_m: number;
    coordinate_contract: string;
  };
  frames: ReplayFrame[];
};

export type PredicateTrace = {
  predicate_id?: string;
  status?: "PASS" | "FAIL" | "UNKNOWN" | string;
  frame_id?: number;
  source_evidence?: JsonObject;
  value?: JsonValue;
  threshold?: JsonValue;
  unit?: string;
  window?: JsonObject;
};

export type InspectResultResponse = Omit<GeneratedInspectResultResponse, "inspection" | "replay"> & {
  ok: true;
  inspection: {
    ok: boolean;
    execution_id: string;
    result: ResultRow & JsonObject;
    predicate_traces: PredicateTrace[];
    requested_evidence: Record<string, JsonValue>;
  };
  replay_window: JsonObject;
  replay: ReplayPayload;
};

export type TimestampTarget = {
  schema_version: "1.0";
  target_id: string;
  match_id: string;
  period: "firstHalf" | "secondHalf";
  approximate_time_ms: number;
  search_radius_ms: number;
};

export type InspectTimestampResponse = Omit<GeneratedInspectTimestampResponse, "inspection" | "replay"> & {
  ok: true;
  inspection: JsonObject;
  replay_window: JsonObject;
  replay: ReplayPayload;
};

export type PlanResponse = Omit<GeneratedPlanResponse, "recipe" | "plan_document"> & {
  ok: true;
  recipe: RecipeSummary;
  plan_document: JsonObject;
  plan_hash: string;
};

export type ErrorResponse = GeneratedErrorResponse & {
  ok: false;
  error_code: string;
  message: string;
  details?: JsonObject;
};
