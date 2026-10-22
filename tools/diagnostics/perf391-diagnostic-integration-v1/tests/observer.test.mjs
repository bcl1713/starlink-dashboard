import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { gzipSync } from "node:zlib";
import { observe, readResponse } from "../observer.mjs";

function transport({
  chunks = [Buffer.from('{"source":"one"}')],
  status = 200,
  encoding = "identity",
  error,
  stall = false,
} = {}) {
  let destroyed = 0,
    opts;
  const request = (url, options, callback) => {
    opts = options;
    const req = new EventEmitter();
    req.destroy = () => {
      destroyed++;
    };
    req.end = () =>
      queueMicrotask(() => {
        if (error) return req.emit("error", Error("reset"));
        const res = new EventEmitter();
        res.statusCode = status;
        res.headers = { "content-encoding": encoding };
        res.rawHeaders = ["content-encoding", encoding];
        res.destroy = () => {
          destroyed++;
        };
        callback(res);
        if (!stall) {
          for (const chunk of chunks) res.emit("data", chunk);
          res.emit("end");
        }
      });
    return req;
  };
  return {
    request,
    get destroyed() {
      return destroyed;
    },
    get options() {
      return opts;
    },
  };
}
const url = "http://127.0.0.1:18000/api/_diagnostic/state";
test("late wake and slow completion skip absolute deadlines without bursts", async () => {
  const rows = [],
    waits = [],
    sends = [];
  let now = 0n;
  const stats = await observe({
    run: "synthetic-test",
    samples: 2,
    url,
    now: () => now,
    wait: async (deadline) => {
      waits.push(deadline);
      now = deadline + 2400000000n;
    },
    read: async ({ mark }) => {
      sends.push(now);
      mark("observer.send");
      now += 100000000n;
      return { ok: true };
    },
    write: async (row) => rows.push(row),
    drain: async () => {
      now += 100000000n;
    },
  });
  assert.deepEqual(waits, [0n, 3000000000n]);
  assert.deepEqual(sends, [2400000000n, 5400000000n]);
  assert.deepEqual(
    rows
      .filter((r) => r.phase === "observer.skipped_deadline")
      .map((r) => r.skipped),
    [2, 2],
  );
  assert.equal(
    rows.find((r) => r.phase === "observer.wake").late_ns,
    "2400000000",
  );
  assert.equal(stats.completed, 2);
  assert.equal(stats.closed, true);
  assert.equal(rows.at(-1).phase, "observer.record_complete");
});
test("bounded response accepts JSON and identity request header", async () => {
  const t = transport(),
    rows = [];
  const result = await readResponse({
    url,
    op: "synthetic-test/source/1",
    request: t.request,
    mark: (p) => rows.push(p),
  });
  assert.equal(result.value.source, "one");
  assert.equal(t.options.headers["x-diagnostic-id"], "synthetic-test/source/1");
  assert.ok(rows.includes("observer.parsed"));
});
for (const [name, config, want] of [
  ["malformed", { chunks: [Buffer.from("{")] }, "json"],
  ["invalid UTF8", { chunks: [Buffer.from([255])] }, "utf8"],
  ["redirect", { status: 302 }, "http_status"],
  ["unsupported encoding", { encoding: "br" }, "encoding"],
  ["socket reset", { error: true }, "transport"],
  ["oversize identity", { chunks: [Buffer.alloc(2097153)] }, "encoded_limit"],
  [
    "zip bomb",
    { encoding: "gzip", chunks: [gzipSync(Buffer.alloc(2097153, 32))] },
    "decoded_limit",
  ],
])
  test(name + " destroys owned transport and reports unavailable", async () => {
    const t = transport(config),
      result = await readResponse({ url, op: "x", request: t.request });
    assert.equal(result.ok, false);
    assert.equal(result.reason, want);
    assert.ok(t.destroyed > 0);
  });
test("gzip response is decoded within cap", async () => {
  const t = transport({
    encoding: "gzip",
    chunks: [gzipSync(Buffer.from('{"ok":true}'))],
  });
  assert.equal(
    (await readResponse({ url, op: "x", request: t.request })).value.ok,
    true,
  );
});
test("total deadline and cancellation destroy stalled requests and clear timers", async () => {
  for (const cancel of [false, true]) {
    const t = transport({ stall: true }),
      c = new AbortController();
    let timeout,
      cleared = 0;
    const pending = readResponse({
      url,
      op: "x",
      request: t.request,
      signal: c.signal,
      timers: {
        setTimeout: (fn) => {
          timeout = fn;
          return 1;
        },
        clearTimeout: () => cleared++,
      },
    });
    await new Promise((resolve) => queueMicrotask(resolve));
    if (cancel) c.abort();
    else timeout();
    assert.equal((await pending).reason, cancel ? "cancelled" : "deadline");
    assert.ok(t.destroyed > 0);
    assert.equal(cleared, 1);
  }
});
test("writer failure stops scheduling and cancellation produces final accounting", async () => {
  const result = await observe({
    run: "synthetic-test",
    samples: 3,
    url,
    wait: async () => {},
    now: () => 0n,
    read: async () => ({ ok: true }),
    write: async () => {
      throw Error("ENOSPC");
    },
    drain: async () => {},
  });
  assert.equal(result.failed, true);
  assert.equal(result.completed, 0);
  assert.equal(result.closed, true);
});
test("only dedicated loopback endpoint is accepted before transport", async () => {
  for (const bad of [
    "https://127.0.0.1/api/_diagnostic/state",
    "http://example.com/api/_diagnostic/state",
    url + "?x=1",
    url + "/other",
  ])
    await assert.rejects(
      () =>
        readResponse({
          url: bad,
          op: "x",
          request: () => {
            throw Error("must not connect");
          },
        }),
      /endpoint/,
    );
});
