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
