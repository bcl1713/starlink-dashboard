import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtempSync, readFileSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createCollection } from "../collect.mjs";
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
test("collection closes real Stage 3A binding jobs and hashes artifacts", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-node-"));
  try {
    const collection = createCollection(join(root, "owned"), {
        run: "synthetic-test",
      }),
      page = new Page();
    const browser = await collection.browser(page, {
      pageId: "p",
      origin: "http://127.0.0.1:18080",
    });
    const req = {
      url: () => "http://127.0.0.1:18080/api/overview-history",
      headers: () => ({ "x-diagnostic-id": "synthetic-test/p/doc/r1" }),
      method: () => "GET",
    };
    page.emit("request", req);
    const binding = [...page.bindings.values()][0];
    const raw = {
      run: "synthetic-test",
      stream: "synthetic-test/p/doc",
      clock: "browser/p/doc",
      seq: 1,
      monotonic_ms: 2,
      phase: "app.request",
      op: "synthetic-test/p/doc/r1",
      outcome: "ok",
      detail: {},
    };
    assert.equal(
      await binding(
        { page },
        {
          run: "synthetic-test",
          page: "p",
          document: "doc",
          seq: 1,
          total: 1,
          part: 0,
          payload: JSON.stringify(raw),
        },
      ),
      true,
    );
    await collection.close();
    assert.equal(page.bindings.size, 0);
    assert.equal(browser.summary().ownedOperations, 0);
    const rows = readFileSync(join(root, "owned/records.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map(JSON.parse);
    assert.ok(rows[0].host_identity.process_uuid);
    assert.equal(rows[0].host_identity.pid, process.pid);
    assert.equal(rows[1].event.clock, "browser/p/doc");
    assert.ok(
      readFileSync(join(root, "owned/summary.json"), "utf8").includes("closed"),
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("bounded collection saturation and abort never publish a complete artifact", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-node-"));
  try {
    const collection = createCollection(join(root, "owned"), {
      run: "synthetic-test",
      diskBytes: 16384,
    });
    const c = new AbortController();
    c.abort();
    await assert.rejects(
      () => collection.artifact(Buffer.from("x"), { signal: c.signal }),
      /cancel/,
    );
    await assert.rejects(
      () => collection.artifact(Buffer.alloc(2097153)),
      /budget/,
    );
    const summary = await collection.close();
    assert.equal(summary.complete, false);
    assert.equal(readdirSync(join(root, "owned/artifacts")).length, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("owner shutdown cancels and awaits the source observer before final summary", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-source-"));
  try {
    const collection = createCollection(join(root, "owned"), {
      run: "synthetic-test",
    });
    let started;
    const ready = new Promise((resolve) => (started = resolve));
    const pending = collection.source({
      url: "http://127.0.0.1:18000/api/_diagnostic/state",
      samples: 2,
      wait: async () => {},
      read: ({ signal }) =>
        new Promise((resolve) => {
          started();
          signal.addEventListener(
            "abort",
            () => resolve({ ok: false, reason: "cancelled" }),
            { once: true },
          );
        }),
    });
    await ready;
    const summary = await collection.close();
    await pending;
    assert.equal(summary.sources.length, 1);
    assert.equal(summary.sources[0].closed, true);
    assert.equal(summary.complete, false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("close during browser binding setup disposes the eventual handles", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-setup-"));
  try {
    const page = new Page();
    let release, entered;
    const ready = new Promise((resolve) => (entered = resolve));
    const original = page.exposeBinding.bind(page);
    page.exposeBinding = async (...args) => {
      entered();
      await new Promise((resolve) => (release = resolve));
      return original(...args);
    };
    const collection = createCollection(join(root, "owned"), {
      run: "synthetic-test",
    });
    const setup = collection.browser(page, {
      pageId: "p",
      origin: "http://127.0.0.1:18080",
    });
    await ready;
    const closing = collection.close();
    release();
    await setup;
    await closing;
    assert.equal(page.bindings.size, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("HTTP failures remain failed evidence in final source and collection summaries", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-http-failure-"));
  try {
    const collection = createCollection(join(root, "owned"), {
      run: "synthetic-test",
    });
    const source = await collection.source({
      url: "http://127.0.0.1:18000/api/_diagnostic/state",
      samples: 2,
      wait: async () => {},
      read: async () => ({ ok: false, reason: "http_status" }),
    });
    const result = await collection.close();
    assert.equal(source.failed, true);
    assert.equal(result.complete, false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
test("Page close during binding setup leaves no eventual binding or init handle", async () => {
  const root = mkdtempSync(join(tmpdir(), "perf391-stage4-page-close-"));
  try {
    const page = new Page();
    let release, entered;
    const ready = new Promise((resolve) => (entered = resolve)),
      original = page.exposeBinding.bind(page);
    page.exposeBinding = async (...args) => {
      entered();
      await new Promise((resolve) => (release = resolve));
      return original(...args);
    };
    const collection = createCollection(join(root, "owned"), {
      run: "synthetic-test",
    });
    const setup = collection.browser(page, {
      pageId: "p",
      origin: "http://127.0.0.1:18080",
    });
    await ready;
    page.emit("close");
    release();
    try {
      await setup;
    } catch {}
    const summary = await collection.close();
    assert.equal(page.bindings.size, 0);
    assert.equal(summary.complete, false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
