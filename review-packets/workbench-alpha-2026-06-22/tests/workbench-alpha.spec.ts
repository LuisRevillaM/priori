import { expect, request as requestFactory, test, type APIRequestContext, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";

type ApiTraceEntry = {
  label: string;
  path: string;
  status: number;
  duration_ms: number;
  summary: Record<string, unknown>;
};

const appRoot = resolve(process.cwd());
const repoRoot = resolve(appRoot, "../..");
const proofRoot = resolve(repoRoot, "artifacts/workbench-alpha/review-proof");

function ensureProofDirs() {
  mkdirSync(join(proofRoot, "screenshots"), { recursive: true });
  mkdirSync(join(proofRoot, "api-traces"), { recursive: true });
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

function hashFile(path: string): string {
  return sha256(readFileSync(path));
}

function hashDirectory(root: string): Record<string, string> {
  if (!existsSync(root)) return {};
  const hashes: Record<string, string> = {};
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      const stat = statSync(path);
      if (stat.isDirectory()) {
        walk(path);
      } else {
        hashes[relative(root, path)] = hashFile(path);
      }
    }
  };
  walk(root);
  return hashes;
}

function git(args: string[]): string {
  const result = spawnSync("git", args, { cwd: repoRoot, encoding: "utf8" });
  if (result.status !== 0) return "";
  return result.stdout.trim();
}

function responsePath(path: string) {
  return (response: { url(): string }) => new URL(response.url()).pathname === path;
}

async function jsonAfterClick<T>(
  page: Page,
  trace: ApiTraceEntry[],
  label: string,
  testId: string,
  path: string
): Promise<T> {
  const start = Date.now();
  const responsePromise = page.waitForResponse(responsePath(path));
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  const payload = (await response.json()) as T;
  trace.push({
    label,
    path,
    status: response.status(),
    duration_ms: Date.now() - start,
    summary: summarizePayload(payload)
  });
  return payload;
}

async function capture(page: Page, name: string) {
  await page.screenshot({
    path: join(proofRoot, "screenshots", `${name}.png`),
    fullPage: true
  });
}

function summarizePayload(payload: unknown): Record<string, unknown> {
  const record = payload as Record<string, unknown>;
  const execution = record.execution as Record<string, unknown> | undefined;
  const inspection = record.inspection as Record<string, unknown> | undefined;
  const replay = record.replay as Record<string, unknown> | undefined;
  const validation = record.validation as Record<string, unknown> | undefined;
  const confirmation = record.confirmation as Record<string, unknown> | undefined;
  return {
    ok: record.ok,
    status: record.status,
    plan_hash: record.plan_hash,
    draft_plan_id: validation?.draft_plan_id,
    bound_plan_id: validation?.bound_plan_id ?? confirmation?.bound_plan_id ?? execution?.bound_plan_id,
    authorization_id: confirmation?.execution_authorization_id,
    execution_id: execution?.execution_id ?? inspection?.execution_id,
    total_result_count: execution?.total_result_count,
    returned_result_count: execution?.returned_result_count,
    result_ids: Array.isArray(execution?.results)
      ? (execution.results as Array<Record<string, unknown>>).map((item) => item.result_id)
      : undefined,
    selected_result_id: (inspection?.result as Record<string, unknown> | undefined)?.result_id,
    replay_window_id: replay?.replay_window_id,
    replay_source_id: replay?.source_id,
    replay_frame_count: Array.isArray(replay?.frames) ? replay.frames.length : undefined,
    trace_statuses: Array.isArray(inspection?.predicate_traces)
      ? (inspection.predicate_traces as Array<Record<string, unknown>>).map((item) => item.status)
      : undefined
  };
}

async function boot(page: Page, consoleErrors: string[]) {
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Host tactical query workbench" })).toBeVisible();
  await expect(page.getByText("browser to host API")).toBeVisible();
  await expect(page.getByTestId("interpret-button")).toBeEnabled();
  await expect(page.getByTestId("confirm-button")).toBeDisabled();
  await expect(page.getByTestId("execute-button")).toBeDisabled();
}

