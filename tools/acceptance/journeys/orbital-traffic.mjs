#!/usr/bin/env node
/** Native local experiment journey; attaches to the platform-owned browser. */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import assert from "node:assert/strict";
import { hostname, cpus, totalmem } from "node:os";
import {
  installOrbitalProbe,
  summarizeProbe,
} from "./orbital-traffic-probe.mjs";
import {
  makeCatalog,
  installFixtureRoutes,
} from "./orbital-traffic-fixtures.mjs";
const args = Object.fromEntries(
  process.argv
    .slice(2)
    .reduce(
      (pairs, v, i, list) =>
        i % 2 ? pairs : [...pairs, [v.replace(/^--/, ""), list[i + 1]]],
      [],
    ),
);
if (!args.session || !args.origin || !args.artifacts)
  throw new Error(
    "required: --session <platform CDP> --origin <local URL> --artifacts <directory>",
  );
const root = resolve(args["repository-root"] ?? ".");
const { chromium, expect } = createRequire(
  resolve(root, "frontend/mission-planner/package.json"),
)("@playwright/test");
const browser = await chromium.connectOverCDP(args.session);
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
});
await context.addInitScript(installOrbitalProbe);
const page = await context.newPage();
const state = {
  catalog: await makeCatalog(2048),
  leases: new Set(),
  catalogRequests: 0,
};
await installFixtureRoutes(page, state);
const report = {
  host: hostname(),
  browser: browser.version(),
  hardware: {
    cpu: cpus()[0]?.model,
    logicalCpus: cpus().length,
    memoryGiB: totalmem() / 1024 ** 3,
  },
  viewport: [1920, 1080],
  fixture: "synthetic OMM; UTC anchored per run",
  assertions: [],
  performance: [],
  toggleResources: [],
  errors: [],
};
page.on("pageerror", (e) => report.errors.push(e.message));
await mkdir(args.artifacts, { recursive: true });
const save = () =>
  writeFile(
    resolve(args.artifacts, "orbital-browser-results.json"),
    JSON.stringify(report, null, 2),
  );
