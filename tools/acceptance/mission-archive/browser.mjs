import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [origin, evidence, playwrightPath] = process.argv.slice(2);
const { chromium } = await import(pathToFileURL(playwrightPath));
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  acceptDownloads: true,
});
const page = await context.newPage();
page.setDefaultTimeout(60000);
const control = async (body) => {
  const response = await page.request.post(
    `${origin}/api/_synthetic/large-export`,
    { data: body },
  );
  if (!response.ok()) throw new Error(await response.text());
};
try {
  await page.goto(`${origin}/missions`);
  const mission = await (
    await page.request.get(`${origin}/api/v2/missions/synthetic-mission-a`)
  ).json();
  const exportButton = page
    .getByText(mission.name, { exact: true })
    .locator("..")
    .locator("..")
    .getByRole("button", { name: "Export", exact: true });
  await exportButton.click();
  await page.getByLabel("Telemetry format").selectOption("compact");
  await page.screenshot({ path: path.join(evidence, "compact-selection.png") });
  const download = page.waitForEvent("download", { timeout: 90000 });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Export", exact: true })
    .click();
  const artifact = await download;
  if (!(await artifact.suggestedFilename()).includes("compact"))
    throw new Error("Compact filename was missing");
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await control({ action: "capacity", bytes: 128 });
  await exportButton.click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Export", exact: true })
    .click();
  await page
    .getByText(/Mission export exceeds the supplementary-members capacity/)
    .waitFor();
  await page.screenshot({ path: path.join(evidence, "capacity-error.png") });
  await control({ action: "capacity" });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await control({ action: "pause" });
  await page.evaluate(async () => {
    const controller = new AbortController();
    const request = fetch("/api/v2/missions/synthetic-mission-a/export", {
      method: "POST",
      signal: controller.signal,
    }).catch((error) => error.name);
    let entered = false;
    for (let i = 0; i < 100; i++) {
      const state = await (await fetch("/api/_synthetic/large-export")).json();
      if (state.entered) {
        entered = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    if (!entered) throw new Error("Capture pause was not reached");
    controller.abort();
    await request;
  });
  for (let i = 0; i < 100; i++) {
    const state = await (
      await page.request.get(`${origin}/api/_synthetic/large-export`)
    ).json();
    if (state.capture_owners === 0) break;
    if (i === 99) throw new Error("Aborted capture retained its files");
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  await control({ action: "release" });
  fs.writeFileSync(
    path.join(evidence, "browser.json"),
    JSON.stringify(
      {
        compactSelection: true,
        realDownload: true,
        readableCapacityError: true,
        preAckAbortCleanup: true,
      },
      null,
      2,
    ),
  );
} finally {
  await context.close();
  await browser.close();
}
