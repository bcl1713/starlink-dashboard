import assert from "node:assert/strict";
import { test } from "node:test";
import {
  CONTRACT_VERSION,
  METRICS,
  validateHistory,
  validateRecovery,
  validateCadence,
} from "./availability.mjs";
const matrix = (result) => ({
  status: "success",
  data: { resultType: "matrix", result },
});
function fixture() {
  const start = 1000,
    end = 2800;
  const result = METRICS.map((name) => ({
    metric: { __name__: name },
    values: Array.from({ length: 1801 }, (_, i) => [start + i, "1"]),
  }));
  const stored = METRICS.map((name) => ({
    metric: { __name__: name },
    values: Array.from({ length: 1803 }, (_, i) => [start - 1 + i + 0.25, "1"]),
  }));
  return {
    history: {
      window_seconds: 1800,
      step_seconds: 1,
      start_timestamp_seconds: start,
      end_timestamp_seconds: end,
      series: Object.fromEntries(
        result.map((s) => [
          s.metric.__name__,
          s.values.map(([t, v]) => [t, +v]),
        ]),
      ),
    },
    evaluated: matrix(result),
    stored: matrix(stored),
    events: [],
    measurement: { start: 2700, end: 2799 },
    workload: "steady",
  };
}
function gap(f, name, t) {
  f.evaluated.data.result.find((s) => s.metric.__name__ === name).values[
    t - 1000
  ][1] = "NaN";
  f.stored.data.result
    .find((s) => s.metric.__name__ === name)
    .values.find((p) => p[0] === t - 0.75)[1] = "NaN";
  f.history.series[name] = f.history.series[name].filter((p) => p[0] !== t);
}
function recovery(at = 2000, fields = METRICS) {
  return {
    at,
    publication: { state: "ready" },
    source: {
      mode: "simulation",
      metric_source: "simulated",
      acquired_at: at - 0.1,
    },
    fields: Object.fromEntries(
      METRICS.map((n) => [n, { available: fields.includes(n) }]),
    ),
  };
}
function event() {
  return {
    id: "setup-activation",
    kind: "activation",
    phase: "setup",
    started_at: 1998,
    completed_at: 1999,
    recovered: recovery(),
    required_fields: METRICS,
    expected_mode: "simulation",
  };
}
test("finite histories preserve the complete 1801-slot grid", () => {
  const r = validateHistory(fixture());
  assert.equal(r.contract_version, CONTRACT_VERSION);
  assert.equal(r.timestamps.length, 1801);
  assert.equal(r.timestamps[1800], 2800);
});
test("explained activation NaN occupies its original slot, API remains sparse", () => {
  const f = fixture();
  f.events = [event()];
  for (const n of METRICS) gap(f, n, 1999);
  const r = validateHistory(f);
  assert.equal(r.series[METRICS[0]][999], null);
  assert.equal(r.setup_gaps[METRICS[0]], 1);
  assert.equal(f.history.series[METRICS[0]].length, 1800);
});
test("unexplained steady NaN is rejected", () => {
  const f = fixture();
  gap(f, METRICS[0], 2750);
  assert.throws(() => validateHistory(f), /unexplained|steady/);
});
test("setup allowance cannot excuse a measured NaN", () => {
  const f = fixture();
  f.events = [
    {
      ...event(),
      started_at: 2748,
      completed_at: 2749,
      recovered: recovery(2750),
    },
  ];
  gap(f, METRICS[0], 2750);
  assert.throws(() => validateHistory(f), /setup.*measurement|steady/);
});
test("shifted API timestamp fails even when point count matches", () => {
  const f = fixture();
  f.history.series[METRICS[0]][100][0] += 0.1;
  assert.throws(() => validateHistory(f), /API|grid/);
});
test("shifted raw grid is distinct from a NaN", () => {
  const f = fixture();
  f.evaluated.data.result[0].values[100][0] += 0.1;
  assert.throws(() => validateHistory(f), /grid/);
});
test("missing raw series is rejected", () => {
  const f = fixture();
  f.evaluated.data.result.pop();
  assert.throws(() => validateHistory(f), /missing.*series/);
});
test("missing raw evaluation cannot be excused as unavailability", () => {
  const f = fixture();
  f.evaluated.data.result[0].values.splice(100, 1);
  assert.throws(() => validateHistory(f), /grid/);
});
test("API deletion of finite raw sample is a projection failure", () => {
  const f = fixture();
  f.history.series[METRICS[0]].splice(100, 1);
  assert.throws(() => validateHistory(f), /API.*filter|projection/);
});
test("fabricated finite API value over raw NaN is a projection failure", () => {
  const f = fixture();
  f.evaluated.data.result[0].values[100][1] = "NaN";
  assert.throws(() => validateHistory(f), /API.*filter|projection/);
});
test("four explained setup NaNs still exceed the bound", () => {
  const f = fixture();
  f.events = [{ ...event(), started_at: 1996 }];
  for (const t of [1997, 1998, 1999, 2000]) gap(f, METRICS[0], t);
  assert.throws(() => validateHistory(f), /three|coverage/);
});
test("infinity is not an unavailable observation", () => {
  const f = fixture();
  f.evaluated.data.result[0].values[100][1] = "+Inf";
  assert.throws(() => validateHistory(f), /nonfinite|NaN/);
});
test("late and persistently unavailable startup do not recover", () => {
  assert.throws(
    () => validateRecovery(event(), recovery(2002)),
    /recovery.*deadline/,
  );
  assert.throws(
    () => validateRecovery(event(), recovery(2000, [])),
    /unavailable/,
  );
});
test("ready is insufficient without a fresh acquisition", () => {
  const s = recovery();
  s.source.acquired_at = 1980;
  assert.throws(() => validateRecovery(event(), s), /fresh/);
});
test("source mode and provenance must agree", () => {
  const s = recovery();
  s.source.metric_source = "observed";
  assert.throws(() => validateRecovery(event(), s), /provenance/);
});
test("successful recovery records actual publication and field availability", () => {
  const r = validateRecovery(event(), recovery());
  assert.equal(r.at, 2000);
});
test("field-specific replay availability is not replaced with finite network values", () => {
  const fields = METRICS.slice(0, 5),
    e = { ...event(), expected_mode: "replay", required_fields: fields },
    s = recovery(2000, fields);
  s.source.mode = "replay";
  s.source.metric_source = "simulated";
  s.source.replay_run_id = "run";
  s.source.replay_mission_time = 123;
  assert.equal(validateRecovery(e, s).fields[METRICS[5]].available, false);
});
test("missing actual scrape fails despite a completely finite evaluation grid", () => {
  const up = matrix([
    {
      metric: { __name__: "up" },
      values: Array.from({ length: 11 }, (_, i) => [2700 + i + 0.25, "1"]),
    },
  ]);
  up.data.result[0].values.splice(4, 1);
  assert.throws(
    () => validateCadence(up, fixture().stored, { start: 2700, end: 2711 }),
    /scrape.*gap/,
  );
});
test("failed scrape differs from explicit NaN", () => {
  const up = matrix([
    {
      metric: { __name__: "up" },
      values: [
        [2700.25, "1"],
        [2701.25, "0"],
        [2702.25, "1"],
      ],
    },
  ]);
  assert.throws(
    () => validateCadence(up, fixture().stored, { start: 2700, end: 2703 }),
    /scrape.*failed/,
  );
});
test("healthy actual 1Hz scrapes are verified independently", () => {
  const up = matrix([
    {
      metric: { __name__: "up" },
      values: Array.from({ length: 11 }, (_, i) => [2700 + i + 0.25, "1"]),
    },
  ]);
  assert.equal(
    validateCadence(up, fixture().stored, { start: 2700, end: 2711 }).samples,
    11,
  );
});
test("omitted exporter family cannot hide behind Prometheus lookback", () => {
  const f = fixture();
  f.stored.data.result[0].values = f.stored.data.result[0].values.filter(
    (p) => p[0] !== 2704.25,
  );
  const up = matrix([
    {
      metric: { __name__: "up" },
      values: Array.from({ length: 11 }, (_, i) => [2700 + i + 0.25, "1"]),
    },
  ]);
  assert.throws(
    () => validateCadence(up, f.stored, { start: 2700, end: 2711 }),
    /missing.*sample/,
  );
});

