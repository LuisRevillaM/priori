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

async function captureCandidate(page: import("@playwright/test").Page, path: string) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame())));
  });
  await page.waitForTimeout(250);
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
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
  response.answer.raw_evidence = {
    ...response.answer.raw_evidence,
    descriptor_index: {
      ...(response.answer.raw_evidence?.descriptor_index ?? {}),
      coverage: {
        schema_version: "film_room.replay_coverage.v1",
        reason_code: "returned_classified_result_source_records",
        shown_count: 115,
        population_count: 2811,
        replay_partition_count: 1,
        completed_partition_count: 1
      }
    }
  };
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
  await expect(page.locator(".provenanceStrip span").filter({ hasText: "TREE not recorded" })).toHaveAttribute(
    "title",
    "Tree hash not recorded in this build"
  );
  await expect(page.getByText("Showing 115 of 2,811 — replay details exist only for the match-half containing the completed chain.")).toHaveCount(2);
  await expect(page.locator(".metricPanel.findingFirst")).toBeVisible();
  await expect(page.getByText("1 of 2,811 seen through")).toBeVisible();
  await expect(page.getByText("observed 1/1 (100%)")).toBeVisible();
  await expect(page.getByRole("button", { name: /COMPLETE ① 63:12 regain → ② \+11.2 m carry/ })).toBeVisible();

  const statusTokenAudit = [
    { selector: ".momentStatus.complete", color: "rgb(255, 177, 61)" },
    { selector: ".momentStatus.unknown", color: "rgb(139, 147, 160)" }
  ];
  for (const audit of statusTokenAudit) {
    await expect(page.locator(audit.selector).first()).toHaveCSS("color", audit.color);
  }

  if (candidateRoot) {
    mkdirSync(candidateRoot, { recursive: true });
    await captureCandidate(page, resolve(candidateRoot, "gallery-answer.png"));
  }

  await page.getByRole("button", { name: /COMPLETE ①/ }).click();
  await expect(page.getByText("① 63:12 regain → ② +11.2 m carry → ③ pass kept").first()).toBeVisible();
  await expect(page.locator("svg").getByText("①")).toBeVisible();
  await expect(page.locator("svg").getByText("②")).toBeVisible();
  await expect(page.locator("svg").getByText("③")).toBeVisible();
  if (candidateRoot) {
    await captureCandidate(page, resolve(candidateRoot, "keyed-moment-replay.png"));
  }

  await page.getByRole("button", { name: /UNKNOWN couldn't see whether ② happened — half ended/ }).click();
  await expect(page.getByText("couldn't see whether ② happened — half ended").first()).toBeVisible();
  await expect(page.locator("svg").getByText("regain — not verified")).toBeVisible();
  await expect(page.locator(".stageKeyText.evidenceUnknown")).toHaveCSS("fill", "rgb(139, 147, 160)");
  await expect(page.locator(".stageKeyChip.evidenceUnknown")).not.toHaveCSS("stroke-dasharray", "none");
  if (candidateRoot) {
    await captureCandidate(page, resolve(candidateRoot, "unknown-moment.png"));
  }

  const scrubber = page.getByRole("slider", { name: "Replay frame" });
  await scrubber.focus();
  await scrubber.press("ArrowRight");
  await expect(scrubber).toHaveCSS("outline-style", "solid");
  if (candidateRoot) {
    await captureCandidate(page, resolve(candidateRoot, "unknown-slate-replay.png"));
  }

  const visibleText = (await page.locator("body").innerText()).toLowerCase();
  for (const token of ["anchor_frame_id", "chain_status", "source_node_id", "stage_1", "stage_2", "stage_3"]) {
    expect(visibleText).not.toContain(token);
  }

  response.answer.interval_metric = {
    ...response.answer.interval_metric,
    observed: 0.8,
    lower: 0.7,
    upper: 0.9,
    unknown_count: 10,
    source: {
      ...response.answer.interval_metric.source,
      population_count: 100,
      a_count: 40,
      b_count: 10,
      e_count: 0
    }
  };
  await page.reload();
  await expect(page.locator(".metricPanel.rateFirst")).toBeVisible();
  await expect(page.getByText("80% observed")).toBeVisible();
  if (candidateRoot) {
    await captureCandidate(page, resolve(candidateRoot, "ratio-first-answer.png"));
  }
});
