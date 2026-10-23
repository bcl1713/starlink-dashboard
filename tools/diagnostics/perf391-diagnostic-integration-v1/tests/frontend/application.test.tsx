/** @vitest-environment jsdom */
import React, { StrictMode } from "react";
import { act, cleanup, render } from "@testing-library/react";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
// Imports resolve only against the exact disposable role export.
import { OverviewMetricHistoryPanel } from "@app/pages/OverviewMetricHistoryPanel";
import { OVERVIEW_METRIC_GRAPHS } from "@app/pages/overview-metric-history";
import { diagnostic } from "../../browser-probe";
const plots = vi.hoisted(() => ({
  instances: [] as any[],
  uploads: 0,
  destroys: 0,
}));
vi.mock("uplot", () => ({
  default: class {
    data: any;
    scales: any = { x: {}, y: {} };
    width: number;
    height: number;
    constructor(options: any, data: any, host: HTMLElement) {
      this.data = data;
      this.width = options.width;
      this.height = options.height;
      plots.instances.push(this);
      host.append(document.createElement("canvas"));
    }
    setData(data: any) {
      this.data = data;
      plots.uploads++;
    }
    setSize(v: any) {
      Object.assign(this, v);
    }
    setScale(key: string, v: any) {
      this.scales[key] = v;
    }
    destroy() {
      plots.destroys++;
    }
  },
}));
let reduced = false;
const metric = OVERVIEW_METRIC_GRAPHS[0];
const bundle = (end = 120) => ({
  window_seconds: 30,
  start_timestamp_seconds: end - 30,
  end_timestamp_seconds: end,
  step_seconds: 5,
  series: {
    [metric.metric]: [
      [end - 10, 5],
      [end, 7],
    ],
  },
  rolling_5m: {
    [metric.metric]: {
      state: "available",
      min: [[end - 10, 3]],
      avg: [[end - 10, 4]],
      max: [[end - 10, 6]],
    },
  },
});
function panel(h: any, error = false) {
  return (
    <OverviewMetricHistoryPanel
      descriptor={metric}
      history={h}
      error={error}
      selectedWindowSeconds={30}
      nowMs={120000}
    />
  );
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(120000);
  plots.instances = [];
  plots.uploads = 0;
  plots.destroys = 0;
  reduced = false;
  (globalThis as any).__stage3Rows.length = 0;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal("matchMedia", () => ({
    get matches() {
      return reduced;
    },
    addEventListener() {},
    removeEventListener() {},
  }));
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get: () => 400,
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    get: () => 80,
  });
  Object.defineProperty(document, "hidden", {
    configurable: true,
    get: () => false,
  });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("captures real panel retained left margin and actual null breaks without extra uploads", async () => {
  const a = bundle();
  a.series[metric.metric].unshift([90, 9]);
  diagnostic!.response("old", a);
  const view = render(panel(a));
  const b = bundle(125);
  diagnostic!.response("new", b);
  view.rerender(panel(b));
  const c = diagnostic!.metadata()[0];
  expect(c).toBeDefined();
  await act(async () => {
    for (let i = 0; i < 40; i++) await Promise.resolve();
  });
  const commits = (globalThis as any).__stage3Rows.filter(
    (r: any) => r.phase === "plot.commit",
  );
  const last = commits.at(-1).detail;
  expect(last.retained.series[metric.metric][0]).toEqual([90, 9]);
  expect(last.provenance.observed[0]).toBe("old");
  expect(last.plot.data).toEqual(plots.instances.at(-1).data);
  expect(last.plot.data[4]).toContain(null);
  expect(last.spanGaps).toBe(false);
  const uploads = plots.uploads;
  view.rerender(panel(b, true));
  expect(plots.uploads).toBe(uploads);
});
it("rejects stale/window mismatched bundles, keeps structural sharing unknown, and invalidates unmount", async () => {
  const h = bundle();
  diagnostic!.response("r", h);
  const view = render(panel(h));
  const before = plots.instances.at(-1).data;
  view.rerender(panel(bundle(110)));
  expect(plots.instances.at(-1).data).toBe(before);
  view.rerender(panel({ ...bundle(140), window_seconds: 60 }));
  expect(plots.instances.at(-1).data).toBe(before);
  expect(diagnostic!.association({ ...h })).toBeNull();
  view.unmount();
  expect(diagnostic!.metadata()).toHaveLength(0);
});
it("StrictMode remount/unmount produces real commits only and cancels panel identities", () => {
  const h = bundle();
  const view = render(<StrictMode>{panel(h)}</StrictMode>);
  expect(diagnostic!.metadata()).toHaveLength(1);
  view.unmount();
  expect(diagnostic!.metadata()).toHaveLength(0);
  const v2 = render(panel(h));
  expect(diagnostic!.metadata()).toHaveLength(1);
  v2.unmount();
  expect(diagnostic!.metadata()).toHaveLength(0);
});
it("missing history never supplies a qualified chart", () => {
  const view = render(panel(undefined));
  expect(plots.instances).toHaveLength(0);
  view.unmount();
});