async function runRealQueryJourney(
  page: Page,
  label: "approved" | "experimental",
  input: { query: string; presetTestId: string },
  consoleErrors: string[]
) {
  ensureProofDirs();
  const trace: ApiTraceEntry[] = [];

  await boot(page, consoleErrors);
  await page.getByTestId(input.presetTestId).click();
  await page.getByTestId("query-input").fill(input.query);

  const interpretation = await jsonAfterClick<Record<string, unknown>>(
    page,
    trace,
    `${label}.interpret`,
    "interpret-button",
    "/api/interpret"
  );
  expect(interpretation.status).toBe("PLAN_INTERPRETED");
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("PLAN_INTERPRETED");
  await expect(page.getByTestId("confirm-button")).toBeDisabled();
  await expect(page.getByTestId("execute-button")).toBeDisabled();
  await capture(page, `${label}-interpretation`);

  const validation = await jsonAfterClick<Record<string, unknown>>(
    page,
    trace,
    `${label}.validate`,
    "validate-button",
    "/api/submit-validate"
  );
  const validationBody = validation.validation as Record<string, unknown>;
  expect(validationBody.ok).toBe(true);
  expect(String(validationBody.bound_plan_id)).toMatch(/^bound_[0-9a-f]{16}$/);
  await expect(page.getByTestId("validation-result")).toContainText(String(validationBody.bound_plan_id));
  await expect(page.getByTestId("confirm-button")).toBeEnabled();
  await expect(page.getByTestId("execute-button")).toBeDisabled();

  const confirmation = await jsonAfterClick<Record<string, unknown>>(
    page,
    trace,
    `${label}.confirm`,
    "confirm-button",
    "/api/confirm"
  );
  const confirmationBody = confirmation.confirmation as Record<string, unknown>;
  expect(String(confirmationBody.execution_authorization_id)).toMatch(/^auth_[0-9a-f]{16}$/);
  await expect(page.getByTestId("host-confirmation")).toContainText(String(confirmationBody.execution_authorization_id));
  await expect(page.getByTestId("execute-button")).toBeEnabled();
  await capture(page, `${label}-confirmation`);

  const executeStart = Date.now();
  const executeResponsePromise = page.waitForResponse(responsePath("/api/execute"));
  const inspectResponsePromise = page.waitForResponse(responsePath("/api/inspect-result"));
  await page.getByTestId("execute-button").click();
  const executeResponse = await executeResponsePromise;
  const execution = (await executeResponse.json()) as Record<string, unknown>;
  const inspectResponse = await inspectResponsePromise;
  const inspection = (await inspectResponse.json()) as Record<string, unknown>;

  trace.push({
    label: `${label}.execute`,
    path: "/api/execute",
    status: executeResponse.status(),
    duration_ms: Date.now() - executeStart,
    summary: summarizePayload(execution)
  });
  trace.push({
    label: `${label}.inspect_initial_result`,
    path: "/api/inspect-result",
    status: inspectResponse.status(),
    duration_ms: Date.now() - executeStart,
    summary: summarizePayload(inspection)
  });

  const executionBody = execution.execution as Record<string, unknown>;
  const results = executionBody.results as Array<Record<string, unknown>>;
  expect(executionBody.ok).toBe(true);
  expect(Number(executionBody.total_result_count)).toBeGreaterThan(0);
  expect(Number(executionBody.returned_result_count)).toBe(results.length);
  await expect(page.getByTestId("result-count")).toHaveText(String(results.length));
  await expect(page.getByTestId("execution-result")).toContainText(String(executionBody.execution_id));

  const inspectionBody = inspection.inspection as Record<string, unknown>;
  const replay = inspection.replay as Record<string, unknown>;
  const replayFrames = replay.frames as unknown[];
  const selectedResult = inspectionBody.result as Record<string, unknown>;
  expect(replayFrames.length).toBeGreaterThan(0);
  expect(selectedResult.result_id).toBe(results[0].result_id);
  await expect(page.getByTestId("replay-window-summary")).toContainText(String(replay.replay_window_id));
  await expect(page.getByTestId("replay-window-summary")).toContainText(String(selectedResult.result_id));
  await expect(page.locator(`[data-testid="result-item"][data-result-id="${selectedResult.result_id}"]`)).toHaveClass(/active/);
  await expect(page.getByTestId("evidence-alias").first()).toBeVisible();

  const traces = inspectionBody.predicate_traces as Array<Record<string, unknown>>;
  expect(traces.length).toBeGreaterThan(0);
  for (const status of new Set(traces.map((item) => String(item.status ?? "UNKNOWN")))) {
    await expect(page.getByTestId("predicate-trace").filter({ hasText: status }).first()).toBeVisible();
  }

  await capture(page, `${label}-result-replay`);

  await page.getByTestId("play-pause-button").click();
  await expect(page.getByTestId("play-pause-button")).toHaveText("Pause");
  await page.getByTestId("play-pause-button").click();
  await expect(page.getByTestId("play-pause-button")).toHaveText("Play");
  await page.getByTestId("replay-scrubber").evaluate((element, value) => {
    const input = element as HTMLInputElement;
    input.value = String(value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, Math.min(3, replayFrames.length - 1));

  const alternateResult = results[1];
  let selectedInspection = inspection;
  if (alternateResult) {
    const selectStart = Date.now();
    const selectedInspectPromise = page.waitForResponse(responsePath("/api/inspect-result"));
    await page.locator(`[data-testid="result-item"][data-result-id="${alternateResult.result_id}"]`).click();
    const selectedInspectResponse = await selectedInspectPromise;
    selectedInspection = (await selectedInspectResponse.json()) as Record<string, unknown>;
    trace.push({
      label: `${label}.inspect_selected_result`,
      path: "/api/inspect-result",
      status: selectedInspectResponse.status(),
      duration_ms: Date.now() - selectStart,
      summary: summarizePayload(selectedInspection)
    });
    await expect(page.getByTestId("replay-window-summary")).toContainText(String(alternateResult.result_id));
  }

  const selectedReplay = selectedInspection.replay as Record<string, unknown>;
  const proof = {
    label,
    sourceCommit: git(["rev-parse", "HEAD"]),
    hostServiceCommit: git(["rev-parse", "HEAD"]),
    trackedDirtyStatus: git(["status", "--short", "--untracked-files=no"]),
    appSourceHashes: hashDirectory(join(appRoot, "src")),
    browserBuildHashes: hashDirectory(join(appRoot, "dist")),
    apiTracePath: relative(repoRoot, join(proofRoot, "api-traces", `${label}.json`)),
    executionId: executionBody.execution_id,
    resultIds: results.map((item) => item.result_id),
    selectedResultId: (selectedInspection.inspection as Record<string, unknown>).result
      ? ((selectedInspection.inspection as Record<string, unknown>).result as Record<string, unknown>).result_id
      : undefined,
    replayWindowId: selectedReplay.replay_window_id,
    replayFrameCount: Array.isArray(selectedReplay.frames) ? selectedReplay.frames.length : 0,
    replayPayloadHash: sha256(stableStringify(selectedReplay)),
    replayPayloadBytes: Buffer.byteLength(stableStringify(selectedReplay), "utf8"),
    performanceBaseline: {
      pageLoadReady: "asserted by visible heading and enabled interpret button",
      replayFrameCadenceHz: selectedReplay.frame_rate_hz,
      apiDurations: trace.map((item) => ({
        label: item.label,
        path: item.path,
        duration_ms: item.duration_ms
      }))
    }
  };

  writeFileSync(join(proofRoot, "api-traces", `${label}.json`), JSON.stringify(trace, null, 2) + "\n");
  writeFileSync(join(proofRoot, `${label}-proof.json`), JSON.stringify(proof, null, 2) + "\n");

  return { execution, inspection: selectedInspection, trace };
}

test("approved recipe runs from query to replay with evidence and predicate trace", async ({ page }) => {
  const consoleErrors: string[] = [];
  await runRealQueryJourney(
    page,
    "approved",
    {
      presetTestId: "preset-approved_block_shift",
      query: "Show possessions where the ball goes wide and the defending block moves toward that side."
    },
    consoleErrors
  );

  const timestampResponsePromise = page.waitForResponse(responsePath("/api/inspect-timestamp"));
  await page.getByTestId("inspect-timestamp-button").click();
  const timestampResponse = await timestampResponsePromise;
  const timestampInspection = (await timestampResponse.json()) as Record<string, unknown>;
  const replay = timestampInspection.replay as Record<string, unknown>;
  expect(Array.isArray(replay.frames) ? replay.frames.length : 0).toBeGreaterThan(0);
  await expect(page.getByTestId("timestamp-inspection")).toContainText("NO_COMPATIBLE_ANCHOR");
  await expect(page.getByTestId("replay-window-summary")).toContainText(String(replay.replay_window_id));
  await capture(page, "approved-known-timestamp");

  expect(consoleErrors).toEqual([]);
});

test("experimental corridor runs from query to replay with real result rail", async ({ page }) => {
  const consoleErrors: string[] = [];
  await runRealQueryJourney(
    page,
    "experimental",
    {
      presetTestId: "preset-experimental_corridor",
      query: "Find possessions where a progressive corridor is available after the ball-side shift."
    },
    consoleErrors
  );
  expect(consoleErrors).toEqual([]);
});

test("clarification, capability-gap, and model-unavailable states remain explicit", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);

  await page.getByTestId("query-input").fill("Find moments where a teammate provides support after the ball carrier receives.");
  const clarification = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.clarification",
    "interpret-button",
    "/api/interpret"
  );
  expect(clarification.status).toBe("CLARIFICATION_REQUIRED");
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("CLARIFICATION_REQUIRED");
  await capture(page, "state-clarification");

  await page.getByTestId("query-input").fill("Show pass probability changes under pressure against the defensive line.");
  const gap = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.capability_gap",
    "interpret-button",
    "/api/interpret"
  );
  expect(gap.status).toBe("CAPABILITY_GAP");
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("CAPABILITY_GAP");
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("pressure_change");
  await capture(page, "state-capability-gap");

  await page.getByRole("button", { name: "Model" }).click();
  const modelUnavailable = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.model_unavailable",
    "interpret-button",
    "/api/interpret"
  );
  expect(modelUnavailable.status).toBe("MODEL_UNAVAILABLE");
  expect(modelUnavailable.manual_available).toBe(true);
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("MODEL_UNAVAILABLE");

  await page.getByRole("button", { name: "Manual" }).click();
  await page.getByTestId("query-input").fill("Show possessions where the ball goes wide and the defending block shifts.");
  const manualInterpretation = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.manual_after_model_unavailable",
    "interpret-button",
    "/api/interpret"
  );
  expect(manualInterpretation.status).toBe("PLAN_INTERPRETED");
  await expect(page.getByTestId("validate-button")).toBeEnabled();
  await capture(page, "state-model-unavailable-manual-recovery");

  expect(consoleErrors).toEqual([]);
});

