// Pure, framework-free state machine for the Workbench workflow. Keeping it out of React lets us
// unit-test every transition (tests/workbenchState.test.ts) and centralises invalidation so a new
// piece of downstream state can't be forgotten when an upstream input changes.
import type {
  BootstrapResponse,
  ConfirmationResponse,
  ExecutionProgressResponse,
  ExecutionResponse,
  InspectResultResponse,
  InspectTimestampResponse,
  InterpretResponse,
  JsonObject,
  MatchLibraryResponse,
  Preset,
  SubmitValidateResponse
} from "./types";

export type Phase =
  | "booting"
  | "idle"
  | "interpreting"
  | "ready"
  | "confirming"
  | "executing"
  | "results"
  | "error";

export type Mode = "manual" | "model";
export type RunStep = "validating" | "confirming" | "executing";

export interface WorkbenchState {
  phase: Phase;
  inFlight: boolean;
  boot: BootstrapResponse | null;
  matchLibrary: MatchLibraryResponse | null;
  matchLibraryLoaded: boolean;
  selectedMatchIds: string[];
  mode: Mode;
  query: string;
  selectedPreset: Preset["preset_id"];
  planDocument: JsonObject | null;
  interpretation: InterpretResponse | null;
  validation: SubmitValidateResponse | null;
  confirmation: ConfirmationResponse | null;
  executionProgress: ExecutionProgressResponse | null;
  execution: ExecutionResponse | null;
  selectedResultId: string | null;
  inspection: InspectResultResponse | null;
  timestampInspection: InspectTimestampResponse | null;
  inspectionLoadingResultId: string | null;
  runStep: RunStep | null;
  runStartedAt: number | null;
  error: string | null;
}

export type WorkbenchAction =
  | { type: "BOOT_READY"; boot: BootstrapResponse; matchLibrary: MatchLibraryResponse }
  | { type: "BOOT_FAILED"; error: string }
  | { type: "SET_MODE"; mode: Mode }
  | { type: "SET_QUERY"; query: string }
  | { type: "SET_PRESET"; preset: Preset["preset_id"] }
  | { type: "SET_SCOPE"; ids: string[] }
  | { type: "INTERPRET_START" }
  | { type: "INTERPRET_RESULT"; interpretation: InterpretResponse }
  | { type: "RUN_STEP"; step: RunStep; startedAt: number }
  | { type: "VALIDATED"; validation: SubmitValidateResponse }
  | { type: "CONFIRMED"; confirmation: ConfirmationResponse }
  | { type: "EXEC_PROGRESS"; progress: ExecutionProgressResponse }
  | { type: "EXECUTED"; execution: ExecutionResponse; selectedResultId: string | null }
  | { type: "INSPECT_START"; resultId: string }
  | { type: "INSPECTED"; inspection: InspectResultResponse }
  | { type: "INSPECT_DONE" }
  | { type: "SELECT_RESULT"; resultId: string }
  | { type: "TIMESTAMP_START" }
  | { type: "TIMESTAMP_INSPECTED"; timestampInspection: InspectTimestampResponse }
  | { type: "ERROR"; error: string }
  | { type: "CLEAR_ERROR" };

export const DEFAULT_QUERY =
  "Show possessions where a progressive corridor opens within four seconds of possession starting, remains available for at least 0.8 seconds, and the ball enters that corridor's destination region within five seconds of the corridor opening.";

export function initialState(): WorkbenchState {
  return {
    phase: "booting",
    inFlight: true,
    boot: null,
    matchLibrary: null,
    matchLibraryLoaded: false,
    selectedMatchIds: [],
    mode: "manual",
    query: DEFAULT_QUERY,
    selectedPreset: "approved_block_shift",
    planDocument: null,
    interpretation: null,
    validation: null,
    confirmation: null,
    executionProgress: null,
    execution: null,
    selectedResultId: null,
    inspection: null,
    timestampInspection: null,
    inspectionLoadingResultId: null,
    runStep: null,
    runStartedAt: null,
    error: null
  };
}

