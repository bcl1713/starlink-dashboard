import { describe, it, expect } from "vitest";
import { createProbe } from "../../browser-probe";

const bundle = (end = 30) => ({
  window_seconds: 30,
  start_timestamp_seconds: end - 30,
  end_timestamp_seconds: end,
  step_seconds: 1,
  series: {
    m: [
      [end - 1, 2],
      [end, 3],
    ],
  },
  rolling_5m: {
    m: {
      state: "available",
      min: [[end, 1]],
      avg: [[end, 2]],
      max: [[end, 4]],
    },
  },
});
function fixture(binding = async (_v: unknown) => true) {
  let time = 0;
  const records: any[] = [];
  const chunks = new Map<number, string[]>();
  const probe = createProbe({
    run: "synthetic-test",
    page: "p1",
    document: "d1",
    metrics: ["m"],
    clock: () => ++time,
    binding: async (v: any) => {
      const parts = chunks.get(v.seq) ?? [];
      parts[v.part] = v.payload;
      chunks.set(v.seq, parts);
      if (parts.filter((x) => x !== undefined).length === v.total)
        records.push(JSON.parse(parts.join("")));
      return binding(v);
    },
  });
  return { probe, records };
}
const drain = async () => {
  for (let i = 0; i < 30; i++) await Promise.resolve();
};
describe("bounded browser origin probe", () => {
  it("keeps unresolved, reordered and cancelled request identity distinct", async () => {
    const { probe, records } = fixture();
    let complete!: (v: any) => void;
    const delayed = probe.query(() => new Promise((r) => (complete = r)));
    const data = bundle();
    await probe.query(async (id) => {
      probe.response(id, data);
      return data;
    });
    const abort = new AbortController();
    abort.abort();
    const error = new Error("cancel");
    await expect(
      probe.query(async () => {
        throw error;
      }, abort.signal),
    ).rejects.toBe(error);
    await drain();
    expect(records.filter((r) => r.phase === "query.success")).toHaveLength(1);
    complete(data);
    expect(await delayed).toBe(data);
    await drain();
    expect(records.filter((r) => r.phase === "query.success")).toHaveLength(2);
    expect(records.find((r) => r.phase === "query.error").outcome).toBe(
      "cancelled",
    );
    expect(
      new Set(records.filter((r) => r.phase === "query.begin").map((r) => r.op))
        .size,
    ).toBe(3);
  });
  it("associates actual response objects without mutating or timestamp joins", async () => {
    const { probe, records } = fixture();
    const a = bundle(),
      b = bundle();
    const before = JSON.stringify(a);
    probe.response("r1", a);
    probe.response("r2", b);
    probe.candidate({}, "m", a, b, a);
    await drain();
    const candidate = records.find((r) => r.phase === "react.render_candidate");
    expect(candidate.detail.candidate).not.toBe(candidate.detail.accepted);
    expect(JSON.stringify(a)).toBe(before);
    expect(probe.association({ ...a })).toBeNull();
  });
  it("never waits for acknowledgments and makes saturation and collector loss sticky", async () => {
    const { probe } = fixture(() => new Promise(() => {}));
    for (let i = 0; i < 400; i++) probe.response("r" + i, bundle());
    expect(probe.summary().pending).toBeLessThanOrEqual(256);
    expect(probe.summary().inflight).toBeLessThanOrEqual(8);
    expect(probe.summary().lost).toBeGreaterThan(0);
    probe.close();
    expect(probe.summary().pending).toBe(0);
    const failed = fixture(async () => {
      throw Error("collector gone");
    });
    failed.probe.response("r", bundle());
    await drain();
    expect(failed.probe.summary().failed).toBe(true);
  });
  it("captures actual retained/projection/plot arrays and invalidates unmount evidence", async () => {
    const { probe, records } = fixture();
    const h = bundle();
    probe.response("r", h);
    const panel = {};
    probe.mount(panel);
    const data = [
      [29, 30],
      [4, null],
      [1, null],
      [2, null],
      [2, 3],
    ];
    const node = {
      style: {
        transform: "translate3d(-1px,0,0)",
        transition: "transform 1s linear",
      },
    };
    probe.commit(panel, {
      metric: "m",
      candidate: h,
      accepted: h,
      retained: h,
      projection: { times: [29, 30] },
      plot: {
        data,
        scales: { x: { min: 0, max: 40 } },
        width: 400,
        height: 80,
      },
      surface: node,
      width: 400,
      height: 80,
      upload: "create",
      hidden: false,
      error: false,
      reducedMotion: false,
    });
    await drain();
    const commit = records.find((r) => r.phase === "plot.commit");
    expect(commit.detail.plot.data).toEqual(data);
    expect(commit.detail.retained.series.m).toEqual(h.series.m);
    expect(commit.detail.provenance.observed).toEqual(["r", "r"]);
    expect(commit.detail.layoutOnly).toBe(true);
    expect(probe.metadata()).toHaveLength(1);
    probe.unmount(panel);
    expect(probe.metadata()).toHaveLength(0);
  });
  it("bounds malformed/deep snapshots before serialization, with loss rather than altered app data", () => {
    const { probe } = fixture();
    const panel = {};
    probe.mount(panel);
    const deep: any = {};
    let p = deep;
    for (let i = 0; i < 40; i++) p = p.child = {};
    expect(() => probe.commit(panel, deep)).not.toThrow();
    expect(probe.summary().failed).toBe(true);
  });
});
it("new documents have different request and clock identities despite equal local sequences", async () => {
  const rows: any[] = [];
  for (const document of ["d1", "d2"]) {
    const p = createProbe({
      run: "synthetic-test",
      page: "p",
      document,
      clock: () => 1,
      binding: async (m: any) => {
        rows.push(JSON.parse(m.payload));
        return true;
      },
    });
    await p.query(async () => 1);
  }
  await drain();
  expect(rows[0].clock).not.toBe(rows[2].clock);
  expect(rows[0].op).not.toBe(rows[2].op);
});
it("accepts the full eleven-metric application response without confusing the five-panel cap", () => {
  const { probe } = fixture();
  const h = bundle();
  for (let i = 0; i < 10; i++) h.series["aircraft" + i] = [[30, 4]];
  probe.response("full", h);
  expect(probe.association(h)).toBe("full");
  expect(probe.summary().failed).toBe(false);
});
it("records parsed network response samples even when no panel ever accepts that response", async () => {
  const { probe, records } = fixture();
  const h = bundle();
  probe.response("rejected", h);
  await drain();
  const parsed = records.find((r) => r.phase === "app.parse_available");
  expect(parsed.detail.history.series.m).toEqual([
    [29, 2],
    [30, 3],
  ]);
  expect(records.some((r) => r.phase === "plot.commit")).toBe(false);
});