it("captures actual hidden/error/reduced-motion commits while preserving frozen CSS motion", async () => {
  const h = bundle();
  const view = render(panel(h));
  Object.defineProperty(document, "hidden", {
    configurable: true,
    get: () => true,
  });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
  reduced = true;
  view.rerender(panel(h, true));
  await act(async () => {
    for (let i = 0; i < 50; i++) await Promise.resolve();
  });
  const last = (globalThis as any).__stage3Rows
    .filter((r: any) => r.phase === "plot.commit")
    .at(-1).detail;
  expect(last.hidden).toBe(true);
  expect(last.error).toBe(true);
  expect(last.reducedMotion).toBe(true);
  expect(last.upload).toBe("reuse");
  expect(last.transition).toBe("none");
  view.unmount();
});
it("captures raw-present/rollup-absent and null filtering separately from the logarithmic plot floor", async () => {
  const d = OVERVIEW_METRIC_GRAPHS[3];
  const h = {
    ...bundle(),
    series: {
      [d.metric]: [
        [110, 0],
        [115, null],
        [120, 5],
      ],
    },
    rolling_5m: undefined,
  };
  diagnostic!.response("raw-only", h);
  const view = render(
    <OverviewMetricHistoryPanel
      descriptor={d}
      history={h as any}
      error={false}
      selectedWindowSeconds={30}
      nowMs={120000}
    />,
  );
  await act(async () => {
    for (let i = 0; i < 60; i++) await Promise.resolve();
  });
  const rows = (globalThis as any).__stage3Rows;
  const response = rows.find(
    (r: any) =>
      r.phase === "app.parse_available" && r.detail.metric === d.metric,
  ).detail;
  const last = rows.filter((r: any) => r.phase === "plot.commit").at(-1).detail;
  expect(response.history.series[d.metric]).toEqual([
    [110, 0],
    [115, null],
    [120, 5],
  ]);
  expect(last.retained.series[d.metric]).toEqual([
    [110, 0],
    [120, 5],
  ]);
  expect(last.projection.state).toBe("unavailable");
  expect(last.projection.observed).toEqual([0, null, 5]);
  expect(last.projection.avg).toEqual([null, null, null]);
  expect(last.plot.data[4]).toEqual([1, null, 5]);
  expect(last.logFloor).toBe(1);
  view.unmount();
});
it("an initially abandoned Suspense render never supplies a committed chart", async () => {
  const h = bundle();
  diagnostic!.response("suspended", h);
  const pending = new Promise(() => {});
  function Suspend(): React.ReactNode {
    throw pending;
  }
  const view = render(
    <React.Suspense fallback={<span>waiting</span>}>
      {panel(h)}
      <Suspend />
    </React.Suspense>,
  );
  await act(async () => {
    for (let i = 0; i < 60; i++) await Promise.resolve();
  });
  const rows = (globalThis as any).__stage3Rows;
  expect(rows.some((r: any) => r.phase === "react.render_candidate")).toBe(
    true,
  );
  expect(rows.some((r: any) => r.phase === "plot.commit")).toBe(false);
  expect(diagnostic!.metadata()).toHaveLength(0);
  view.unmount();
});

it("retains the authentic full-size history and captures the real panel's uPlot inputs", async () => {
  const { readFileSync } = await import("node:fs");
  const { resolve } = await import("node:path");
  const path = resolve(
    import.meta.dirname,
    "../../../perf391-a-network-smoke-v1/evidence/runtime/browser/node/artifacts/b0c67faf174567e9523d98a9f2a7a8dac6f86b1d88acb1efe41a4832301b3d45.bin",
  );
  const h = JSON.parse(readFileSync(path, "utf8")).detail.history;
  const id = "synthetic-408a/p/b34655ed4a2b4e82/r1";
  const original = JSON.stringify(h);
  vi.setSystemTime(h.end_timestamp_seconds * 1000);
  diagnostic!.response(id, h);
  const view = render(
    <OverviewMetricHistoryPanel
      descriptor={metric}
      history={h}
      error={false}
      selectedWindowSeconds={1800}
      nowMs={h.end_timestamp_seconds * 1000}
    />,
  );
  await act(async () => {
    for (let i = 0; i < 300; i++) await Promise.resolve();
  });
  expect(diagnostic!.summary().failed).toBe(false);
  const commits = (globalThis as any).__stage3Rows.filter(
    (r: any) => r.phase === "plot.commit",
  );
  expect(commits.length).toBeGreaterThan(0);
  const captured = commits.at(-1);
  expect(captured.op).toBe(id);
  expect(captured.detail.retained.series[metric.metric]).toEqual(
    h.series[metric.metric],
  );
  expect(captured.detail.retained.rolling_5m[metric.metric]).toEqual(
    h.rolling_5m[metric.metric],
  );
  expect(captured.detail.plot.data).toEqual(plots.instances.at(-1).data);
  for (const name of ["observed", "min", "avg", "max"])
    expect(captured.detail.provenance[name]).toEqual(Array(1801).fill(id));
  expect(JSON.stringify(h)).toBe(original);
  view.unmount();
});
