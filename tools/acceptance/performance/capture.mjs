/** Read-only API evidence. Never intercept requests or relax the native gate. */
import { createHash } from "node:crypto";

const BODY_LIMIT = 64 * 1024;
const BODY_TIMEOUT_MS = 5000;
const PHASES = ["warmup", "measured", "post", "teardown"];
const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const CDP_BUFFERS = {
  maxTotalBufferSize: 8 * 1024 * 1024,
  maxResourceBufferSize: 1024 * 1024,
  maxPostDataSize: 0,
};
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
  const transitions = [];
  const measuredCancellations = new Map();
  const abortInvocations = new Map();
  const abortHooks = new Map();
  const networkStates = new Map();
  const sessionDetaches = new Set();
  let verifiedCancellations = new Set();
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

  function cancellationMarker(entry, at) {
    if (
      entry.method !== "GET" ||
      entry.path !== "/api/v2/operator/events" ||
      entry.start.resourceType !== "xhr"
    )
      return null;
    return transitions.find(
      (marker) =>
        entry.start.query.mission_id === marker.missionId &&
        entry.start.at >= marker.at - 2 &&
        entry.start.at <= marker.at + 10 &&
        at >= marker.at - 2 &&
        at <= marker.at + 10 &&
        ![...measuredCancellations.values()].some(
          (previous) =>
            previous.page === entry.page && previous.transitionId === marker.id,
        ),
    );
  }

  function pairNetworkStart(index, key, value, network) {
    const state = networkStates.get(index);
    const own = network ? state.network : state.requests;
    const other = network ? state.requests : state.network;
    const waiting = other.get(key);
    if (waiting?.length) {
      const match = waiting.shift();
      if (!waiting.length) other.delete(key);
      state.unmatched--;
      const entry = network ? match : value;
      entry.networkStart = network ? value : match;
    } else {
      if (state.unmatched >= 1024) {
        observerError(currentPhase);
        return;
      }
      const queue = own.get(key) ?? [];
      queue.push(value);
      own.set(key, queue);
      state.unmatched++;
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
        else if (entry.path === "/api/v2/operator/events") {
          if (
            !["store_id", "api_epoch", "source_mode", "mission_id"].every(
              (key) => typeof payload[key] === "string" && payload[key],
            ) ||
            (payload.simulation_run_id !== null &&
              typeof payload.simulation_run_id !== "string")
          )
            throw new Error("Malformed Operator event source metadata");
          entry.eventSource = {
            identity: JSON.stringify([
              payload.store_id,
              payload.api_epoch,
              payload.source_mode,
              payload.simulation_run_id,
            ]),
            missionId: payload.mission_id,
          };
        } else if (entry.path === "/api/v2/operator/context") {
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
    if (REDIRECT_STATUSES.has(entry.status)) {
      const headers = response.headers();
      entry.redirect = true;
      entry.classification = "http_redirect";
      entry.redirectLocation = headers.location ?? null;
      const body = {
        contentType: headers["content-type"] ?? null,
        bytes: null,
        sha256: null,
        truncated: false,
        error: null,
        unavailableByProtocol: true,
        notCapturedReason: "chromium_redirect_body_unavailable",
      };
      // Chromium does not expose redirect bodies through Playwright. Preserve
      // the response/chain metadata rather than requesting an unavailable body.
      if (
        typeof entry.redirectLocation !== "string" ||
        !entry.redirectLocation.trim()
      ) {
        body.error = "Redirect response is missing its Location header";
        observerError(entry.startedPhase);
      }
      entry.bodyPending = Promise.resolve(body);
      return;
    }
    const metadata =
      entry.method === "GET" &&
      entry.status === 200 &&
      (RECORD_PATHS.has(entry.path) ||
        entry.path === "/api/v2/operator/health" ||
        entry.path === "/api/v2/operator/events" ||
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
        if (entry.startedPhase === "measured") {
          const at = clock();
          const marker = cancellationMarker(entry, at);
          if (measuredCancellations.size >= 32) observerError("measured");
          else
            measuredCancellations.set(entry.id, {
              ...entry.start,
              terminalAt: at,
              transitionId: marker?.id ?? null,
            });
          verifiedCancellations = new Set();
        }
      } else {
        phases[entry.startedPhase].network_errors++;
        outcome = "network_error";
      }
    }
    try {
      if (networkStates.has(entry.page) && !entry.networkStart) {
        const deadline = performance.now() + 500;
        while (!entry.networkStart && performance.now() < deadline)
          await new Promise((resolve) => setTimeout(resolve, 5));
        if (!entry.networkStart) observerError(entry.startedPhase);
      }
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
            : entry.redirect
              ? "redirect"
              : "success";
      const at = clock();
      const wallTimeMs = Date.now();
      const cancellation = measuredCancellations.get(entry.id);
      if (cancellation) {
        cancellation.wallTimeMs = wallTimeMs;
        Object.assign(cancellation, entry.networkStart);
      }
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
          ...entry.networkStart,
          event: "terminal",
          at,
          wallTimeMs,
          terminalPhase,
          status: entry.status ?? null,
          outcome,
          classification: entry.classification ?? null,
          redirectLocation: entry.redirectLocation ?? null,
          errorText,
          cancellationCause:
            outcome === "client_cancellation"
              ? terminalPhase === "teardown"
                ? "explicit_teardown"
                : "unknown"
              : null,
          responseSourceIdentity: entry.responseSourceIdentity ?? null,
          healthIdentity: entry.healthIdentity ?? null,
          context: entry.context ?? null,
          eventSource: entry.eventSource ?? null,
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
          wallTimeMs: Date.now(),
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
    if (
      measuredCancellations.size !== measured.cancellations ||
      [...measuredCancellations.values()].some((entry) => !entry.transitionId)
    )
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
          const redirectedFrom = req.redirectedFrom?.();
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
            wallStartTimeMs: req.timing?.()?.startTime ?? null,
            wallStartTimeSource: "playwright.timing.startTime",
            resourceType: req.resourceType?.() ?? null,
            url: req.url(),
            query: Object.fromEntries(url.searchParams),
            sourceIdentity: url.searchParams.get("source_identity"),
            redirectedFromId: requests.get(redirectedFrom)?.id ?? null,
            redirectedFromURL: redirectedFrom?.url() ?? null,
            frameURL,
            pageURL: page.url(),
          };
          requests.set(req, entry);
          active.add(entry);
          phases[currentPhase].started++;
          phases[currentPhase].inflight++;
          state.inflight++;
          state.idleSince = null;
          if (networkStates.has(index))
            pairNetworkStart(
              index,
              JSON.stringify([entry.method, req.url()]),
              entry,
              false,
            );
          record({ ...entry.start, ...entry.networkStart }, entry.startedPhase);
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
    async observeClientAborts(page, index) {
      if (!pages.has(index) || stopped || abortHooks.has(index))
        throw new Error("Invalid client abort observer installation");
      const bindingName = `__issue393ClientAbortV2_${index}`;
      try {
        await page.exposeBinding(bindingName, (source, value) => {
          if (stopped) return false;
          try {
            if (source.page !== page || value?.observerError)
              throw new Error(
                value?.observerError || "Abort observer page mismatch",
              );
            if (
              !value ||
              typeof value.id !== "string" ||
              value.id.length > 200 ||
              typeof value.url !== "string" ||
              typeof value.method !== "string" ||
              value.mechanism !== "xhr.abort" ||
              !Number.isFinite(value.sendWallTimeMs) ||
              !Number.isFinite(value.abortWallTimeMs) ||
              value.abortWallTimeMs < value.sendWallTimeMs ||
              !new URL(value.url).pathname.startsWith("/api/")
            )
              throw new Error("Malformed actual client abort invocation");
            const id = `p${index}-${value.id}`;
            if (abortInvocations.has(id) || abortInvocations.size >= 1024)
              throw new Error(
                "Duplicate abort invocation or bounded observer capacity exceeded",
              );
            const invocation = {
              id,
              page: index,
              method: value.method,
              url: value.url,
              sendWallTimeMs: value.sendWallTimeMs,
              abortWallTimeMs: value.abortWallTimeMs,
              mechanism: "xhr.abort",
              at: clock(),
            };
            abortInvocations.set(id, invocation);
            append("client-aborts.jsonl", invocation);
            return true;
          } catch (error) {
            observerError(currentPhase);
            try {
              append("client-abort-observers.jsonl", {
                event: "observer-error",
                page: index,
                at: clock(),
                error: String(error.message ?? error),
              });
            } catch {
              observerError(currentPhase);
            }
            return false;
          }
        });
        const session = await page.context().newCDPSession(page);
        const network = {
          session,
          network: new Map(),
          requests: new Map(),
          hops: new Map(),
          unmatched: 0,
        };
        networkStates.set(index, network);
        listen(
          session,
          "Network.requestWillBeSent",
          guard((event) => {
            if (!new URL(event.request.url).pathname.startsWith("/api/"))
              return;
            if (!Number.isFinite(event.wallTime) || event.wallTime <= 0)
              throw new Error("CDP API start has no authoritative wall time");
            const hop = (network.hops.get(event.requestId) ?? -1) + 1;
            network.hops.set(event.requestId, hop);
            pairNetworkStart(
              index,
              JSON.stringify([event.request.method, event.request.url]),
              {
                wallStartTimeMs: event.wallTime * 1000,
                wallStartTimeSource: "cdp",
                cdpRequestId: event.requestId,
                cdpRedirectHop: hop,
              },
              true,
            );
          }),
        );
        for (const name of ["Network.loadingFinished", "Network.loadingFailed"])
          listen(session, name, (event) =>
            network.hops.delete(event.requestId),
          );
        await session.send("Network.enable", CDP_BUFFERS);
        await page.addInitScript(
          ({ bindingName }) => {
            const metadata = new WeakMap();
            const prototype = XMLHttpRequest.prototype;
            const originalOpen = prototype.open;
            const originalSend = prototype.send;
            const originalAbort = prototype.abort;
            let sequence = 0;
            function emit(value) {
              try {
                const pending = globalThis[bindingName](value);
                void pending?.catch(() => {});
              } catch {
                // Never turn a native XHR call into an instrumentation exception.
                // Missing invocation evidence cannot qualify a cancellation.
              }
            }
            prototype.open = function (...args) {
              const result = Reflect.apply(originalOpen, this, args);
              try {
                metadata.set(this, {
                  method: String(args[0]).toUpperCase(),
                  url: new URL(String(args[1]), location.href).href,
                  sendWallTimeMs: null,
                });
              } catch (error) {
                emit({ observerError: String(error.message ?? error) });
              }
              return result;
            };
            prototype.send = function (...args) {
              let sentAt;
              try {
                sentAt = performance.timeOrigin + performance.now();
              } catch (error) {
                emit({ observerError: String(error.message ?? error) });
              }
              const entry = metadata.get(this);
              const previous = entry?.sendWallTimeMs;
              if (entry) entry.sendWallTimeMs = sentAt;
              try {
                return Reflect.apply(originalSend, this, args);
              } catch (error) {
                if (entry) entry.sendWallTimeMs = previous;
                throw error;
              }
            };
            prototype.abort = function (...args) {
              const entry = metadata.get(this);
              let abortedAt;
              try {
                abortedAt = performance.timeOrigin + performance.now();
              } catch (error) {
                emit({ observerError: String(error.message ?? error) });
              }
              const result = Reflect.apply(originalAbort, this, args);
              if (
                entry &&
                Number.isFinite(entry.sendWallTimeMs) &&
                new URL(entry.url).pathname.startsWith("/api/")
              )
                emit({
                  id: `a${performance.timeOrigin}-${++sequence}`,
                  method: entry.method,
                  url: entry.url,
                  sendWallTimeMs: entry.sendWallTimeMs,
                  abortWallTimeMs: abortedAt,
                  mechanism: "xhr.abort",
                });
              return result;
            };
          },
          { bindingName },
        );
        abortHooks.set(index, true);
        return true;
      } catch (error) {
        observerError(currentPhase);
        throw error;
      }
    },
    beginTransition(marker) {
      if (
        stopped ||
        transitions.length >= 3 ||
        !marker ||
        typeof marker.id !== "string" ||
        !marker.id ||
        !Number.isFinite(marker.at) ||
        typeof marker.missionId !== "string" ||
        !marker.missionId ||
        transitions.some((previous) => previous.id === marker.id)
      )
        throw new Error("Invalid or excessive planned transition marker");
      transitions.push(structuredClone(marker));
    },
    applyCancellationQualification(proof) {
      const invalid = () => {
        throw new Error("Invalid client cancellation qualification proof");
      };
      const hash = (value) =>
        typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
      if (
        captureErrors ||
        unknownTerminal ||
        phases.measured.http_errors ||
        phases.measured.network_errors ||
        phases.measured.inflight ||
        proof?.protocol !== "issue393-client-abort-v2" ||
        proof.clean !== true ||
        !Array.isArray(proof.expected) ||
        !Array.isArray(proof.unexpected) ||
        proof.unexpected.length ||
        !hash(proof.source_sha256) ||
        !["api", "abort", "transition"].every((key) =>
          hash(proof.input_sha256?.[key]),
        ) ||
        proof.expected.length !== phases.measured.cancellations ||
        measuredCancellations.size !== phases.measured.cancellations
      )
        invalid();
      const verified = new Set();
      const usedAborts = new Set();
      const usedScopes = new Set();
      for (const item of proof.expected) {
        const entry = measuredCancellations.get(item?.request_id);
        const marker = transitions.find(
          (value) => value.id === item?.transition_id,
        );
        const abort = abortInvocations.get(item?.abort_id);
        if (
          !entry ||
          !marker ||
          entry.transitionId !== marker.id ||
          item.page !== entry.page ||
          verified.has(entry.id) ||
          !abort ||
          usedAborts.has(item.abort_id) ||
          abort.page !== entry.page ||
          abort.method !== entry.method ||
          abort.url !== entry.url ||
          !Number.isFinite(entry.wallStartTimeMs) ||
          entry.wallStartTimeMs <= 0 ||
          entry.wallStartTimeSource !== "cdp" ||
          !Number.isFinite(entry.wallTimeMs) ||
          Math.abs(abort.sendWallTimeMs - entry.wallStartTimeMs) > 100 ||
          abort.abortWallTimeMs < entry.wallStartTimeMs ||
          abort.abortWallTimeMs > entry.wallTimeMs + 100 ||
          usedScopes.has(`${entry.page}:${marker.id}`) ||
          entry.method !== "GET" ||
          entry.resourceType !== "xhr" ||
          entry.path !== "/api/v2/operator/events" ||
          entry.query.mission_id !== marker.missionId ||
          entry.at < marker.at - 2 ||
          entry.at > marker.at + 10 ||
          entry.terminalAt < marker.at - 2 ||
          entry.terminalAt > marker.at + 10 ||
          ![
            "health",
            "context",
            "fresh_source",
            "operator_health",
            "operator_context",
          ].every(
            (key) =>
              typeof item.recovery_ids?.[key] === "string" &&
              item.recovery_ids[key],
          ) ||
          !(
            item.recovery_ids.operator_records === null ||
            typeof item.recovery_ids.operator_records === "string"
          )
        )
          invalid();
        verified.add(entry.id);
        usedAborts.add(item.abort_id);
        usedScopes.add(`${entry.page}:${marker.id}`);
      }
      verifiedCancellations = verified;
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
      if ([...networkStates.values()].some((state) => state.unmatched)) {
        observerError(currentPhase);
        throw new Error(
          "Cannot stop API capture with unmatched CDP API starts",
        );
      }
      for (const remove of detach) remove();
      detach.length = 0;
      stopped = true;
      for (const { session } of networkStates.values()) {
        const pending = Promise.resolve(session.detach())
          .catch(() => observerError(currentPhase))
          .finally(() => sessionDetaches.delete(pending));
        sessionDetaches.add(pending);
      }
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
      while (
        [...active].some((entry) => entry.startedPhase === "measured") ||
        sessionDetaches.size
      ) {
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
        client_abort_hooks: Object.fromEntries(abortHooks),
        cdp_observer_buffers: networkStates.size ? { ...CDP_BUFFERS } : null,
        expected_control_cancellations: verifiedCancellations.size,
        unexpected_cancellations:
          measured.cancellations - verifiedCancellations.size,
        qualification_clean:
          measured.started > 0 &&
          measured.inflight === 0 &&
          measured.started === measured.terminal &&
          measured.http_errors === 0 &&
          measured.cancellations === verifiedCancellations.size &&
          measured.network_errors === 0 &&
          captureErrors === 0 &&
          unknownTerminal === 0,
      };
    },
    assertHealthy,
  };
}
