/** Short synthetic diagnostic, never an acceptance harness. No payload logging. */
import { validateWorkload, wireRequestId } from "./workload.mjs";
import { channel } from "node:diagnostics_channel";
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { execFileSync } from "node:child_process";
const o = JSON.parse(process.env.PERF_RUN);
const browserErrors = [];
let workloadEvidence, measurementStart, measurementEnd;
const events = [],
  captures = [],
  traffic = [],
  contexts = [];
let browser,
  server,
  cancelled = false,
  sequence = 0;
const ns = () => Math.round(performance.now() * 1e6);
const record = (event, fields = {}) =>
  events.push({ event, ns: ns(), ...fields });
channel("undici:client:sendHeaders").subscribe(({ headers }) => {
  const id = wireRequestId(headers);
  if (id) record("http.wire_send", { op: id });
});
const out = (name, value) =>
  writeFileSync(resolve(o.output, name), JSON.stringify(value));
const handler = () => {
  cancelled = true;
  void browser?.close();
};
process.on("SIGTERM", handler);
process.on("SIGINT", handler);
let loopActive = true;
const loop = (async () => {
  while (loopActive) {
    const scheduled = ns() + 50e6;
    await delay(50);
    record("loop.wake", {
      scheduled_ns: scheduled,
      delay_ns: Math.max(0, ns() - scheduled),
    });
  }
})();
async function api(path, method = "GET", body) {
  const r = await fetch(o.origin + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!r.ok) throw new Error("Setup HTTP " + r.status);
  return r.status === 204 ? null : r.json();
}
function backendCPU() {
  return JSON.parse(
    execFileSync(
      "docker",
      [
        "exec",
        o.containers["starlink-location"],
        "python",
        "-c",
        'import json; from pathlib import Path; print(json.dumps({"cpu_stat":Path("/sys/fs/cgroup/cpu.stat").read_text(),"schedstat":Path("/proc/1/schedstat").read_text()}))',
      ],
      { encoding: "utf8", timeout: 10000 },
    ),
  );
}
let faultTimer,
  initialCPU,
  finalCPU,
  initialObserverCPU,
  finalObserverCPU,
  elapsed,
  failure;
