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

async function setReplayFrame(page: Page, frameIndex: number) {
  await page.getByTestId("replay-scrubber").evaluate((element, value) => {
    const input = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(input, String(value));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, frameIndex);
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
    cache_status: (record.cache as Record<string, unknown> | undefined)?.cache_status,
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
  await expect(page.getByTestId("host-status")).toBeVisible();
  await expect(page.getByTestId("path-chooser")).toBeVisible();
  await expect(page.getByTestId("interpret-button")).toBeEnabled();
  await expect(page.getByTestId("primary-action")).toBeDisabled();
}

// One product action drives the whole host-authority sequence (validate -> confirm -> execute).
// Captures the three host responses that fire from the single "Confirm and run" click.
async function confirmAndRun(page: Page, trace: ApiTraceEntry[], label: string) {
  const start = Date.now();
  const validatePromise = page.waitForResponse(responsePath("/api/submit-validate"));
  const confirmPromise = page.waitForResponse(responsePath("/api/confirm"));
  const executePromise = page.waitForResponse(responsePath("/api/execute"));
  await page.getByTestId("primary-action").click();

  const validateResponse = await validatePromise;
  const validation = (await validateResponse.json()) as Record<string, unknown>;
  trace.push({
    label: `${label}.validate`,
    path: "/api/submit-validate",
    status: validateResponse.status(),
    duration_ms: Date.now() - start,
    summary: summarizePayload(validation)
  });

  const confirmResponse = await confirmPromise;
  const confirmation = (await confirmResponse.json()) as Record<string, unknown>;
  trace.push({
    label: `${label}.confirm`,
    path: "/api/confirm",
    status: confirmResponse.status(),
    duration_ms: Date.now() - start,
    summary: summarizePayload(confirmation)
  });

  const executeResponse = await executePromise;
  const execution = (await executeResponse.json()) as Record<string, unknown>;
  trace.push({
    label: `${label}.execute`,
    path: "/api/execute",
    status: executeResponse.status(),
    duration_ms: Date.now() - start,
    summary: summarizePayload(execution)
  });
  return { validation, confirmation, execution, executeStatus: executeResponse.status() };
}

async function waitForInspectionResponse(page: Page, resultId: string) {
  return page.waitForResponse(async (response) => {
    if (new URL(response.url()).pathname !== "/api/inspect-result") return false;
    try {
      const payload = (await response.json()) as Record<string, unknown>;
      const inspection = payload.inspection as Record<string, unknown> | undefined;
      const result = inspection?.result as Record<string, unknown> | undefined;
      return result?.result_id === resultId;
    } catch {
      return false;
    }
  });
}

async function runRealQueryJourney(
  page: Page,
  label: "approved" | "experimental",
  input: { presetTestId: string },
  consoleErrors: string[]
) {
  ensureProofDirs();
  const trace: ApiTraceEntry[] = [];

  await boot(page, consoleErrors);
  await page.getByTestId(input.presetTestId).click();
  await expect(page.getByTestId("manual-recipe-description")).toBeVisible();
  await expect(page.getByTestId("query-input")).toHaveCount(0);

  const interpretation = await jsonAfterClick<Record<string, unknown>>(
    page,
    trace,
    `${label}.interpret`,
    "interpret-button",
    "/api/interpret"
  );
  const expectedProvenance = label === "approved" ? "REVIEWED_RECIPE" : "MANUAL_PRESET";
  const expectedSourceLabel = label === "approved" ? "Reviewed recipe" : "Manual preset";
  expect(interpretation.status).toBe("PLAN_INTERPRETED");
  expect(interpretation.provenance_source).toBe(expectedProvenance);
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("PLAN_INTERPRETED");
  await expect(page.getByTestId("interpretation-source")).toContainText(expectedSourceLabel);
  await expect(page.getByTestId("interpretation-source").locator("code")).toHaveCount(0);
  expect(await page.getByTestId("interpretation-source").getAttribute("data-raw-source")).toBe("manual_host_interpreter");
  expect(await page.getByTestId("interpretation-source").getAttribute("data-provenance-source")).toBe(expectedProvenance);
  await expect(page.getByTestId("primary-action")).toBeEnabled();
  await expect(page.getByTestId("primary-action")).toHaveText("Confirm and run");
  await capture(page, `${label}-interpretation`);

  const { validation, confirmation, execution } = await confirmAndRun(page, trace, label);
  const validationBody = validation.validation as Record<string, unknown>;
  expect(validationBody.ok).toBe(true);
  expect(String(validationBody.bound_plan_id)).toMatch(/^bound_[0-9a-f]{16}$/);
  const confirmationBody = confirmation.confirmation as Record<string, unknown>;
  expect(String(confirmationBody.execution_authorization_id)).toMatch(/^auth_[0-9a-f]{16}$/);
  const executionBody = execution.execution as Record<string, unknown>;
  expect(execution.ok).toBe(true);
  expect(executionBody.ok).toBe(true);
  const results = executionBody.results as Array<Record<string, unknown>>;
  expect(results.length).toBeGreaterThan(0);

  // Host artifacts are preserved in Developer details (collapsed by default; still in the DOM).
  await expect(page.getByTestId("validation-result")).toContainText(String(validationBody.bound_plan_id));
  await expect(page.getByTestId("host-confirmation")).toContainText(String(confirmationBody.execution_authorization_id));
  await capture(page, `${label}-confirmation`);

  const executeStart = Date.now();
  await expect(page.getByTestId("result-count")).toHaveText(String(results.length));
  const firstResultId = String(results[0].result_id);
  const inspectResponsePromise = waitForInspectionResponse(page, firstResultId);
  await page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`).click();
  const inspectResponse = await inspectResponsePromise;
  const inspection = (await inspectResponse.json()) as Record<string, unknown>;

  trace.push({
    label: `${label}.inspect_initial_result`,
    path: "/api/inspect-result",
    status: inspectResponse.status(),
    duration_ms: Date.now() - executeStart,
    summary: summarizePayload(inspection)
  });

  expect(Number(executionBody.total_result_count)).toBeGreaterThan(0);
  expect(Number(executionBody.returned_result_count)).toBe(results.length);
  await expect(page.getByTestId("execution-result")).toContainText(String(executionBody.execution_id));

  const inspectionBody = inspection.inspection as Record<string, unknown>;
  const replay = inspection.replay as Record<string, unknown>;
  const replayFrames = replay.frames as unknown[];
  const selectedResult = inspectionBody.result as Record<string, unknown>;
  const selectedEvidence = (selectedResult.requested_evidence ?? {}) as Record<string, unknown>;
  expect(replayFrames.length).toBeGreaterThan(0);
  expect(typeof selectedResult.match_time_ms).toBe("number");
  expect(replay.plan_path).toBeUndefined();
  expect(JSON.stringify(replay.canonical_sources)).not.toContain("/Users/");
  expect(JSON.stringify(replay.canonical_sources)).not.toContain(".parquet");
  for (const value of Object.values((replay.canonical_sources ?? {}) as Record<string, unknown>)) {
    expect(String(value)).toMatch(/^canonical_source:[0-9a-f]{16}$/);
  }
  expect(selectedResult.result_id).toBe(results[0].result_id);
  await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
    "data-replay-window-id",
    String(replay.replay_window_id)
  );
  await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
    "data-result-id",
    String(selectedResult.result_id)
  );
  await expect(page.locator(`[data-testid="result-item"][data-result-id="${selectedResult.result_id}"]`)).toHaveClass(/active/);
  await expect(page.getByTestId("evidence-alias").first()).toBeVisible();

  let overlayEvidenceCorrelation: Record<string, unknown> = {
    mode: "hidden",
    reason: "no exact overlay geometry requested"
  };
  if (label === "experimental" && typeof selectedEvidence.target_player_id === "string") {
    const targetPlayerId = selectedEvidence.target_player_id;
    const anchorFrameId = Number(replay.anchor_frame_id);
    const exactFrameIndex = (replayFrames as Array<Record<string, unknown>>).findIndex((frame) => {
      const entities = (frame.entities ?? []) as Array<Record<string, unknown>>;
      return frame.frame_id === anchorFrameId &&
        entities.some((entity) => entity.entity_type === "ball") &&
        entities.some((entity) => entity.entity_id === targetPlayerId);
    });
    expect(exactFrameIndex).toBeGreaterThanOrEqual(0);
    await setReplayFrame(page, exactFrameIndex);
    await expect(page.getByTestId("overlay-proof")).toContainText("Witness-frame corridor");
    overlayEvidenceCorrelation = {
      mode: "witness_frame_corridor",
      targetPlayerId,
      frameIndex: exactFrameIndex,
      evidenceAlias: "target_player_id"
    };
    await capture(page, `${label}-overlay-evidence-correlation`);
  } else {
    await expect(page.getByTestId("overlay-proof")).toContainText("No exact corridor witness available");
  }

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
  await setReplayFrame(page, Math.min(3, replayFrames.length - 1));

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
    await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
      "data-result-id",
      String(alternateResult.result_id)
    );
  }

  const rapidTargets = results.slice(2, Math.min(5, results.length));
  const finalRapidTarget = rapidTargets.at(-1);
  if (finalRapidTarget) {
    const rapidStart = Date.now();
    const finalInspectPromise = waitForInspectionResponse(page, String(finalRapidTarget.result_id));
    for (const result of rapidTargets) {
      await page.locator(`[data-testid="result-item"][data-result-id="${result.result_id}"]`).click();
    }
    const finalInspectResponse = await finalInspectPromise;
    selectedInspection = (await finalInspectResponse.json()) as Record<string, unknown>;
    trace.push({
      label: `${label}.inspect_rapid_final_result`,
      path: "/api/inspect-result",
      status: finalInspectResponse.status(),
      duration_ms: Date.now() - rapidStart,
      summary: summarizePayload(selectedInspection)
    });
    await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
      "data-result-id",
      String(finalRapidTarget.result_id)
    );
    await expect(page.locator(`[data-testid="result-item"][data-result-id="${finalRapidTarget.result_id}"]`)).toHaveClass(/active/);
    await expect(page.getByTestId("inspection-loading")).toHaveCount(0);
    await expect(page.getByTestId("evidence-alias").first().locator("code")).not.toHaveText("");
    await expect(page.getByTestId("predicate-trace").first()).toBeVisible();
    await page.waitForTimeout(250);
    await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
      "data-result-id",
      String(finalRapidTarget.result_id)
    );
  }

  const selectedReplay = selectedInspection.replay as Record<string, unknown>;
  const proof = {
    label,
    sourceCommit: git(["rev-parse", "HEAD"]),
    workbenchCommit: git(["rev-parse", "HEAD"]),
    hostRuntimeCommit: git(["rev-parse", "HEAD"]),
    hostServiceCommit: git(["rev-parse", "HEAD"]),
    cleanGitStatus: git(["status", "--short", "--untracked-files=all"]),
    trackedDirtyStatus: git(["status", "--short", "--untracked-files=no"]),
    tacticalKnowledgePackHash: hashFile(join(repoRoot, "generated/tactical-knowledge-pack.json")),
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
    overlayEvidenceCorrelation,
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
      presetTestId: "preset-approved_block_shift"
    },
    consoleErrors
  );

  // Known-timestamp probe now lives behind a collapsed Developer details drawer.
  await page.getByTestId("dev-tools-toggle").click();
  await expect(page.getByTestId("inspect-timestamp-button")).toBeVisible();
  const timestampResponsePromise = page.waitForResponse(responsePath("/api/inspect-timestamp"));
  await page.getByTestId("inspect-timestamp-button").click();
  const timestampResponse = await timestampResponsePromise;
  const timestampInspection = (await timestampResponse.json()) as Record<string, unknown>;
  const replay = timestampInspection.replay as Record<string, unknown>;
  expect(Array.isArray(replay.frames) ? replay.frames.length : 0).toBeGreaterThan(0);
  await expect(page.getByTestId("timestamp-inspection")).toContainText("NO_COMPATIBLE_ANCHOR");
  await expect(page.getByTestId("replay-window-summary")).toHaveAttribute(
    "data-replay-window-id",
    String(replay.replay_window_id)
  );
  await capture(page, "approved-known-timestamp");

  expect(consoleErrors).toEqual([]);
});

test("experimental corridor runs from query to replay with real result rail", async ({ page }) => {
  const consoleErrors: string[] = [];
  await runRealQueryJourney(
    page,
    "experimental",
    {
      presetTestId: "preset-experimental_corridor"
    },
    consoleErrors
  );
  expect(consoleErrors).toEqual([]);
});

test("model-unavailable UI and backend clarification/gap contracts remain explicit", async ({ page, request }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);

  const clarificationResponse = await request.post("/api/interpret", {
    data: {
      mode: "manual",
      query: "Find moments where a teammate provides support after the ball carrier receives."
    }
  });
  expect(clarificationResponse.ok()).toBe(true);
  const clarification = (await clarificationResponse.json()) as Record<string, unknown>;
  expect(clarification.status).toBe("CLARIFICATION_REQUIRED");
  expect(clarification.provenance_source).toBe("DETERMINISTIC_REPAIR");

  const gapResponse = await request.post("/api/interpret", {
    data: {
      mode: "manual",
      query: "Infer what the midfielder meant to do from his scanning and body angle.",
      preset_id: "experimental_corridor"
    }
  });
  expect(gapResponse.ok()).toBe(true);
  const gap = (await gapResponse.json()) as Record<string, unknown>;
  expect(gap.status).toBe("CAPABILITY_GAP");
  expect(gap.provenance_source).toBe("CAPABILITY_GAP");
  expect(gap.plan_document).toBeNull();

  await page.getByTestId("path-ask-hermes").click();
  await page.getByTestId("query-input").fill("Show possessions where the ball goes wide and the defending block shifts.");
  const modelUnavailable = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.model_unavailable",
    "interpret-button",
    "/api/interpret"
  );
  expect(modelUnavailable.status).toBe("MODEL_UNAVAILABLE");
  expect(modelUnavailable.provenance_source).toBe("MODEL_UNAVAILABLE");
  expect(modelUnavailable.manual_available).toBe(true);
  await expect(page.getByTestId("interpreted-plan-panel")).toContainText("MODEL_UNAVAILABLE");
  await expect(page.getByTestId("model-unavailable-state")).toBeVisible();
  await expect(page.getByTestId("switch-to-recipes")).toBeVisible();

  // Honest manual recovery: the typed model-unavailable state routes the user to recipes.
  await page.getByTestId("switch-to-recipes").click();
  await page.getByTestId("preset-approved_block_shift").click();
  const manualInterpretation = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.manual_after_model_unavailable",
    "interpret-button",
    "/api/interpret"
  );
  expect(manualInterpretation.status).toBe("PLAN_INTERPRETED");
  expect(manualInterpretation.provenance_source).toBe("REVIEWED_RECIPE");
  await expect(page.getByTestId("primary-action")).toBeEnabled();

  // Confirm and run drives the full host-authority chain; capture the bound plan id it produced.
  const { validation } = await confirmAndRun(page, [], "state");
  const boundPlanId = String((validation.validation as Record<string, unknown>).bound_plan_id);
  await expect(page.getByTestId("validation-result")).toContainText(boundPlanId);

  let intercepted = false;
  await page.route("**/api/interpret", async (route) => {
    if (intercepted) {
      await route.continue();
      return;
    }
    intercepted = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        status: "MODEL_UNAVAILABLE",
        provenance_source: "MODEL_UNAVAILABLE",
        query: "",
        source: "hermes_frontier_agent",
        message: "Synthetic model-unavailable state.",
        model_session_id: null,
        manual_available: true,
        repair_applied: false,
        fallback_reason: "test_model_unavailable"
      })
    });
  });
  const staleClear = await jsonAfterClick<Record<string, unknown>>(
    page,
    [],
    "state.non_plan_reinterpret_clears_validation",
    "interpret-button",
    "/api/interpret"
  );
  expect(staleClear.status).toBe("MODEL_UNAVAILABLE");
  await expect(page.getByTestId("validation-result")).not.toContainText(boundPlanId);
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.unroute("**/api/interpret");
  await capture(page, "state-model-unavailable-manual-recovery");

  expect(consoleErrors).toEqual([]);
});

test("host authority is enforced through public API routes", async ({ request }) => {
  const matchesResponse = await request.get("/api/matches");
  expect(matchesResponse.ok()).toBe(true);
  const matchesPayload = (await matchesResponse.json()) as Record<string, unknown>;
  const matchIds = ((matchesPayload.matches ?? []) as Array<Record<string, unknown>>).map((item) => item.match_id);
  expect(matchIds).toEqual(["J03WOY", "J03WPY", "J03WQQ", "J03WR9"]);
  expect(matchIds).not.toContain("J03WOH");
  expect(matchIds).not.toContain("J03WMX");
  for (const match of (matchesPayload.matches ?? []) as Array<Record<string, unknown>>) {
    expect(String(match.match_title ?? "")).not.toBe("");
    expect(String(match.home_team ?? "")).not.toBe("");
    expect(String(match.away_team ?? "")).not.toBe("");
    expect(match).toHaveProperty("match_day");
    expect(match).toHaveProperty("kickoff_time_utc");
  }

  const bootstrapResponse = await request.get("/api/bootstrap");
  expect(bootstrapResponse.ok()).toBe(true);
  const bootstrapPayload = (await bootstrapResponse.json()) as Record<string, unknown>;
  expect(String(JSON.stringify(bootstrapPayload))).not.toContain("output_root");
  expect(String(JSON.stringify(bootstrapPayload))).not.toContain("/Users/");

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
  const unconfirmedPayload = await unconfirmedExecution.json();
  expect(unconfirmedPayload).toMatchObject({ ok: false });
  expect(JSON.stringify(unconfirmedPayload)).not.toContain("auth_deadbeefdeadbeef");
  expect(JSON.stringify(unconfirmedPayload)).not.toContain("/Users/");

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
  const profileOverridePayload = await profileOverride.json();
  expect(profileOverridePayload).toMatchObject({ ok: false, error_code: "REQUEST_SCHEMA_INVALID" });
  expect(JSON.stringify(profileOverridePayload)).not.toContain("compatibility_profile");
  expect(JSON.stringify(profileOverridePayload)).not.toContain("/Users/");

  const localArtifact = await request.get("/artifacts/m1.2/workshop/handles/executions/exec_deadbeefdeadbeef.json");
  expect(localArtifact.status()).toBe(404);
  expect(await localArtifact.json()).toMatchObject({ ok: false, error_code: "STATIC_NOT_FOUND" });

  for (const path of ["/api/record_feedback", "/api/dispatch_tool", "/api/retrieve_replay_window"]) {
    const unavailable = await request.post(path, { data: {} });
    expect(unavailable.status()).toBe(404);
    expect(await unavailable.json()).toMatchObject({ ok: false, error_code: "NOT_FOUND" });
  }
});

test("scope transitions invalidate validation execution results and replay", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);
  await page.getByTestId("preset-approved_block_shift").click();
  await jsonAfterClick<Record<string, unknown>>(page, [], "scope.interpret", "interpret-button", "/api/interpret");

  const selector = page.getByTestId("match-scope-selector");
  const allButton = selector.getByRole("button").first();
  const firstMatch = selector.getByRole("button").nth(1);
  const secondMatch = selector.getByRole("button").nth(2);
  const thirdMatch = selector.getByRole("button").nth(3);
  const fourthMatch = selector.getByRole("button").nth(4);

  await expect(page.getByTestId("analysis-scope")).toContainText("All 4 available matches");
  await secondMatch.click();
  await thirdMatch.click();
  await fourthMatch.click();
  await expect(page.getByTestId("analysis-scope")).toContainText("1 selected match");

  // zero matches disables the single primary action
  await firstMatch.click();
  await expect(page.getByTestId("analysis-scope")).toContainText("0 selected matches");
  await expect(page.getByTestId("scope-warning")).toBeVisible();
  await expect(page.getByTestId("primary-action")).toBeDisabled();

  await secondMatch.click();
  await expect(page.getByTestId("analysis-scope")).toContainText("1 selected match");
  await expect(page.getByTestId("scope-warning")).toHaveCount(0);
  await expect(page.getByTestId("primary-action")).toBeEnabled();

  // run over the full scope via the single Confirm and run action
  await allButton.click();
  const { validation, execution } = await confirmAndRun(page, [], "scope");
  const boundPlanId = String((validation.validation as Record<string, unknown>).bound_plan_id);
  const results = (execution.execution as Record<string, unknown>).results as Array<Record<string, unknown>>;
  expect(results.length).toBeGreaterThan(0);
  await expect(page.getByTestId("validation-result")).toContainText(boundPlanId);
  const firstResultId = String(results[0].result_id);
  const inspectResponsePromise = waitForInspectionResponse(page, firstResultId);
  await page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`).click();
  await inspectResponsePromise;
  await expect(page.getByTestId("result-count")).toHaveText(String(results.length));
  await expect(page.getByTestId("replay-window-summary")).not.toContainText("No replay window selected");

  // changing scope after execution invalidates validation, results, and replay
  await firstMatch.click();
  await expect(page.getByTestId("validation-result")).not.toContainText(boundPlanId);
  await expect(page.getByTestId("result-count")).toHaveText("0");
  await expect(page.getByTestId("replay-window-summary")).toContainText("No replay window selected");
  // the plan is still interpreted, so the user can immediately re-run over the new scope
  await expect(page.getByTestId("primary-action")).toBeEnabled();

  expect(consoleErrors).toEqual([]);
});

