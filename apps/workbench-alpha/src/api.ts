import Ajv, { type ValidateFunction } from "ajv";
import { apiSchemas } from "./generated/api-types";
import type {
  BootstrapResponse,
  ConfirmationResponse,
  ErrorResponse,
  ExecutionProgressResponse,
  ExecutionResponse,
  InspectResultResponse,
  InspectTimestampResponse,
  InterpretResponse,
  JsonObject,
  MatchLibraryResponse,
  PlanResponse,
  SubmitValidateResponse,
  TimestampTarget
} from "./types";

type ApiSchemaName = keyof typeof apiSchemas;

const ajv = new Ajv({ allErrors: true, strict: false });
const validators = new Map<ApiSchemaName, ValidateFunction>();

function validatorFor(schemaName: ApiSchemaName) {
  const cached = validators.get(schemaName);
  if (cached) return cached;
  const compiled = ajv.compile(apiSchemas[schemaName]);
  validators.set(schemaName, compiled);
  return compiled;
}

function assertValidResponse<T>(schemaName: ApiSchemaName, payload: unknown): T {
  const validate = validatorFor(schemaName);
  if (!validate(payload)) {
    const details = ajv.errorsText(validate.errors, { separator: "; " });
    throw new Error(`Host response schema invalid for ${schemaName}: ${details}`);
  }
  return payload as T;
}

async function request<T>(schemaName: ApiSchemaName, path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });
  const payload = (await parseJsonResponse(path, response)) as T & { ok?: boolean; message?: string; error_code?: string };
  if (!response.ok || payload.ok === false) {
    const errorPayload = assertValidResponse<ErrorResponse>("ErrorResponse", payload);
    const message = errorPayload.message ?? errorPayload.error_code ?? `Request failed: ${path}`;
    throw new Error(message);
  }
  return assertValidResponse<T>(schemaName, payload);
}

async function parseJsonResponse(path: string, response: Response): Promise<unknown> {
  const text = await response.text();
  const contentType = response.headers.get("content-type") ?? "";
  const status = `${response.status} ${response.statusText}`.trim();
  if (!text.trim()) {
    throw new Error(`Workbench host returned an empty response for ${path} (${status}).`);
  }
  if (!contentType.toLowerCase().includes("json")) {
    const looksLikeHtml = /^\s*<!doctype html/i.test(text) || /^\s*<html[\s>]/i.test(text);
    const responseKind = looksLikeHtml ? "HTML" : "non-JSON";
    throw new Error(
      `Workbench host returned ${responseKind} for ${path} (${status}). The service may be restarting, overloaded, or serving the app shell instead of the API.`
    );
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Workbench host returned invalid JSON for ${path} (${status}).`);
  }
}

export function bootstrap(): Promise<BootstrapResponse> {
  return request<BootstrapResponse>("BootstrapResponse", "/api/bootstrap");
}

export function fetchMatches(): Promise<MatchLibraryResponse> {
  return request<MatchLibraryResponse>("MatchLibraryResponse", "/api/matches");
}

export function fetchPlan(recipeId: string): Promise<PlanResponse> {
  return request<PlanResponse>("PlanResponse", `/api/plan?recipe_id=${encodeURIComponent(recipeId)}`);
}

export function interpret(input: {
  query: string;
  mode: "manual" | "model";
  selected_recipe_id?: string;
  preset_id?: string;
  clarifications?: string[];
}): Promise<InterpretResponse> {
  return request<InterpretResponse>("InterpretResponse", "/api/interpret", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function submitValidate(planDocument: JsonObject): Promise<SubmitValidateResponse> {
  return request<SubmitValidateResponse>("SubmitValidateResponse", "/api/submit-validate", {
    method: "POST",
    body: JSON.stringify({ plan_document: planDocument })
  });
}

export function confirm(boundPlanId: string): Promise<ConfirmationResponse> {
  return request<ConfirmationResponse>("ConfirmationResponse", "/api/confirm", {
    method: "POST",
    body: JSON.stringify({ bound_plan_id: boundPlanId, reviewer: "workbench_alpha_host" })
  });
}

export function executionCacheStatus(input: {
  bound_plan_id: string;
  execution_authorization_id: string;
  result_limit: number;
}): Promise<ExecutionProgressResponse> {
  return request<ExecutionProgressResponse>("ExecutionProgressResponse", "/api/execution-cache-status", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function execute(input: {
  bound_plan_id: string;
  execution_authorization_id: string;
  result_limit: number;
}): Promise<ExecutionResponse> {
  return request<ExecutionResponse>("ExecutionResponse", "/api/execute", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function inspectResult(input: {
  execution_id: string;
  result_id: string;
  padding_seconds?: number;
}): Promise<InspectResultResponse> {
  return request<InspectResultResponse>("InspectResultResponse", "/api/inspect-result", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function inspectTimestamp(input: {
  execution_id: string;
  target: TimestampTarget;
  padding_seconds?: number;
}): Promise<InspectTimestampResponse> {
  return request<InspectTimestampResponse>("InspectTimestampResponse", "/api/inspect-timestamp", {
    method: "POST",
    body: JSON.stringify(input)
  });
}
