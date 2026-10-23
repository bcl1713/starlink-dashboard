/** Owned bounded sinks for Stage 3A and source observer. No launch or live CLI. */
import {
  mkdirSync,
  openSync,
  closeSync,
  writeSync,
  writeFileSync,
  readSync,
} from "node:fs";
import { join } from "node:path";
import { randomUUID, createHash } from "node:crypto";
import { createBrowserObserver } from "./browser.mjs";
import { readResponse, observe } from "./observer.mjs";
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
function fileHash(path) {
  const digest = createHash("sha256"),
    fd = openSync(path, "r"),
    buffer = Buffer.alloc(65536);
  try {
    let n;
    while ((n = readSync(fd, buffer, 0, buffer.length, null)))
      digest.update(buffer.subarray(0, n));
    return digest.digest("hex");
  } finally {
    closeSync(fd);
  }
}
export function createCollection(
  root,
  { run, diskBytes = 256 * 1024 * 1024 } = {},
) {
  if (
    !/^synthetic-[A-Za-z0-9_-]{1,22}$/.test(run) ||
    !Number.isSafeInteger(diskBytes) ||
    diskBytes < 16384 ||
    diskBytes > 256 * 1024 * 1024
  )
    throw Error("collection budget/run");
  mkdirSync(root);
  mkdirSync(join(root, "artifacts"));
  const host_identity = {
    process_uuid: randomUUID(),
    pid: process.pid,
    process_start_id: process.hrtime.bigint().toString(),
    clock_id: randomUUID(),
  };
  const fd = openSync(join(root, "records.jsonl"), "wx");
  let used = 0,
    dropped = 0,
    closed = false,
    closing = false,
    seq = 0,
    closingPromise,
    browserAdmissions = 0;
  const screenshotBudget = { screenshots: 0, busy: false };
  const setups = new Set();
  const metadataBudget = Math.min(65536, Math.floor(diskBytes / 4));
  // A finite optional partition cannot consume mandatory chart/source capacity.
  const optionalBudget = Math.min(2 * 1024 * 1024, Math.floor(diskBytes / 8));
  let optionalUsed = 0,
    optionalDropped = 0;
  const optionalPaths = new Set(),
    mandatoryPaths = new Set();
  const mandatoryLimit = diskBytes - metadataBudget - optionalBudget;
  const observers = [],
    sources = new Set(),
    sourceSummaries = [],
    artifacts = {},
    streams = new Map(),
    controller = new AbortController();
  function write(row, { signal } = {}) {
    if (closed || signal?.aborted || controller.signal.aborted) {
      dropped++;
      throw Error("cancelled collection");
    }
    const raw = Buffer.from(
      JSON.stringify({
        host_seq: ++seq,
        host_received_ns: process.hrtime.bigint().toString(),
        ...row,
        host_identity,
      }) + "\n",
    );
    if (
      raw.length > 1024 * 1024 ||
      used - optionalUsed + raw.length > mandatoryLimit
    ) {
      dropped++;
      throw Error("record budget");
    }
    try {
      if (writeSync(fd, raw) !== raw.length) throw Error("short write");
      used += raw.length;
    } catch (error) {
      dropped++;
      throw error;
    }
    if (row.origin === "browser") {
      if (streams.size >= 32 && !streams.has(row.event.stream)) {
        dropped++;
        throw Error("stream budget");
      }
      streams.set(row.event.stream, row.event.seq);
    }
  }
  async function artifact(body, { signal, kind } = {}) {
    const optional = kind === "compositor-png";
    const drop = () => {
      if (optional) optionalDropped++;
      else dropped++;
    };
    if (closed || signal?.aborted || controller.signal.aborted) {
      drop();
      throw Error("cancelled artifact");
    }
    if (
      body.length > 2 * 1024 * 1024 ||
      (optional
        ? optionalPaths.size >= 8 || optionalUsed + body.length > optionalBudget
        : mandatoryPaths.size >= 64 ||
          used - optionalUsed + body.length > mandatoryLimit)
    ) {
      drop();
      throw Error(optional ? "optional artifact budget" : "artifact budget");
    }
    const sha256 = hash(body),
      path = `artifacts/${sha256}.bin`;
    try {
      if (!artifacts[path]) {
        writeFileSync(join(root, path), body, { flag: "wx" });
        used += body.length;
        if (optional) optionalUsed += body.length;
        artifacts[path] = sha256;
      }
      (optional ? optionalPaths : mandatoryPaths).add(path);
      return { path, sha256, bytes: body.length };
    } catch (error) {
      drop();
      throw error;
    }
  }
  async function close() {
    if (closingPromise) return closingPromise;
    closing = true;
    closingPromise = (async () => {
      // Stop admissions first; browser.close aborts and accounts pending jobs.
      controller.abort();
      const summaries = [];
      await Promise.allSettled([...sources, ...setups]);
      try {
        for (const observer of observers) {
          await observer.close();
          summaries.push(observer.summary());
        }
      } finally {
        closeSync(fd);
        closed = true;
      }
      const summary = {
        schema: "perf391-node-collection-v1",
        version: 1,
        run,
        host_identity,
        closed,
        complete:
          !dropped &&
          sourceSummaries.every((s) => s.closed && !s.failed && !s.cancelled) &&
          summaries.every(
            (s) => !s.failed && !s.lost && !s.ownedOperations && !s.bindingJobs,
          ),
        dropped,
        optionalArtifacts: {
          dropped: optionalDropped,
          bytes: optionalUsed,
          limit_bytes: optionalBudget,
        },
        written_bytes: used,
        browsers: summaries,
        sources: sourceSummaries,
        streams: [...streams].map(([stream_id, last_seq]) => ({
          stream_id,
          last_seq,
        })),
        artifacts,
      };
      try {
        const summaryRaw = Buffer.from(JSON.stringify(summary) + "\n");
        const hashes = {
          ...artifacts,
          "records.jsonl": fileHash(join(root, "records.jsonl")),
          "summary.json": hash(summaryRaw),
        };
        const hashRaw = Buffer.from(JSON.stringify(hashes) + "\n");
        if (summaryRaw.length + hashRaw.length > metadataBudget)
          throw Error("metadata budget");
        writeFileSync(join(root, "summary.json"), summaryRaw, { flag: "wx" });
        writeFileSync(join(root, "SHA256SUMS.json"), hashRaw, { flag: "wx" });
      } catch (error) {
        summary.complete = false;
        summary.finalization_unavailable = error.code ?? "disk_error";
      }
      return summary;
    })();
    return closingPromise;
  }
  return {
    write,
    artifact,
    close,
    async browser(page, options) {
      if (closing || browserAdmissions >= 2)
        throw Error("browser owner budget");
      browserAdmissions++;
      const setup = createBrowserObserver(page, {
        ...options,
        run,
        budget: screenshotBudget,
        write: (row, opts) => write({ ...row, page_id: options.pageId }, opts),
        artifact,
      }).then((observer) => {
        observers.push(observer);
        return observer;
      });
      setups.add(setup);
      try {
        return await setup;
      } catch (error) {
        dropped++;
        throw error;
      } finally {
        setups.delete(setup);
      }
    },
    async source(options) {
      if (closing || sources.size || sourceSummaries.length >= 64)
        throw Error("closed collection or active source");
      const read = options.read ?? readResponse;
      const job = observe({
        ...options,
        run,
        signal: controller.signal,
        read: async (args) => {
          const result = await read(args);
          if (result.ok && result.body) {
            const reference = await artifact(result.body, {
              signal: args.signal,
            });
            write({
              origin: "source-body",
              op: args.op,
              artifact: reference,
              status: 200,
            });
          }
          return result;
        },
        write: (row) => write({ origin: "observer", event: row }),
        drain: async () => {},
      });
      sources.add(job);
      try {
        const summary = await job;
        sourceSummaries.push(summary);
        return summary;
      } finally {
        sources.delete(job);
      }
    },
  };
}