const { validateObservations } = await import("./availability.mjs");
test("steady observer rejects unchanged acquisition clocks", () => {
  const observations = Array.from({ length: 11 }, (_, i) => ({
    ...recovery(2700 + i),
    source: { ...recovery().source, acquired_at: 2700 },
  }));
  assert.throws(
    () => validateObservations(observations, { start: 2700, end: 2710 }),
    /stalled|acquisition/,
  );
});
test("steady observer rejects pending frames even if a sample is finite", () => {
  const observations = Array.from({ length: 11 }, (_, i) => recovery(2700 + i));
  observations[4].publication.state = "pending";
  assert.throws(
    () => validateObservations(observations, { start: 2700, end: 2710 }),
    /Publication/,
  );
});
test("steady observer reports actual fresh acquisition progress", () => {
  const observations = Array.from({ length: 11 }, (_, i) => recovery(2700 + i));
  assert.equal(
    validateObservations(observations, { start: 2700, end: 2710 })
      .distinct_acquisitions,
    11,
  );
});
test("startup without a recovered observation is rejected, even for a finite history", () => {
  const f = fixture();
  f.events = [event()];
  delete f.events[0].recovered;
  assert.throws(() => validateHistory(f), /recovery/);
});
test("a setup transition outside the measured interval is not a blanket permission", () => {
  const f = fixture();
  f.events = [event()];
  gap(f, METRICS[0], 2500);
  assert.throws(() => validateHistory(f), /unexplained/);
});
test("partial setup field loss preserves other aligned series", () => {
  const f = fixture();
  f.events = [event()];
  gap(f, METRICS[3], 1999);
  const r = validateHistory(f);
  assert.equal(r.series[METRICS[3]][999], null);
  assert.equal(r.series[METRICS[0]][999], 1);
});
test("a replay source cannot be mistaken for legacy simulation", () => {
  const s = recovery();
  s.source.mode = "replay";
  assert.throws(() => validateRecovery(event(), s), /provenance/);
});
const { validateMeasuredSamples } = await import("./availability.mjs");
test("an early measured NaN outside the final 30-minute history cannot escape", () => {
  const f = fixture();
  f.stored.data.result[0].values.find((p) => p[0] === 1100.25)[1] = "NaN";
  assert.throws(
    () =>
      validateMeasuredSamples(
        f.stored,
        { start: 1000, end: 2800 },
        [],
        "steady",
      ),
    /steady/,
  );
});
test("recovery rejects a fresh frame from the wrong route or replay run", () => {
  const e = {
    ...event(),
    expected_identity: { active_route_id: "new", replay_run_id: "new-run" },
  };
  const s = recovery();
  s.source.active_route_id = "old";
  s.source.replay_run_id = "old-run";
  assert.throws(() => validateRecovery(e, s), /identity/);
});
test("unexplained steady coordinator changes fail", () => {
  const samples = Array.from({ length: 11 }, (_, i) => recovery(2700 + i));
  for (const s of samples) s.source.coordinator_id = "a";
  samples[7].source.coordinator_id = "b";
  assert.throws(
    () => validateObservations(samples, { start: 2700, end: 2710 }),
    /identity/,
  );
});
for (const workload of ["steady", "transitions"])
  test("localized acquisition stall fails in " + workload, () => {
    const samples = Array.from({ length: 31 }, (_, i) => recovery(2700 + i));
    for (let i = 10; i < 18; i++) samples[i].source.acquired_at = 2709.9;
    assert.throws(
      () =>
        validateObservations(samples, { start: 2700, end: 2730 }, [], workload),
      /acquisition.*stalled/,
    );
  });
