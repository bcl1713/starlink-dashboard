/** Actual production UI downloads; no response interception or fixture endpoint. */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)(
  "/opt/customer-briefing/node_modules/playwright",
);
const [origin, missionName, mode, output] = process.argv.slice(2);
await mkdir(output, { recursive: true });
let browser, context;
const report = {
  mode,
  missionName,
  status: "failed",
  requests: [],
  errors: [],
};
try {
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => report.errors.push(String(error)));
  page.on("response", (response) => {
    if (response.url().endsWith("/export"))
      report.requests.push({
        url: response.url(),
        status: response.status(),
        headers: response.headers(),
      });
  });
  await page.goto(origin + "/missions", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.getByText(missionName, { exact: true }).waitFor();
  const card = page
    .getByText(missionName, { exact: true })
    .locator('xpath=ancestor::div[contains(@class,"rounded-xl")][1]');
  await card.getByRole("button", { name: "Export", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  const downloadPromise = page.waitForEvent("download", { timeout: 95000 });
  await dialog.getByRole("button", { name: "Export", exact: true }).click();
  const download = await downloadPromise;
  if (await download.failure()) throw Error(await download.failure());
  await download.saveAs(path.join(output, "download.zip"));
  report.filename = download.suggestedFilename();
  if (mode === "omitted") {
    await dialog
      .getByText(
        "ZIP downloaded. Mission data and CSVs are included; the customer PDF could not be included.",
      )
      .waitFor();
    await page.waitForTimeout(2300);
    if (!(await dialog.isVisible()))
      throw Error("omission dialog dismissed automatically");
    await page.screenshot({ path: path.join(output, "omission.png") });
    await dialog
      .getByRole("button", { name: "Close", exact: true })
      .first()
      .click();
    await card.getByRole("button", { name: "Export", exact: true }).click();
    await dialog.getByRole("button", { name: "Export", exact: true }).waitFor();
    if (
      await dialog
        .getByText(
          "ZIP downloaded. Mission data and CSVs are included; the customer PDF could not be included.",
        )
        .count()
    )
      throw Error("stale omission after reopen");
    await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
    report.persistentOmissionAndReset = true;
  } else {
    await dialog.waitFor({ state: "hidden", timeout: 5000 });
    report.ordinarySuccessDismissed = true;
  }
  if (
    report.requests.length !== 1 ||
    report.requests[0].status !== 200 ||
    report.errors.length
  )
    throw Error("unexpected download requests or page errors");
  report.status = "passed";
} finally {
  if (context) await context.close();
  if (browser) await browser.close();
  report.cleanup = { contextClosed: true, browserClosed: true };
  await writeFile(
    path.join(output, "journey.json"),
    JSON.stringify(report, null, 2),
  );
}
console.log(JSON.stringify(report));
