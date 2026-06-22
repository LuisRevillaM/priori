import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

// Captures the Beta 1A required product screenshots into a dedicated proof folder.
const proofRoot = resolve(process.cwd(), "../../artifacts/workbench-alpha/beta1a-proof/screenshots");

function shot(page: Page, name: string) {
  mkdirSync(proofRoot, { recursive: true });
  return page.screenshot({ path: join(proofRoot, `${name}.png`), fullPage: true });
}

function responsePath(path: string) {
  return (response: { url(): string }) => new URL(response.url()).pathname === path;
}

async function expandAllDetails(page: Page) {
  await page.evaluate(() => {
    document.querySelectorAll("details").forEach((node) => node.setAttribute("open", "true"));
  });
}

async function collapseAllDetails(page: Page) {
  await page.evaluate(() => {
    document.querySelectorAll("details").forEach((node) => node.removeAttribute("open"));
  });
}

test("beta1a product screenshots", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Host tactical query workbench" })).toBeVisible();
  await expect(page.getByTestId("path-chooser")).toBeVisible();
  // wait for bootstrap + match library to resolve so the hero shot is not a loading frame
  await expect(page.getByTestId("analysis-scope")).toContainText("All 4 available matches");
  await expect(page.getByTestId("host-status")).not.toContainText("Loading");

  // 1) Initial screen: two distinct paths (Ask Hermes / Browse recipes)
  await shot(page, "01-initial-split");

  // 3) Browse recipes selection + interpretation (Reviewed recipe provenance)
  await page.getByTestId("preset-approved_block_shift").click();
  const interpretPromise = page.waitForResponse(responsePath("/api/interpret"));
  await page.getByTestId("interpret-button").click();
  await interpretPromise;
  await expect(page.getByTestId("interpretation-source")).toContainText("Reviewed recipe");
  await expect(page.getByTestId("primary-action")).toBeEnabled();
  await shot(page, "03-browse-recipes-selection");

  // 4) Confirmed execution / result state (single Confirm and run -> validate->confirm->execute)
  const executePromise = page.waitForResponse(responsePath("/api/execute"));
  await page.getByTestId("primary-action").click();
  const executeResponse = await executePromise;
  const execution = (await executeResponse.json()) as Record<string, unknown>;
  const results = (execution.execution as Record<string, unknown>).results as Array<Record<string, unknown>>;
  const firstResultId = String(results[0].result_id);
  const inspectPromise = page.waitForResponse(async (response) => {
    if (new URL(response.url()).pathname !== "/api/inspect-result") return false;
    try {
      const payload = (await response.json()) as Record<string, unknown>;
      const inspection = payload.inspection as Record<string, unknown> | undefined;
      const result = inspection?.result as Record<string, unknown> | undefined;
      return result?.result_id === firstResultId;
    } catch {
      return false;
    }
  });
  await page.locator(`[data-testid="result-item"][data-result-id="${firstResultId}"]`).click();
  await inspectPromise;
  await expect(page.getByTestId("replay-window-summary")).toHaveAttribute("data-result-id", firstResultId);

  // 5a) Developer details collapsed (default product state)
  await collapseAllDetails(page);
  await shot(page, "04-confirmed-result");
  await shot(page, "05a-developer-collapsed");

  // 5b) Developer details expanded (raw JSON / IDs preserved for engineers)
  await expandAllDetails(page);
  await shot(page, "05b-developer-expanded");
  await collapseAllDetails(page);

  // 2 & 6) Ask Hermes interpretation state today = honest typed MODEL_UNAVAILABLE
  await page.getByTestId("path-ask-hermes").click();
  await page.getByTestId("query-input").fill("Show possessions where the ball goes wide and the block shifts.");
  const modelPromise = page.waitForResponse(responsePath("/api/interpret"));
  await page.getByTestId("interpret-button").click();
  await modelPromise;
  await expect(page.getByTestId("model-unavailable-state")).toBeVisible();
  await shot(page, "02-ask-hermes-state");
  await shot(page, "06-model-unavailable");
});
