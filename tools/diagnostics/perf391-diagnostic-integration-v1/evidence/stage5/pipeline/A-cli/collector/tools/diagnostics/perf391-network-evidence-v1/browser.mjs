/** Passive Playwright Page adapter, no Playwright dependency or app injection. */
import { validateEvent } from "./browser-schema.mjs";
import { createHash, randomUUID } from "node:crypto";
import {
  openSync,
  writeSync,
  closeSync,
  mkdirSync,
  existsSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

const ns = () => process.hrtime.bigint().toString();

export function createSink(
  root,
  {
    runId = "offline",
    maxDiskBytes = 256 * 1024 ** 2,
    maxEventBytes = 1024 ** 2,
    maxBodyBytes = 2 * 1024 ** 2,
  } = {},
) {
  if (maxDiskBytes <= 4096 || maxEventBytes <= 0 || maxBodyBytes <= 0)
    throw Error("invalid limits");
  mkdirSync(root, { recursive: true });
  const fd = openSync(join(root, "events.jsonl"), "wx");
  const clockId = `node-${randomUUID()}`;
  let seq = 0,
    bytes = 0,
    dropped = 0,
    droppedBodies = 0,
    closed = false,
    writeNs = 0n;
  const row = (kind, data, meta = {}) => ({
    schema: "perf391-network-evidence-v1",
    version: 1,
    kind,
    run_id: runId,
    stream_id: clockId,
    seq: ++seq,
    clock_id: clockId,
    mono_ns: ns(),
    pid: process.pid,
    tid: 0,
    thread_cpu_ns: null,
    op_id: meta.opId ?? null,
    span_id: null,
    data,
  });
  function write(raw) {
    const start = process.hrtime.bigint();
    writeSync(fd, raw);
    bytes += Buffer.byteLength(raw);
    writeNs += process.hrtime.bigint() - start;
  }
  return {
    maxBodyBytes,
    drop() {
      dropped++;
    },
    emit(kind, data, meta) {
      if (closed) throw Error("closed sink");
      let raw;
      try {
        raw = JSON.stringify(validateEvent(row(kind, data, meta))) + "\n";
      } catch (error) {
        dropped++;
        throw error;
      }
      if (
        Buffer.byteLength(raw) > maxEventBytes ||
        bytes + Buffer.byteLength(raw) > maxDiskBytes - 4096
      ) {
        dropped++;
        return false;
      }
      write(raw);
      return true;
    },
    unavailableBody(reason, size = 0) {
      droppedBodies++;
      return {
        state: "unavailable",
        path: null,
        sha256: null,
        bytes: size,
        reason,
      };
    },
    artifact(body) {
      if (closed) throw Error("closed sink");
      if (
        body.length > maxBodyBytes ||
        bytes + body.length > maxDiskBytes - 4096
      )
        return this.unavailableBody("body_or_disk_limit", body.length);
      const sha256 = createHash("sha256").update(body).digest("hex");
      const path = `bodies/${sha256}.bin`;
      mkdirSync(join(root, "bodies"), { recursive: true });
      if (!existsSync(join(root, path))) {
        const start = process.hrtime.bigint();
        writeFileSync(join(root, path), body, { flag: "wx" });
        writeNs += process.hrtime.bigint() - start;
        bytes += body.length;
      }
      return {
        state: "available",
        path,
        sha256,
        bytes: body.length,
        reason: null,
      };
    },
    close() {
      if (closed) return;
      try {
        write(
          JSON.stringify(
            row("summary", {
              dropped_events: dropped,
              dropped_bodies: droppedBodies,
              written_bytes: bytes,
              write_wall_ns: writeNs.toString(),
              reason: "closed",
            }),
          ) + "\n",
        );
      } finally {
        closeSync(fd);
        closed = true;
      }
    },
  };
}

export function attachHistory(
  page,
  sink,
  { viewer, segment = "measured", maxActive = 8 } = {},
) {
  if (!viewer || !Number.isInteger(maxActive) || maxActive < 1)
    throw Error("viewer and positive maxActive required");
  const requests = new Map(),
    jobs = new Set(),
    responding = new Set(),
    networkDone = new Set(),
    bodyDone = new Set();
  let sequence = 0,
    closed = false;
  const mark = (name, id) =>
    sink.emit("boundary", { name: `browser.${name}` }, { opId: id });
  const coverage = (boundary, reason) =>
    sink.emit("coverage", { boundary, available: false, reason });
  for (const boundary of [
    "browser.parse",
    "browser.callback",
    "browser.bundle_commit",
    "plot.input",
    "paint",
  ])
    coverage(
      boundary,
      "external Page events cannot inspect this boundary; separate diagnostic build required",
    );
  sink.emit("anchor", {
    utc_ns: (BigInt(Date.now()) * 1000000n).toString(),
    uncertainty_ns: "1000000",
  });
  function request(r) {
    if (new URL(r.url()).pathname !== "/api/overview-history") return;
    if (requests.size >= maxActive || jobs.size >= maxActive) {
      sink.drop();
      return;
    }
    const id = `${viewer}-poll-${++sequence}`;
    requests.set(r, id);
    mark("request", id);
  }
  function response(r) {
    const id = requests.get(r.request());
    if (!id) return;
    if (responding.has(r.request())) {
      sink.drop();
      return;
    }
    responding.add(r.request());
    mark("headers", id);
    const job = (async () => {
      let artifact;
      try {
        const headers = r.headers();
        const length = Number(headers["content-length"]);
        if (
          !Number.isSafeInteger(length) ||
          length < 0 ||
          length > sink.maxBodyBytes ||
          headers["content-encoding"]
        ) {
          artifact = sink.unavailableBody(
            "bounded_uncompressed_content_length_required",
            Number.isSafeInteger(length) && length >= 0 ? length : 0,
          );
        } else {
          const body = await r.body();
          if (closed) return;
          artifact = sink.artifact(body);
          mark("body", id);
          if (artifact.state === "available" && !closed) {
            const h = JSON.parse(body.toString("utf8"));
            sink.emit(
              "history",
              {
                viewer,
                request_id: id,
                bundle_id: id,
                start: h.start_timestamp_seconds,
                end: h.end_timestamp_seconds,
                step: h.step_seconds,
                series: h.series,
                ...(h.rolling_5m ? { rolling_5m: h.rolling_5m } : {}),
                segment,
                artifact,
              },
              { opId: id },
            );
          }
        }
        sink.emit(
          "body",
          { viewer, request_id: id, status: r.status(), artifact },
          { opId: id },
        );
      } catch (error) {
        if (!closed) coverage("browser.response_body", error.name);
      }
    })();
    jobs.add(job);
    const cleanup = () => {
      jobs.delete(job);
      responding.delete(r.request());
      if (!requests.has(r.request())) return;
      bodyDone.add(r.request());
      if (networkDone.has(r.request())) {
        requests.delete(r.request());
        networkDone.delete(r.request());
        bodyDone.delete(r.request());
      }
    };
    void job.then(cleanup, cleanup);
  }
  function finished(r) {
    const id = requests.get(r);
    if (id) {
      mark("end", id);
      networkDone.add(r);
      if (bodyDone.has(r)) {
        requests.delete(r);
        networkDone.delete(r);
        bodyDone.delete(r);
      }
    }
  }
  function failed(r) {
    const id = requests.get(r);
    if (id) {
      mark("failed", id);
      requests.delete(r);
      networkDone.delete(r);
      bodyDone.delete(r);
    }
  }
  page.on("request", request);
  page.on("response", response);
  page.on("requestfinished", finished);
  page.on("requestfailed", failed);
  return {
    async close() {
      if (closed) return { pending: jobs.size, requests: 0 };
      // Detach first, then drain; owner must close its context if body() hangs.
      page.off("request", request);
      page.off("response", response);
      page.off("requestfinished", finished);
      page.off("requestfailed", failed);
      let timer;
      await Promise.race([
        Promise.allSettled([...jobs]),
        new Promise((resolve) => {
          timer = setTimeout(resolve, 1000);
        }),
      ]);
      clearTimeout(timer);
      const pending = jobs.size;
      for (let i = 0; i < pending; i++) sink.drop();
      if (pending || requests.size)
        coverage(
          "browser.cleanup",
          `pending_bodies=${pending}; pending_requests=${requests.size}; close owned context before sink`,
        );
      const requestCount = requests.size;
      closed = true;
      requests.clear();
      networkDone.clear();
      bodyDone.clear();
      responding.clear();
      return { pending, requests: requestCount };
    },
  };
}

/** Called only by a separately built diagnostic hook with the actual uPlot.
 * Never discovers, patches, exposes, or fabricates application plot state.
 * Paint intervals require separately reviewed screenshot/video evidence.
 */
export function recordPlot(
  sink,
  {
    plot,
    viewer,
    requestId,
    bundleId,
    series,
    moduleHashes,
    retainedHistory,
    segment = "measured",
    logFloor = null,
    visibleGaps = null,
    paintEvidence = null,
  },
) {
  const [times, max, min, avg, observed] = plot.data;
  return sink.emit(
    "chart",
    {
      viewer,
      request_id: requestId,
      bundle_id: bundleId,
      series,
      segment,
      times: [...times],
      traces: {
        observed: [...observed],
        min: [...min],
        avg: [...avg],
        max: [...max],
      },
      viewport: [plot.scales.x.min, plot.scales.x.max],
      visible_gaps: visibleGaps,
      ...(retainedHistory ? { projection_input: retainedHistory } : {}),
      module_hashes: moduleHashes,
      paint_evidence: paintEvidence,
      input_stage: "plot",
      log_floor: logFloor,
    },
    { opId: requestId },
  );
}
