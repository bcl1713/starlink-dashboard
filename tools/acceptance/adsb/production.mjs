import { writeFile, mkdir } from "node:fs/promises";
import {
  chromium,
  expect,
} from "../../../frontend/mission-planner/node_modules/@playwright/test/index.mjs";
const directory = process.env.ADSB_EVIDENCE_DIR;
if (!directory) throw new Error("ADSB_EVIDENCE_DIR required");
await mkdir(directory, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  baseURL: "http://127.0.0.1:15244",
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: directory },
});
try {
  const overview = await context.newPage(),
    editing = await context.newPage();
  await overview.goto("/overview");
  await editing.goto("/configuration");
  await editing.getByRole("switch", { name: "ADS-B aircraft layer" }).click();
  await expect(
    editing.getByRole("switch", { name: "ADS-B aircraft layer" }),
  ).toBeChecked();
  const started = Date.now();
  await expect(
    overview.getByRole("button", { name: "Details for 00AB12" }),
  ).toBeVisible({ timeout: 5500 });
  const enableMs = Date.now() - started;
  await editing.getByLabel("Included ICAO hexes").fill("000001");
  await editing
    .getByRole("button", { name: "Save included aircraft", exact: true })
    .click();
  const includedAt = Date.now();
  await expect(overview.locator('[data-adsb-label="000001"]')).toBeVisible({
    timeout: 5500,
  });
  const includeMs = Date.now() - includedAt;
  const trigger = overview.getByRole("button", { name: "Details for 000001" });
  await trigger.focus();
  await trigger.press("Enter");
  await expect(overview.getByRole("dialog")).toContainText("CIVIL");
  await expect(overview.getByRole("dialog")).toContainText("Unavailable");
  await overview.screenshot({ path: `${directory}/production-details.png` });
  await overview.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await editing.getByLabel("Excluded ICAO hexes").fill("00AB12");
  await editing
    .getByRole("button", { name: "Save excluded aircraft", exact: true })
    .click();
  const excludedAt = Date.now();
  await expect(
    overview.getByRole("button", { name: "Details for 00AB12" }),
  ).toHaveCount(0, { timeout: 5500 });
  const excludeMs = Date.now() - excludedAt;
  await overview.screenshot({ path: `${directory}/production-overview.png` });
  await editing.screenshot({
    path: `${directory}/production-configuration.png`,
    fullPage: true,
  });
  for (const endpoint of ["settings", "traffic"]) {
    const response = await context.request.get(
      `/api/overview-adsb/${endpoint}`,
    );
    expect(response.status()).toBe(200);
    await writeFile(
      `${directory}/production-${endpoint}.json`,
      JSON.stringify(await response.json(), null, 2),
    );
  }
  const history = await context.request.get("/api/overview-history");
  expect(history.status()).toBe(200);
  await writeFile(
    `${directory}/production-history.json`,
    JSON.stringify(await history.json(), null, 2),
  );
  await writeFile(
    `${directory}/production-browser.json`,
    JSON.stringify(
      {
        candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
        browser: browser.version(),
        enableMs,
        includeMs,
        excludeMs,
        viewport: { width: 1920, height: 1080 },
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
  await browser.close();
}
