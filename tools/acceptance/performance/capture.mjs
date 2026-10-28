/** Read-only API evidence. Never intercept requests or relax the native gate. */
import { createHash } from "node:crypto";

const BODY_LIMIT = 64 * 1024;
const BODY_TIMEOUT_MS = 5000;
const PHASES = ["warmup", "measured", "post", "teardown"];
const RECORD_PATHS = new Set([
  "/api/v2/operator/records",
  "/api/v2/operator/record-changes",
]);

export function identityFromHealth(health) {
  if (
    !health ||
    typeof health !== "object" ||
    !["store_id", "api_epoch", "source_mode"].every(
      (key) => typeof health[key] === "string" && health[key].length > 0,
    ) ||
    typeof health.mission_journal !== "boolean"
  )
    throw new Error("Malformed Operator source identity");
  if (
    health.source_mode === "simulation" &&
    !health.operating_context_id &&
    !health.replay_run_id &&
    (typeof health.simulation_run_id !== "string" || !health.simulation_run_id)
  )
    throw new Error("Malformed Operator simulation source identity");
  const run = health.mission_journal
    ? health.operating_context_id ||
      health.replay_run_id ||
      `idle:${health.simulation_run_id}`
    : health.simulation_run_id;
  if (
    (health.source_mode === "simulation" && !run) ||
    (run != null && typeof run !== "string")
  )
    throw new Error("Malformed Operator simulation source identity");
  return JSON.stringify([
    health.store_id,
    health.api_epoch,
    health.source_mode,
    run ?? null,
  ]);
}

const counters = () => ({
  started: 0,
  terminal: 0,
  inflight: 0,
  cancellations: 0,
  http_errors: 0,
  network_errors: 0,
  observer_errors: 0,
  allowedGPS503: 0,
});