test("beta1a interpretation invalidation: recipe switch, path switch, and query edit clear downstream state", async ({
  page,
  request
}) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);

  // T2 — selecting a different recipe clears a ready interpretation
  await page.getByTestId("preset-approved_block_shift").click();
  const approved = await jsonAfterClick<Record<string, unknown>>(page, [], "inval.approved", "interpret-button", "/api/interpret");
  expect(approved.provenance_source).toBe("REVIEWED_RECIPE");
  await expect(page.getByTestId("primary-action")).toBeEnabled();
  await page.getByTestId("preset-experimental_corridor").click();
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await expect(page.getByTestId("interpreted-plan-panel")).not.toContainText("PLAN_INTERPRETED");

  // T5 — switching Ask Hermes <-> Browse recipes clears a ready interpretation
  const experimental = await jsonAfterClick<Record<string, unknown>>(page, [], "inval.experimental", "interpret-button", "/api/interpret");
  expect(experimental.provenance_source).toBe("MANUAL_PRESET");
  await expect(page.getByTestId("primary-action")).toBeEnabled();
  await page.getByTestId("path-ask-hermes").click();
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.getByTestId("path-browse-recipes").click();
  await expect(page.getByTestId("primary-action")).toBeDisabled();

  // T1 — Ask Hermes: editing the query after validation marks the plan stale.
  // A one-shot synthetic Hermes interpretation injects the REAL approved plan document so the
  // model-path query-edit invalidation can be exercised deterministically (live Hermes is offline).
  const planResponse = await request.get("/api/plan?recipe_id=ball_side_block_shift_v1");
  const planPayload = (await planResponse.json()) as Record<string, unknown>;
  let injected = false;
  await page.route("**/api/interpret", async (route) => {
    if (injected) {
      await route.continue();
      return;
    }
    injected = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        status: "PLAN_INTERPRETED",
        provenance_source: "HERMES_RECIPE_SELECTION",
        query: "synthetic hermes recipe selection",
        source: "hermes_frontier_agent",
        recipe: planPayload.recipe,
        recipe_id: "ball_side_block_shift_v1",
        plan_document: planPayload.plan_document,
        plan_hash: planPayload.plan_hash,
        manual_available: true,
        repair_applied: false
      })
    });
  });
  await page.getByTestId("path-ask-hermes").click();
  await page.getByTestId("query-input").fill("Find ball-side block shifts.");
  const hermesPlan = await jsonAfterClick<Record<string, unknown>>(page, [], "inval.hermes_plan", "interpret-button", "/api/interpret");
  expect(hermesPlan.status).toBe("PLAN_INTERPRETED");
  expect(hermesPlan.provenance_source).toBe("HERMES_RECIPE_SELECTION");
  await page.unroute("**/api/interpret");
  await expect(page.getByTestId("primary-action")).toBeEnabled();

  const { validation } = await confirmAndRun(page, [], "inval");
  const boundPlanId = String((validation.validation as Record<string, unknown>).bound_plan_id);
  await expect(page.getByTestId("validation-result")).toContainText(boundPlanId);

  await page.getByTestId("query-input").fill("Find ball-side block shifts, now edited after running.");
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await expect(page.getByTestId("validation-result")).not.toContainText(boundPlanId);
  await expect(page.getByTestId("result-count")).toHaveText("0");
  await expect(page.getByTestId("replay-window-summary")).toContainText("No replay window selected");

  expect(consoleErrors).toEqual([]);
});

