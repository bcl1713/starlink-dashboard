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

test("interrupted assembly retains its pre-close counters and exact loss reason", async () => {
  const { page, observer } = await fixture();
  await page.bindings.get("__perf391Binding")(
    { page },
    {
      run: "synthetic-test",
      page: "p",
      document: "d1",
      seq: 1,
      part: 0,
      total: 2,
      payload: "{",
    },
  );
  await observer.close();
  const s = observer.summary();
  assert.equal(s.lost, 1);
  assert.equal(s.preClose.assemblies, 1);
  assert.equal(s.assemblies, 0);
  assert.equal(s.failures[0].code, "close-incomplete");
});

test("binding, write, listener and disposal failures retain bounded reason codes", async () => {
  const malformed = await fixture();
  await malformed.page.bindings.get("__perf391Binding")(
    { page: malformed.page },
    {},
  );
  assert.equal(
    malformed.observer.summary().failures[0].code,
    "binding-failure",
  );
  assert.equal(
    malformed.observer.summary().failures[0].reason,
    "invalid chunk",
  );
  await malformed.observer.close();
  const write = await fixture({
    write: async () => {
      throw Error("disk full");
    },
  });
  write.page.emit("request", request("write"));
  await drain();
  assert.equal(write.observer.summary().failures[0].code, "write-failure");
  assert.equal(write.observer.summary().failures[0].reason, "disk full");
  await write.observer.close();
  const listener = await fixture();
  listener.page.emit("response", {
    request: () => {
      throw Error("callback fault");
    },
  });
  assert.equal(
    listener.observer.summary().failures[0].code,
    "listener-failure",
  );
  await listener.observer.close();
  const dispose = await fixture();
  dispose.page.exposeBinding = async () => {};
  // Existing handle closes over this Map method, simulating disposal rejection.
  dispose.page.bindings.delete = () => {
    throw Error("dispose fault");
  };
  await dispose.observer.close();
  assert.equal(dispose.observer.summary().failures[0].code, "dispose-failure");
  assert.equal(dispose.observer.summary().preClose.failed, false);
  const cap = await fixture();
  for (let i = 0; i < 100; i++)
    cap.page.emit("response", {
      request: () => {
        throw Error("fault");
      },
    });
  assert.equal(cap.observer.summary().failures.length, 16);
  assert.equal(cap.observer.summary().failureOverflow, 84);
  assert.equal(cap.observer.summary().lost, 100);
  await cap.observer.close();
});

test("screenshot distinguishes metadata deadline, native deadline and native failure without chart loss", async () => {
  for (const mode of [
    "metadata",
    "native-timeout",
    "native-failure",
    "after-metadata",
  ]) {
    const { page, observer, rows } = await fixture({ deadlineMs: 10 });
    let evaluations = 0,
      screenshots = 0;
    const evaluate = page.evaluate.bind(page);
    page.evaluate = () => {
      evaluations++;
      return mode === "metadata" ||
        (mode === "after-metadata" && evaluations === 2)
        ? new Promise(() => {})
        : evaluate();
    };
    page.screenshot = async () => {
      screenshots++;
      if (mode === "native-timeout") return new Promise(() => {});
      if (mode === "native-failure") throw Error("native capture failed");
      return Buffer.from("png");
    };
    const result = await observer.screenshot("o1");
    assert.equal(result.outcome, "unavailable");
    assert.equal(
      result.stage,
      mode === "metadata"
        ? "before-metadata"
        : mode === "after-metadata"
          ? "after-metadata"
          : "native-screenshot",
    );
    assert.equal(
      result.code,
      mode === "native-failure"
        ? "screenshot-native-failure"
        : mode.startsWith("native")
          ? "screenshot-native-timeout"
          : "screenshot-metadata-timeout",
    );
    assert.equal(screenshots, mode === "metadata" ? 0 : 1);
    assert.equal(
      rows.some((r) => r.phase === "paint.request"),
      mode !== "metadata",
    );
    assert.equal(observer.summary().lost, 0);
    await observer.close();
  }
});

test("duplicate, stale, oversized and malformed browser chunks fail closed with reasons", async () => {
  for (const mode of ["duplicate", "stale", "oversized", "malformed"]) {
    const { page, observer } = await fixture();
    const binding = page.bindings.get("__perf391Binding");
    const m = {
      run: "synthetic-test",
      page: "p",
      document: "d1",
      seq: 1,
      total: mode === "oversized" ? 34 : 2,
      part: 0,
      payload: "{",
    };
    const realNow = Date.now;
    try {
      assert.equal(await binding({ page }, m), true);
      if (mode === "stale") Date.now = () => realNow() + 2001;
      if (mode === "oversized") {
        for (let part = 1; part <= 33; part++)
          await binding({ page }, { ...m, part, payload: "x".repeat(65536) });
      } else
        await binding(
          { page },
          { ...m, part: mode === "duplicate" ? 0 : 1, payload: "x" },
        );
      assert.equal(observer.summary().failed, true);
      assert.equal(observer.summary().failures[0].code, "binding-failure");
      assert.match(
        observer.summary().failures[0].reason,
        mode === "oversized"
          ? /artifact cap/
          : mode === "malformed"
            ? /JSON/
            : /duplicate\/stale chunk/,
      );
    } finally {
      Date.now = realNow;
      await observer.close();
    }
  }
});