// Authentic retained r1 latency shape; no fabricated workload or shortened IDs.
it("captures authentic full-ID 1801-point commits through binding and collector", async () => {
  const {
    readFileSync,
    mkdtempSync,
    rmSync,
    cpSync,
    mkdirSync,
    writeFileSync,
  } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");
  const { createHash } = await import("node:crypto");
  const { EventEmitter } = await import("node:events");
  const { createCollection } = await import("../../collect.mjs");
  const source = new URL(
    "../../../perf391-a-network-smoke-v1/evidence/runtime/browser/node/artifacts/b0c67faf174567e9523d98a9f2a7a8dac6f86b1d88acb1efe41a4832301b3d45.bin",
    import.meta.url,
  );
  const raw = readFileSync(source);
  expect(createHash("sha256").update(raw).digest("hex")).toBe(
    "b0c67faf174567e9523d98a9f2a7a8dac6f86b1d88acb1efe41a4832301b3d45",
  );
  const history = JSON.parse(raw.toString()).detail.history;
  const metric = Object.keys(history.series)[0];
  const original = JSON.stringify(history);
  const traces = [
    history.series[metric],
    ...["min", "avg", "max"].map((k) => history.rolling_5m[metric][k]),
  ];
  expect(traces.map((t) => t.length)).toEqual([1801, 1801, 1801, 1801]);
  const temp = mkdtempSync(join(tmpdir(), "perf391-authentic-correction-"));
  const root = join(temp, "collection");
  const collection = createCollection(root, { run: "synthetic-408a" });
  const page: any = new EventEmitter();
  let binding: any;
  page.exposeBinding = async (_: any, fn: any) => {
    binding = fn;
    return { dispose: async () => {} };
  };
  page.addInitScript = async () => ({ dispose: async () => {} });
  const observer = await collection.browser(page, {
    pageId: "p",
    origin: "http://127.0.0.1",
  });
  let time = 0;
  const probe = createProbe({
    run: "synthetic-408a",
    page: "p",
    document: "b34655ed4a2b4e82",
    metrics: [metric],
    clock: () => ++time,
    binding: (m) => binding({ page }, m),
  });
  const settle = async () => {
    for (
      let i = 0;
      i < 300 &&
      (probe.summary().pending ||
        probe.summary().inflight ||
        observer.summary().jobs);
      i++
    )
      await new Promise((resolve) => setImmediate(resolve));
    expect(probe.summary()).toMatchObject({
      failed: false,
      lost: 0,
      pending: 0,
      inflight: 0,
    });
  };
  try {
    const id = probe.requestId();
    expect(id).toHaveLength(36);
    probe.response(id, history);
    await settle();
    const panel = {};
    probe.mount(panel);
    const data = [
      traces[0].map((s) => s[0]),
      ...[traces[3], traces[1], traces[2], traces[0]].map((t) =>
        t.map((s) => s[1]),
      ),
    ];
    const projection = {
      times: data[0],
      max: data[1],
      min: data[2],
      avg: data[3],
      observed: data[4],
    };
    for (const upload of ["create", "setData"]) {
      probe.commit(panel, {
        metric,
        candidate: history,
        accepted: history,
        retained: history,
        projection,
        plot: {
          data,
          scales: {
            x: { min: data[0][0], max: data[0].at(-1) },
            y: { min: 1, max: 100, distr: 3 },
          },
          width: 400,
          height: 80,
        },
        surface: { style: { transform: "none", transition: "none" } },
        width: 400,
        height: 80,
        upload,
        hidden: false,
        error: false,
        reducedMotion: false,
      });
      await settle();
    }
    const { transpileModule, ModuleKind } = await import("typescript");
    const { runInNewContext } = await import("node:vm");
    const { selectPanel, finishFrontend } = await import(
      "../../../perf391-runtime-preparation-v1/browser-evidence.mjs"
    );
    const window: any = {
      __perf391ReadCommit: () => ({
        commits: probe.metadata(),
        summary: probe.summary(),
      }),
    };
    const runtime = readFileSync(
      new URL(
        "../../../perf391-runtime-preparation-v1/browser-runtime.ts",
        import.meta.url,
      ),
      "utf8",
    );
    // Execute the real Finish source in memory, supplying this authentic probe.
    runInNewContext(
      transpileModule(runtime, {
        compilerOptions: { module: ModuleKind.CommonJS },
      }).outputText,
      {
        require: () => ({ diagnostic: probe }),
        exports: {},
        globalThis: window,
      },
    );
    page.evaluate = async (fn: any) =>
      runInNewContext(`(${fn.toString()})()`, { globalThis: window });
    page.waitForFunction = async (fn: any) => ({
      jsonValue: async () => page.evaluate(fn),
      dispose: async () => {},
    });
    const facts: any = {};
    const save = (name: string, value: any) => {
      facts[name] = value;
    };
    expect(await selectPanel(page, save)).toBe(probe.metadata()[0].panel);
    const final = await finishFrontend(page, observer, save);
    expect(final.after).toMatchObject({
      seq: final.before.seq,
      closed: true,
      failed: false,
      lost: 0,
    });
    await observer.close();
    const summary = await collection.close();
    expect(summary.complete).toBe(true);
    const rows = readFileSync(join(root, "records.jsonl"), "utf8")
      .trim()
      .split("\n")
      .map((s) => JSON.parse(s));
    const commits = rows.filter((r) => r.event?.phase === "plot.commit");
    expect(commits).toHaveLength(2);
    expect(new Set(commits.map((r) => r.commit)).size).toBe(2);
    for (const row of commits) {
      const artifact = readFileSync(join(root, row.artifact.path));
      expect(createHash("sha256").update(artifact).digest("hex")).toBe(
        row.sha256,
      );
      const captured = JSON.parse(artifact.toString());
      expect(captured.op).toBe(id);
      expect(captured.detail.retained).toEqual(history);
      expect(captured.detail.projection).toEqual(projection);
      expect(captured.detail.plot.data).toEqual(data);
      for (const name of ["observed", "min", "avg", "max"])
        expect(captured.detail.provenance[name]).toEqual(Array(1801).fill(id));
      for (const [name, expected] of Object.entries({
        retained: history,
        projection,
        plot: captured.detail.plot,
      })) {
        const snapshot = readFileSync(
          join(root, row.snapshots[name].artifact.path),
        );
        expect(createHash("sha256").update(snapshot).digest("hex")).toBe(
          row.snapshots[name].sha256,
        );
        expect(JSON.parse(snapshot.toString())).toEqual(expected);
      }
    }
    expect(rows.filter((r) => r.event?.phase === "react.commit")).toHaveLength(
      2,
    );
    const evidence = process.env.PERF391_CORRECTION_EVIDENCE;
    if (evidence) {
      mkdirSync(evidence, { recursive: true });
      cpSync(root, join(evidence, "node"), { recursive: true });
      writeFileSync(
        join(evidence, "verified.json"),
        JSON.stringify(
          {
            source_sha256:
              "b0c67faf174567e9523d98a9f2a7a8dac6f86b1d88acb1efe41a4832301b3d45",
            points_per_trace: 1801,
            traces: 4,
            provenance_id: id,
            exact_retained_projection_plot_and_provenance: true,
            commits: commits.map((r) => ({
              commit: r.commit,
              request: r.event.op,
              artifact: r.artifact,
              snapshots: r.snapshots,
            })),
            frontend: facts,
            summary,
          },
          null,
          2,
        ) + "\n",
      );
    }
    expect(JSON.stringify(history)).toBe(original);
  } finally {
    probe.close();
    await collection.close();
    rmSync(temp, { recursive: true, force: true });
  }
});

it("rejects actual over-budget escaped JSON, excessive depth and traversal without mutation", async () => {
  for (const kind of ["bytes", "depth", "nodes"]) {
    const { probe } = fixture();
    const h: any = bundle();
    let v: any = "value";
    if (kind === "depth") for (let i = 0; i < 35; i++) v = { child: v };
    h.series.m =
      kind === "bytes"
        ? Array.from({ length: 1820 }, () => [1, "\0".repeat(256)])
        : kind === "nodes"
          ? Array.from({ length: 1820 }, () => Array(30).fill(0))
          : [[1, v]];
    const before = JSON.stringify(h);
    probe.response("full-provenance-request", h);
    await drain();
    expect(probe.summary().failed).toBe(true);
    expect(probe.summary().lost).toBeGreaterThan(0);
    expect(JSON.stringify(h)).toBe(before);
    probe.close();
  }
});
