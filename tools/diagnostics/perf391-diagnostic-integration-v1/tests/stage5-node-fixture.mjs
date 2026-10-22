/** Offline fixture generator: fake Page only; no network or browser launch. */
import { EventEmitter } from "node:events";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { createCollection } from "../collect.mjs";
const root = process.argv[2];
const run = "synthetic-stage5";
const identity = {
  process_uuid: "33333333-3333-4333-8333-333333333333",
  pid: 79,
  process_start_id: "fixture-node-start",
  clock_id: "fixture-node-clock",
};
class Page extends EventEmitter {
  bindings = new Map();
  async exposeBinding(name, fn) {
    this.bindings.set(name, fn);
    return { dispose: async () => this.bindings.delete(name) };
  }
  async addInitScript() {
    return { dispose: async () => {} };
  }
}
const page = new Page();
const owner = createCollection(root, { run });
try {
  const browser = await owner.browser(page, {
    pageId: "p",
    origin: "http://127.0.0.1:18080",
    now: () => "1000",
  });
  const op = `${run}/p/doc/r1`;
  const request = {
    url: () => "http://127.0.0.1:18080/api/overview-history",
    headers: () => ({ "x-diagnostic-id": op }),
    method: () => "GET",
  };
  page.emit("request", request);
  page.emit("response", {
    request: () => request,
    headers: () => ({}),
    status: () => 200,
  });
  page.emit("requestfinished", request);
  const history = {
    window_seconds: 60,
    start_timestamp_seconds: 1,
    end_timestamp_seconds: 3,
    step_seconds: 1,
    series: {
      latency: [
        [1, 2],
        [2, 3],
        [3, 4],
      ],
    },
  };
  const details = {
    accepted: "bundle1",
    acceptedRequest: op,
    metric: "latency",
    commit: "plot1",
    retained: history,
    projection: { times: [1, 2, 3] },
    logFloor: 1,
    plot: {
      data: [
        [1, 2, 3],
        [null, null, null],
        [null, null, null],
        [null, null, null],
        [2, 3, 4],
      ],
      scales: { x: { min: 1, max: 3 } },
    },
  };
  const binding = [...page.bindings.values()][0];
  const events = [
    ["app.request", {}],
    ["app.response", {}],
    ["app.parse_available", { bundle: "bundle1", metric: "latency", history }],
    ["query.success", {}],
    ["history.retained", { commit: "plot1" }],
    ["plot.commit", details],
  ];
  for (const [index, [phase, detail]] of events.entries()) {
    const seq = index + 1;
    const event = {
      run,
      stream: `${run}/p/doc`,
      clock: "browser/p/doc",
      seq,
      monotonic_ms: seq,
      phase,
      op,
      outcome: "ok",
      detail,
    };
    if (
      !(await binding(
        { page },
        {
          run,
          page: "p",
          document: "doc",
          seq,
          total: 1,
          part: 0,
          payload: JSON.stringify(event),
        },
      ))
    )
      throw Error("fixture rejected");
  }
  await new Promise(setImmediate);
  await browser.close();
} finally {
  const result = await owner.close();
  if (!result.complete || page.bindings.size)
    throw Error("fixture cleanup/integrity");
}
// Explicit fixture normalization: these are synthetic identities, never runtime measurements.
const records = readFileSync(join(root, "records.jsonl"), "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
for (const [i, row] of records.entries()) {
  row.host_identity = identity;
  row.host_received_ns = String(1000 + i * 10);
}
writeFileSync(
  join(root, "records.jsonl"),
  records.map(JSON.stringify).join("\n") + "\n",
);
const summary = JSON.parse(readFileSync(join(root, "summary.json")));
summary.host_identity = identity;
summary.written_bytes =
  Buffer.byteLength(readFileSync(join(root, "records.jsonl"))) +
  Object.keys(summary.artifacts).reduce(
    (n, path) => n + readFileSync(join(root, path)).length,
    0,
  );
writeFileSync(join(root, "summary.json"), JSON.stringify(summary) + "\n");
const hashes = JSON.parse(readFileSync(join(root, "SHA256SUMS.json")));
for (const path of Object.keys(hashes))
  hashes[path] = createHash("sha256")
    .update(readFileSync(join(root, path)))
    .digest("hex");
writeFileSync(join(root, "SHA256SUMS.json"), JSON.stringify(hashes) + "\n");