test("host authority is enforced through public API routes", async ({ request }) => {
  const planResponse = await request.get("/api/plan?recipe_id=ball_side_block_shift_v1");
  expect(planResponse.ok()).toBe(true);
  const planPayload = (await planResponse.json()) as Record<string, unknown>;

  const validationResponse = await request.post("/api/submit-validate", {
    data: { plan_document: planPayload.plan_document }
  });
  expect(validationResponse.ok()).toBe(true);
  const validationPayload = (await validationResponse.json()) as Record<string, unknown>;
  const boundPlanId = String((validationPayload.validation as Record<string, unknown>).bound_plan_id);

  const unconfirmedExecution = await request.post("/api/execute", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: "auth_deadbeefdeadbeef",
      result_limit: 1
    }
  });
  expect(unconfirmedExecution.status()).toBe(403);
  expect(await unconfirmedExecution.json()).toMatchObject({ ok: false });

  const forgedConfirmation = await request.post("/api/confirm", {
    data: {
      bound_plan_id: boundPlanId,
      reviewer: "workbench_authority_test",
      execution_authorization_id: "auth_deadbeefdeadbeef"
    }
  });
  expect(forgedConfirmation.ok()).toBe(true);
  const confirmationPayload = (await forgedConfirmation.json()) as Record<string, unknown>;
  const authorizationId = String((confirmationPayload.confirmation as Record<string, unknown>).execution_authorization_id);
  expect(authorizationId).toMatch(/^auth_[0-9a-f]{16}$/);
  expect(authorizationId).not.toBe("auth_deadbeefdeadbeef");

  const profileOverride = await request.post("/api/execute", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: authorizationId,
      result_limit: 1,
      compatibility_profile: "legacy_m1_parity"
    }
  });
  expect(profileOverride.status()).toBe(400);
  expect(await profileOverride.json()).toMatchObject({ ok: false, error_code: "REQUEST_SCHEMA_INVALID" });

  const localArtifact = await request.get("/artifacts/m1.2/workshop/handles/executions/exec_deadbeefdeadbeef.json");
  expect(localArtifact.status()).toBe(404);
  expect(await localArtifact.json()).toMatchObject({ ok: false, error_code: "STATIC_NOT_FOUND" });

  for (const path of ["/api/record_feedback", "/api/dispatch_tool", "/api/retrieve_replay_window"]) {
    const unavailable = await request.post(path, { data: {} });
    expect(unavailable.status()).toBe(404);
    expect(await unavailable.json()).toMatchObject({ ok: false, error_code: "NOT_FOUND" });
  }
});