export function createApiCapture({ append, clock }) {
  const requests = new WeakMap();
  const pages = new Map();
  const detach = [];
  const active = new Set();
  const phases = Object.fromEntries(PHASES.map((name) => [name, counters()]));
  let currentPhase = "warmup";
  let captureErrors = 0;
  let unknownTerminal = 0;
  let stopped = false;

  function listen(page, name, handler) {
    page.on(name, handler);
    detach.push(() => page.off(name, handler));
  }

  function observerError(phase) {
    captureErrors++;
    phases[phase].observer_errors++;
  }

  function record(value, phase = currentPhase) {
    try {
      append("api-outcomes.jsonl", value);
    } catch {
      // A broken evidence sink cannot be repaired by writing to that same sink.
      observerError(phase);
    }
  }

  function readUrl(req) {
    const url = new URL(req.url());
    return url.pathname.startsWith("/api/") ? url : null;
  }

  function lookup(req) {
    const entry = requests.get(req);
    if (entry) return entry;
    if (readUrl(req)) {
      unknownTerminal++;
      observerError(currentPhase);
    }
    return null;
  }

  async function captureBody(entry, response) {
    const headers = response.headers();
    const body = {
      contentType: headers["content-type"] ?? null,
      bytes: null,
      sha256: null,
      truncated: false,
      error: null,
    };
    const unsuccessful = entry.status < 200 || entry.status >= 300;
    let timer;
    try {
      const length = headers["content-length"];
      if (length !== undefined && Number(length) > BODY_LIMIT) {
        body.truncated = true;
        body.declaredBytes = Number(length);
        throw new Error("Response Content-Length exceeds capture limit");
      }
      // Playwright exposes a whole Buffer, not a streaming reader. Known-large
      // bodies are rejected above; unknown-length bodies are checked immediately
      // after retrieval. The cap bounds retained evidence, not peak allocation.
      const bytes = await Promise.race([
        response.body(),
        new Promise((_, reject) => {
          timer = setTimeout(
            () => reject(new Error("Response body capture timeout")),
            BODY_TIMEOUT_MS,
          );
        }),
      ]);
      if (!Buffer.isBuffer(bytes))
        throw new Error("Response body is not a Buffer");
      body.bytes = bytes.length;
      body.sha256 = createHash("sha256").update(bytes).digest("hex");
      body.truncated = bytes.length > BODY_LIMIT;
      const text = new TextDecoder("utf-8", { fatal: true }).decode(
        bytes.subarray(0, BODY_LIMIT),
        { stream: body.truncated },
      );
      if (unsuccessful) body.text = text;
      if (body.truncated)
        throw new Error("Response body exceeds capture limit");
      const jsonType = body.contentType?.toLowerCase().includes("json");
      if (unsuccessful) {
        if (jsonType) {
          const payload = JSON.parse(text);
          if (typeof payload?.error?.code === "string")
            entry.classification = payload.error.code;
        }
      } else {
        if (!jsonType) throw new Error("Operator metadata body is not JSON");
        const payload = JSON.parse(text);
        if (!payload || typeof payload !== "object" || Array.isArray(payload))
          throw new Error("Malformed Operator metadata body");
        if (entry.path === "/api/v2/operator/health")
          entry.healthIdentity = identityFromHealth(payload);
        else if (RECORD_PATHS.has(entry.path))
          entry.responseSourceIdentity = identityFromHealth(payload.source);
        else if (entry.path === "/api/v2/operator/context") {
          for (const key of ["mission_id", "operating_context_id"])
            if (payload[key] !== null && typeof payload[key] !== "string")
              throw new Error("Malformed Operator context body");
          entry.context = {
            missionId: payload.mission_id,
            operatingContextId: payload.operating_context_id,
          };
        }
      }
    } catch (error) {
      body.error = String(error.message ?? error);
      observerError(entry.startedPhase);
    } finally {
      clearTimeout(timer);
    }
    return body;
  }

  function observeResponse(entry, response) {
    if (entry.responseObserved) return;
    entry.responseObserved = true;
    entry.status = response.status();
    const allowedGPS503 =
      entry.path === "/api/v2/gps/config" && entry.status === 503;
    if (allowedGPS503) phases[entry.startedPhase].allowedGPS503++;
    else if (entry.status >= 400) phases[entry.startedPhase].http_errors++;
    entry.allowedGPS503 = allowedGPS503;
    const metadata =
      entry.method === "GET" &&
      entry.status === 200 &&
      (RECORD_PATHS.has(entry.path) ||
        entry.path === "/api/v2/operator/health" ||
        entry.path === "/api/v2/operator/context");
    if (entry.status < 200 || entry.status >= 300 || metadata)
      entry.bodyPending = captureBody(entry, response).catch((error) => {
        observerError(entry.startedPhase);
        return { error: String(error.message ?? error) };
      });
  }

  async function finish(entry, req, failed) {
    if (entry.finishing) return;
    entry.finishing = true;
    const terminalPhase = currentPhase;
    let outcome;
    let errorText = null;
    if (failed) {
      errorText = req.failure()?.errorText ?? "Unknown network failure";
      if (errorText === "net::ERR_ABORTED") {
        phases[entry.startedPhase].cancellations++;
        outcome = "client_cancellation";
      } else {
        phases[entry.startedPhase].network_errors++;
        outcome = "network_error";
      }
    }
    try {
      if (!failed && !entry.responseObserved) {
        const response = await req.response();
        if (!response) throw new Error("Finished API request has no response");
        observeResponse(entry, response);
      }
      const body = entry.bodyPending ? await entry.bodyPending : null;
      if (!failed)
        outcome =
          entry.status >= 400 && !entry.allowedGPS503
            ? "http_error"
            : "success";
      const at = clock();
      const page = pages.get(entry.page);
      if (!failed && !body?.error && entry.method === "GET") {
        if (RECORD_PATHS.has(entry.path))
          page.lastRecordCompletion = {
            id: entry.id,
            at,
            sourceIdentity: entry.responseSourceIdentity ?? null,
            status: entry.status,
          };
        else if (entry.path === "/api/v2/operator/health")
          page.lastHealthCompletion = {
            id: entry.id,
            at,
            status: entry.status,
            identity: entry.healthIdentity ?? null,
          };
        else if (entry.path === "/api/v2/operator/context")
          page.lastContextCompletion = {
            id: entry.id,
            at,
            status: entry.status,
            missionId: entry.context?.missionId ?? null,
            operatingContextId: entry.context?.operatingContextId ?? null,
          };
      }
      record(
        {
          ...entry.start,
          event: "terminal",
          at,
          terminalPhase,
          status: entry.status ?? null,
          outcome,
          classification: entry.classification ?? null,
          errorText,
          cancellationCause:
            outcome === "client_cancellation"
              ? terminalPhase === "teardown"
                ? "explicit_teardown"
                : "unknown"
              : null,
          responseSourceIdentity: entry.responseSourceIdentity ?? null,
          healthIdentity: entry.healthIdentity ?? null,
          body,
        },
        entry.startedPhase,
      );
    } catch (error) {
      observerError(entry.startedPhase);
      record(
        {
          ...entry.start,
          event: "terminal",
          at: clock(),
          terminalPhase,
          outcome: "capture_error",
          error: String(error.message ?? error),
        },
        entry.startedPhase,
      );
    } finally {
      phases[entry.startedPhase].terminal++;
      phases[entry.startedPhase].inflight--;
      active.delete(entry);
      const page = pages.get(entry.page);
      page.inflight--;
      if (!page.inflight) page.idleSince = clock();
      // Only a bounded per-page checkpoint survives after completion. The
      // WeakMap association permits duplicate terminal events to be ignored.
      entry.start = null;
      entry.bodyPending = null;
    }
  }

  function guard(fn) {
    return (...args) => {
      try {
        fn(...args);
      } catch {
        observerError(currentPhase);
      }
    };
  }

  function assertHealthy() {
    const measured = phases.measured;
    if (captureErrors || unknownTerminal)
      throw new Error(
        "API capture observer errors or unknown terminal outcomes",
      );
    if (measured.http_errors) throw new Error("Measured API HTTP errors");
    if (measured.cancellations)
      throw new Error("Measured API client cancellations");
    if (measured.network_errors) throw new Error("Measured API network errors");
  }

  return {
    attach(page, index) {
      if (stopped) throw new Error("Capture already stopped");
      if (pages.has(index)) throw new Error("Duplicate capture page index");
      const state = {
        sequence: 0,
        inflight: 0,
        idleSince: clock(),
        lastRecordCompletion: null,
        lastContextCompletion: null,
        lastHealthCompletion: null,
      };
      pages.set(index, state);
      listen(
        page,
        "request",
        guard((req) => {
          const url = readUrl(req);
          if (!url || requests.has(req)) return;
          let frameURL = null;
          try {
            frameURL = req.frame().url();
          } catch {
            // Service worker requests do not necessarily have a frame.
          }
          const entry = {
            id: `p${index}-r${++state.sequence}`,
            page: index,
            path: url.pathname,
            method: req.method(),
            startedPhase: currentPhase,
          };
          entry.start = {
            ...entry,
            event: "start",
            at: clock(),
            url: req.url(),
            query: Object.fromEntries(url.searchParams),
            sourceIdentity: url.searchParams.get("source_identity"),
            frameURL,
            pageURL: page.url(),
          };
          requests.set(req, entry);
          active.add(entry);
          phases[currentPhase].started++;
          phases[currentPhase].inflight++;
          state.inflight++;
          state.idleSince = null;
          record(entry.start, entry.startedPhase);
        }),
      );
      listen(
        page,
        "response",
        guard((response) => {
          const entry = lookup(response.request());
          if (entry) observeResponse(entry, response);
        }),
      );
      for (const [name, failed] of [
        ["requestfinished", false],
        ["requestfailed", true],
      ])
        listen(
          page,
          name,
          guard((req) => {
            const entry = lookup(req);
            if (entry)
              void finish(entry, req, failed).catch(() =>
                observerError(entry.startedPhase),
              );
          }),
        );
    },
    phase(name) {
      if (!PHASES.includes(name)) throw new Error("Unknown capture phase");
      currentPhase = name;
    },
    stop() {
      if (stopped) return;
      if (active.size)
        throw new Error(
          "Cannot stop API capture with active inflight requests",
        );
      for (const remove of detach) remove();
      detach.length = 0;
      stopped = true;
      record({ event: "capture-end", at: clock(), phase: currentPhase });
    },
    snapshot(index) {
      const page = pages.get(index);
      if (!page) throw new Error("Unknown capture page");
      const { sequence, ...snapshot } = page;
      return structuredClone(snapshot);
    },
    async drain(timeoutMs = 10000) {
      const deadline = performance.now() + timeoutMs;
      while ([...active].some((entry) => entry.startedPhase === "measured")) {
        if (performance.now() >= deadline) {
          observerError("measured");
          throw new Error(
            "API capture drain timeout: unfinished measured requests",
          );
        }
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
    },
    summary() {
      const measured = phases.measured;
      return {
        phases: structuredClone(phases),
        capture_errors: captureErrors,
        unknown_terminal: unknownTerminal,
        qualification_clean:
          measured.started > 0 &&
          measured.inflight === 0 &&
          measured.started === measured.terminal &&
          measured.http_errors === 0 &&
          measured.cancellations === 0 &&
          measured.network_errors === 0 &&
          captureErrors === 0 &&
          unknownTerminal === 0,
      };
    },
    assertHealthy,
  };
}
