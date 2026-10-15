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

export function subscriptionsComplete(subscriptions, start, end, cadence) {
  // A qualification tolerance for response/GC pauses, not strict one-Hz starts.
  const tolerance = 30;
  return (
    subscriptions.length > 0 &&
    subscriptions.every(
      (entry) =>
        entry.maxActive <= 1 &&
        entry.starts >= 2 &&
        entry.starts <= (end - start) / cadence + 2 &&
        entry.firstStart !== null &&
        entry.lastCompletion !== null &&
        entry.firstStart >= start &&
        entry.firstStart - start <= tolerance &&
        end - entry.lastCompletion <= tolerance &&
        entry.lastCompletion - end <= tolerance &&
        entry.maxStartGap <= tolerance,
    )
  );
}

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

export function expectedOutageError(message, url, active, origin) {
  if (!active || !message.includes("503")) return false;
  const source = new URL(url || origin);
  if (source.origin !== new URL(origin).origin) return false;
  return (
    source.pathname === "/api/overview-history" ||
    (message.startsWith("API Error:") &&
      message.includes("Overview history is temporarily unavailable"))
  );
}

export function expectedNavigationError(message, url, active, origin) {
  if (!active || new URL(url || origin).origin !== new URL(origin).origin)
    return false;
  if (
    message.includes("503") &&
    (new URL(url || origin).pathname === "/api/v2/gps/config" ||
      (message.startsWith("API Error:") &&
        message.includes("GPS configuration not available in simulation mode")))
  )
    return true;
  return (
    message.startsWith("API Error:") &&
    message.includes("status: undefined") &&
    message.includes("message: canceled")
  );
}

export function encodeMovie(encoder, frames, output, elapsed) {
  const input = Buffer.concat(
    Array.from({ length: 20 }, (_, frame) =>
      readFileSync(resolve(frames, `${String(frame).padStart(3, "0")}.jpg`)),
    ),
  );
  if (input.length > 64 * 1024 ** 2)
    throw new Error("bounded video input exceeds 64 MiB");
  execFileSync(
    encoder,
    [
      "-hide_banner",
      "-loglevel",
      "error",
      "-f",
      "image2pipe",
      "-vcodec",
      "mjpeg",
      "-r",
      String(20 / elapsed),
      "-i",
      "pipe:0",
      "-c:v",
      "libvpx",
      "-b:v",
      "1M",
      "-deadline",
      "realtime",
      output,
    ],
    { input, maxBuffer: 1024 ** 2 },
  );
}