test("backend execution artifacts are the source of result inspection", async ({ request }) => {
  const api = await requestFactory.newContext({ baseURL: "http://127.0.0.1:8765" });
  try {
    const execution = await executeOneResult(api);
    const resultId = String(execution.result_id);
    const executionId = String(execution.execution_id);
    const firstInspection = await api.post("/api/inspect-result", {
      data: { execution_id: executionId, result_id: resultId, padding_seconds: 1 }
    });
    expect(firstInspection.ok()).toBe(true);

    const executionPath = join(
      repoRoot,
      "artifacts/workbench-alpha/e2e-workshop/handles/executions",
      `${executionId}.json`
    );
    expect(existsSync(executionPath)).toBe(true);
    const backup = readFileSync(executionPath, "utf8");
    writeFileSync(executionPath, "");
    const brokenInspection = await api.post("/api/inspect-result", {
      data: { execution_id: executionId, result_id: resultId, padding_seconds: 1 }
    });
    expect(brokenInspection.ok()).toBe(false);
    writeFileSync(executionPath, backup);
  } finally {
    await api.dispose();
  }
});

async function executeOneResult(api: APIRequestContext): Promise<Record<string, unknown>> {
  const planResponse = await api.get("/api/plan?recipe_id=ball_side_block_shift_v1");
  const planPayload = (await planResponse.json()) as Record<string, unknown>;
  const validationResponse = await api.post("/api/submit-validate", {
    data: { plan_document: planPayload.plan_document }
  });
  const validationPayload = (await validationResponse.json()) as Record<string, unknown>;
  const boundPlanId = String((validationPayload.validation as Record<string, unknown>).bound_plan_id);
  const confirmationResponse = await api.post("/api/confirm", {
    data: { bound_plan_id: boundPlanId, reviewer: "workbench_fixture_source_test" }
  });
  const confirmationPayload = (await confirmationResponse.json()) as Record<string, unknown>;
  const authorizationId = String((confirmationPayload.confirmation as Record<string, unknown>).execution_authorization_id);
  const executionResponse = await api.post("/api/execute", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: authorizationId,
      result_limit: 1
    }
  });
  const executionPayload = (await executionResponse.json()) as Record<string, unknown>;
  const execution = executionPayload.execution as Record<string, unknown>;
  const first = (execution.results as Array<Record<string, unknown>>)[0];
  return {
    execution_id: execution.execution_id,
    result_id: first.result_id
  };
}
