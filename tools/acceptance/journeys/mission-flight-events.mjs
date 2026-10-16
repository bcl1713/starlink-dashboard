import { createRequire } from "node:module";
const require = createRequire(
  new URL("../../../frontend/mission-planner/package.json", import.meta.url),
);
const { chromium, expect } = require("@playwright/test");
import fs from "node:fs/promises";
const base = process.env.FLIGHT_EVENTS_BASE_URL;
const evidence = process.env.FLIGHT_EVENTS_ARTIFACTS_DIR;
if (!base || !evidence || !process.env.ACCEPTANCE_CDP_URL) {
  throw new Error(
    "Supply isolated runtime URL, artifact directory and existing CDP session",
  );
}
await fs.mkdir(evidence, { recursive: true });
const browser = await chromium.connectOverCDP(process.env.ACCEPTANCE_CDP_URL);
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  acceptDownloads: true,
});
const errors = [];
try {
  await context.tracing.start({ screenshots: true, snapshots: true });
  const response = await context.request.post(base + "/api/v2/missions", {
    data: {
      id: "browser-flight-events",
      name: "Flight recording browser acceptance",
      legs: [
        {
          id: "local-leg",
          name: "Local acceptance leg",
          route_id: "local-route",
          transports: { initial_x_satellite_id: "X-1" },
        },
      ],
    },
  });
  if (response.status() !== 201)
    throw new Error(
      "Mission create failed: " +
        response.status() +
        " " +
        (await response.text()),
    );
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(base + "/missions/browser-flight-events");
  const panel = page.getByRole("region", { name: "Flight recording" });
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Movement uncertain");
  await panel
    .getByText("Confirm or correct flight events", { exact: true })
    .click();
  const start = Date.now() - 3 * 3600 * 1000;
  const actions = [
    ["off_blocks", 0],
    ["takeoff", 5],
    ["landed", 45],
    ["on_blocks", 50],
  ];
  for (const [kind, minutes] of actions) {
    await panel.locator("form select").nth(0).selectOption(kind);
    await panel
      .getByLabel("Observed time (UTC)", { exact: true })
      .fill(new Date(start + minutes * 60000).toISOString().slice(0, 16));
    await panel
      .getByLabel("Reason", { exact: true })
      .fill("Synthetic local browser acceptance");
    await panel
      .getByRole("button", { name: "Record event", exact: true })
      .click();
    await expect(panel).toContainText("Event recorded.");
    await expect(panel.locator("ol li")).toHaveCount(
      actions.findIndex((action) => action[0] === kind) + 1,
    );
  }
  await panel
    .locator("form select")
    .nth(0)
    .selectOption("destination_complete");
  await expect(
    panel.locator("form select").nth(1).locator("option"),
  ).toHaveCount(2);
  await panel.locator("form select").nth(1).selectOption({ index: 1 });
  await panel
    .getByLabel("Reason", { exact: true })
    .fill("Synthetic DV offload parking");
  await panel
    .getByRole("button", { name: "Record event", exact: true })
    .click();
  await expect(panel.locator("ol li")).toHaveCount(5);
  await expect(panel).toContainText("Movement: parked");
  await page.screenshot({
    path: evidence + "/manual-events-parked.png",
    fullPage: true,
  });
  await panel
    .getByRole("checkbox", {
      name: "Allow a clearly labeled partial mission package",
    })
    .check();
  await panel
    .getByRole("button", { name: "Prepare telemetry download" })
    .click();
  await expect(
    panel.getByRole("link", { name: "Download mission telemetry" }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await panel.getByRole("link", { name: "Download mission telemetry" }).click();
  const download = await downloadPromise;
  await download.saveAs(evidence + "/manual-telemetry.zip");
  const status = await context.request.get(
    base +
      "/api/v2/missions/browser-flight-events/legs/local-leg/flight-events",
  );
  const data = await status.json();
  await fs.writeFile(
    evidence + "/manual-browser-result.json",
    JSON.stringify(
      {
        status: "passed",
        candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
        browser: browser.version(),
        viewport: [1920, 1080],
        source:
          "real production Nginx and backend; synthetic operator events; no aircraft telemetry",
        event_count: data.events.length,
        movement_state: data.status.movement_state,
        capture_state: data.status.capture_state,
        gap_count: data.capture.gaps?.length || 0,
        page_errors: errors,
      },
      null,
      2,
    ),
  );
  if (errors.length)
    throw new Error("Uncaught browser errors: " + errors.join("; "));
  await context.tracing.stop({ path: evidence + "/manual-browser-trace.zip" });
} finally {
  try {
    await context.close();
  } finally {
    await browser.close();
  }
}
