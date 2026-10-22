/** Supplemental source observer. Importing never sends traffic or starts timers. */
import http from "node:http";
import { createGunzip } from "node:zlib";
import { TextDecoder } from "node:util";
import { setTimeout as sleep } from "node:timers/promises";
export const LIMITS = Object.freeze({
  body: 2 * 1024 * 1024,
  headers: 64 * 1024,
  deadline: 2000,
  period: 1000000000n,
});
function endpoint(url) {
  const u = new URL(url);
  if (
    u.protocol !== "http:" ||
    !["127.0.0.1", "[::1]"].includes(u.hostname) ||
    u.pathname !== "/api/_diagnostic/state" ||
    u.search ||
    u.hash ||
    u.username ||
    u.password
  )
    throw Error("dedicated loopback diagnostic endpoint required");
  return u;
}
export async function readResponse({
  url,
  op,
  request = http.request,
  signal,
  mark = () => {},
  timers = globalThis,
}) {
  const target = endpoint(url);
  if (!/^[\x21-\x7e]{1,96}$/.test(op)) throw Error("operation identity");
  return new Promise((resolve) => {
    let req,
      res,
      decoder,
      timer,
      done = false,
      encoded = 0,
      decoded = 0;
    const chunks = [];
    function finish(result) {
      if (done) return;
      done = true;
      timers.clearTimeout(timer);
      signal?.removeEventListener("abort", cancel);
      // No keep-alive agent; every socket/decoder belongs to this invocation.
      decoder?.destroy();
      res?.destroy();
      req?.destroy();
      chunks.length = 0;
      resolve(result);
    }
    const fail = (reason) => finish({ ok: false, reason, encoded, decoded });
    const cancel = () => fail("cancelled");
    function collect(chunk) {
      if (done) return;
      if (decoded + chunk.length > LIMITS.body) return fail("decoded_limit");
      decoded += chunk.length;
      chunks.push(chunk);
    }
    function parsed() {
      if (done) return;
      mark("observer.received");
      let value;
      try {
        value = new TextDecoder("utf-8", { fatal: true }).decode(
          Buffer.concat(chunks, decoded),
        );
      } catch {
        return fail("utf8");
      }
      try {
        value = JSON.parse(value);
        if (!value || typeof value !== "object" || Array.isArray(value))
          throw Error();
      } catch {
        return fail("json");
      }
      mark("observer.parsed");
      const body = Buffer.concat(chunks, decoded);
      finish({ ok: true, value, body, encoded, decoded });
    }
    timer = timers.setTimeout(() => fail("deadline"), LIMITS.deadline);
    signal?.addEventListener("abort", cancel, { once: true });
    if (signal?.aborted) return cancel();
    try {
      mark("observer.send");
      req = request(
        target,
        {
          method: "GET",
          agent: false,
          maxHeaderSize: LIMITS.headers,
          headers: { "x-diagnostic-id": op },
        },
        (response) => {
          res = response;
          if (done) {
            res.destroy();
            return;
          }
          res.on("error", () => fail("transport"));
          res.on("aborted", () => fail("transport"));
          if (
            Buffer.byteLength((res.rawHeaders ?? []).join("\r\n")) >
            LIMITS.headers
          )
            return fail("header_limit");
          mark("observer.headers");
          if (res.statusCode < 200 || res.statusCode >= 300)
            return fail("http_status");
          const encoding = res.headers["content-encoding"] ?? "identity";
          if (!["identity", "gzip"].includes(encoding)) return fail("encoding");
          if (encoding === "gzip") {
            decoder = createGunzip({ chunkSize: 16384 });
            decoder.on("error", () => fail("gzip"));
            decoder.on("data", collect);
            decoder.on("end", parsed);
          }
          res.on("data", (chunk) => {
            if (done) return;
            if (encoded + chunk.length > LIMITS.body)
              return fail("encoded_limit");
            encoded += chunk.length;
            if (decoder) decoder.write(chunk);
            else collect(chunk);
          });
          res.on("end", () => {
            if (!done) {
              if (decoder) decoder.end();
              else parsed();
            }
          });
        },
      );
      req.on("error", () => fail("transport"));
      req.end();
    } catch {
      fail("transport");
    }
  });
}
export async function observe({
  run,
  url,
  samples,
  write,
  drain,
  signal,
  read = readResponse,
  now = () => process.hrtime.bigint(),
  wait = async (deadline, signal) => {
    const remaining = deadline - process.hrtime.bigint();
    if (remaining > 0n)
      await sleep(Number((remaining + 999999n) / 1000000n), undefined, {
        signal,
      });
  },
}) {
  endpoint(url);
  if (
    !/^synthetic-[A-Za-z0-9_-]{1,22}$/.test(run) ||
    !Number.isInteger(samples) ||
    samples < 1 ||
    samples > 3600
  )
    throw Error("bounded synthetic run required");
  const summary = {
    completed: 0,
    failed: false,
    cancelled: false,
    skipped: 0,
    closed: false,
  };
  let deadline = now(),
    seq = 0;
  try {
    for (let index = 1; index <= samples; index++) {
      if (signal?.aborted) {
        summary.cancelled = true;
        break;
      }
      await wait(deadline, signal);
      const op = `${run}/source/${index}`;
      const mark = async (phase, extra = {}) =>
        write({
          run,
          op,
          seq: ++seq,
          phase,
          mono_ns: now().toString(),
          ...extra,
        });
      // A scheduled boundary retains the actual absolute target; wake is captured separately.
      await mark("observer.scheduled", { mono_ns: deadline.toString() });
      await mark("observer.wake", {
        late_ns: (now() > deadline ? now() - deadline : 0n).toString(),
      });
      // Transport marks must be captured synchronously even if sink is async.
      const pending = [];
      const result = await read({
        url,
        op,
        signal,
        mark: (phase) => {
          const row = { run, op, seq: ++seq, phase, mono_ns: now().toString() };
          pending.push(
            Promise.resolve()
              .then(() => write(row))
              .then(
                () => null,
                (error) => error,
              ),
          );
        },
      });
      const failures = await Promise.all(pending);
      if (failures.some(Boolean)) throw failures.find(Boolean);
      if (!result.ok)
        await mark("probe.failure", {
          outcome: result.reason === "cancelled" ? "cancelled" : "unavailable",
          reason: result.reason,
        });
      await drain();
      await mark("observer.written");
      summary.completed++;
      deadline += LIMITS.period;
      if (deadline <= now()) {
        const skipped = (now() - deadline) / LIMITS.period + 1n;
        summary.skipped += Number(skipped);
        await mark("observer.skipped_deadline", {
          skipped: Number(skipped),
          first_ns: deadline.toString(),
        });
        deadline += skipped * LIMITS.period;
      }
      await mark("observer.record_complete", {
        outcome: result.ok ? "ok" : "unavailable",
      });
      await drain();
      if (signal?.aborted) {
        summary.cancelled = true;
        break;
      }
    }
    await drain();
  } catch (error) {
    summary.failed = true;
    summary.cancelled = signal?.aborted ?? false;
    summary.reason = String(error.message).slice(0, 128);
  } finally {
    summary.closed = true;
  }
  return summary;
}