try {
  await api("/api/overview-history/settings", "PUT", { window_seconds: 1800 });
  await api(
    "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-1/activate",
    "POST",
  );
  await api("/api/overview-history");
  if (o.viewers || o.operator) {
    const { chromium } = createRequire(
      resolve(
        process.env.PERF391_BROWSER_ROOT || o.root,
        "frontend/mission-planner/package.json",
      ),
    )("@playwright/test");
    server = await chromium.launchServer({
      headless: true,
      args: ["--enable-unsafe-swiftshader", "--window-size=1920,1080"],
    });
    const fields = readFileSync(`/proc/${server.process().pid}/stat`, "utf8")
      .split(") ")[1]
      .trim()
      .split(/\s+/);
    out("browser-owner.json", {
      pid: server.process().pid,
      pgid: Number(fields[2]),
      start_ticks: fields[19],
      command: server.process().spawnargs,
    });
    browser = await chromium.connect(server.wsEndpoint());
    for (let i = 0; i < o.viewers + Number(o.operator); i++) {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
      });
      contexts.push(context);
      const page = await context.newPage();
      page.on("pageerror", () =>
        browserErrors.push({ page: i, kind: "pageerror", ns: ns() }),
      );
      page.on("requestfailed", (r) => {
        if (!cancelled)
          browserErrors.push({
            page: i,
            kind: "requestfailed",
            path: new URL(r.url()).pathname,
            ns: ns(),
          });
      });
      page.on("response", (r) => {
        const p = new URL(r.url()).pathname;
        if (p.startsWith("/api/"))
          traffic.push({ page: i, path: p, status: r.status(), ns: ns() });
      });
      await page.goto(o.origin + (i < o.viewers ? "/overview" : "/operator"), {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      if (i < o.viewers)
        await page
          .locator('[aria-label="Overview controls and metrics"]')
          .waitFor({ timeout: 30000 });
      else
        await page
          .getByRole("heading", { name: "Operator", exact: true })
          .waitFor({ timeout: 30000 });
    }
    out("browser.json", {
      history_step_seconds: 1,
      version: browser.version(),
      contexts: contexts.length,
    });
  } else out("browser.json", { history_step_seconds: 1, contexts: 0 });
  await delay(o.warmup * 1000);
  initialCPU = backendCPU();
  initialObserverCPU = process.cpuUsage();
  const start = ns();
  measurementStart = start;
  if (process.env.PERF391_STOP_MODE === "failure")
    throw new Error("Deliberate diagnostic failure");
  if (process.env.PERF391_STOP_MODE === "timeout") await delay(300000);
  const faults =
    process.env.PERF391_FAULTS === "1"
      ? [
          "dispatch",
          "worker",
          "admission",
          "collection",
          "frame_prepare",
          "source_validation",
          "publication",
          "lock_hold",
          "backend_loop",
          "response",
        ]
      : [];
  let faultIndex = 0;
  if (faults.length)
    faultTimer = setInterval(() => {
      const boundary = faults[faultIndex++];
      if (boundary) void api("/api/_diagnostic/fault/" + boundary, "POST");
    }, 3500);
  let next = start,
    index = 0;
  while (!cancelled && ns() - start < o.duration * 1e9) {
    await delay(Math.max(0, (next - ns()) / 1e6));
    const id = "diag-" + sequence++,
      scheduled = next;
    record("observer.wake", {
      op: id,
      scheduled_ns: scheduled,
      delay_ns: Math.max(0, ns() - scheduled),
    });
    if (process.env.PERF391_FAULTS === "1" && index === 2) {
      record("injection", { boundary: "observer_loop", duration_ns: 700e6 });
      const until = ns() + 700e6;
      while (ns() < until) {
        /* deliberate fault */
      }
    }
    try {
      record("http.send", { op: id });
      const response = await fetch(o.origin + "/api/_diagnostic/state", {
        headers: { "x-diagnostic-id": id },
        signal: AbortSignal.timeout(1000),
      });
      record("http.headers", { op: id, status: response.status });
      const s = await response.json();
      record("http.body", { op: id });
      captures.push({
        op: id,
        capture_ns: s.diagnostic_capture_ns ?? null,
        age_seconds: s.acquisition_age_seconds,
        capture_wall_ms: s.capture_wall_ms,
        capture_cpu_ms: s.capture_thread_cpu_ms,
        publication: s.publication.state,
      });
    } catch (e) {
      record("http.error", { op: id, error: e.name });
    }
    next += 1e9;
    index++;
  }
  measurementEnd = ns();
  workloadEvidence = validateWorkload(
    traffic,
    browserErrors,
    o.viewers,
    o.operator,
    start,
    measurementEnd,
  );
  elapsed = measurementEnd - start;
  finalObserverCPU = process.cpuUsage(initialObserverCPU);
  finalCPU = backendCPU();
} catch (e) {
  failure = e.message;
  throw e;
} finally {
  clearInterval(faultTimer);
  loopActive = false;
  await loop;
  for (const context of contexts) {
    for (const page of context.pages()) page.removeAllListeners();
    await context.close().catch(() => {});
  }
  await browser?.close().catch(() => {});
  await server?.close().catch(() => {});
  out("observer.json", {
    clock: "observer-local monotonic nanoseconds",
    events,
    captures,
    traffic,
    browser_errors: browserErrors,
    workload_evidence: workloadEvidence,
    measurement_start_ns: measurementStart,
    measurement_end_ns: measurementEnd,
    cancelled,
    failure,
    elapsed_ns: elapsed,
    observer_cpu_us: finalObserverCPU,
    backend_before: initialCPU,
    backend_after: finalCPU,
  });
}
if (cancelled) throw new Error("Diagnostic cancelled");
