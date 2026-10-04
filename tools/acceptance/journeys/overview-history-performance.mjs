#!/usr/bin/env node
/** Real history path; process/resource capture is separate from product code. */
import { createRequire } from "node:module";
import {
  appendFileSync,
  readFileSync,
  mkdirSync,
  writeFileSync,
} from "node:fs";
import { request as httpRequest } from "node:http";
import { cpus, hostname, totalmem } from "node:os";
import { dirname, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { installOverviewHistoryProbe } from "./overview-history-probe.mjs";

export function parseArgs(argv) {
  const flags = new Set(["check", "controls", "record-video"]);
  const keys = new Set([
    "session",
    "origin",
    "artifacts",
    "cadence",
    "viewers",
    "window",
    "warmup-seconds",
    "duration-seconds",
  ]);
  const raw = {};
  for (let index = 0; index < argv.length; index++) {
    const key = argv[index].replace(/^--/, "");
    if (flags.has(key)) raw[key] = true;
    else if (keys.has(key) && argv[index + 1] !== undefined)
      raw[key] = argv[++index];
    else throw new Error(`invalid argument ${argv[index]}`);
  }
  for (const key of ["session", "origin", "artifacts"])
    if (!raw[key]) throw new Error(`invalid missing ${key}`);
  for (const key of ["session", "origin"]) {
    const url = new URL(raw[key]);
    if (
      url.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
    )
      throw new Error(`invalid non-loopback ${key}`);
  }
  const integer = (key, fallback, minimum = 1) => {
    const value = String(raw[key] ?? fallback);
    if (
      !/^\d+$/.test(value) ||
      !Number.isSafeInteger(Number(value)) ||
      Number(value) < minimum
    )
      throw new Error(`invalid ${key}`);
    return Number(value);
  };
  const cadence = integer("cadence", 5),
    viewers = integer("viewers", 1);
  if (![1, 5].includes(cadence) || ![1, 2].includes(viewers))
    throw new Error("invalid cadence/viewers");
  return {
    ...raw,
    viewport: [1920, 1080],
    dpr: 1,
    viewers,
    window_seconds: integer("window", 1800),
    configured_interval_seconds: cadence,
    requested_measured_seconds: integer("duration-seconds", 600),
    warmup_seconds: integer("warmup-seconds", 300, 0),
  };
}

export function classifyPhase({
  requested_seconds,
  measured_seconds,
  warmup_seconds,
  errors,
}) {
  return {
    status: errors
      ? "failed"
      : measured_seconds < requested_seconds
        ? "incomplete"
        : "measured",
    requested_seconds,
    measured_seconds,
    warmup_seconds,
    final_acceptance: false,
  };
}

const clock = () => Number(process.hrtime.bigint()) / 1e9;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function dockerSocket() {
  const endpoint =
    process.env.DOCKER_HOST ||
    execFileSync(
      "docker",
      ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
      { encoding: "utf8" },
    ).trim();
  if (!endpoint.startsWith("unix://"))
    throw new Error(
      "configured actor Docker endpoint must be Unix for this sampler",
    );
  return endpoint.slice(7);
}

function dockerStats(socketPath, name) {
  return new Promise((resolve, reject) => {
    const request = httpRequest(
      {
        socketPath,
        path: `/containers/${name}/stats?stream=false&one-shot=true`,
        method: "GET",
      },
      (response) => {
        let body = "";
        response.on("data", (chunk) => (body += chunk));
        response.on("end", () => {
          if (response.statusCode !== 200)
            return reject(
              new Error(`Docker stats ${name}: ${response.statusCode}`),
            );
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    request.setTimeout(5000, () =>
      request.destroy(new Error("Docker stats timeout")),
    );
    request.on("error", reject);
    request.end();
  });
}

async function run(options) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
  const { chromium, expect } = createRequire(
    resolve(root, "frontend/mission-planner/package.json"),
  )("@playwright/test");
  const output = resolve(options.artifacts),
    parent = dirname(output);
  mkdirSync(output, { recursive: true });
  const append = (row) =>
    appendFileSync(
      resolve(output, "samples.jsonl"),
      JSON.stringify(row) + "\n",
    );
  const event = (row) =>
    appendFileSync(
      resolve(output, "events.jsonl"),
      JSON.stringify({ monotonic_seconds: clock(), ...row }) + "\n",
    );
  const browser = await chromium.connectOverCDP(options.session);
  const context = await browser.newContext({
    viewport: null,
    ...(options["record-video"]
      ? {
          recordVideo: {
            dir: resolve(output, "video"),
            size: { width: 1920, height: 1080 },
          },
        }
      : {}),
  });
  await context.addInitScript(installOverviewHistoryProbe);
  const pages = [],
    sessions = [],
    requests = new WeakMap();
  const errors = [];
  let measuring = false;
  const metadata = {
    sha: readFileSync(resolve(parent, "candidate-sha.txt"), "utf8").trim(),
    images: readFileSync(resolve(parent, "images.txt"), "utf8")
      .trim()
      .split("\n"),
    hardware: {
      host: hostname(),
      cpu: cpus()[0]?.model,
      logical_cpus: cpus().length,
      memory_bytes: totalmem(),
    },
    renderer: process.env.OVERVIEW_PROFILE_RENDERER ?? "unknown",
    window_seconds: options.window_seconds,
    viewers: options.viewers,
    cadence_seconds: options.configured_interval_seconds,
    mode: process.env.OVERVIEW_PROFILE_MODE ?? "incremental",
    fixture: "seed-v1-and-public-simulation",
    gc_mode: "controlled",
    warmup_seconds: options.warmup_seconds,
    resource_interval_seconds: 5,
    cleanup: "pending",
    behavior: {},
    upstream_work: "pending",
    browser_version: browser.version(),
    viewport: options.viewport,
    dpr: 1,
    limitations: [
      "Acceptance probes add counters and append-only I/O; cProfile is separate.",
      "Synthetic historical density; public simulation current scrapes.",
      "Configured delay is separate from actual request-start spacing.",
      "Canvas clears are observed redraws, not an exact uPlot setData count.",
    ],
  };
  const save = () =>
    writeFileSync(
      resolve(output, "metadata.json"),
      JSON.stringify(metadata, null, 2),
    );
  save();
  const socket = dockerSocket();
  const capture = async (gc) => {
    const began = clock();
    const [backend, prometheus] = await Promise.all([
      dockerStats(socket, "starlink-224-history-starlink-location-1"),
      dockerStats(socket, "starlink-224-history-prometheus-1"),
    ]);
    if (gc) {
      event({ kind: "gc", stage: "begin" });
      await Promise.all(
        sessions.map((session) => session.send("HeapProfiler.collectGarbage")),
      );
      event({ kind: "gc", stage: "end" });
    }
    const heaps = await Promise.all(
      sessions.map((session) => session.send("Runtime.getHeapUsage")),
    );
    const probes = await Promise.all(
      pages.map((page) =>
        page.evaluate(() => ({
          hidden: document.hidden,
          probe: window.__overviewHistoryProbe.snapshot(),
          panels: document.querySelectorAll("[data-metric-panel]").length,
        })),
      ),
    );
    const row = {
      kind: "resource",
      monotonic_seconds: began,
      backend_cpu_seconds: backend.cpu_stats.cpu_usage.total_usage / 1e9,
      prometheus_cpu_seconds: prometheus.cpu_stats.cpu_usage.total_usage / 1e9,
      backend_rss_bytes:
        backend.memory_stats.stats.anon ??
        backend.memory_stats.stats.rss ??
        backend.memory_stats.usage,
      heap_bytes: heaps.reduce((total, heap) => total + heap.usedSize, 0),
    };
    if (gc) row.post_gc_heap_bytes = row.heap_bytes;
    append(row);
    event({
      kind: "browser_probe",
      probes,
      sampling_ms: (clock() - began) * 1000,
    });
    const response = await fetch(
      `${options.origin}/api/_acceptance/history-profile`,
    );
    if (!response.ok)
      throw new Error(`upstream counter read ${response.status}`);
    event({ kind: "backend_counters", counters: await response.json() });
    metadata.upstream_work = "recorded";
    save();
    return row;
  };
  const history = (request) =>
    new URL(request.url()).pathname === "/api/overview-history" &&
    request.method() === "GET";
  try {
    for (let index = 0; index < options.viewers; index++) {
      const page = await context.newPage();
      const session = await context.newCDPSession(page);
      pages.push(page);
      sessions.push(session);
      const pageId = String(index + 1);
      page.on("request", (request) => {
        if (history(request) && measuring)
          requests.set(request, {
            kind: "request",
            started_seconds: clock(),
            page_id: pageId,
            cold: false,
          });
      });
      page.on("requestfinished", (request) => {
        const row = requests.get(request);
        if (!row) return;
        requests.delete(request);
        request
          .response()
          .then((response) => {
            const status = response?.status() ?? 0;
            append({ ...row, completed_seconds: clock(), status });
            if (status >= 400) errors.push(`history HTTP ${status}`);
          })
          .catch((error) => errors.push(error.message));
      });
      page.on("requestfailed", (request) => {
        const row = requests.get(request);
        if (!row) return;
        requests.delete(request);
        append({ ...row, completed_seconds: clock(), status: 0 });
        errors.push(request.failure()?.errorText ?? "request failed");
      });
      page.on("pageerror", (error) => {
        errors.push(error.message);
        event({ kind: "page_error", message: error.message });
      });
      page.on("console", (message) => {
        if (message.type() === "error") {
          errors.push(message.text());
          event({ kind: "console_error", message: message.text() });
        }
      });
      const target = await session.send("Browser.getWindowForTarget");
      await session.send("Browser.setContentsSize", {
        windowId: target.windowId,
        width: 1920,
        height: 1080,
      });
      await page.goto(`${options.origin}/overview`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.locator("[data-metric-panel]")).toHaveCount(5, {
        timeout: 30000,
      });
      await expect(page.locator(".uplot canvas").first()).toBeVisible({
        timeout: 30000,
      });
      const metrics = await page.evaluate(() => ({
        width: innerWidth,
        height: innerHeight,
        dpr: devicePixelRatio,
      }));
      if (
        metrics.width !== 1920 ||
        metrics.height !== 1080 ||
        metrics.dpr !== 1
      )
        throw new Error(`native viewport mismatch ${JSON.stringify(metrics)}`);
      event({ kind: "native_viewport", page_id: pageId, metrics });
    }
    metadata.behavior.shared_subscription = "pending";
    if (options.controls) {
      for (const window of [
        300,
        900,
        1800,
        3600,
        3601,
        3600,
        1800,
        900,
        300,
        options.window_seconds,
      ]) {
        const response = await pages[0].request.put(
          `${options.origin}/api/overview-history/settings`,
          { data: { window_seconds: window } },
        );
        if (!response.ok())
          throw new Error(`window update ${response.status()}`);
        for (const page of pages) {
          await expect
            .poll(
              () =>
                page.evaluate(
                  () => window.__overviewHistoryProbe.snapshot().lastWindow,
                ),
              { timeout: 20000 },
            )
            .toBe(window);
          await expect
            .poll(
              () =>
                page.evaluate(() =>
                  document.body.textContent.includes("refresh unavailable"),
                ),
              { timeout: 20000 },
            )
            .toBe(false);
        }
        event({ kind: "window_control", window_seconds: window });
      }
      const page = pages.at(-1),
        session = sessions.at(-1);
      await page.bringToFront();
      await page
        .getByRole("button", { name: "Enter fullscreen overview" })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
      await page.screenshot({ path: resolve(output, "native-fullscreen.png") });
      await page.evaluate(() => document.exitFullscreen());
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(false);
      const target = await session.send("Browser.getWindowForTarget");
      await session.send("Browser.setContentsSize", {
        windowId: target.windowId,
        width: 1280,
        height: 720,
      });
      await sleep(1000);
      await session.send("Browser.setContentsSize", {
        windowId: target.windowId,
        width: 1920,
        height: 1080,
      });
      await sleep(1000);
      await session.send("Browser.setWindowBounds", {
        windowId: target.windowId,
        bounds: { windowState: "minimized" },
      });
      await expect.poll(() => page.evaluate(() => document.hidden)).toBe(true);
      const hiddenBefore = await page.evaluate(
        () => window.__overviewHistoryProbe.snapshot().historyParseCount,
      );
      await sleep((options.configured_interval_seconds + 2) * 1000);
      const hiddenAfter = await page.evaluate(
        () => window.__overviewHistoryProbe.snapshot().historyParseCount,
      );
      if (hiddenAfter <= hiddenBefore)
        throw new Error("background history polling stopped");
      event({ kind: "background_polling", hiddenBefore, hiddenAfter });
      await session.send("Browser.setWindowBounds", {
        windowId: target.windowId,
        bounds: { windowState: "normal" },
      });
      await page.bringToFront();
      await expect(page.locator(".uplot canvas").first()).toBeVisible();
      await page.goto(`${options.origin}/configuration`);
      await page.goto(`${options.origin}/overview`);
      await expect(page.locator(".uplot canvas").first()).toBeVisible();
      await expect
        .poll(
          () =>
            page.evaluate(
              () => window.__overviewHistoryProbe.snapshot().lastWindow,
            ),
          { timeout: 20000 },
        )
        .toBe(options.window_seconds);
      const axes = page.locator(".overview-metric-history__value-axis").first();
      const surface = page.locator(".overview-metric-history__surface").first();
      const firstAxis = await axes.boundingBox();
      const before = await surface.evaluate(
        (node) => getComputedStyle(node).transform,
      );
      await sleep(250);
      const after = await surface.evaluate(
        (node) => getComputedStyle(node).transform,
      );
      const lastAxis = await axes.boundingBox();
      if (JSON.stringify(firstAxis) !== JSON.stringify(lastAxis))
        throw new Error("stationary axis moved");
      if (before === after)
        throw new Error("visible history surface did not move");
      event({ kind: "motion_control", before, after, axis: firstAxis });
      metadata.behavior.motion = "passed";
      metadata.behavior.lifecycle = "passed";
      event({ kind: "lifecycle_controls", status: "passed" });
    }
    console.log(
      JSON.stringify({ stage: "warmup", seconds: options.warmup_seconds }),
    );
    for (
      let remaining = options.warmup_seconds;
      remaining > 0;
      remaining -= 30
    ) {
      await sleep(Math.min(30, remaining) * 1000);
      console.log(
        JSON.stringify({
          stage: "warmup",
          remaining: Math.max(0, remaining - 30),
        }),
      );
    }
    await pages.at(-1).screenshot({ path: resolve(output, "warmup.png") });
    const first = await capture(true);
    measuring = true;
    const stop = first.monotonic_seconds + options.requested_measured_seconds;
    let last = first,
      lastGc = first.monotonic_seconds,
      nextProgress = first.monotonic_seconds + 60;
    while (clock() < stop) {
      await sleep(Math.min(5, Math.max(0, stop - clock())) * 1000);
      const final = clock() >= stop;
      const gc = final || clock() - lastGc >= 300;
      last = await capture(gc);
      if (gc) lastGc = last.monotonic_seconds;
      if (last.monotonic_seconds >= nextProgress) {
        console.log(
          JSON.stringify({
            stage: "measuring",
            elapsed: last.monotonic_seconds - first.monotonic_seconds,
            heap_mib: last.heap_bytes / 1024 ** 2,
            backend_rss_mib: last.backend_rss_bytes / 1024 ** 2,
            errors: errors.length,
          }),
        );
        nextProgress += 60;
      }
    }
    measuring = false;
    await sleep(1000);
    await pages.at(-1).screenshot({ path: resolve(output, "end.png") });
    metadata.phase = classifyPhase({
      requested_seconds: options.requested_measured_seconds,
      measured_seconds: last.monotonic_seconds - first.monotonic_seconds,
      warmup_seconds: options.warmup_seconds,
      errors: errors.length,
    });
    metadata.errors = errors;
    save();
    console.log(JSON.stringify({ stage: "complete", ...metadata.phase }));
    if (errors.length)
      throw new Error(`${errors.length} captured browser errors`);
  } catch (error) {
    metadata.phase = { status: "failed", final_acceptance: false };
    metadata.errors = [...errors, error.message];
    save();
    throw error;
  } finally {
    measuring = false;
    await context.close();
    await browser.close();
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.check) console.log(JSON.stringify(options));
    else await run(options);
  } catch (error) {
    console.error(error.stack ?? error.message);
    process.exitCode = 1;
  }
}
