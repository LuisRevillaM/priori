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
  preset_id: "approved_block_shift" | "experimental_corridor";
  label: string;
  recipe: RecipeSummary;
  plan_hash: string;
};

export type BootstrapResponse = {
  ok: boolean;
  service: {
    name: string;
    mcp_adapter: boolean;
    output_root: string;
  };
  model: {
    available: boolean;
    status: string;
    message: string;
  };
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

export type InterpretResponse = {
  ok: boolean;
  status: InterpretStatus;
  query?: string;
  message?: string;
  source?: string;
  recipe?: RecipeSummary;
  plan_document?: JsonObject;
  plan_hash?: string;
  clarification_questions?: string[];
  clarification_codes?: string[];
  capability_gaps?: Array<{ concept: string; reason: string }>;
  manual_available?: boolean;
};

export type SubmitValidateResponse = {
  ok: boolean;
  submit: JsonObject;
  validation: {
    ok: boolean;
    draft_plan_id: string;
    bound_plan_id?: string;
    plan_id?: string;
    recipe_id?: string;
    plan_status?: string;
    bound_plan_hash?: string;
    execution_profile?: string;
    issues: JsonObject[];
  };
};

export type ConfirmationResponse = {
  ok: boolean;
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
  requested_evidence: Record<string, JsonValue>;
};

export type ExecutionResponse = {
  ok: boolean;
  execution: {
    ok: boolean;
    execution_id: string;
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
  timestamp_utc?: string;
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

export type InspectResultResponse = {
  ok: boolean;
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

export type InspectTimestampResponse = {
  ok: boolean;
  inspection: JsonObject;
  replay_window: JsonObject;
  replay: ReplayPayload;
};

export type ApiError = {
  ok: false;
  error_code: string;
  message: string;
  details?: JsonObject;
};
