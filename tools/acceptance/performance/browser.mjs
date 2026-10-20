/** Real production Nginx traffic; existing installed Playwright, no downloads. */
import { createRequire } from "node:module";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { request } from "node:http";
import { performance } from "node:perf_hooks";
import { randomUUID } from "node:crypto";

const options = JSON.parse(process.env.PERF_RUN);
const out = (name, value) =>
  writeFileSync(resolve(options.output, name), JSON.stringify(value, null, 2));
const append = (name, value) =>
  appendFileSync(resolve(options.output, name), JSON.stringify(value) + "\n");
const endpoint =
  process.env.DOCKER_HOST ||
  execFileSync(
    "docker",
    ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
    { encoding: "utf8" },
  ).trim();
if (!endpoint.startsWith("unix://"))
  throw new Error("Sampler requires configured Unix actor socket");
function stats(id) {
  return new Promise((accept, reject) => {
    const req = request(
      {
        socketPath: endpoint.slice(7),
        path: `/containers/${id}/stats?stream=false&one-shot=true`,
      },
      (response) => {
        let body = "";
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          if (response.statusCode !== 200)
            return reject(new Error(`Docker stats ${response.statusCode}`));
          try {
            accept(JSON.parse(body));
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    req.setTimeout(5000, () => req.destroy(new Error("Docker stats deadline")));
    req.on("error", reject);
    req.end();
  });
}
async function api(path, method = "GET", body = undefined, headers = {}) {
  const response = await fetch(options.origin + path, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok)
    throw new Error(
      `${method} ${path}: ${response.status} ${await response.text()}`,
    );
  return response.status === 204 ? null : response.json();
}
const memory = (data) => ({
  cpu_seconds: data.cpu_stats.cpu_usage.total_usage / 1e9,
  memory_bytes: data.memory_stats.usage,
  anonymous_bytes:
    data.memory_stats.stats?.anon ?? data.memory_stats.stats?.rss ?? null,
  read_bytes: data.blkio_stats.io_service_bytes_recursive?.length
    ? data.blkio_stats.io_service_bytes_recursive
        .filter((r) => r.op.toLowerCase() === "read")
        .reduce((sum, r) => sum + r.value, 0)
    : null,
  written_bytes: data.blkio_stats.io_service_bytes_recursive?.length
    ? data.blkio_stats.io_service_bytes_recursive
        .filter((r) => r.op.toLowerCase() === "write")
        .reduce((sum, r) => sum + r.value, 0)
    : null,
});
const diskProbe = `
import json,os,urllib.request
from pathlib import Path
result={'storage':{},'sqlite':{},'prometheus_metrics':{}}
for name,root in [('mission', '/app/data/missions'),('operator','/app/data/operator'),('data','/app/data'),('routes_cache_export','/data')]:
 files=[p for p in Path(root).rglob('*') if p.is_file()]
 result['storage'][name+'_bytes']=sum(p.stat().st_size for p in files)
 result['storage'][name+'_allocated_bytes']=sum(p.stat().st_blocks*512 for p in files)
files=[p for root in ['/app/data','/data'] for p in Path(root).rglob('*') if p.is_file()]
result['sqlite']['database_bytes']=sum(p.stat().st_size for p in files if p.suffix in ('.db','.sqlite','.sqlite3'))
result['sqlite']['wal_bytes']=sum(p.stat().st_size for p in files if p.name.endswith('-wal'))
text=urllib.request.urlopen('http://prometheus:9090/metrics',timeout=5).read().decode()
keys={'prometheus_tsdb_head_series','prometheus_tsdb_head_series_created_total','prometheus_tsdb_head_series_removed_total','prometheus_tsdb_storage_blocks_bytes','prometheus_tsdb_wal_storage_size_bytes','prometheus_tsdb_head_chunks_storage_size_bytes'}
for line in text.splitlines():
 if line.split(' ',1)[0] in keys:
  key,value=line.split(' ',1);result['prometheus_metrics'][key]=float(value)
print(json.dumps(result))
`;
let browser,
  server,
  rootSession,
  stopped = false;
const contexts = [],
  pages = [],
  sessions = [],
  latencies = {},
  failures = [],
  requests = new WeakMap();
const cpuByPid = new Map(),
  subscriptions = [];
const started = performance.now();
const seconds = () => (performance.now() - started) / 1000;
let measuring = false,
  inflight = 0,
  maxInflight = 0;
const handler = () => {
  stopped = true;
  void browser?.close();
};
process.on("SIGTERM", handler);
process.on("SIGINT", handler);
const browserMeta = {
  node_version: process.version,
  mode: "headless-diagnostic",
  fullscreen: false,
  viewport: [1920, 1080],
  dpr: 1,
  version: null,
  renderer: null,
};
try {
  await api("/api/overview-history/settings", "PUT", {
    window_seconds: options.window,
  });
  await api(
    "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-1/activate",
    "POST",
  );
  const coldStart = performance.now();
  const history = await api("/api/overview-history");
  out("cold-history.json", {
    elapsed_ms: performance.now() - coldStart,
    window: history.window_seconds,
    step: history.step_seconds,
    series: Object.fromEntries(
      Object.entries(history.series).map(([key, values]) => [
        key,
        {
          points: values.length,
          qualified: values.filter((p) => p[1] !== null).length,
          first: values[0],
          last: values.at(-1),
        },
      ]),
    ),
  });
  if (history.step_seconds !== 1 || history.window_seconds !== options.window)
    throw new Error("History cadence/window differs from workload");
  if (options.viewers || options.operator) {
    const { chromium } = createRequire(
      resolve(options.root, "frontend/mission-planner/package.json"),
    )("@playwright/test");
    server = await chromium.launchServer({
      headless: true,
      args: ["--enable-unsafe-swiftshader", "--window-size=1920,1080"],
      timeout: 30000,
    });
    const processFields = readFileSync(
      `/proc/${server.process().pid}/stat`,
      "utf8",
    )
      .split(") ")[1]
      .trim()
      .split(/\s+/);
    out("browser-owner.json", {
      pid: server.process().pid,
      pgid: Number(processFields[2]),
      start_ticks: processFields[19],
      purpose: "perf390 isolated Chromium",
      command: server.process().spawnargs,
    });
    browser = await chromium.connect(server.wsEndpoint());
    browserMeta.version = browser.version();
    browserMeta.executable_sha256 = execFileSync(
      "sha256sum",
      [server.process().spawnargs[0]],
      { encoding: "utf8", timeout: 10000 },
    ).split(" ")[0];
    rootSession = await browser.newBrowserCDPSession();
    for (let i = 0; i < options.viewers + Number(options.operator); i++) {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
      });
      contexts.push(context);
      await context.addInitScript(() => {
        window.__perf = { longTasks: [], frames: [], lastFrame: null };
        new PerformanceObserver((list) => {
          for (const task of list.getEntries())
            window.__perf.longTasks.push(task.duration);
        }).observe({ type: "longtask", buffered: false });
        function frame(t) {
          const p = window.__perf;
          if (p.lastFrame !== null && p.frames.length < 10000)
            p.frames.push(t - p.lastFrame);
          p.lastFrame = t;
          requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
      const page = await context.newPage();
      pages.push(page);
      const subscription = {
        page: i,
        overview: i < options.viewers,
        starts: 0,
        first: null,
        last: null,
        max_gap_seconds: 0,
      };
      subscriptions.push(subscription);
      page.on("request", (req) => {
        if (measuring && new URL(req.url()).pathname.startsWith("/api/")) {
          if (new URL(req.url()).pathname === "/api/overview-history") {
            const now = seconds();
            subscription.starts++;
            subscription.first ??= now;
            if (subscription.last !== null)
              subscription.max_gap_seconds = Math.max(
                subscription.max_gap_seconds,
                now - subscription.last,
              );
            subscription.last = now;
          }
          requests.set(req, performance.now());
          inflight++;
          maxInflight = Math.max(maxInflight, inflight);
        }
      });
      page.on("requestfinished", async (req) => {
        const start = requests.get(req);
        if (start === undefined) return;
        inflight--;
        const path = new URL(req.url()).pathname;
        const elapsed = performance.now() - start;
        requests.delete(req);
        const response = await req.response();
        if (response?.ok()) (latencies[path] ||= []).push(elapsed);
      });
      page.on("requestfailed", (req) => {
        if (requests.has(req)) {
          inflight--;
          requests.delete(req);
          failures.push({
            path: new URL(req.url()).pathname,
            error: req.failure(),
          });
        }
      });
      page.on("response", (response) => {
        if (
          measuring &&
          response.status() >= 400 &&
          !(
            new URL(response.url()).pathname === "/api/v2/gps/config" &&
            response.status() === 503
          )
        )
          failures.push({
            path: new URL(response.url()).pathname,
            status: response.status(),
          });
      });
      const cdp = await context.newCDPSession(page);
      sessions.push(cdp);
      await cdp.send("Performance.enable");
      await page.goto(
        options.origin + (i < options.viewers ? "/overview" : "/operator"),
        { waitUntil: "domcontentloaded", timeout: 60000 },
      );
      if (i === 0)
        browserMeta.renderer = await page.evaluate(() => {
          const gl = document.createElement("canvas").getContext("webgl2");
          const ext = gl?.getExtension("WEBGL_debug_renderer_info");
          return ext
            ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)
            : "unavailable";
        });
    }
  }
  out("browser.json", browserMeta);
  const readyAt = seconds();
  const end = readyAt + options.warmup + options.duration;
  let nextSample = readyAt,
    nextDisk = 0,
    operation = 0;
  while (!stopped) {
    const now = seconds(),
      elapsed = now - readyAt;
    if (!measuring && elapsed >= options.warmup) {
      measuring = true;
      if (options.instrumentation === "counters")
        await api("/api/_acceptance/performance");
      for (const page of pages)
        await page.evaluate(() => {
          window.__perf.frames = [];
          window.__perf.longTasks = [];
        });
    }
    if (now < nextSample) {
      await new Promise((accept) =>
        setTimeout(accept, Math.min(200, (nextSample - now) * 1000)),
      );
      continue;
    }
    const sampleStart = performance.now();
    const [backend, prom] = await Promise.all([
      stats(options.containers["starlink-location"]),
      stats(options.containers.prometheus),
    ]);
    const row = {
      seconds: elapsed,
      phase: measuring ? "measured" : "warmup",
      backend: memory(backend),
      prometheus: memory(prom),
      browser: {},
      sqlite: {},
      storage: {},
      latency: {},
      outstanding_requests: inflight,
      max_outstanding_requests: maxInflight,
    };
    if (browser) {
      const processes = (await rootSession.send("SystemInfo.getProcessInfo"))
        .processInfo;
      for (const p of processes)
        cpuByPid.set(p.id, Math.max(cpuByPid.get(p.id) || 0, p.cpuTime));
      row.browser.cpu_seconds = [...cpuByPid.values()].reduce(
        (s, v) => s + v,
        0,
      );
      const memoryRows = processes.map((p) => {
        try {
          const text = readFileSync(`/proc/${p.id}/smaps_rollup`, "utf8");
          return {
            pid: p.id,
            type: p.type,
            cpu_seconds: p.cpuTime,
            rss: Number(text.match(/^Rss:\s+(\d+)/m)[1]) * 1024,
            pss: Number(text.match(/^Pss:\s+(\d+)/m)[1]) * 1024,
          };
        } catch {
          return { pid: p.id, type: p.type, rss: null, pss: null };
        }
      });
      append("browser-processes.jsonl", {
        seconds: elapsed,
        processes: memoryRows,
      });
      row.browser.rss_bytes = memoryRows.every((p) => p.rss !== null)
        ? memoryRows.reduce((s, p) => s + p.rss, 0)
        : null;
      row.browser.pss_bytes = memoryRows.every((p) => p.pss !== null)
        ? memoryRows.reduce((s, p) => s + p.pss, 0)
        : null;
      row.browser.heap_bytes = 0;
      row.browser.task_seconds = 0;
      row.browser.frame_count = 0;
      row.browser.long_task_ms = 0;
      row.latency.frame = [];
      for (let i = 0; i < pages.length; i++) {
        const data = await sessions[i].send("Runtime.getHeapUsage");
        row.browser.heap_bytes += data.usedSize;
        const metrics = Object.fromEntries(
          (await sessions[i].send("Performance.getMetrics")).metrics.map(
            (m) => [m.name, m.value],
          ),
        );
        row.browser.task_seconds += metrics.TaskDuration;
        const paint = await pages[i].evaluate(() => {
          const p = window.__perf;
          const result = {
            frames: p.frames,
            longTasks: p.longTasks,
            hidden: document.hidden,
          };
          p.frames = [];
          p.longTasks = [];
          return result;
        });
        row.latency.frame.push(...paint.frames);
        row.browser.frame_count += paint.frames.length;
        row.browser.long_task_ms += paint.longTasks.reduce((s, v) => s + v, 0);
        append("browser-pages.jsonl", {
          seconds: elapsed,
          page: i,
          hidden: paint.hidden,
          metrics,
        });
      }
    }
    const statusStart = performance.now();
    await api("/api/status");
    row.latency["observer_status"] = [performance.now() - statusStart];
    if (options.operator) {
      const t = performance.now();
      await api("/api/v2/operator/records?mission_id=synthetic-mission-a");
      row.latency["observer_operator_read"] = [performance.now() - t];
    }
    if (options.instrumentation === "counters") {
      const probe = await api("/api/_acceptance/performance");
      append("backend-counters.jsonl", {
        seconds: elapsed,
        phase: row.phase,
        ...probe,
      });
      row.sqlite = Object.fromEntries(
        Object.entries(probe.counts).filter(
          ([key]) => !["ticks", "http_requests"].includes(key),
        ),
      );
      Object.assign(
        row.latency,
        Object.fromEntries(
          Object.entries(probe.timings).map(([key, values]) => [
            "backend_" + key,
            values,
          ]),
        ),
      );
      row.prometheus.range_queries = probe.queries.count;
      row.prometheus.planned_evaluation_points =
        probe.queries.evaluation_points;
    }
    if (now >= nextDisk) {
      const data = JSON.parse(
        execFileSync(
          "docker",
          [
            "exec",
            options.containers["starlink-location"],
            "python",
            "-c",
            diskProbe,
          ],
          { encoding: "utf8", timeout: 15000 },
        ),
      );
      Object.assign(row.storage, data.storage);
      Object.assign(row.sqlite, data.sqlite);
      Object.assign(row.prometheus, data.prometheus_metrics);
      nextDisk = now + 30;
    }
    for (const [path, values] of Object.entries(latencies)) {
      row.latency[path] = values;
      delete latencies[path];
    }
    row.instrumentation = { sample_wall_ms: performance.now() - sampleStart };
    row.subscriptions = subscriptions.map((s) => ({ ...s }));
    append("samples.jsonl", row);
    if (
      options.operations &&
      measuring &&
      elapsed - options.warmup >= ((operation + 1) * options.duration) / 4 &&
      operation < 3
    ) {
      const action = operation++;
      const path =
        action === 0
          ? "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-2/activate"
          : action === 1
            ? "/api/v2/missions/synthetic-mission-a/legs/deactivate"
            : "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-1/activate";
      const t = performance.now();
      const result = await api(path, "POST");
      append("operations.jsonl", {
        seconds: elapsed,
        path,
        elapsed_ms: performance.now() - t,
        result,
      });
      const health = await api("/api/v2/operator/health");
      const receipt = await api(
        "/api/v2/operator/records",
        "POST",
        {
          schema_version: 1,
          record_type: "journal_entry",
          mission_id: "synthetic-mission-a",
          scope: "mission",
          time: {
            occurred_at: new Date().toISOString(),
            precision: "exact",
            end_state: "instant",
          },
          payload: {
            entry_type: "note",
            title: `Synthetic measured operation ${action}`,
            note: "Fictional performance workload",
          },
        },
        {
          "Idempotency-Key": randomUUID(),
          "X-Operator-Store-Epoch": health.api_epoch,
          "X-Operator-Replay-Id":
            health.operating_context_id ||
            health.replay_run_id ||
            `idle:${health.simulation_run_id}`,
        },
      );
      append("operations.jsonl", {
        seconds: elapsed,
        operation: "journal_write",
        receipt,
      });
    }
    if (now >= end) break;
    nextSample += 5;
    if (seconds() > nextSample + 5) nextSample = seconds() + 5;
  }
  if (stopped) throw new Error("Measurement interrupted");
  out("polling.json", subscriptions);
  const final = await api("/api/overview-history");
  out("final-history.json", {
    end: final.end_timestamp_seconds,
    step: final.step_seconds,
    series: Object.fromEntries(
      Object.entries(final.series).map(([k, v]) => [
        k,
        {
          points: v.length,
          qualified: v.filter((p) => p[1] !== null).length,
          last: v.at(-1),
        },
      ]),
    ),
  });
  if (
    subscriptions.some(
      (s) => s.overview && (s.starts < 2 || s.max_gap_seconds > 5),
    )
  )
    throw new Error("Overview polling coverage failed; inspect polling.json");
  for (let i = 0; i < pages.length; i++)
    await pages[i].screenshot({
      path: resolve(options.output, `page-${i}.png`),
    });
  out("failures.json", failures);
  if (failures.length)
    throw new Error(
      "Unexpected browser requests failed; this run is not a valid baseline (failures.json)",
    );
  if (options.instrumentation === "counters") {
    measuring = false;
    await api("/api/_acceptance/arm-profile", "POST");
    await new Promise((accept) => setTimeout(accept, 3000));
  }
} finally {
  for (const context of contexts) await context.close().catch(() => {});
  await browser?.close();
  await server?.close();
  out("browser-cleanup.json", {
    closed: true,
    pid: server?.process().pid ?? null,
    exitCode: server?.process().exitCode ?? null,
  });
}
