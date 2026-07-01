import type {
  BootstrapResponse,
  ConfirmationResponse,
  ExecutionResponse,
  InspectResultResponse,
  InspectTimestampResponse,
  InterpretResponse,
  JsonObject,
  RecipeSummary,
  SubmitValidateResponse,
  TimestampTarget
} from "./types";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });
  const payload = (await response.json()) as T & { ok?: boolean; message?: string; error_code?: string };
  if (!response.ok || payload.ok === false) {
    const message = payload.message ?? payload.error_code ?? `Request failed: ${path}`;
    throw new Error(message);
  }
  return payload;
}

export function bootstrap(): Promise<BootstrapResponse> {
  return request<BootstrapResponse>("/api/bootstrap");
}

export function fetchPlan(recipeId: string): Promise<{ ok: boolean; recipe: RecipeSummary; plan_document: JsonObject; plan_hash: string }> {
  return request(`/api/plan?recipe_id=${encodeURIComponent(recipeId)}`);
}

export function interpret(input: {
  query: string;
  mode: "manual" | "model";
  selected_recipe_id?: string;
  preset_id?: string;
  clarifications?: string[];
}): Promise<InterpretResponse> {
  return request<InterpretResponse>("/api/interpret", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function submitValidate(planDocument: JsonObject): Promise<SubmitValidateResponse> {
  return request<SubmitValidateResponse>("/api/submit-validate", {
    method: "POST",
    body: JSON.stringify({ plan_document: planDocument })
  });
}

export function confirm(boundPlanId: string): Promise<ConfirmationResponse> {
  return request<ConfirmationResponse>("/api/confirm", {
    method: "POST",
    body: JSON.stringify({ bound_plan_id: boundPlanId, reviewer: "workbench_alpha_host" })
  });
}

export function execute(input: {
  bound_plan_id: string;
  execution_authorization_id: string;
  result_limit: number;
}): Promise<ExecutionResponse> {
  return request<ExecutionResponse>("/api/execute", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function inspectResult(input: {
  execution_id: string;
  result_id: string;
  padding_seconds?: number;
}): Promise<InspectResultResponse> {
  return request<InspectResultResponse>("/api/inspect-result", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function inspectTimestamp(input: {
  execution_id: string;
  target: TimestampTarget;
  padding_seconds?: number;
}): Promise<InspectTimestampResponse> {
  return request<InspectTimestampResponse>("/api/inspect-timestamp", {
    method: "POST",
    body: JSON.stringify(input)
  });
}
