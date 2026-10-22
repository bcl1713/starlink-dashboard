import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { createBrowserObserver } from "../browser.mjs";
class Page extends EventEmitter {
  bindings = new Map();
  disposedInit = 0;
  disposedBinding = 0;
  meta = {
    commits: [
      {
        panel: "o1",
        document: "doc1",
        commit: "p/c1",
        generation: 1,
        mounted: true,
        hidden: false,
        visibility: "visible",
        dpr: 1,
        rect: { x: 1, y: 2, width: 400, height: 80 },
        transform: "none",
      },
    ],
    summary: { lost: 0, failed: false },
  };
  async exposeBinding(n, f) {
    this.bindings.set(n, f);
    return {
      dispose: async () => {
        this.disposedBinding++;
        this.bindings.delete(n);
      },
    };
  }
  async addInitScript() {
    return {
      dispose: async () => {
        this.disposedInit++;
      },
    };
  }
  async evaluate() {
    return structuredClone(this.meta);
  }
  viewportSize() {
    return { width: 1920, height: 1080 };
  }
  async screenshot() {
    return Buffer.from("png");
  }
}
function request(id) {
  return {
    url: () => "http://127.0.0.1:18080/api/overview-history",
    headers: () => ({ "x-diagnostic-id": id }),
    method: () => "GET",
    failure: () => ({ errorText: "aborted" }),
    timing: () => ({ startTime: 100, responseEnd: 50 }),
  };
}
async function fixture(options = {}) {
  const page = new Page(),
    rows = [],
    artifacts = [];
  const observer = await createBrowserObserver(page, {
    run: "synthetic-test",
    pageId: "p",
    origin: "http://127.0.0.1:18080",
    write: async (r) => rows.push(r),
    artifact: async (bytes, meta) => {
      artifacts.push({ bytes, meta });
      return "sha";
    },
    ...options,
  });
  return { page, observer, rows, artifacts };
}
const drain = async () => {
  for (let i = 0; i < 50; i++) await Promise.resolve();
};
test("joins by Request identity through reordered callbacks; body APIs never used", async () => {
  const { page, observer, rows } = await fixture();
  const a = request("a"),
    b = request("b");
  page.emit("request", a);
  page.emit("request", b);
  page.emit("requestfinished", b);
  page.emit("response", {
    request: () => b,
    status: () => 200,
    headers: () => ({}),
  });
  page.emit("response", {
    request: () => a,
    status: () => 200,
    headers: () => ({ "content-encoding": "gzip" }),
    body: () => {
      throw Error("forbidden");
    },
  });
  page.emit("requestfailed", a);
  await drain();
  assert.equal(rows.find((r) => r.phase === "browser.finished").requestId, "b");
  assert.equal(rows.find((r) => r.phase === "browser.failed").requestId, "a");
  assert.equal(observer.summary().active, 0);
  await observer.close();
  assert.equal(page.listenerCount("request"), 0);
});
test("missing callbacks and saturation remain loss; cancellation clears owned jobs", async () => {
  const { page, observer } = await fixture({
    write: () => new Promise(() => {}),
  });
  for (let i = 0; i < 300; i++) page.emit("request", request("r" + i));
  assert.ok(observer.summary().lost > 0);
  assert.ok(observer.summary().active <= 8);
  assert.ok(observer.summary().pending <= 256);
  await observer.close();
  assert.equal(observer.summary().active, 0);
  assert.equal(page.eventNames().length, 0);
});
test("binding reassembles out-of-order bounded chunks without forging browser timestamps", async () => {
  const { page, observer, rows } = await fixture();
  const binding = page.bindings.get("__perf391Binding");
  const text = JSON.stringify({
    run: "synthetic-test",
    stream: "synthetic-test/p/d1",
    seq: 1,
    clock: "browser/p/d1",
    monotonic_ms: 10,
    phase: "plot.commit",
    op: null,
    outcome: "ok",
    detail: { retained: {}, projection: {}, plot: {} },
  });
  const msg = {
    run: "synthetic-test",
    page: "p",
    document: "d1",
    seq: 1,
    total: 2,
  };
  assert.equal(
    await binding({ page }, { ...msg, part: 1, payload: text.slice(20) }),
    true,
  );
  assert.equal(
    await binding({ page }, { ...msg, part: 0, payload: text.slice(0, 20) }),
    true,
  );
  await drain();
  assert.equal(rows.find((r) => r.origin === "browser").event.monotonic_ms, 10);
  assert.equal(
    await binding({ page }, { ...msg, part: 0, payload: "x".repeat(65537) }),
    false,
  );
  assert.ok(observer.summary().lost > 0);
  await observer.close();
});
test("screenshots require stable commit and geometry and never retry ambiguity", async () => {
  const { page, observer, rows, artifacts } = await fixture();
  assert.equal((await observer.screenshot("o1")).outcome, "ok");
  assert.equal(artifacts.length, 1);
  page.screenshot = async () => {
    page.meta.commits[0].generation++;
    return Buffer.from("png");
  };
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  assert.equal(artifacts.length, 2);
  assert.equal(rows.filter((r) => r.phase === "paint.artifact").length, 2);
  await observer.close();
});
test("viewport changes, hidden panels, collector failures and close invalidate capture", async () => {
  const { page, observer } = await fixture();
  page.meta.commits[0].hidden = true;
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  page.meta.commits[0].hidden = false;
  page.screenshot = async () => {
    page.meta.commits[0].rect.width++;
    return Buffer.from("png");
  };
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  await observer.close();
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  const bad = await fixture({
    write: async () => {
      throw Error("lost");
    },
  });
  bad.page.emit("request", request("r"));
  await drain();
  assert.equal(bad.observer.summary().failed, true);
  await bad.observer.close();
});
test("opt-in build helper refuses generic or non-synthetic frontend builds", async () => {
  const { diagnosticFrontendOptions } = await import("../frontend-config.mjs");
  assert.throws(() =>
    diagnosticFrontendOptions({
      enabled: false,
      syntheticRunToken: "synthetic-test",
    }),
  );
  assert.throws(() =>
    diagnosticFrontendOptions({
      enabled: true,
      syntheticRunToken: "production",
    }),
  );
  assert.equal(
    diagnosticFrontendOptions({
      enabled: true,
      syntheticRunToken: "synthetic-test",
    }).define["import.meta.env.VITE_PERF391_DIAGNOSTIC"],
    '"true"',
  );
});
test("unmount, DPR mismatch, artifact loss, and eight shared screenshots cannot qualify paint", async () => {
  const { page, observer } = await fixture();
  page.screenshot = async () => {
    page.meta.commits = [];
    return Buffer.from("png");
  };
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  await observer.close();
  const dpr = await fixture();
  dpr.page.meta.commits[0].dpr = 2;
  assert.equal((await dpr.observer.screenshot("o1")).outcome, "unavailable");
  await dpr.observer.close();
  const broken = await fixture({
    artifact: async () => {
      throw Error("storage lost");
    },
  });
  assert.equal((await broken.observer.screenshot("o1")).outcome, "unavailable");
  await broken.observer.close();
  const budget = { screenshots: 8, busy: false };
  const capped = await fixture({ budget });
  assert.equal(
    (await capped.observer.screenshot("o1")).reason,
    "closed/busy/quota",
  );
  await capped.observer.close();
});
test("collector callbacks hang only until the total deadline and cannot keep close alive", async () => {
  const { page, observer } = await fixture({
    write: () => new Promise(() => {}),
  });
  page.emit("request", request("r"));
  await observer.close();
  assert.equal(observer.summary().jobs, 0);
  assert.equal(observer.summary().pending, 0);
});
test("successful terminal callback without response metadata remains incomplete loss on close", async () => {
  const { page, observer } = await fixture();
  const r = request("missing");
  page.emit("request", r);
  page.emit("requestfinished", r);
  await drain();
  await observer.close();
  assert.ok(observer.summary().lost > 0);
});
test("host refuses a ninth concurrent binding artifact and cancels the owned waiters", async () => {
  const { page, observer } = await fixture({
    artifact: () => new Promise(() => {}),
  });
  const binding = page.bindings.get("__perf391Binding");
  const pending = [];
  for (let seq = 1; seq <= 9; seq++) {
    const row = {
      run: "synthetic-test",
      stream: "synthetic-test/p/d1",
      seq,
      clock: "browser/p/d1",
      monotonic_ms: 10,
      phase: "plot.commit",
      op: null,
      outcome: "ok",
      detail: { commit: "c", retained: {}, projection: {}, plot: {} },
    };
    pending.push(
      binding(
        { page },
        {
          run: "synthetic-test",
          page: "p",
          document: "d1",
          seq,
          part: 0,
          total: 1,
          payload: JSON.stringify(row),
        },
      ),
    );
  }
  assert.equal(observer.summary().bindingJobs, 8);
  await observer.close();
  const results = await Promise.all(pending);
  assert.equal(results[8], false);
  assert.equal(observer.summary().bindingJobs, 0);
});
test("request object token allocation does not create phantom host event sequence gaps", async () => {
  const { page, observer, rows } = await fixture();
  const r = request("seq");
  page.emit("request", r);
  page.emit("response", {
    request: () => r,
    status: () => 200,
    headers: () => ({}),
  });
  page.emit("requestfinished", r);
  await drain();
  assert.deepEqual(
    rows.map((r) => r.host_seq),
    [1, 2, 3],
  );
  await observer.close();
});
test("a total sink deadline aborts its signal and never replaces it with more jobs", async () => {
  let aborted = false,
    calls = 0;
  const { page, observer } = await fixture({
    deadlineMs: 5,
    write: (_row, { signal }) =>
      new Promise((resolve) => {
        calls++;
        signal.addEventListener(
          "abort",
          () => {
            aborted = true;
            resolve();
          },
          { once: true },
        );
      }),
  });
  page.emit("request", request("deadline"));
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal(aborted, true);
  const before = calls;
  for (let i = 0; i < 30; i++) page.emit("request", request("late" + i));
  await drain();
  assert.equal(calls, before);
  assert.equal(observer.summary().failed, true);
  await observer.close();
});
test("navigation with identical local plot IDs cannot qualify a screenshot from a different document", async () => {
  const { page, observer } = await fixture();
  page.meta.commits[0].document = "doc1";
  page.screenshot = async () => {
    page.meta.commits[0].document = "doc2";
    return Buffer.from("png");
  };
  assert.equal((await observer.screenshot("o1")).outcome, "unavailable");
  await observer.close();
});
test("cleanup disposes the pinned Playwright binding and init-script handles exactly once", async () => {
  const { page, observer } = await fixture();
  await observer.close();
  await observer.close();
  assert.equal(page.bindings.size, 0);
  assert.equal(page.disposedInit, 1);
  assert.equal(page.disposedBinding, 1);
});
test("close settles all owned capture wrappers and releases the shared screenshot slot", async () => {
  const budget = { screenshots: 0, busy: false };
  const { page, observer } = await fixture({ budget });
  page.screenshot = () => new Promise(() => {});
  const capture = observer.screenshot("o1");
  await drain();
  assert.equal(budget.busy, true);
  assert.equal(observer.summary().ownedOperations, 1);
  await observer.close();
  assert.equal(observer.summary().ownedOperations, 0);
  assert.equal(budget.busy, false);
  assert.equal((await capture).outcome, "unavailable");
});
