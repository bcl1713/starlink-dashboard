import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createSink, attachHistory } from "../browser.mjs";

test("passive response capture joins IDs and detaches cleanly", async () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir, { maxDiskBytes: 100000 });
    const page = new EventEmitter();
    const adapter = attachHistory(page, sink, { viewer: "v1" });
    const body = Buffer.from(
      JSON.stringify({
        start_timestamp_seconds: 100,
        end_timestamp_seconds: 101,
        step_seconds: 1,
        series: {
          x: [
            [100, 0],
            [101, 2],
          ],
        },
      }),
    );
    const request = {
      url: () => "http://fictional.invalid/api/overview-history",
    };
    const response = {
      request: () => request,
      status: () => 200,
      headers: () => ({ "content-length": String(body.length) }),
      body: async () => body,
    };
    page.emit("request", request);
    page.emit("response", response);
    page.emit("requestfinished", request);
    assert.equal((await adapter.close()).pending, 0);
    sink.close();
    const rows = readFileSync(join(dir, "events.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map(JSON.parse);
    const history = rows.find((x) => x.kind === "history");
    assert.equal(history.data.series.x[0][1], 0);
    assert.equal(history.op_id, rows.find((x) => x.kind === "body").op_id);
    assert.equal(page.listenerCount("response"), 0);
    assert.equal(rows.at(-1).kind, "summary");
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("missing length never triggers unbounded body read; drops are counted", async () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir, { maxDiskBytes: 10000, maxEventBytes: 800 });
    const page = new EventEmitter();
    const adapter = attachHistory(page, sink, { viewer: "v1", maxActive: 1 });
    const r = { url: () => "http://fictional.invalid/api/overview-history" };
    page.emit("request", r);
    page.emit("request", { ...r });
    page.emit("response", {
      request: () => r,
      status: () => 200,
      headers: () => ({}),
      body: () => {
        throw Error("must not read");
      },
    });
    await adapter.close();
    sink.emit("coverage", {
      boundary: "huge",
      available: false,
      reason: "x".repeat(1000),
    });
    sink.close();
    const rows = readFileSync(join(dir, "events.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map(JSON.parse);
    assert.ok(rows.at(-1).data.dropped_events >= 2);
    assert.equal(rows.at(-1).data.dropped_bodies, 1);
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("schema rejects unknown fields and nonfinite numbers before writing", () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir);
    assert.throws(() =>
      sink.emit("coverage", {
        boundary: "x",
        available: false,
        reason: "fixture",
        unknown: true,
      }),
    );
    assert.throws(() =>
      sink.emit("scrape", {
        series: "x",
        timestamp: 100,
        value: NaN,
        state: "finite",
        segment: "measured",
      }),
    );
    sink.close();
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("pending body rejection after close never writes to closed sink", async () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir);
    const page = new EventEmitter();
    const adapter = attachHistory(page, sink, { viewer: "v1" });
    let reject;
    const request = {
      url: () => "http://fictional.invalid/api/overview-history",
    };
    page.emit("request", request);
    page.emit("response", {
      request: () => request,
      status: () => 200,
      headers: () => ({ "content-length": "1" }),
      body: () =>
        new Promise((_, r) => {
          reject = r;
        }),
    });
    assert.equal((await adapter.close()).pending, 1);
    sink.close();
    reject(Error("context closed"));
    await new Promise((resolve) => setImmediate(resolve));
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("shared schema accepts every versioned fixture event", async () => {
  const { validateEvent } = await import("../browser-schema.mjs");
  const cases = JSON.parse(
    readFileSync(new URL("../fixtures/cases.json", import.meta.url), "utf8"),
  );
  for (const c of cases) for (const row of c.events) validateEvent(row);
});

test("unavailable body keeps request ID until terminal event", async () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir);
    const page = new EventEmitter();
    const adapter = attachHistory(page, sink, { viewer: "v1" });
    const r = { url: () => "http://fictional.invalid/api/overview-history" };
    page.emit("request", r);
    page.emit("response", {
      request: () => r,
      status: () => 200,
      headers: () => ({}),
      body: () => {
        throw Error("must not read");
      },
    });
    await new Promise((resolve) => setImmediate(resolve));
    page.emit("requestfinished", r);
    await adapter.close();
    sink.close();
    const rows = readFileSync(join(dir, "events.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map(JSON.parse);
    assert.ok(
      rows.some((r) => r.kind === "boundary" && r.data.name === "browser.end"),
    );
  } finally {
    rmSync(dir, { recursive: true });
  }
});

test("failed requests with pending bodies cannot exceed active job bound", async () => {
  const dir = mkdtempSync(join(tmpdir(), "perf391-browser-"));
  try {
    const sink = createSink(dir);
    const page = new EventEmitter();
    const adapter = attachHistory(page, sink, { viewer: "v1", maxActive: 1 });
    let resolve;
    const r = { url: () => "http://fictional.invalid/api/overview-history" };
    page.emit("request", r);
    page.emit("response", {
      request: () => r,
      status: () => 200,
      headers: () => ({ "content-length": "1" }),
      body: () =>
        new Promise((r) => {
          resolve = r;
        }),
    });
    page.emit("requestfailed", r);
    for (let i = 0; i < 10; i++) page.emit("request", { ...r });
    resolve(Buffer.from("{}"));
    await adapter.close();
    sink.close();
    const rows = readFileSync(join(dir, "events.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map(JSON.parse);
    assert.ok(rows.at(-1).data.dropped_events >= 10);
  } finally {
    rmSync(dir, { recursive: true });
  }
});