function asRecord(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function applyScopeToPlan(planDocument: JsonObject, matchIds: string[]): JsonObject {
  const next = structuredClone(planDocument) as JsonObject;
  const invocation = asRecord(next.default_invocation);
  invocation.match_ids = matchIds;
  invocation.periods = asArray(invocation.periods).length > 0 ? invocation.periods : ["firstHalf", "secondHalf"];
  invocation.perspective_team_role = invocation.perspective_team_role || "home";
  next.default_invocation = invocation;
  return next;
}

const SCOPE_DEPENDENT_RESET = {
  validation: null,
  confirmation: null,
  executionProgress: null,
  execution: null,
  selectedResultId: null,
  inspection: null,
  timestampInspection: null,
  inspectionLoadingResultId: null
} as const;

const INTERPRETATION_RESET = {
  interpretation: null,
  planDocument: null,
  ...SCOPE_DEPENDENT_RESET
} as const;

// --- selectors (pure, derived) ---
export function selectPlanReady(state: WorkbenchState): boolean {
  return Boolean(state.planDocument && state.interpretation?.status === "PLAN_INTERPRETED");
}

export function selectHasSelectedScope(state: WorkbenchState): boolean {
  return state.selectedMatchIds.length > 0;
}

export function selectIsNovelComposition(state: WorkbenchState): boolean {
  return state.interpretation?.provenance_source === "HERMES_NOVEL_COMPOSITION";
}

export function selectIsUnverifiedExperimental(state: WorkbenchState): boolean {
  return state.interpretation?.provenance_source === "HERMES_EXPERIMENTAL_UNVERIFIED";
}

export function selectBusy(state: WorkbenchState): boolean {
  return state.inFlight;
}

export function selectCanRun(state: WorkbenchState): boolean {
  return (
    selectPlanReady(state) &&
    selectHasSelectedScope(state) &&
    !selectIsUnverifiedExperimental(state) &&
    !state.inFlight
  );
}

function scopeFromPlan(planDocument: JsonObject): string[] {
  const invocation = asRecord(planDocument.default_invocation);
  return asArray(invocation.match_ids).filter((item): item is string => typeof item === "string");
}

// Phase a settled (non-in-flight) state should rest in, given its data.
function settledPhase(state: WorkbenchState): Phase {
  if (state.execution) return "results";
  if (selectPlanReady(state) && selectHasSelectedScope(state)) return "ready";
  return "idle";
}

export function reducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case "BOOT_READY":
      return {
        ...state,
        phase: "idle",
        inFlight: false,
        boot: action.boot,
        matchLibrary: action.matchLibrary,
        matchLibraryLoaded: true,
        selectedMatchIds: action.matchLibrary.default_match_ids
      };
    case "BOOT_FAILED":
      return { ...state, phase: "error", inFlight: false, error: action.error };
    case "SET_MODE": {
      if (action.mode === state.mode) return state;
      return { ...state, mode: action.mode, ...INTERPRETATION_RESET, phase: "idle", error: null };
    }
    case "SET_QUERY":
      return { ...state, query: action.query, ...INTERPRETATION_RESET, phase: "idle", error: null };
    case "SET_PRESET":
      return { ...state, selectedPreset: action.preset, ...INTERPRETATION_RESET, phase: "idle", error: null };
    case "SET_SCOPE": {
      if (selectIsNovelComposition(state)) {
        return state;
      }
      const planDocument = state.planDocument ? applyScopeToPlan(state.planDocument, action.ids) : null;
      const next = { ...state, selectedMatchIds: action.ids, planDocument, ...SCOPE_DEPENDENT_RESET };
      return { ...next, phase: settledPhase(next) };
    }
    case "INTERPRET_START":
      return { ...state, phase: "interpreting", inFlight: true, error: null };
    case "INTERPRET_RESULT": {
      const interpretation = action.interpretation;
      const incomingPlan =
        interpretation.status === "PLAN_INTERPRETED" && interpretation.plan_document ? interpretation.plan_document : null;
      const isNovel = interpretation.provenance_source === "HERMES_NOVEL_COMPOSITION";
      const planDocument =
        incomingPlan && isNovel ? incomingPlan : incomingPlan ? applyScopeToPlan(incomingPlan, state.selectedMatchIds) : null;
      const selectedMatchIds = incomingPlan && isNovel ? scopeFromPlan(incomingPlan) : state.selectedMatchIds;
      const next = { ...state, interpretation, selectedMatchIds, planDocument, ...SCOPE_DEPENDENT_RESET, inFlight: false };
      return { ...next, phase: settledPhase(next) };
    }
    case "RUN_STEP":
      return {
        ...state,
        inFlight: true,
        runStep: action.step,
        runStartedAt: state.runStartedAt ?? action.startedAt,
        phase: action.step === "executing" ? "executing" : "confirming"
      };
    case "VALIDATED":
      return {
        ...state,
        validation: action.validation,
        confirmation: null,
        execution: null,
        selectedResultId: null,
        inspection: null,
        timestampInspection: null,
        inspectionLoadingResultId: null
      };
    case "CONFIRMED":
      return { ...state, confirmation: action.confirmation };
    case "EXEC_PROGRESS":
      return { ...state, executionProgress: action.progress };
    case "EXECUTED":
      return {
        ...state,
        execution: action.execution,
        executionProgress: action.execution.cache,
        selectedResultId: action.selectedResultId,
        phase: "results",
        inFlight: false,
        runStep: null,
        runStartedAt: null
      };
    case "INSPECT_START":
      return {
        ...state,
        inFlight: true,
        inspection: null,
        timestampInspection: null,
        inspectionLoadingResultId: action.resultId
      };
    case "INSPECTED":
      return { ...state, inspection: action.inspection, inspectionLoadingResultId: null, inFlight: false };
    case "INSPECT_DONE":
      return { ...state, inspectionLoadingResultId: null, inFlight: false };
    case "SELECT_RESULT":
      return { ...state, selectedResultId: action.resultId };
    case "TIMESTAMP_START":
      return { ...state, inFlight: true };
    case "TIMESTAMP_INSPECTED":
      return {
        ...state,
        timestampInspection: action.timestampInspection,
        inspection: null,
        inspectionLoadingResultId: null,
        inFlight: false
      };
    case "ERROR":
      return { ...state, error: action.error, inFlight: false, phase: settledPhase(state) };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    default:
      return state;
  }
}
