/** Proposed real Playwright attachment. Explicit --execute required by launcher. */
import http from "node:http";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { selectPanel, finishFrontend } from "./browser-evidence.mjs";
import { createCollection } from "../perf391-diagnostic-integration-v1/collect.mjs";

const options = JSON.parse(readFileSync(process.argv[2], "utf8"));
if (
  !/^synthetic-[A-Za-z0-9_-]{1,22}$/.test(options.run) ||
  options.samples !== 5
)
  throw Error("fixed synthetic smoke required");
const [major, minor, patch] = process.versions.node.split(".").map(Number);
if (major !== 22 || minor < 22 || (minor === 22 && patch < 2))
  throw Error("reviewed Node 22.22.2 or later 22.x required");
const req = createRequire(join(options.nodeRoot, "package.json"));
if (req("playwright/package.json").version !== "1.63.0")
  throw Error("Playwright identity");
const { chromium } = req("playwright");
if (chromium.executablePath() !== options.chromiumExecutable)
  throw Error("Chromium path differs from receipt");
const save = (name, data) =>
  writeFileSync(
    join(options.output, name),
    JSON.stringify(data, null, 2) + "\n",
  );
mkdirSync(options.output);
save("browser-intent.json", {
  kind: "Playwright launchServer then connect",
  host: "127.0.0.1",
  port: options.browserPort,
  executable: chromium.executablePath(),
  temporaryRoot: process.env.TMPDIR,
});
let server, browser, context, collection, observer, source, closing;
let failed = false;
async function close() {
  if (closing) return closing;
  closing = (async () => {
    try {
      if (observer) save("observer-before-close.json", observer.summary());
      if (collection) save("collection-final.json", await collection.close());
    } finally {
      try {
        await context?.close();
      } finally {
        try {
          await browser?.close();
        } finally {
          await server?.close();
        }
      }
    }
  })();
  return closing;
}
const interrupt = () => {
  failed = true;
  void collection?.close();
  void context?.close().catch(() => {});
};
process.on("SIGINT", interrupt);
process.on("SIGTERM", interrupt);
async function settings(method, path, payload) {
  // Ordinary synthetic operator preference, through unchanged Nginx. Never a body-evidence adapter.
  const data = Buffer.from(JSON.stringify(payload));
  await new Promise((resolve, reject) => {
    let size = 0,
      response,
      done = false;
    const finish = (error) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      response?.destroy();
      request.destroy();
      error ? reject(error) : resolve();
    };
    const request = http.request(
      new URL(path, options.origin),
      {
        method,
        agent: false,
        maxHeaderSize: 16384,
        headers: {
          "content-type": "application/json",
          "content-length": data.length,
        },
      },
      (res) => {
        response = res;
        res.on("data", (chunk) => {
          size += chunk.length;
          if (size > 65536) finish(Error("settings body cap"));
        });
        res.on("error", finish);
        res.on("end", () =>
          finish(
            res.statusCode >= 200 && res.statusCode < 300
              ? null
              : Error("settings status"),
          ),
        );
      },
    );
    const timer = setTimeout(() => finish(Error("settings deadline")), 2000);
    request.on("error", finish);
    request.end(data);
  });
}
try {
  await settings("PUT", "/api/overview-history/settings", {
    window_seconds: 1800,
  });
  await settings("PUT", "/api/overview-links/settings", {
    latency_panel_enabled: true,
    downlink_panel_enabled: false,
    uplink_panel_enabled: false,
    packet_loss_panel_enabled: false,
    obstruction_panel_enabled: false,
  });
  await settings(
    "POST",
    "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-1/activate",
    {},
  );
  if (failed) throw Error("interrupted before browser startup");
  // No CDP attachment to a shared browser. This server and its profile belong to this run.
  server = await chromium.launchServer({
    headless: true,
    host: "127.0.0.1",
    port: options.browserPort,
    executablePath: chromium.executablePath(),
    timeout: 5000,
  });
  if (failed) throw Error("interrupted during browser startup");
  const pid = server.process().pid;
  const stat = readFileSync(`/proc/${pid}/stat`, "utf8")
    .split(") ")
    .at(-1)
    .split(" ");
  save("browser-process.json", {
    pid,
    pgid: Number(stat[2]),
    start_id: stat[19],
    command: readFileSync(`/proc/${pid}/cmdline`, "utf8")
      .split("\0")
      .filter(Boolean),
  });
  if (Number(stat[2]) !== pid)
    throw Error("independent browser process group required");
  browser = await chromium.connect(server.wsEndpoint(), { timeout: 5000 });
  if (failed) throw Error("interrupted during browser connect");
  save("browser-version.json", {
    version: browser.version(),
    executable: chromium.executablePath(),
  });
  context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  if (failed) throw Error("interrupted during context setup");
  const page = await context.newPage();
  if (failed) throw Error("interrupted during page setup");
  // Validate actual 1.63 disposal support before admissions/navigation.
  const handles = [
    await page.exposeBinding("__perf391Compatibility", () => true),
    await page.addInitScript(() => {}),
  ];
  for (const handle of handles) {
    if (typeof handle?.dispose !== "function")
      throw Error("Disposable API unavailable");
    await handle.dispose();
  }
  collection = createCollection(join(options.output, "node"), {
    run: options.run,
    diskBytes: 134217728,
  });
  observer = await collection.browser(page, {
    pageId: "p",
    origin: options.origin,
  });
  source = collection.source({ url: options.source, samples: options.samples });
  await page.goto(options.origin + "/overview", {
    waitUntil: "domcontentloaded",
    timeout: 10000,
  });
  const panel = await selectPanel(page, save);
  // Optional compositor capability remains independent of mandatory chart evidence.
  save(
    "compositor-result.json",
    panel
      ? await observer.screenshot(panel)
      : { outcome: "unavailable", reason: "no visible committed panel" },
  );
  await finishFrontend(page, observer, save);
  // End the browser evidence slice immediately, independently of source observation.
  await observer.close();
  if (observer.summary().failed || observer.summary().lost)
    throw Error("browser final loss");
  await context.close();
  context = undefined;
  const sourceSummary = await source;
  if (
    sourceSummary.failed ||
    sourceSummary.skipped ||
    sourceSummary.completed !== 5
  )
    throw Error("source sample/loss gate");
  const summary = await collection.close();
  if (!summary.complete || summary.dropped || failed)
    throw Error("collection loss");
} catch (error) {
  failed = true;
  save("failure.json", { reason: String(error.message).slice(0, 512) });
  process.exitCode = 1;
} finally {
  await close();
  process.off("SIGINT", interrupt);
  process.off("SIGTERM", interrupt);
  if (failed) process.exitCode = 1;
}
