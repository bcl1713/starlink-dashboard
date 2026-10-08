// Connect only to the platform-owned CDP session. Never intercept export responses.
import { chromium } from "../../../frontend/mission-planner/node_modules/playwright-core/index.mjs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const [session, base, output, missionName, expectedStatus] =
  process.argv.slice(2);
await mkdir(output, { recursive: true });
const browser = await chromium.connectOverCDP(session);
const context = await browser.newContext({ acceptDownloads: true });
try {
  const page = await context.newPage();
  await page.goto(`${base}/missions`);
  const card = page
    .locator("div.rounded-xl.border.bg-card")
    .filter({ hasText: missionName });
  await card.getByRole("button", { name: "Export", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/export") && r.request().method() === "POST",
    { timeout: 180000 },
  );
  const downloadPromise = page.waitForEvent("download", { timeout: 180000 });
  await dialog.getByRole("button", { name: "Export", exact: true }).click();
  const [response, download] = await Promise.all([
    responsePromise,
    downloadPromise,
  ]);
  const headers = response.headers();
  if (
    response.status() !== 200 ||
    headers["x-mission-export-trial-status"] !== expectedStatus
  )
    throw new Error("Unexpected real export response");
  const warnings = JSON.parse(headers["x-mission-export-warnings"]);
  await download.saveAs(path.join(output, "download.zip"));
  if (warnings.length) {
    await dialog.getByRole("alert").waitFor();
    await page.waitForTimeout(2500);
    if (!(await dialog.isVisible()))
      throw new Error("Warnings dismissed automatically");
    for (const warning of warnings)
      if (!(await dialog.getByRole("alert").innerText()).includes(warning))
        throw new Error("Warning missing from UI");
    await page.screenshot({
      path: path.join(output, "warning.png"),
      fullPage: true,
    });
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
  } else {
    await dialog.waitFor({ state: "hidden", timeout: 5000 });
    await page.screenshot({
      path: path.join(output, "download-complete.png"),
      fullPage: true,
    });
  }
  await writeFile(
    path.join(output, "journey.json"),
    JSON.stringify(
      {
        status: "pass",
        interceptedResponses: false,
        expectedStatus,
        warnings,
        browserVersion: browser.version(),
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
  await browser.close();
}