test("beta1a product surface hides developer internals by default", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);

  // raw host/model internals are not product copy, but are preserved as data attributes for tooling
  await expect(page.getByText("browser to host API")).toHaveCount(0);
  const hostStatus = page.getByTestId("host-status");
  await expect(hostStatus).not.toContainText("HERMES_FRONTIER_READY");
  expect(await hostStatus.getAttribute("data-model-status")).not.toBeNull();

  // the known-timestamp probe is hidden until the developer drawer is opened
  await expect(page.getByTestId("inspect-timestamp-button")).toBeHidden();
  await page.getByTestId("dev-tools-toggle").click();
  await expect(page.getByTestId("inspect-timestamp-button")).toBeVisible();

  // result cards lead with a tactical headline and never print the raw result id
  await page.getByTestId("preset-approved_block_shift").click();
  await jsonAfterClick<Record<string, unknown>>(page, [], "hidden.interpret", "interpret-button", "/api/interpret");
  const { execution } = await confirmAndRun(page, [], "hidden");
  const results = (execution.execution as Record<string, unknown>).results as Array<Record<string, unknown>>;
  expect(results.length).toBeGreaterThan(0);
  const firstResultId = String(results[0].result_id);
  const card = page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`);
  await expect(card).toBeVisible();
  await expect(card).not.toContainText(firstResultId);
  expect(await card.getAttribute("data-classification")).not.toBeNull();

  expect(consoleErrors).toEqual([]);
});

test("unverified Hermes experimental draft is inspectable but not runnable", async ({
  page,
  request
}) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);

  const planResponse = await request.get("/api/plan?recipe_id=possession_corridor_availability_v1");
  const planPayload = (await planResponse.json()) as Record<string, unknown>;
  await page.route("**/api/interpret", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        status: "PLAN_INTERPRETED",
        provenance_source: "HERMES_EXPERIMENTAL_UNVERIFIED",
        query: "synthetic unverified experimental draft",
        source: "hermes_frontier_agent",
        recipe: planPayload.recipe,
        plan_document: planPayload.plan_document,
        plan_hash: planPayload.plan_hash,
        manual_available: true,
        repair_applied: false
      })
    });
  });
  await page.getByTestId("path-ask-hermes").click();
  await page.getByTestId("query-input").fill("Compose a brand new tactical pattern.");
  const draft = await jsonAfterClick<Record<string, unknown>>(page, [], "unverified.interpret", "interpret-button", "/api/interpret");
  expect(draft.provenance_source).toBe("HERMES_EXPERIMENTAL_UNVERIFIED");

  await expect(page.getByTestId("experimental-unverified-state")).toBeVisible();
  await expect(page.getByTestId("interpretation-source")).toContainText("unverified");
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.unroute("**/api/interpret");

  expect(consoleErrors).toEqual([]);
});

test("beta1b corridor overlay shows only within its valid interval, with a legend", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);
  await page.getByTestId("preset-experimental_corridor").click();
  await jsonAfterClick<Record<string, unknown>>(page, [], "ov.interpret", "interpret-button", "/api/interpret");
  const { execution } = await confirmAndRun(page, [], "ov");
  const results = (execution.execution as Record<string, unknown>).results as Array<Record<string, unknown>>;
  const firstResultId = String(results[0].result_id);
  const inspectPromise = waitForInspectionResponse(page, firstResultId);
  await page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`).click();
  const inspection = (await (await inspectPromise).json()) as Record<string, unknown>;
  const replay = inspection.replay as Record<string, unknown>;
  const frames = replay.frames as Array<Record<string, unknown>>;
  const evidence = ((inspection.inspection as Record<string, unknown>).result as Record<string, unknown>).requested_evidence as
    | Record<string, unknown>
    | undefined;

  // The legend is always present with the non-optimality disclaimer.
  await expect(page.getByTestId("overlay-legend")).toContainText("optimal pass");

  if (evidence && typeof evidence.target_player_id === "string") {
    const anchorFrameId = Number(replay.anchor_frame_id);
    const witnessIdx = frames.findIndex((frame) => frame.frame_id === anchorFrameId);
    expect(witnessIdx).toBeGreaterThanOrEqual(0);

    await setReplayFrame(page, witnessIdx);
    await expect(page.getByTestId("overlay-proof")).toContainText("Witness-frame corridor");
    await expect(page.getByTestId("overlay-proof")).toHaveAttribute("data-overlay-kind", "witness");
    await expect(page.getByTestId("overlay-legend")).toContainText("witness frame");

    const otherIdx = frames.findIndex((_frame, index) => index !== witnessIdx);
    await setReplayFrame(page, otherIdx);
    await expect(page.getByTestId("overlay-proof")).toContainText("hidden outside the witness frame");
  }

  expect(consoleErrors).toEqual([]);
});

