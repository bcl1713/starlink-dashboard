import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

const require = createRequire(
  new URL("../../../frontend/mission-planner/package.json", import.meta.url),
);
const { expect } = require("@playwright/test");

export async function simulateReviewedLeg(
  page,
  context,
  origin,
  mission,
  output,
) {
  await page.goto(`${origin}/missions/${mission}`);
  await page
    .getByRole("button", { name: "Simulate leg…", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Simulate leg",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Multiplier", { exact: true }).fill("10");
  const previewResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/simulation/preview") &&
      r.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "Preview", exact: true }).click();
  const response = await previewResponse;
  assert.equal(response.status(), 200, await response.text());
  const preview = await response.json();
  assert(preview.flight_duration_seconds > 0);
  assert.equal(preview.effective_multiplier, 10);
  await expect(dialog.getByLabel("Simulation preview")).toBeVisible();
  await page.screenshot({
    path: join(output, "reviewed-leg-simulation-preview.png"),
    fullPage: true,
  });
  const startResponse = page.waitForResponse(
    (r) => r.url().endsWith("/activate") && r.request().method() === "POST",
  );
  let started;
  try {
    await dialog
      .getByRole("button", { name: "Start simulation", exact: true })
      .click();
    const activation = await startResponse;
    assert.equal(activation.status(), 200, await activation.text());
    started = await activation.json();
    assert.equal(started.simulation_run.state, "running");
    assert.equal(started.simulation_run.run.mission_id, mission);
    assert.equal(started.simulation_run.run.leg_id, started.active_leg_id);
    assert.equal(started.simulation_run.run.plan_token, preview.plan_token);
    await expect(dialog).not.toBeVisible();
    await page.goto(`${origin}/overview`);
    await expect(
      page.getByLabel("Simulation clock", { exact: true }),
    ).toBeVisible();
    const currentResponse = await context.request.get(
      `${origin}/api/simulation/run`,
    );
    assert(currentResponse.ok(), await currentResponse.text());
    const current = await currentResponse.json();
    assert.equal(current.state, "running");
    assert.equal(current.run.run_id, started.simulation_run.run.run_id);
    await page.screenshot({
      path: join(output, "reviewed-leg-simulation-running.png"),
      fullPage: true,
    });
  } finally {
    const stopped = await context.request.post(
      `${origin}/api/v2/missions/${mission}/legs/deactivate`,
    );
    assert(stopped.ok(), await stopped.text());
  }
  const status = await context.request.get(`${origin}/api/simulation/run`);
  assert(status.ok(), await status.text());
  const cancelled = await status.json();
  assert.equal(cancelled.state, "cancelled");
  const readback = await context.request.get(
    `${origin}/api/v2/missions/${mission}`,
  );
  assert(readback.ok(), await readback.text());
  assert((await readback.json()).legs.every((leg) => !leg.is_active));
  await writeFile(
    join(output, "reviewed-leg-simulation.json"),
    JSON.stringify({ preview, started, cancelled }, null, 2),
  );
}