export async function measureResources(
  first,
  duration,
  capture,
  { timerClock = clock, wait = sleep, progress = () => {} } = {},
) {
  const stop = first.monotonic_seconds + duration;
  let last = first,
    lastGc = first.monotonic_seconds,
    nextProgress = first.monotonic_seconds + 60;
  while (last.monotonic_seconds < stop) {
    await wait(Math.min(5, Math.max(0, stop - timerClock())) * 1000);
    const gc = timerClock() >= stop || timerClock() - lastGc >= 300;
    last = await capture(gc);
    if (gc) lastGc = last.monotonic_seconds;
    if (last.monotonic_seconds >= nextProgress) {
      progress(last);
      nextProgress += 60;
    }
  }
  return last;
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
  const browser = await chromium.connectOverCDP(options.session, {
    noDefaults: true,
  });
  const context = browser.contexts()[0];
  await context.addInitScript(installOverviewHistoryProbe);
  const pages = [],
    sessions = [],
    requests = new WeakMap();
  const errors = [];
  let measuring = false,
    faultControl = false,
    lifecycleNavigation = false;
  const subscriptions = [];
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
      let page;
      if (index === 0) page = await context.newPage();
      else {
        const rootSession = await browser.newBrowserCDPSession();
        const ready = context.waitForEvent("page");
        await rootSession.send("Target.createTarget", {
          url: "about:blank",
          newWindow: true,
        });
        page = await ready;
        await rootSession.detach();
      }
      const session = await context.newCDPSession(page);
      await session.send("Emulation.setFocusEmulationEnabled", {
        enabled: false,
      });
      pages.push(page);
      sessions.push(session);
      const pageId = String(index + 1);
      const subscription = {
        page_id: pageId,
        starts: 0,
        active: 0,
        maxActive: 0,
        firstStart: null,
        lastStart: null,
        lastCompletion: null,
        maxStartGap: 0,
      };
      subscriptions.push(subscription);
      page.on("request", (request) => {
        if (history(request) && measuring) {
          const started = clock();
          if (subscription.lastStart !== null)
            subscription.maxStartGap = Math.max(
              subscription.maxStartGap,
              started - subscription.lastStart,
            );
          subscription.firstStart ??= started;
          subscription.lastStart = started;
          subscription.starts++;
          subscription.active++;
          subscription.maxActive = Math.max(
            subscription.maxActive,
            subscription.active,
          );
          requests.set(request, {
            kind: "request",
            started_seconds: started,
            page_id: pageId,
            cold: false,
          });
        }
      });
      page.on("requestfinished", (request) => {
        const row = requests.get(request);
        if (!row) return;
        requests.delete(request);
        subscription.active--;
        request
          .response()
          .then((response) => {
            const status = response?.status() ?? 0;
            const completed = clock();
            subscription.lastCompletion = Math.max(
              subscription.lastCompletion ?? 0,
              completed,
            );
            append({ ...row, completed_seconds: completed, status });
            if (status >= 400) errors.push(`history HTTP ${status}`);
          })
          .catch((error) => errors.push(error.message));
      });
      page.on("requestfailed", (request) => {
        const row = requests.get(request);
        if (!row) return;
        requests.delete(request);
        subscription.active--;
        const completed = clock();
        subscription.lastCompletion = Math.max(
          subscription.lastCompletion ?? 0,
          completed,
        );
        append({ ...row, completed_seconds: completed, status: 0 });
        errors.push(request.failure()?.errorText ?? "request failed");
      });
      page.on("pageerror", (error) => {
        errors.push(error.message);
        event({ kind: "page_error", message: error.message });
      });
      page.on("console", (message) => {
        if (message.type() === "error") {
          const expected =
            expectedOutageError(
              message.text(),
              message.location().url,
              faultControl,
              options.origin,
            ) ||
            expectedNavigationError(
              message.text(),
              message.location().url,
              lifecycleNavigation,
              options.origin,
            );
          if (!expected) errors.push(message.text());
          event({
            kind: "console_error",
            message: message.text(),
            expected_control_error: expected,
          });
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
          const label =
            window % 60 === 0
              ? `LAST ${window / 60} MIN`
              : `LAST ${window} SEC`;
          await expect(
            page.locator(".overview-metric-history-panels__windows").first(),
          ).toContainText(label, { timeout: 20000 });
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
      const rootSession = await browser.newBrowserCDPSession();
      const info = await session.send("Target.getTargetInfo");
      const background = await rootSession.send("Target.createTarget", {
        url: "about:blank",
        browserContextId: info.targetInfo.browserContextId,
        newWindow: false,
        background: false,
      });
      await rootSession.send("Target.activateTarget", {
        targetId: background.targetId,
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
      await rootSession.send("Target.closeTarget", {
        targetId: background.targetId,
      });
      await rootSession.detach();
      await page.bringToFront();
      await expect(page.locator(".uplot canvas").first()).toBeVisible();
      lifecycleNavigation = true;
      await page
        .getByRole("link", { name: "Configuration", exact: true })
        .click();
      await expect(page.locator("#overview-history-window")).toBeVisible();
      await sleep(1000);
      await page.getByRole("link", { name: "Overview", exact: true }).click();
      await expect(page.locator(".uplot canvas").first()).toBeVisible();
      await sleep(1000);
      lifecycleNavigation = false;
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
      let before, after;
      for (let attempt = 0; attempt < 10; attempt++) {
        before = await surface.evaluate(
          (node) => getComputedStyle(node).transform,
        );
        await sleep(500);
        after = await surface.evaluate(
          (node) => getComputedStyle(node).transform,
        );
        event({
          kind: "motion_sample",
          before,
          after,
          diagnostic: await page.evaluate(() => ({
            hidden: document.hidden,
            reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
            probe: window.__overviewHistoryProbe.snapshot(),
            statuses: [...document.querySelectorAll("[role=status]")].map(
              (node) => node.textContent,
            ),
          })),
        });
        if (before !== after) break;
      }
      const lastAxis = await axes.boundingBox();
      if (JSON.stringify(firstAxis) !== JSON.stringify(lastAxis))
        throw new Error("stationary axis moved");
      if (before === after)
        throw new Error("visible history surface did not move");
      event({ kind: "motion_control", before, after, axis: firstAxis });
      if (options["record-video"]) {
        const encoder = process.env.OVERVIEW_PROFILE_FFMPEG;
        if (!encoder)
          throw new Error("bounded recording requires OVERVIEW_PROFILE_FFMPEG");
        const frames = resolve(output, "video-frames");
        mkdirSync(frames, { recursive: true });
        await session.send("Profiler.enable");
        await session.send("Profiler.start");
        const began = clock();
        for (let frame = 0; frame < 20; frame++) {
          await page.screenshot({
            path: resolve(frames, `${String(frame).padStart(3, "0")}.jpg`),
            type: "jpeg",
            quality: 75,
          });
          event({ kind: "video_frame", frame });
          await sleep(200);
        }
        const elapsed = clock() - began;
        const profile = await session.send("Profiler.stop");
        await session.send("Profiler.disable");
        writeFileSync(
          resolve(output, "browser-control.cpuprofile"),
          JSON.stringify(profile.profile),
        );
        encodeMovie(
          encoder,
          frames,
          resolve(output, "arrival-rebase.webm"),
          elapsed,
        );
        event({ kind: "bounded_video", frames: 20, elapsed_seconds: elapsed });
      }
      metadata.behavior.motion = "passed";
      const prom = "starlink-224-history-prometheus-1";
      if (
        execFileSync(
          "docker",
          [
            "inspect",
            "--format",
            '{{index .Config.Labels "com.docker.compose.project"}}',
            prom,
          ],
          { encoding: "utf8" },
        ).trim() !== "starlink-224-history"
      )
        throw new Error("fault control ownership mismatch");
      faultControl = true;
      try {
        execFileSync("docker", ["stop", prom], { stdio: "ignore" });
        await expect
          .poll(
            () =>
              page.evaluate(() =>
                document.body.textContent.includes("refresh unavailable"),
              ),
            { timeout: 25000 },
          )
          .toBe(true);
        await expect(page.locator(".uplot canvas")).toHaveCount(5);
        await page.screenshot({
          path: resolve(output, "last-good-outage.png"),
        });
        event({
          kind: "raw_source_outage",
          retained_plots: 5,
          status: "observed",
        });
      } finally {
        execFileSync("docker", ["start", prom], { stdio: "ignore" });
      }
      await expect
        .poll(
          () =>
            page.evaluate(() =>
              document.body.textContent.includes("refresh unavailable"),
            ),
          { timeout: 25000 },
        )
        .toBe(false);
      faultControl = false;
      event({ kind: "raw_source_recovery", status: "observed" });
      metadata.behavior.masking = "passed";
      metadata.behavior.lifecycle = "passed";
      event({ kind: "lifecycle_controls", status: "passed" });
      save();
    }
    if (errors.length)
      throw new Error(`${errors.length} unexpected setup/control errors`);
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
    const last = await measureResources(
      first,
      options.requested_measured_seconds,
      capture,
      {
        progress: (row) =>
          console.log(
            JSON.stringify({
              stage: "measuring",
              elapsed: row.monotonic_seconds - first.monotonic_seconds,
              heap_mib: row.heap_bytes / 1024 ** 2,
              backend_rss_mib: row.backend_rss_bytes / 1024 ** 2,
              errors: errors.length,
            }),
          ),
      },
    );
    measuring = false;
    for (
      let drain = 0;
      drain < 100 && subscriptions.some((entry) => entry.active);
      drain++
    )
      await sleep(100);
    if (subscriptions.some((entry) => entry.active))
      errors.push("history requests did not drain");
    metadata.behavior.shared_subscription = subscriptionsComplete(
      subscriptions,
      first.monotonic_seconds,
      last.monotonic_seconds,
      options.configured_interval_seconds,
    )
      ? "passed"
      : "failed";
    if (metadata.behavior.shared_subscription === "failed")
      errors.push("History subscriptions did not cover the measured period");
    event({ kind: "request_subscriptions", subscriptions });
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
    if (pages.length)
      await pages
        .at(-1)
        .screenshot({ path: resolve(output, "failure.png") })
        .catch(() => {});
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