test("beta1b result rail groups by match and shows readable why-matched summaries", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);
  await page.getByTestId("preset-approved_block_shift").click();
  await jsonAfterClick<Record<string, unknown>>(page, [], "wm.interpret", "interpret-button", "/api/interpret");
  const { execution } = await confirmAndRun(page, [], "wm");
  const results = (execution.execution as Record<string, unknown>).results as Array<Record<string, unknown>>;
  const firstResultId = String(results[0].result_id);

  // grouping + principal measurement are visible without inspecting
  await expect(page.getByTestId("result-group-header").first()).toBeVisible();
  await expect(page.getByTestId("result-measurement").first()).toBeVisible();

  // inspect -> readable why-matched summary backed by the trace; raw JSON only in Developer details
  const inspectPromise = waitForInspectionResponse(page, firstResultId);
  await page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`).click();
  await inspectPromise;
  await expect(page.getByTestId("predicate-why").first()).toBeVisible();
  const why = await page.getByTestId("predicate-why").first().textContent();
  expect(why && /Matched|Did not match|Could not be determined/.test(why)).toBeTruthy();
  await expect(page.getByText("Trace details")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("beta1a.1 booting state shows a loading view with no false empty/scope warning", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (errorEvent) => consoleErrors.push(errorEvent.message));

  // Delay the match library so the booting state is observable.
  await page.route("**/api/matches", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.continue();
  });
  await page.goto("/");

  await expect(page.getByTestId("booting-state")).toBeVisible();
  await expect(page.getByTestId("booting-state")).toContainText("Loading workbench");
  // No misleading empty/scope state before the library resolves.
  await expect(page.getByTestId("scope-warning")).toHaveCount(0);
  await expect(page.getByTestId("analysis-scope")).toHaveCount(0);
  await expect(page.getByText("0 selected matches")).toHaveCount(0);

  // After load: full UI, all matches selected, still no scope warning, booting gone.
  await expect(page.getByTestId("path-chooser")).toBeVisible();
  await expect(page.getByTestId("booting-state")).toHaveCount(0);
  await expect(page.getByTestId("analysis-scope")).toContainText("All 4 available matches");
  await expect(page.getByTestId("scope-warning")).toHaveCount(0);
  await expect(page.getByTestId("primary-action")).toBeDisabled();
  await page.unroute("**/api/matches");

  expect(consoleErrors).toEqual([]);
});

test("beta1a.1 cold-run state shows step, elapsed, and non-cancelable honesty while executing", async ({ page }) => {
  const consoleErrors: string[] = [];
  await boot(page, consoleErrors);
  await page.getByTestId("preset-approved_block_shift").click();
  await jsonAfterClick<Record<string, unknown>>(page, [], "cold.interpret", "interpret-button", "/api/interpret");

  // Hold the execute response so the executing phase is observable.
  await page.route("**/api/execute", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  const executePromise = page.waitForResponse(responsePath("/api/execute"));
  await page.getByTestId("primary-action").click();

  const coldRun = page.getByTestId("cold-run-state");
  await expect(coldRun).toBeVisible();
  await expect(coldRun).toHaveAttribute("data-run-step", "executing");
  await expect(coldRun).toContainText("Executing over selected matches");
  await expect(page.getByTestId("cold-run-elapsed")).toContainText("Elapsed");
  await expect(coldRun).toContainText("First run may take longer");
  await expect(coldRun).toContainText("cannot be canceled once started");
  await expect(page.getByTestId("primary-action")).toBeDisabled();

  await executePromise;
  await expect(page.getByTestId("cold-run-state")).toHaveCount(0);
  await expect(page.getByTestId("result-count")).not.toHaveText("0");
  await page.unroute("**/api/execute");

  expect(consoleErrors).toEqual([]);
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
  const initialCacheStatus = await api.post("/api/execution-cache-status", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: authorizationId,
      result_limit: 1
    }
  });
  expect(initialCacheStatus.ok()).toBe(true);
  expect(await initialCacheStatus.json()).toMatchObject({ ok: true });
  const executionResponse = await api.post("/api/execute", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: authorizationId,
      result_limit: 1
    }
  });
  expect(executionResponse.ok()).toBe(true);
  const executionPayload = (await executionResponse.json()) as Record<string, unknown>;
  expect(executionPayload).toMatchObject({ ok: true });
  expect((executionPayload.cache as Record<string, unknown>).cache_status).toMatch(/^(HIT|MISS)$/);
  const execution = executionPayload.execution as Record<string, unknown>;
  const first = (execution.results as Array<Record<string, unknown>>)[0];
  const postExecutionCacheStatus = await api.post("/api/execution-cache-status", {
    data: {
      bound_plan_id: boundPlanId,
      execution_authorization_id: authorizationId,
      result_limit: 1
    }
  });
  expect(postExecutionCacheStatus.ok()).toBe(true);
  expect(await postExecutionCacheStatus.json()).toMatchObject({ ok: true, cache_status: "HIT" });
  return {
    execution_id: execution.execution_id,
    result_id: first.result_id
  };
}
