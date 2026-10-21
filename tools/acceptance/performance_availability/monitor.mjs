import { serialReader } from "./serial.mjs";
/** Owned host observer; never a production worker or exporter callback. */
import { setTimeout as delay } from "node:timers/promises";
import {
  CONTRACT_VERSION,
  METRICS,
  validateRecovery,
  validateHistory,
  validateCadence,
  validateObservations,
  validateMeasuredSamples,
} from "./availability.mjs";
export function createMonitor(options, api, out, append) {
  const events = [],
    observations = [];
  let active = true,
    task = null,
    error = null,
    measurement = null;
  const checkpoints = [];
  let nextCheckpoint = Infinity;
  const state = serialReader(async (deadline = Date.now() + 1000) => {
    const remaining = deadline - Date.now();
    if (remaining <= 0) throw new Error("Source observation deadline exceeded");
    const s = await api(
      "/api/_acceptance/availability/state",
      "GET",
      undefined,
      {},
      remaining,
    );
    observations.push(s);
    append("availability-observations.jsonl", s);
    return s;
  });
  async function transition(
    id,
    kind,
    operation,
    phase = "setup",
    required = METRICS,
    mode = "simulation",
  ) {
    const event = {
      id,
      kind,
      phase,
      started_at: Date.now() / 1000,
      required_fields: required,
      expected_mode: mode,
      expected_identity: {
        active_route_id: kind === "deactivation" ? null : "synthetic-route",
      },
    };
    events.push(event);
    out("availability-events.json", events);
    let watching = true,
      watchError = null;
    const watcher = (async () => {
      while (watching) {
        try {
          await state();
        } catch (e) {
          watchError = e;
          break;
        }
        await delay(50);
      }
    })();
    let result;
    try {
      result = await operation();
    } finally {
      event.completed_at = Date.now() / 1000;
      watching = false;
      await watcher;
      out("availability-events.json", events);
    }
    if (watchError) throw watchError;
    let lastError;
    do {
      const sample = await state(event.completed_at * 1000 + 2000);
      try {
        event.recovered = validateRecovery(event, sample);
        break;
      } catch (e) {
        lastError = e;
      }
      await delay(25);
    } while (Date.now() / 1000 <= event.completed_at + 2);
    out("availability-events.json", events);
    if (!event.recovered) throw lastError;
    return result;
  }
  function start() {
    task = (async () => {
      let next = Date.now();
      while (active) {
        try {
          await state();
        } catch (e) {
          error = e;
          break;
        }
        next += 1000;
        await delay(Math.max(0, next - Date.now()));
      }
    })();
  }
  async function stop() {
    active = false;
    await task;
    if (error) throw error;
  }
  async function prom(path, params) {
    const response = await fetch(
      options.prometheus_origin + path + "?" + new URLSearchParams(params),
      { signal: AbortSignal.timeout(30000) },
    );
    if (!response.ok)
      throw new Error("Prometheus evidence HTTP " + response.status);
    const payload = await response.json();
    if (payload.status !== "success")
      throw new Error("Prometheus evidence query failed");
    return payload;
  }
  async function history(h, stage) {
    const start = h.start_timestamp_seconds,
      end = h.end_timestamp_seconds;
    const query = '{__name__=~"' + METRICS.join("|") + '"}';
    const span = Math.ceil(
      Math.max(1810, measurement ? end - measurement.start + 10 : 1810),
    );
    const evaluated = await prom("/api/v1/query_range", {
      query,
      start: String(start),
      end: String(end),
      step: "1",
    });
    const stored = await prom("/api/v1/query", {
      query: query + "[" + span + "s]",
      time: String(end + 1),
    });
    const up = await prom("/api/v1/query", {
      query: 'up{job="starlink-location"}[' + span + "s]",
      time: String(end + 1),
    });
    out(stage + "-history-full.json", h);
    out(stage + "-raw-evaluated.json", evaluated);
    out(stage + "-raw-stored.json", stored);
    out(stage + "-scrapes.json", up);
    const verified = validateHistory({
      history: h,
      evaluated,
      stored,
      events,
      measurement: measurement
        ? { ...measurement, end: measurement.end ?? Date.now() / 1000 }
        : null,
      workload: options.workload,
    });
    checkpoints.push({ stage, start, end });
    out("availability-checkpoints.json", checkpoints);
    out(stage + "-availability-grid.json", verified);
    return verified;
  }
  return {
    transition,
    start,
    stop,
    history,
    begin() {
      measurement = { start: Date.now() / 1000, end: null };
      nextCheckpoint = measurement.start + 900;
      out("availability-boundaries.json", measurement);
    },
    end() {
      measurement.end = Date.now() / 1000;
      out("availability-boundaries.json", measurement);
    },
    async checkpoint() {
      if (Date.now() / 1000 < nextCheckpoint) return;
      const h = await api("/api/overview-history");
      await history(h, "checkpoint-" + checkpoints.length);
      nextCheckpoint = Date.now() / 1000 + 900;
    },
    async finish(h) {
      await stop();
      await state();
      const verified = await history(h, "final");
      const up = JSON.parse(
        await (
          await import("node:fs/promises")
        ).readFile(options.output + "/final-scrapes.json", "utf8"),
      );
      const stored = JSON.parse(
        await (
          await import("node:fs/promises")
        ).readFile(options.output + "/final-raw-stored.json", "utf8"),
      );
      const cadence = validateCadence(up, stored, measurement);
      const availability = validateMeasuredSamples(
        stored,
        measurement,
        events,
        options.workload,
      );
      let covered = measurement.start;
      for (const c of checkpoints) {
        if (c.start <= covered) covered = Math.max(covered, c.end);
      }
      if (covered < Math.floor(measurement.end))
        throw new Error("History validation coverage gap");
      const source = validateObservations(
        observations,
        measurement,
        events,
        options.workload,
      );
      const result = {
        contract_version: CONTRACT_VERSION,
        harness_sha: options.harness_sha,
        status: "passed",
        measurement,
        events,
        cadence,
        availability,
        checkpoints,
        source,
        setup_gaps: verified.setup_gaps,
        finite_coverage: verified.finite_coverage,
      };
      out("availability-result.json", result);
      return result;
    },
  };
}
