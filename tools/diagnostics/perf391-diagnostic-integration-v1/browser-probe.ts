/** Diagnostic derivative only. No app state, subscriptions, timers or telemetry globals. */
type Binding = (message: unknown) => Promise<unknown>;
type Config = {
  run: string;
  page: string;
  document: string;
  metrics?: readonly string[];
  clock: () => number;
  binding: Binding;
};
type Row = Record<string, any>;
export const LIMITS = Object.freeze({
  events: 256,
  bytes: 8 * 1024 * 1024,
  jobs: 8,
  artifact: 2 * 1024 * 1024,
  panels: 5,
  points: 1820,
  nodes: 50000,
  chunk: 15000,
});

/** Bound traversal before JSON.stringify; application objects are never modified. */
function snapshot(value: any): any {
  let nodes = 0,
    bytes = 0;
  function copy(v: any, depth: number): any {
    if (++nodes > LIMITS.nodes || depth > 32)
      throw Error("snapshot traversal cap");
    if (v === undefined) return null;
    if (v === null || typeof v === "boolean") {
      bytes += 5;
      return v;
    }
    if (typeof v === "number") {
      bytes += 32;
      return Number.isFinite(v) ? v : null;
    }
    if (typeof v === "string") {
      if (v.length > 256) throw Error("string cap");
      bytes += v.length * 6 + 2;
      return v;
    }
    if (typeof v !== "object") throw Error("unsupported evidence");
    if (Array.isArray(v)) {
      if (v.length > LIMITS.points * 4) throw Error("array cap");
      const out = [];
      for (const item of v) {
        out.push(copy(item, depth + 1));
        if (bytes > LIMITS.artifact) throw Error("artifact cap");
      }
      return out;
    }
    if (
      Object.getPrototypeOf(v) !== Object.prototype &&
      Object.getPrototypeOf(v) !== null
    )
      throw Error("plain evidence required");
    const out: Row = {};
    let keys = 0;
    for (const key in v)
      if (Object.hasOwn(v, key)) {
        if (
          ++keys > 64 ||
          key.length > 64 ||
          ["__proto__", "constructor", "prototype"].includes(key)
        )
          throw Error("key cap");
        bytes += key.length * 6 + 4;
        out[key] = copy(v[key], depth + 1);
        if (bytes > LIMITS.artifact) throw Error("artifact cap");
      }
    return out;
  }
  return copy(value, 0);
}