const check = async (name, fn) => {
  await fn();
  report.assertions.push(name);
  console.log("PASS", name);
  await save();
};
const probe = () => page.evaluate(() => window.__orbitalProbe.read());
async function settings(changes) {
  const response = await page.request.put(
    `${args.origin}/api/overview-links/settings`,
    { data: changes },
  );
  assert.equal(response.status(), 200);
}
async function openOverview() {
  if (
    page.url().startsWith(args.origin) &&
    new URL(page.url()).pathname === "/overview"
  ) {
    await page
      .getByRole("link", { name: "Configuration", exact: true })
      .click();
    await page.waitForTimeout(150);
  }
  await page.goto(`${args.origin}/overview`);
}
async function overview() {
  await openOverview();
  await expect(page.getByLabel("Globe legend")).toBeVisible();
  await expect(page.getByText("Traffic path", { exact: true })).toBeVisible();
  await page.waitForTimeout(1000);
}
async function sprites(visible = true) {
  await expect(
    page.getByLabel("Globe legend").getByText("Satellites", { exact: true }),
  )[visible ? "toBeVisible" : "toHaveCount"](visible ? undefined : 0, {
    timeout: 15000,
  });
}
async function toggle(enabled) {
  await page.getByRole("link", { name: "Configuration", exact: true }).click();
  await expect(
    page.getByRole("switch", { name: "Orbital traffic view" }),
  ).toBeVisible();
  const control = page.getByRole("switch", { name: "Orbital traffic view" });
  await expect(control).toBeChecked({ checked: !enabled });
  await control.click();
  await expect(control).toBeChecked({ checked: enabled });
  await expect(control).toBeEnabled();
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.getByLabel("Globe legend")).toBeVisible();
}
async function reloadCase(changes = {}) {
  Object.assign(
    state,
    {
      warning: false,
      invalid: false,
      stale: false,
      unavailable: false,
      zero: false,
      disconnected: false,
      statusFailure: false,
    },
    changes,
  );
  await overview();
}
async function measure(mode, size) {
  await page.waitForTimeout(30000);
  await page.screenshot({
    path: resolve(args.artifacts, `orbital-performance-${mode}-1920x1080.png`),
  });
  await page.evaluate(() => window.__orbitalProbe.reset());
  const start = Date.now();
  await page.waitForTimeout(120000);
  const raw = await probe();
  const summary = summarizeProbe(raw, (Date.now() - start) / 1000);
  report.performance.push({
    mode,
    size,
    warmupSeconds: 30,
    measurementSeconds: 120,
    ...summary,
  });
  console.log("MEASURE", mode, size, JSON.stringify(summary));
  await save();
}
try {
  await settings({
    orbital_traffic_enabled: false,
    starshield_link_enabled: true,
    x_band_link_enabled: true,
  });
  await overview();
  if (args["prove-failure"] === "true") {
    let caught = false;
    try {
      await expect(
        page
          .getByLabel("Globe legend")
          .getByText("Satellites", { exact: true }),
      ).toBeVisible({
        timeout: 1000,
      });
    } catch {
      caught = true;
    }
    assert(caught, "negative control must detect absent layer");
    report.assertions.push("negative control detected absent satellite layer");
    await save();
    console.log("NEGATIVE_CONTROL_DETECTED");
  }
  await check(
    "default off: production arc, route/history and both links; zero workers/demand",
    async () => {
      await sprites(false);
      assert.equal((await probe()).activeWorkers, 0);
      assert.equal(state.catalogRequests, 0);
      assert.equal(state.leases.size, 0);
      for (const label of [
        "Planned route",
        "Track history",
        "Planned satellite link",
      ])
        await expect(page.getByText(label, { exact: true })).toBeVisible();
    },
  );
  await page.screenshot({
    path: resolve(args.artifacts, "orbital-off-1920x1080.png"),
  });
  await toggle(true);
  await check(
    "real module worker propagates realistic synthetic constellation; unlabeled satellites",
    async () => {
      await sprites();
      await page.waitForTimeout(2000);
      const p = await probe();
      assert.equal(p.activeWorkers, 1);
      assert.equal(p.snapshots.at(-1).size, 2048);
      assert(p.snapshots.at(-1).valid > 0);
      await expect
        .poll(async () => Boolean((await probe()).snapshots.at(-1)?.route), {
          timeout: 15000,
        })
        .toBe(true);
      assert.equal(await page.getByText(/100000\d+/).count(), 0);
    },
  );
  await page.screenshot({
    path: resolve(args.artifacts, "orbital-on-1920x1080.png"),
  });
  await check(
    "independent X-band warning retains satellites and measured traffic",
    async () => {
      await reloadCase({ warning: true });
      await sprites();
      await expect(page.getByLabel("Map status")).toContainText(
        "Planned link warning",
      );
      await expect(
        page.getByText("Traffic path", { exact: true }),
      ).toBeVisible();
    },
  );
  for (const condition of ["zero", "unavailable"])
    await check(
      `${condition} measured throughput retains single static path and dots`,
      async () => {
        await reloadCase({ [condition]: true });
        await sprites();
      },
    );
  for (const condition of ["invalid", "stale", "statusFailure"])
    await check(
      `${condition} telemetry removes traffic while dots remain`,
      async () => {
        Object.assign(state, {
          warning: false,
          invalid: false,
          stale: false,
          statusFailure: false,
          [condition]: true,
        });
        await openOverview();
        await sprites();
        await expect(
          page.getByText("Traffic path", { exact: true }),
        ).toHaveCount(0);
      },
    );
  await reloadCase();
  await check("hidden demand release and return refresh", async () => {
    await sprites();
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => (window.__acceptanceHidden ? "hidden" : "visible"),
      });
      window.__acceptanceHidden = true;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForTimeout(500);
    assert.equal((await probe()).activeWorkers, 0);
    await expect.poll(() => state.leases.size, { timeout: 15000 }).toBe(0);
    await sprites(false);
    await page.evaluate(() => {
      window.__acceptanceHidden = false;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await sprites();
    assert.equal((await probe()).activeWorkers, 1);
  });
  await check(
    "worker failure latches through visibility return; explicit retry recovers",
    async () => {
      await page.evaluate(() => window.__orbitalProbe.failWorker());
      await sprites(false);
      await page.evaluate(() => {
        window.__acceptanceHidden = true;
        document.dispatchEvent(new Event("visibilitychange"));
        window.__acceptanceHidden = false;
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await page.waitForTimeout(1500);
      assert.equal((await probe()).activeWorkers, 0);
      await toggle(false);
      await toggle(true);
      await sprites();
    },
  );
  await check(
    "Starshield off releases orbital resources independently of X-band",
    async () => {
      await settings({ starshield_link_enabled: false });
      await openOverview();
      await sprites(false);
      await expect(page.getByText("Traffic path", { exact: true })).toHaveCount(
        0,
      );
      await expect(
        page.getByText("Planned satellite link", { exact: true }),
      ).toBeVisible();
      assert.equal((await probe()).activeWorkers, 0);
      await settings({
        starshield_link_enabled: true,
        x_band_link_enabled: false,
      });
      await overview();
      await sprites();
      await expect(
        page.getByText("Planned satellite link", { exact: true }),
      ).toHaveCount(0);
      await settings({ x_band_link_enabled: true });
    },
  );
  await check(
    "empty and expired catalogs keep production fallback and release worker",
    async () => {
      state.catalog = await makeCatalog(0);
      await overview();
      await sprites(false);
      assert.equal((await probe()).activeWorkers, 0);
      state.catalog = await makeCatalog(2048, Date.now(), true);
      await overview();
      await page.waitForTimeout(2000);
      await sprites(false);
      assert.equal((await probe()).activeWorkers, 0);
      state.catalog = await makeCatalog(2048);
    },
  );
  await check(
    "delayed catalog after disable cannot restore the layer",
    async () => {
      let release;
      state.catalogDelay = new Promise((r) => (release = r));
      await overview();
      await page.waitForTimeout(500);
      await toggle(false);
      release();
      state.catalogDelay = null;
      await page.waitForTimeout(500);
      await sprites(false);
      assert.equal((await probe()).activeWorkers, 0);
      assert.equal(state.leases.size, 0);
      await toggle(true);
      await sprites();
    },
  );
  await check(
    "reduced motion still receives periodic static snapshots",
    async () => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      const before = (await probe()).snapshots.length;
      await page.waitForTimeout(2100);
      assert((await probe()).snapshots.length > before);
      await sprites();
      await page.screenshot({
        path: resolve(args.artifacts, "orbital-reduced-motion.png"),
      });
      await page.emulateMedia({ reducedMotion: "no-preference" });
    },
  );
  state.catalog = await makeCatalog(16384);
  await overview();
  await sprites();
  await page.waitForTimeout(3000);
  await check(
    "16,384-object cap with one worker and bounded GPU arrays",
    async () => {
      const p = await probe();
      assert.equal(p.snapshots.at(-1).size, 16384);
      assert.equal(p.activeWorkers, 1);
      assert(p.maximumSpriteDrawsPerFrame <= 2);
      report.maximumCatalogResources = {
        activeWorkers: p.activeWorkers,
        buffers: p.buffers,
        bufferBytes: p.bufferBytes,
        orbitalBufferBytes: p.orbitalBufferBytes,
        maximumSpriteDrawsPerFrame: p.maximumSpriteDrawsPerFrame,
        snapshot: p.snapshots.at(-1),
      };
    },
  );
  await page.screenshot({ path: resolve(args.artifacts, "orbital-16384.png") });
  await check(
    "dense disconnected fixture retains eligible dots and production fallback",
    async () => {
      await reloadCase({ disconnected: true });
      await sprites();
      await page.waitForTimeout(4000);
      assert.equal((await probe()).snapshots.at(-1).route, null);
      await expect(
        page.getByText("Traffic path", { exact: true }),
      ).toBeVisible();
    },
  );
  await reloadCase();
  await toggle(false);
  await page.waitForTimeout(1000);

  const toggles = Number(args.toggles ?? 50);
  await check(
    `${toggles} repeated off/on mounts release workers and GPU buffers`,
    async () => {
      for (let i = 0; i < toggles; i++) {
        await toggle(true);
        await sprites();
        await toggle(false);
        await page.waitForTimeout(1000);
        const p = await probe();
        assert.equal(p.activeWorkers, 0);
        assert.equal(state.leases.size, 0);
        assert.equal(p.orbitalBufferBytes, 0);
        await expect
          .poll(async () => (await probe()).bufferContexts, { timeout: 15000 })
          .toBe(1);
        report.toggleResources.push({
          cycle: i + 1,
          buffers: p.buffers,
          bufferBytes: p.bufferBytes,
          orbitalBufferBytes: p.orbitalBufferBytes,
          bufferContexts: p.bufferContexts,
          created: p.created,
          terminated: p.terminated,
        });
        if (i % 10 === 0) console.log("TOGGLES", i + 1);
      }
    },
  );
  if (args.performance !== "false") {
    await measure("off", 16384);
    await toggle(true);
    await sprites();
    await measure("on", 16384);
  }
  report.result =
    "passed functional assertions; performance evaluated separately";
  await save();
} catch (error) {
  report.result = "failed";
  report.failure = error.stack;
  await save();
  throw error;
} finally {
  await settings({ orbital_traffic_enabled: false });
  await context.close();
  await browser.close();
}
