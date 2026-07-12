import { expect, test } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve(process.cwd(), "../..");
const evidenceRoot = resolve(
  repoRoot,
  "delivery/packets/deploy-2-fix-evidence/runs/2026-07-10T192707.624506Z-f90b19f71268"
);
const candidateRoot = process.env.LEGIBILITY_CANDIDATE_DIR
  ? resolve(repoRoot, process.env.LEGIBILITY_CANDIDATE_DIR)
  : null;

function loadJson(path: string) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function replayFor(moment: Record<string, unknown>) {
  const anchor = Number(moment.anchor_frame_id);
  const replayWindowId = String(moment.replay_window_id);
  const pass = moment.chain_status === "PASS";
  const frames = Array.from({ length: 13 }, (_, index) => {
    const frameId = anchor - 30 + index * 5;
    return {
      frame_id: frameId,
      timestamp_utc: null,
      entities: [
        { team_id: "home", team_role: "home", entity_id: "home-8", entity_type: "player", x_m: -10 + index, y_m: 2 },
        { team_id: "away", team_role: "away", entity_id: "away-4", entity_type: "player", x_m: 2, y_m: -8 + index / 2 },
        { team_id: "ball", team_role: "home", entity_id: "ball", entity_type: "ball", x_m: -7 + index, y_m: 1 }
      ]
    };
  });
  return {
    schema_version: "1.0",
    replay_window_id: replayWindowId,
    source_kind: "chain_record",
    source_id: String(moment.result_id),
    match_id: String(moment.match_id),
    period: String(moment.period),
    frame_rate_hz: 25,
    start_frame_id: anchor - 30,
    end_frame_id: anchor + 30,
    anchor_frame_id: anchor,
    generated_at: "2026-07-10T00:00:00Z",
    canonical_sources: {},
    pitch: { length_m: 105, width_m: 68, coordinate_contract: "canonical" },
    frames,
    overlays: pass
      ? {
          stage_labels: [
            { stage: 1, label: "regain", frame_id: anchor - 20, status: "PASS", player_id: "home-8" },
            {
              stage: 2,
              label: "at least 3 m",
              frame_id: anchor,
              status: "PASS",
              player_id: "home-8",
              observed_numeric_value: 11.2
            },
            { stage: 3, label: "pass kept", frame_id: anchor + 20, status: "PASS", player_id: "home-8" }
          ],
          anchor_markers: [
            { stage: 1, frame_id: anchor - 20, status: "PASS", player_id: "home-8" },
            { stage: 3, frame_id: anchor + 20, status: "PASS", player_id: "home-8" }
          ],
          carry_trails: [
            {
              start_frame_id: anchor - 10,
              end_frame_id: anchor + 10,
              player_id: "home-8",
              status: "PASS",
              observed_numeric_value: 11.2,
              minimum_numeric_value: 3,
              unit: "metre"
            }
          ],
          unknown: { is_unknown: false, reason: null }
        }
      : {
          stage_labels: [{ stage: 1, label: "regain", frame_id: anchor, status: "PASS", player_id: "home-8" }],
          anchor_markers: [{ stage: 1, frame_id: anchor, status: "PASS", player_id: "home-8" }],
          carry_trails: [],
          unknown: { is_unknown: true, reason: "stage_2_window_truncated" }
        }
  };
}

test.use({ viewport: { width: 1440, height: 1100 } });

test('N8 cold walkthrough: "read the question, watch one replay, narrate which part is which"', async ({ page }) => {
  const envelope = loadJson(resolve(evidenceRoot, "local-bootstrap.json"));
  const bootstrap = structuredClone(envelope.bootstrap);
  const response = bootstrap.prewarmed_response;
  const meaningExpression = loadJson(
    resolve(
      repoRoot,
      "delivery/packets/r2-4-flagship/meaning-expressions/counterattack_initiation_sequence_rate.v0.json"
    )
  );
  const moments = response.answer.moments as Array<Record<string, unknown>>;
  const passMoment = moments.find((moment) => moment.chain_status === "PASS");
  const unknownMoment = moments.find((moment) => moment.chain_reason === "stage_2_window_truncated");
  expect(passMoment).toBeTruthy();
  expect(unknownMoment).toBeTruthy();
  passMoment!.match_time_ms = 3_792_000;
  response.answer.meaning_expression = meaningExpression;
  response.answer.moments = [unknownMoment, passMoment];
  response.answer.visible_moment_count = 2;
  bootstrap.prewarmed_response = response;
  bootstrap.answer = response.answer;

  await page.route("**/api/film-room/bootstrap", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/film-room/replay-window**", async (route) => {
    const replayWindowId = new URL(route.request().url()).searchParams.get("replay_window_id");
    const moment = [unknownMoment, passMoment].find((item) => item?.replay_window_id === replayWindowId);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, replay_window_id: replayWindowId, replay: replayFor(moment!) })
    });
  });

  await page.goto("/film-room");
  await expect(page.locator(".questionClauses span").nth(0)).toHaveText("①they win the ball back");
  await expect(page.locator(".questionClauses span").nth(1)).toHaveText("②carry it forward at least 3 m");
  await expect(page.locator(".questionClauses span").nth(2)).toHaveText("③keep it with a completed pass");
  await expect(page.getByText(/Of 2,811 regains, 1 completed the whole chain ①→②→③/)).toBeVisible();
  await expect(page.locator("svg").getByText("①")).toBeVisible();
  await expect(page.locator(".provenanceStrip span").filter({ hasText: "TREE —" })).toHaveAttribute(
    "title",
    "Tree hash unavailable in this build"
  );
  await expect(page.getByRole("button", { name: /PASS ① 63:12 regain → ② watching the carry…/ })).toBeVisible();

  if (candidateRoot) {
    mkdirSync(candidateRoot, { recursive: true });
    await page.screenshot({ path: resolve(candidateRoot, "gallery-answer.png"), fullPage: true });
  }

  await page.getByRole("button", { name: /PASS ①/ }).click();
  await expect(page.getByText("① 63:12 regain → ② +11.2 m carry → ③ pass kept").first()).toBeVisible();
  await expect(page.locator("svg").getByText("①")).toBeVisible();
  await expect(page.locator("svg").getByText("②")).toBeVisible();
  await expect(page.locator("svg").getByText("③")).toBeVisible();
  if (candidateRoot) {
    await page.screenshot({ path: resolve(candidateRoot, "keyed-moment-replay.png"), fullPage: true });
  }

  await page.getByRole("button", { name: /UNKNOWN couldn't see whether ② happened — half ended/ }).click();
  await expect(page.getByText("couldn't see whether ② happened — half ended").first()).toBeVisible();
  if (candidateRoot) {
    await page.screenshot({ path: resolve(candidateRoot, "unknown-moment.png"), fullPage: true });
  }

  const visibleText = (await page.locator("body").innerText()).toLowerCase();
  for (const token of ["anchor_frame_id", "chain_status", "source_node_id", "stage_1", "stage_2", "stage_3"]) {
    expect(visibleText).not.toContain(token);
  }
});
