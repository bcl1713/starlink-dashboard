/** Acceptance-only contract. Sparse API values never redefine the time grid. */
export const CONTRACT_VERSION = "perf390-availability-v2";
export const METRICS = [
  "latitude_degrees",
  "longitude_degrees",
  "altitude_feet",
  "speed_knots",
  "heading_degrees",
]
  .map((n) => "starlink_dish_" + n)
  .concat(
    [
      "latency_ms_current",
      "throughput_down_mbps_current",
      "throughput_up_mbps_current",
      "packet_loss_percent",
    ].map((n) => "starlink_network_" + n),
    ["starlink_dish_obstruction_percent", "starlink_signal_quality_percent"],
  );
const fail = (message) => {
  throw new Error(message);
};
function value(raw) {
  if (raw === "NaN") return null;
  if (
    (typeof raw !== "number" && typeof raw !== "string") ||
    raw === "" ||
    !Number.isFinite(Number(raw))
  )
    fail("Invalid nonfinite value; only explicit NaN is unavailable");
  return Number(raw);
}
function matrix(payload, names) {
  if (
    payload?.status !== "success" ||
    payload.data?.resultType !== "matrix" ||
    !Array.isArray(payload.data.result)
  )
    fail("Missing successful raw Prometheus matrix");
  const result = {};
  for (const series of payload.data.result) {
    const name = series.metric?.__name__;
    if (!names.includes(name) || result[name])
      fail("Unexpected or ambiguous raw series identity");
    if (!Array.isArray(series.values)) fail("Missing raw sample values");
    let previous = -Infinity;
    result[name] = series.values.map((pair) => {
      if (
        !Array.isArray(pair) ||
        pair.length !== 2 ||
        !Number.isFinite(pair[0]) ||
        pair[0] <= previous
      )
        fail("Invalid raw time grid/order");
      previous = pair[0];
      return [pair[0], value(pair[1])];
    });
  }
  for (const name of names)
    if (!result[name]) fail("missing raw series: " + name);
  return result;
}
export function validateRecovery(event, sample) {
  if (
    !Number.isFinite(event.started_at) ||
    !Number.isFinite(event.completed_at) ||
    event.started_at > event.completed_at ||
    !Number.isFinite(sample?.at) ||
    sample.at < event.completed_at ||
    sample.at > event.completed_at + 2
  )
    fail("Setup recovery deadline exceeded or invalid event times");
  if (!["ready", "legacy-untracked"].includes(sample.publication?.state))
    fail("Publication unavailable during recovery");
  const source = sample.source;
  for (const [key, expected] of Object.entries(event.expected_identity || {})) {
    if (source?.[key] !== expected) fail("Source identity mismatch: " + key);
  }
  for (const [key, expected] of Object.entries(sample.expected_source || {})) {
    if (source?.[key] !== expected)
      fail("Authoritative source identity mismatch: " + key);
  }
  if (
    !source ||
    source.mode !== event.expected_mode ||
    source.metric_source !== (source.mode === "live" ? "observed" : "simulated")
  )
    fail("Source provenance mismatch");
  if (
    !Number.isFinite(source.acquired_at) ||
    sample.at - source.acquired_at > 10 ||
    source.acquired_at > sample.at + 0.1
  )
    fail("Source acquisition is not fresh");
  if (
    source.mode === "replay" &&
    (!source.replay_run_id || !Number.isFinite(source.replay_mission_time))
  )
    fail("Replay provenance lacks run identity/mission clock");
  if (
    !Array.isArray(event.required_fields) ||
    !event.required_fields.length ||
    event.required_fields.some(
      (n) => !METRICS.includes(n) || sample.fields?.[n]?.available !== true,
    )
  )
    fail("Required observation fields unavailable during recovery");
  return sample;
}
export function validateHistory({
  history,
  evaluated,
  stored,
  events,
  measurement,
  workload = "steady",
}) {
  const h = history,
    start = h?.start_timestamp_seconds,
    end = h?.end_timestamp_seconds;
  if (
    h?.window_seconds !== 1800 ||
    h.step_seconds !== 1 ||
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    end - start !== 1800
  )
    fail("History grid must be the inclusive 30-minute 1Hz window");
  if (!["steady", "transitions"].includes(workload)) fail("Unknown workload");
  if (
    measurement &&
    (!Number.isFinite(measurement.start) ||
      !Number.isFinite(measurement.end) ||
      measurement.end < measurement.start)
  )
    fail("Invalid measurement boundary");
  const raw = matrix(evaluated, METRICS),
    samples = matrix(stored, METRICS);
  const timestamps = Array.from({ length: 1801 }, (_, i) => start + i);
  const eventIds = new Set();
  for (const e of events) {
    if (
      !e.id ||
      eventIds.has(e.id) ||
      !["activation", "configuration", "deactivation"].includes(e.kind) ||
      !["setup", "transition"].includes(e.phase)
    )
      fail("Undocumented controlled transition");
    eventIds.add(e.id);
    validateRecovery(e, e.recovered);
    if (
      measurement &&
      e.phase === "setup" &&
      e.recovered.at >= measurement.start
    )
      fail("setup overlaps measurement boundary");
    if (e.phase === "transition" && workload !== "transitions")
      fail("Transition exception is forbidden in steady workload");
  }
  const apiNames = Object.keys(h.series || {});
  if (apiNames.some((n) => !METRICS.includes(n))) fail("Unexpected API series");
  const output = {
    contract_version: CONTRACT_VERSION,
    timestamps,
    series: {},
    setup_gaps: {},
    exceptions: [],
    finite_coverage: {},
  };
  for (const name of METRICS) {
    const expected = raw[name];
    if (
      expected.length !== timestamps.length ||
      expected.some((p, i) => p[0] !== timestamps[i])
    )
      fail("Incomplete or shifted raw evaluation grid: " + name);
    const projected = expected.filter((p) => p[1] !== null);
    const api = h.series[name] || [];
    if (
      !Array.isArray(api) ||
      api.length !== projected.length ||
      api.some(
        (p, i) =>
          !Array.isArray(p) ||
          p.length !== 2 ||
          !Number.isFinite(p[1]) ||
          p[0] !== projected[i][0] ||
          p[1] !== projected[i][1],
      )
    )
      fail("API filtering/projection error: " + name);
    output.series[name] = expected.map((p) => p[1]);
    output.setup_gaps[name] = 0;
    output.finite_coverage[name] = projected.length / timestamps.length;
    const counts = new Map();
    let cursor = 0;
    for (const [t, v] of expected) {
      while (
        cursor + 1 < samples[name].length &&
        samples[name][cursor + 1][0] <= t
      )
        cursor++;
      const actual = samples[name][cursor];
      if (!actual || actual[0] > t || t - actual[0] > 300 || actual[1] !== v)
        fail("Raw stored sample/evaluation disagreement: " + name);
      if (v !== null) continue;
      const event = events.find(
        (e) =>
          actual[0] >= e.started_at &&
          actual[0] <= e.recovered.at &&
          actual[0] <= e.completed_at + 2,
      );
      if (
        measurement &&
        actual[0] >= measurement.start &&
        actual[0] <= measurement.end &&
        (workload === "steady" || event?.phase !== "transition")
      )
        fail("unexplained steady-state NaN: " + name);
      if (!event) fail("unexplained unavailable sample: " + name);
      counts.set(event.id, (counts.get(event.id) || 0) + 1);
      if (counts.get(event.id) > 3)
        fail(
          "More than three unavailable samples for controlled transition: " +
            name,
        );
      if (event.phase === "setup") output.setup_gaps[name]++;
      output.exceptions.push({
        metric: name,
        evaluation_at: t,
        sample_at: actual[0],
        event_id: event.id,
      });
    }
    if (
      output.setup_gaps[name] > 3 ||
      (workload === "steady" && output.finite_coverage[name] < 0.998)
    )
      fail("Setup coverage exceeds three samples: " + name);
  }
  return output;
}
export function validateCadence(upPayload, storedPayload, interval) {
  if (
    !Number.isFinite(interval.start) ||
    !Number.isFinite(interval.end) ||
    interval.end - interval.start < 2
  )
    fail("Invalid cadence measurement interval");
  const all = matrix(upPayload, ["up"]).up;
  const up = all.filter((p) => p[0] >= interval.start && p[0] <= interval.end);
  if (up.some((p) => p[1] !== 1)) fail("Prometheus scrape failed");
  if (
    up.length < Math.floor(interval.end - interval.start) - 1 ||
    !up.length ||
    up[0][0] - interval.start > 1.25 ||
    interval.end - up.at(-1)[0] > 1.25 ||
    up.some(
      (p, i) => i && (p[0] - up[i - 1][0] > 1.25 || p[0] - up[i - 1][0] < 0.75),
    )
  )
    fail("Actual scrape cadence gap");
  const stored = matrix(storedPayload, METRICS);
  for (const name of METRICS) {
    const times = new Set(stored[name].map((p) => Math.round(p[0] * 1000)));
    if (up.some((p) => !times.has(Math.round(p[0] * 1000))))
      fail("missing exported sample at actual successful scrape: " + name);
  }
  return {
    samples: up.length,
    first: up[0][0],
    last: up.at(-1)[0],
    max_gap_seconds: Math.max(...up.slice(1).map((p, i) => p[0] - up[i][0])),
  };
}