export function createProbe(config: Config) {
  if (
    !/^[A-Za-z0-9_-]{1,32}$/.test(config.run) ||
    !/^[A-Za-z0-9_-]{1,16}$/.test(config.page) ||
    !/^[A-Za-z0-9_-]{1,16}$/.test(config.document)
  )
    throw Error("synthetic run/page token required");
  const metrics = config.metrics ?? [
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
  ];
  if (metrics.length > 5) throw Error("network metric cap");
  let seq = 0,
    nextId = 0,
    nextObject = 0,
    generation = 0,
    closed = false,
    failed = false,
    lost = 0,
    inflight = 0,
    queuedBytes = 0;
  const queue: { text: string; part: number; seq: number; bytes: number }[] =
    [];
  let identities = new WeakMap<object, string>();
  let responses = new WeakMap<object, string>();
  let samples = new WeakMap<object, string>();
  const panels = new Map<object, Row>();
  function fail() {
    failed = true;
    lost++;
  }
  const safe = (fn: () => any) => {
    if (closed) return;
    try {
      return fn();
    } catch {
      fail();
    }
  };
  function token(v: any) {
    if (!v || typeof v !== "object") return null;
    let id = identities.get(v);
    if (!id) {
      id = `o${++nextObject}`;
      identities.set(v, id);
    }
    return id;
  }
  function pump() {
    while (!closed && inflight < LIMITS.jobs && queue.length) {
      const job = queue[0];
      const part = job.part++,
        start = part * LIMITS.chunk;
      const payload = job.text.slice(start, start + LIMITS.chunk);
      const total = Math.ceil(job.text.length / LIMITS.chunk);
      if (job.part === total) {
        queue.shift();
        queuedBytes -= job.bytes;
      }
      inflight++;
      const message = {
        run: config.run,
        page: config.page,
        document: config.document,
        seq: job.seq,
        part,
        total,
        payload,
      };
      Promise.resolve()
        .then(() => (closed ? false : config.binding(message)))
        .then(
          (ack) => {
            if (ack !== true && !closed) fail();
          },
          () => {
            if (!closed) fail();
          },
        )
        .finally(() => {
          inflight--;
          pump();
        });
    }
  }
  function emit(
    phase: string,
    op: string | null,
    detail: Row = {},
    outcome = "ok",
    capturedMs?: number,
  ) {
    const row = {
      run: config.run,
      stream: `${config.run}/${config.page}/${config.document}`,
      seq: ++seq,
      clock: `browser/${config.page}/${config.document}`,
      monotonic_ms: capturedMs ?? config.clock(),
      phase,
      op,
      outcome,
      detail: snapshot(detail),
    };
    const text = JSON.stringify(row),
      bytes = new TextEncoder().encode(text).length;
    if (
      bytes > LIMITS.artifact ||
      queue.length >= LIMITS.events ||
      queuedBytes + bytes > LIMITS.bytes
    ) {
      fail();
      return;
    }
    queue.push({ text, seq, bytes, part: 0 });
    queuedBytes += bytes;
    pump();
  }
  function requestId() {
    return `${config.run}/${config.page}/${config.document}/r${++nextId}`;
  }
  function response(id: string | undefined, data: any) {
    safe(() => {
      if (!id || !data || typeof data !== "object")
        throw Error("missing response association");
      const availableMs = config.clock();
      emit("app.response", id, { bundle: token(data) }, "ok", availableMs);
      responses.set(data, id);
      token(data);
      for (const metric of metrics) {
        if (metric.length > 256) throw Error("metric name cap");
        const rollup = data.rolling_5m?.[metric];
        for (const entries of [
          data.series[metric],
          rollup?.min,
          rollup?.avg,
          rollup?.max,
        ]) {
          if (entries === undefined) continue;
          if (!Array.isArray(entries) || entries.length > LIMITS.points)
            throw Error("trace cap");
          for (const sample of entries)
            if (sample && typeof sample === "object") samples.set(sample, id);
        }
        emit(
          "app.parse_available",
          id,
          {
            bundle: token(data),
            metric,
            parseStartAvailable: false,
            history: {
              window_seconds: data.window_seconds,
              start_timestamp_seconds: data.start_timestamp_seconds,
              end_timestamp_seconds: data.end_timestamp_seconds,
              step_seconds: data.step_seconds,
              series: { [metric]: data.series?.[metric] },
              rolling_5m: data.rolling_5m ? { [metric]: rollup } : undefined,
            },
          },
          "ok",
          availableMs,
        );
      }
    });
  }
  const association = (v: any) =>
    v && typeof v === "object" ? (responses.get(v) ?? null) : null;
  function candidate(
    panel: object,
    metric: string,
    incoming: any,
    accepted: any,
    retained: any,
  ) {
    safe(() =>
      emit("react.render_candidate", association(incoming), {
        panel: token(panel),
        metric,
        candidate: token(incoming),
        accepted: token(accepted),
        retained: token(retained),
        candidateRequest: association(incoming),
        acceptedRequest: association(accepted),
        decision:
          incoming === accepted
            ? "accepted"
            : incoming
              ? "rejected_or_shared"
              : "missing",
      }),
    );
  }
  function mount(panel: object) {
    safe(() => {
      if (!panels.has(panel) && panels.size >= LIMITS.panels)
        throw Error("panel cap");
      panels.set(panel, {
        panel: token(panel),
        generation: ++generation,
        mounted: true,
        commit: null,
      });
      emit("react.mount", null, { panel: token(panel), generation });
    });
  }
  function unmount(panel: object) {
    safe(() => {
      const state = panels.get(panel);
      panels.delete(panel);
      emit("react.unmount", null, {
        panel: token(panel),
        generation: ++generation,
        previous: state?.commit,
      });
    });
  }
  function commit(panel: object, input: Row) {
    safe(() => {
      const state = panels.get(panel);
      if (!state) throw Error("unmounted panel");
      const {
        metric,
        candidate: incoming,
        accepted,
        retained,
        projection,
        plot,
        surface,
        width,
        height,
        upload,
        hidden,
        error,
        reducedMotion,
      } = input;
      if (
        typeof metric !== "string" ||
        !retained ||
        !projection ||
        !plot ||
        !surface
      )
        throw Error("missing actual chart boundary");
      const provenance: Row = {};
      const rollup = retained.rolling_5m?.[metric];
      for (const [trace, entries] of Object.entries({
        observed: retained.series?.[metric],
        min: rollup?.min,
        avg: rollup?.avg,
        max: rollup?.max,
      })) {
        if (!Array.isArray(entries) || entries.length > LIMITS.points)
          throw Error("retained trace cap");
        provenance[trace] = entries.map(
          (sample) => samples.get(sample) ?? null,
        );
      }
      if (
        !Array.isArray(plot.data) ||
        plot.data.length !== 5 ||
        plot.data.some(
          (v: any) => !Array.isArray(v) || v.length > LIMITS.points,
        )
      )
        throw Error("plot trace cap");
      const g = ++generation,
        id = `${config.page}/c${g}`;
      const detail = {
        panel: token(panel),
        document: config.document,
        commit: id,
        generation: g,
        metric,
        candidate: token(incoming),
        accepted: token(accepted),
        acceptedRequest: association(accepted),
        retainedId: token(retained),
        retained,
        projection,
        provenance,
        plot: {
          data: plot.data,
          scales: {
            x: { min: plot.scales.x?.min, max: plot.scales.x?.max },
            y: {
              min: plot.scales.y?.min,
              max: plot.scales.y?.max,
              distr: plot.scales.y?.distr,
            },
          },
          width: plot.width,
          height: plot.height,
        },
        width,
        height,
        upload,
        hidden,
        error,
        reducedMotion,
        transform: surface.style.transform,
        transition: surface.style.transition,
        layoutOnly: true,
        spanGaps: false,
        logFloor: 1,
      };
      emit("history.retained", association(accepted), {
        panel: token(panel),
        document: config.document,
        commit: id,
        retained: token(retained),
      });
      emit("plot.upload", association(accepted), {
        panel: token(panel),
        document: config.document,
        commit: id,
        upload,
      });
      emit("plot.commit", association(accepted), detail);
      emit("react.commit", association(accepted), {
        panel: token(panel),
        document: config.document,
        commit: id,
        layoutOnly: true,
      });
      panels.set(panel, {
        panel: token(panel),
        document: config.document,
        commit: id,
        generation: g,
        metric,
        mounted: true,
        width,
        height,
        hidden,
        error,
        reducedMotion,
        accepted: token(accepted),
        retained: token(retained),
        surface,
        viewport: input.viewport,
      });
    });
  }
  function metadata() {
    return (
      safe(() =>
        Array.from(panels.values()).map(({ surface, viewport, ...state }) => {
          const rect = viewport?.getBoundingClientRect();
          return {
            ...state,
            document: config.document,
            rect: rect
              ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
              : null,
            transform:
              surface && typeof getComputedStyle === "function"
                ? getComputedStyle(surface).transform
                : null,
            visibility:
              typeof document === "undefined"
                ? "unknown"
                : document.visibilityState,
            dpr:
              typeof devicePixelRatio === "undefined" ? null : devicePixelRatio,
          };
        }),
      ) ?? []
    );
  }
  function close() {
    closed = true;
    queue.length = 0;
    queuedBytes = 0;
    panels.clear();
    identities = new WeakMap();
    responses = new WeakMap();
    samples = new WeakMap();
  }
  return {
    requestId,
    response,
    association,
    candidate,
    mount,
    unmount,
    commit,
    metadata,
    close,
    invalidate: (panel: object) =>
      safe(() => {
        const state = panels.get(panel);
        if (state)
          panels.set(panel, {
            ...state,
            document: config.document,
            generation: ++generation,
            commit: null,
          });
      }),
    request: (id: string | undefined, signal?: AbortSignal) =>
      safe(() =>
        emit("app.request", id ?? null, { aborted: signal?.aborted ?? false }),
      ),
    requestError: (id: string | undefined, signal?: AbortSignal) =>
      safe(() =>
        emit(
          "app.response_error",
          id ?? null,
          {},
          signal?.aborted ? "cancelled" : "error",
        ),
      ),
    async query<T>(
      fn: (id: string) => Promise<T>,
      signal?: AbortSignal,
    ): Promise<T> {
      const id = requestId();
      safe(() => emit("query.begin", id));
      try {
        const data = await fn(id);
        safe(() =>
          emit("query.success", id, {
            bundle: token(data),
            responseRequest: association(data),
          }),
        );
        return data;
      } catch (error) {
        safe(() =>
          emit("query.error", id, {}, signal?.aborted ? "cancelled" : "error"),
        );
        throw error;
      }
    },
    summary: () => ({
      seq,
      lost,
      failed,
      closed,
      pending: queue.length,
      bytes: queuedBytes,
      inflight,
      panels: panels.size,
    }),
  };
}

// Only a dedicated build plus an explicitly synthetic host handshake can attach.
// The read-only global exposes commit metadata only; bundles/arrays stay private.
const host = globalThis as typeof globalThis & {
  __perf391Host?: { run: string; page: string; document: string };
  __perf391Binding?: Binding;
  __perf391ReadCommit?: () => unknown;
};
function attach() {
  try {
    return import.meta.env.VITE_PERF391_DIAGNOSTIC === "true" &&
      host.__perf391Host?.run.startsWith("synthetic-") &&
      typeof host.__perf391Binding === "function"
      ? createProbe({
          ...host.__perf391Host,
          clock: () => performance.now(),
          binding: host.__perf391Binding,
        })
      : undefined;
  } catch {
    return undefined;
  }
}
export const diagnostic = attach();
if (diagnostic)
  host.__perf391ReadCommit = () => ({
    commits: diagnostic.metadata(),
    summary: diagnostic.summary(),
  });