test("owner retains actual selected state and final guard facts for absent, invalid and incomplete Finish", async () => {
  const { selectPanel, finishFrontend } = await import(
    "../../perf391-runtime-preparation-v1/browser-evidence.mjs"
  );
  for (const mode of [
    "ok",
    "absent",
    "invalid",
    "incomplete",
    "busy",
    "metadata-timeout",
  ]) {
    const saved = {};
    const state = {
      commits: [
        {
          panel: "o1",
          commit: mode === "incomplete" ? null : "p/c1",
          mounted: true,
          hidden: false,
        },
      ],
      summary: {
        seq: 10,
        closed: false,
        failed: false,
        lost: 0,
        pending: mode === "busy" ? 1 : 0,
        inflight: 0,
      },
    };
    let disposed = false;
    const page = {
      waitForFunction: async () => ({
        jsonValue: async () => structuredClone(state),
        dispose: async () => {
          disposed = true;
        },
      }),
      evaluate: async (fn) => {
        if (mode === "metadata-timeout") return new Promise(() => {});
        if (String(fn).includes("__perf391Finish"))
          return {
            available: mode !== "absent",
            value:
              mode === "invalid"
                ? { before: {}, after: { closed: true } }
                : {
                    before: state.summary,
                    after: { ...state.summary, closed: true },
                  },
          };
        return structuredClone(state);
      },
    };
    const save = (name, value) => {
      saved[name] = structuredClone(value);
    };
    const observer = {
      summary: () => ({
        active: 0,
        pending: 0,
        jobs: 0,
        bindingJobs: 0,
        ownedOperations: 0,
        assemblies: 0,
        failed: false,
        lost: 0,
      }),
    };
    if (mode === "incomplete")
      await assert.rejects(selectPanel(page, save), /incomplete-commits/);
    else {
      assert.equal(await selectPanel(page, save), "o1");
      assert.deepEqual(saved["panel-selection.json"].metadata, state);
    }
    assert.equal(disposed, true);
    if (mode === "ok")
      assert.equal(
        (await finishFrontend(page, observer, save, { deadlineMs: 10 })).after
          .closed,
        true,
      );
    else
      await assert.rejects(
        finishFrontend(page, observer, save, { deadlineMs: 10 }),
        new RegExp(
          {
            absent: "finish-absent",
            invalid: "finish-invalid",
            incomplete: "incomplete-commits",
            busy: "finish-not-admitted",
            "metadata-timeout": "frontend-metadata-timeout",
          }[mode],
        ),
      );
    const trace = saved["frontend-finalization.json"];
    assert.ok(trace);
    assert.deepEqual(
      trace.last?.frontend ?? null,
      mode === "metadata-timeout" ? null : state,
    );
    assert.equal(
      trace.finishAdmitted,
      ["ok", "absent", "invalid"].includes(mode),
    );
    if (mode === "invalid")
      assert.deepEqual(trace.final, { before: {}, after: { closed: true } });
  }
});

test("artifact failure remains optional and the screenshot uses the remaining total budget", async () => {
  for (const mode of [
    "artifact-failure",
    "artifact-timeout",
    "remaining-budget",
  ]) {
    const f = await fixture({
      deadlineMs: 30,
      artifact: async () => {
        if (mode === "artifact-failure") throw Error("PNG storage failure");
        return new Promise(() => {});
      },
    });
    try {
      if (mode === "remaining-budget") {
        const evaluate = f.page.evaluate.bind(f.page);
        f.page.evaluate = async () => {
          await new Promise((r) => setTimeout(r, 8));
          return evaluate();
        };
        f.page.screenshot = async (options) => {
          assert.ok(options.timeout < 30 && options.timeout > 0);
          return new Promise(() => {});
        };
      }
      const result = await f.observer.screenshot("o1");
      assert.equal(result.outcome, "unavailable");
      assert.equal(
        result.stage,
        mode === "remaining-budget" ? "native-screenshot" : "artifact",
      );
      assert.equal(
        result.code,
        mode === "remaining-budget"
          ? "screenshot-native-timeout"
          : mode === "artifact-timeout"
            ? "screenshot-artifact-timeout"
            : "screenshot-stage-failure",
      );
      assert.equal(f.observer.summary().lost, 0);
    } finally {
      await f.observer.close();
    }
  }
});