export function validateObservations(
  observations,
  measurement,
  events = [],
  workload = "steady",
) {
  const selected = observations.filter(
    (s) => s.at >= measurement.start && s.at <= measurement.end,
  );
  if (
    !selected.length ||
    selected[0].at - measurement.start > 1.5 ||
    measurement.end - selected.at(-1).at > 1.5 ||
    selected.some(
      (s, i) =>
        i && (s.at - selected[i - 1].at > 1.5 || s.at <= selected[i - 1].at),
    )
  )
    fail("Source observer cadence gap");
  const acquisitions = new Set();
  let previous = -Infinity,
    progressAt = null;
  const initial = selected[0].source;
  for (const s of selected) {
    const event = events.find(
      (e) =>
        e.phase === "transition" &&
        s.at >= e.started_at &&
        s.at <= e.recovered.at,
    );
    if (workload === "transitions" && event) {
      previous = -Infinity;
      progressAt = null;
      continue;
    }
    const binding =
      [...events].reverse().find((e) => e.recovered.at <= s.at)?.recovered
        .source || initial;
    for (const key of [
      "coordinator_id",
      "active_route_id",
      "replay_runtime_id",
      "replay_run_id",
    ]) {
      if (s.source[key] !== binding[key])
        fail("Unexpected steady source identity change: " + key);
    }
    validateRecovery(
      {
        started_at: s.at,
        completed_at: s.at,
        expected_mode: "simulation",
        required_fields: METRICS,
      },
      s,
    );
    if (s.source.acquired_at < previous)
      fail("Source acquisition clock moved backwards");
    if (s.source.acquired_at > previous) progressAt = s.at;
    else if (progressAt !== null && s.at - progressAt > 2.1)
      fail("Source acquisition locally stalled");
    previous = s.source.acquired_at;
    acquisitions.add(previous);
  }
  if (
    workload === "steady" &&
    acquisitions.size < Math.floor((measurement.end - measurement.start) / 2)
  )
    fail("Source acquisition stalled");
  return {
    samples: selected.length,
    distinct_acquisitions: acquisitions.size,
    first: selected[0].at,
    last: selected.at(-1).at,
  };
}

export function validateMeasuredSamples(
  payload,
  measurement,
  events,
  workload,
) {
  const stored = matrix(payload, METRICS),
    exceptions = [];
  for (const name of METRICS) {
    const counts = new Map();
    for (const [t, v] of stored[name]) {
      if (t < measurement.start || t > measurement.end || v !== null) continue;
      const event = events.find(
        (e) =>
          e.phase === "transition" && t >= e.started_at && t <= e.recovered.at,
      );
      if (workload !== "transitions" || !event)
        fail("unexplained steady-state stored NaN: " + name);
      counts.set(event.id, (counts.get(event.id) || 0) + 1);
      if (counts.get(event.id) > 3)
        fail("More than three unavailable transition samples: " + name);
      exceptions.push({ metric: name, sample_at: t, event_id: event.id });
    }
  }
  return { exceptions };
}
