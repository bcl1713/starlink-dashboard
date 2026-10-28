/** Observe natural read boundaries; never pause, intercept, or suppress requests. */
import { performance } from "node:perf_hooks";

const defaults = {
  clock: () => performance.now() / 1000,
  sleep: () => new Promise((resolve) => setTimeout(resolve, 20)),
  timeoutMs: 10000,
  idleMs: 75,
};

async function wait(capture, label, condition, settings) {
  const options = { ...defaults, ...settings };
  const start = options.clock();
  while (true) {
    capture.assertHealthy();
    const result = condition(options.clock(), options.idleMs);
    if (result)
      return { ...result, waited_ms: (options.clock() - start) * 1000 };
    if ((options.clock() - start) * 1000 >= options.timeoutMs)
      throw new Error(`Operator ${label} timeout; no traffic was suppressed`);
    await options.sleep();
  }
}

function idle(state, now, idleMs) {
  return (
    state.inflight === 0 &&
    typeof state.idleSince === "number" &&
    (now - state.idleSince) * 1000 >= idleMs
  );
}

export async function waitForReadBoundary(capture, page, options = {}) {
  const field = options.recordsActive
    ? "lastRecordCompletion"
    : "lastContextCompletion";
  const initial = capture.snapshot(page)[field]?.id;
  return wait(
    capture,
    "read boundary",
    (now, idleMs) => {
      const state = capture.snapshot(page),
        read = state[field];
      if (
        !read ||
        read.id === initial ||
        read.status !== 200 ||
        (options.recordsActive && !read.sourceIdentity) ||
        !idle(state, now, idleMs)
      )
        return null;
      return {
        kind: options.recordsActive ? "records" : "context",
        request_id: read.id,
        source_identity: read.sourceIdentity ?? null,
        observed_idle_ms: (now - state.idleSince) * 1000,
      };
    },
    options,
  );
}

export async function waitForSource(capture, page, options) {
  return wait(
    capture,
    "source recovery",
    (now, idleMs) => {
      const state = capture.snapshot(page),
        health = state.lastHealthCompletion;
      const context = state.lastContextCompletion,
        records = state.lastRecordCompletion;
      const selected = options.recordsActive
        ? context?.missionId === options.missionId &&
          records?.status === 200 &&
          records.sourceIdentity === options.identity
        : context?.missionId === null;
      if (
        !selected ||
        context?.status !== 200 ||
        health?.status !== 200 ||
        health.identity !== options.identity ||
        !idle(state, now, idleMs)
      )
        return null;
      return {
        identity: options.identity,
        records_active: options.recordsActive,
        health_request_id: health.id,
        context_request_id: context.id,
        records_request_id: options.recordsActive ? records.id : null,
        observed_idle_ms: (now - state.idleSince) * 1000,
      };
    },
    options,
  );
}

export async function waitForAllIdle(capture, count, options = {}) {
  return wait(
    capture,
    "terminal drain",
    (now, idleMs) => {
      const states = Array.from({ length: count }, (_, page) =>
        capture.snapshot(page),
      );
      return states.every((state) => idle(state, now, idleMs))
        ? { pages: count }
        : null;
    },
    options,
  );
}
