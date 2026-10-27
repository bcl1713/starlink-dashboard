/** Real Nginx/API journey with explicitly injected synthetic backend dependencies. */
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
const [origin, evidence, project] = process.argv.slice(2);
const { chromium, expect } = createRequire(project + "/package.json")(
  "@playwright/test",
);
let browser, context;
const report = {
  fixture:
    "Synthetic backend dependencies; no browser response interception; no operational routing claims",
  cases: [],
};
try {
  browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
  });
  context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();
  const api = context.request;
  const select = async (name) => {
    const response = await api.post(origin + "/api/_synthetic/pop-evidence", {
      data: { case: name },
    });
    assert.equal(response.status(), 200);
    const status = await (await api.get(origin + "/api/status")).json();
    report.cases.push({ name, status });
    return status;
  };
  let status = await select("tokyo");
  assert.equal(status.pop_observation.entry.pop_id, "tokyo");
  assert.equal(
    status.pop_observation.entry.provider_geoip.city,
    "Invented Domestic City",
  );
  assert.deepEqual(status.ground_entry_point, {
    latitude: 35.6895,
    longitude: 139.69171,
  });
  await page.goto(origin + "/overview");
  await expect(
    page.locator('[data-overview-label-id="gep"] [data-label-source]'),
  ).toHaveText("PoP · Tokyo", { timeout: 60000 });
  await expect(
    page.locator('[data-overview-label-id="gep"] [data-label-source]'),
  ).toBeVisible();
  await page.screenshot({ path: evidence + "/tokyo-map.png" });
  const csv = await (
    await api.get(origin + "/api/_synthetic/pop-evidence.csv")
  ).text();
  assert.match(csv, /Mission Snapshot Egress PoP ID/);
  assert.match(csv, /Snapshot only; not leg-time history/);
  assert.match(csv, /Tokyo/);
  assert.match(csv, /Invented Domestic City/);
  assert.match(csv, /operator_static_cidr/);
  await writeFile(evidence + "/synthetic-timeline.csv", csv);
  const metrics = await (await api.get(origin + "/metrics")).text();
  assert.match(metrics, /city="Tokyo"/);
  assert.match(metrics, /identity_source="operator_static_cidr"/);
  await writeFile(evidence + "/synthetic-metrics.txt", metrics);
  await page.goto(origin + "/operator");
  const panel = page.getByLabel("PoP evidence", { exact: true });
  await panel.locator("summary").first().click();
  await expect(panel).toContainText("operator-supplied static CIDR mapping");
  await expect(panel).toContainText("Invented Domestic City");
  await expect(panel).toContainText("physical routing is unverified");
  await page.screenshot({ path: evidence + "/tokyo-operator.png" });
  status = await select("mapped-failure");
  assert.equal(status.pop_observation.entry.pop_id, "tokyo");
  assert.equal(status.pop_observation.entry.provider_geoip, null);
  assert.deepEqual(status.ground_entry_point, {
    latitude: 35.6895,
    longitude: 139.69171,
  });
  status = await select("changed-failure");
  assert.equal(status.pop_observation.ip, "192.0.2.42");
  assert.equal(status.pop_observation.entry, null);
  assert.equal(status.ground_entry_point, null);
  const failedCsv = await (
    await api.get(origin + "/api/_synthetic/pop-evidence.csv")
  ).text();
  assert.doesNotMatch(failedCsv, /Tokyo|Invented Domestic City/);
  status = await select("geoip");
  assert.equal(status.pop_observation.entry.pop_id, null);
  assert.deepEqual(status.ground_entry_point, { latitude: 33, longitude: -84 });
  // Centering is separately controlled synthetic aircraft data; marker stays at GeoIP.
  await page.goto(origin + "/overview");
  await expect(
    page.locator('[data-overview-label-id="gep"] [data-label-source]'),
  ).toHaveText("GeoIP · Invented Domestic City", { timeout: 60000 });
  await expect(
    page.locator('[data-overview-label-id="gep"] [data-label-source]'),
  ).toBeVisible();
  await page.screenshot({ path: evidence + "/geoip-map.png" });
  status = await select("stale");
  assert.equal(status.pop_observation.status, "unknown");
  assert.equal(status.pop_observation.entry.freshness, "stale");
  assert.equal(status.ground_entry_point, null);
  for (const name of ["window", "skipped", "mismatch", "early"]) {
    status = await select(name);
    await page.goto(origin + "/overview");
    const advisory = page.getByRole("status", { name: "Starshield advisory" });
    if (name === "window")
      await expect(advisory).toContainText("Starshield transition window");
    else await expect(advisory).toHaveCount(0);
    if (name === "skipped") {
      assert.deepEqual(
        status.pop_occurrences.map((item) => item.disposition),
        ["superseded", "observed"],
      );
      await page.goto(origin + "/operator");
      const evidencePanel = page.getByLabel("PoP evidence", { exact: true });
      await evidencePanel.locator("summary").first().click();
      await evidencePanel
        .getByText("Forecast comparison", { exact: true })
        .click();
      await expect(evidencePanel).toContainText("superseded");
      await expect(evidencePanel).toContainText("observed");
    }
    await page.screenshot({ path: evidence + `/lifecycle-${name}.png` });
  }
  report.passed = true;
} finally {
  await context?.close();
  await browser?.close();
  report.cleanup = { contextClosed: true, browserClosed: true };
  await writeFile(evidence + "/browser.json", JSON.stringify(report, null, 2));
}
