/** Passive Page adapter; no launch, navigation, body retrieval, routing or disk I/O.
 * The later owner supplies bounded write/artifact sinks honoring AbortSignal.
 */
import { setMaxListeners } from "node:events";
import { createHash } from "node:crypto";
export const BOUNDS = Object.freeze({
  requests: 8,
  jobs: 8,
  events: 256,
  queue: 8 * 1024 * 1024,
  artifact: 2 * 1024 * 1024,
  chunk: 64 * 1024,
  assemblies: 8,
  deadline: 2000,
  screenshots: 8,
  png: 8 * 1024 * 1024,
});
export async function createBrowserObserver(
  page,
  {
    run,
    pageId,
    origin,
    write,
    artifact,
    deadlineMs = BOUNDS.deadline,
    budget = { screenshots: 0, busy: false },
    now = () => process.hrtime.bigint().toString(),
  },
) {
  if (
    !/^synthetic-[A-Za-z0-9_-]{1,22}$/.test(run) ||
    !/^[A-Za-z0-9_-]{1,16}$/.test(pageId)
  )
    throw Error("synthetic run/page required");
  if (
    !Number.isInteger(deadlineMs) ||
    deadlineMs < 1 ||
    deadlineMs > BOUNDS.deadline
  )
    throw Error("invalid total deadline");
  let bindingHandle, initHandle, closePromise;
  let initialized = false;
  const target = new URL("/api/overview-history", origin);
  let closed = false,
    failed = false,
    lost = 0,
    seq = 0,
    nextRequest = 0,
    jobs = 0,
    bindingJobs = 0,
    bytes = 0;
  const controller = new AbortController(),
    queue = [],
    active = new Map(),
    assemblies = new Map(),
    writes = new Set(),
    operations = new Set();
  setMaxListeners(BOUNDS.jobs * 2 + 4, controller.signal);
  let known = new WeakMap();
  const failures = [];
  let failureOverflow = 0,
    preClose = null;
  const stateSummary = () => ({
    closed,
    failed,
    lost,
    active: active.size,
    pending: queue.length,
    bytes,
    jobs,
    bindingJobs,
    ownedOperations: operations.size,
    assemblies: assemblies.size,
  });
  const fail = (code, error) => {
    failed = true;
    lost++;
    if (failures.length < 16)
      failures.push({
        code,
        reason: String(error?.message ?? error ?? code).slice(0, 256),
        at_ns: now(),
        state: stateSummary(),
      });
    else failureOverflow++;
  };
  async function bounded(fn, ms = deadlineMs, parent = controller.signal) {
    const operation = new AbortController();
    let timer, cancel;
    try {
      const interrupted = new Promise((_, reject) => {
        const stop = (reason) => {
          reject(Error(reason));
          operation.abort(Error(reason));
        };
        cancel = () => stop("cancelled");
        timer = setTimeout(() => stop("deadline"), ms);
        parent?.addEventListener("abort", cancel, { once: true });
        if (parent?.aborted) cancel();
      });
      return await Promise.race([
        interrupted,
        Promise.resolve().then(() => {
          if (operation.signal.aborted) throw Error("cancelled");
          return fn(operation.signal);
        }),
      ]);
    } finally {
      clearTimeout(timer);
      parent?.removeEventListener("abort", cancel);
    }
  }
  function pump() {
    while (!closed && !failed && jobs < BOUNDS.jobs && queue.length) {
      const job = queue.shift();
      jobs++;
      const work = bounded((signal) => write(job.row, { signal }))
        .catch((error) => fail("write-failure", error))
        .finally(() => {
          jobs--;
          bytes -= job.size;
          writes.delete(work);
          pump();
        });
      writes.add(work);
    }
  }
  function emit(row) {
    if (closed || failed) return false;
    const size = Buffer.byteLength(JSON.stringify(row));
    if (
      size > 1024 * 1024 ||
      queue.length >= BOUNDS.events ||
      bytes + size > BOUNDS.queue
    ) {
      fail("event-budget");
      return false;
    }
    queue.push({
      row: { host_seq: ++seq, host_received_ns: now(), ...row },
      size,
    });
    bytes += size;
    pump();
    return true;
  }
  function selected(request) {
    try {
      const u = new URL(request.url());
      return (
        u.origin === target.origin &&
        u.pathname === target.pathname &&
        request.method() === "GET"
      );
    } catch {
      return false;
    }
  }
  function identity(request) {
    return request.headers()["x-diagnostic-id"]?.slice(0, 96) ?? null;
  }
  function state(request) {
    let s = known.get(request);
    if (!s) {
      s = {
        requestId: identity(request),
        requestToken: `${pageId}/n${++nextRequest}`,
      };
      known.set(request, s);
    }
    return s;
  }
  function event(phase, request, extra = {}) {
    if (!selected(request)) return;
    try {
      emit({ phase, ...state(request), ...extra });
    } catch (error) {
      fail("event-failure", error);
    }
  }
  const listeners = {
    request(request) {
      if (!selected(request)) return;
      if (active.size >= BOUNDS.requests) {
        fail("request-cap");
        return;
      }
      active.set(request, state(request));
      event("browser.request", request);
    },
    response(response) {
      const request = response.request();
      if (!selected(request)) return;
      const h = response.headers();
      const item = state(request);
      item.response = true;
      event("browser.response", request, {
        status: response.status(),
        encoding: (h["content-encoding"] ?? "identity").slice(0, 64),
      });
      if (item.finished) active.delete(request);
    },
    requestfinished(request) {
      event("browser.finished", request);
      const item = state(request);
      item.finished = true;
      if (item.response) active.delete(request);
    },
    requestfailed(request) {
      event("browser.failed", request, { outcome: "error" });
      active.delete(request);
    },
    close() {
      if (!initialized) fail("closed-during-setup");
      void close();
    },
  };
  function track(fn) {
    const job = fn();
    operations.add(job);
    job.then(
      () => operations.delete(job),
      () => operations.delete(job),
    );
    return job;
  }
  function binding(source, message) {
    return track(() => bindingWork(source, message));
  }
  async function bindingWork(source, message) {
    if (closed || failed) return false;
    if (bindingJobs >= BOUNDS.jobs) {
      fail("binding-job-cap");
      return false;
    }
    bindingJobs++;
    try {
      if (
        source.page !== page ||
        message.run !== run ||
        message.page !== pageId ||
        !/^[A-Za-z0-9_-]{1,16}$/.test(message.document) ||
        !Number.isSafeInteger(message.seq) ||
        message.seq < 1 ||
        !Number.isInteger(message.total) ||
        message.total < 1 ||
        message.total > 140 ||
        !Number.isInteger(message.part) ||
        message.part < 0 ||
        message.part >= message.total ||
        typeof message.payload !== "string" ||
        Buffer.byteLength(message.payload) > BOUNDS.chunk
      )
        throw Error("invalid chunk");
      let entry = assemblies.get(`${message.document}/${message.seq}`);
      if (!entry) {
        if (assemblies.size >= BOUNDS.assemblies) throw Error("assembly cap");
        entry = {
          parts: new Map(),
          total: message.total,
          bytes: 0,
          started: Date.now(),
        };
        assemblies.set(`${message.document}/${message.seq}`, entry);
      }
      if (
        entry.parts.has(message.part) ||
        entry.total !== message.total ||
        Date.now() - entry.started > BOUNDS.deadline
      )
        throw Error("duplicate/stale chunk");
      entry.bytes += Buffer.byteLength(message.payload);
      if (entry.bytes > BOUNDS.artifact) throw Error("artifact cap");
      entry.parts.set(message.part, message.payload);
      if (entry.parts.size === entry.total) {
        assemblies.delete(`${message.document}/${message.seq}`);
        const text = Array.from({ length: entry.total }, (_, i) =>
          entry.parts.get(i),
        ).join("");
        const row = JSON.parse(text);
        if (
          row.run !== run ||
          row.stream !== `${run}/${pageId}/${message.document}` ||
          row.seq !== message.seq ||
          row.clock !== `browser/${pageId}/${message.document}` ||
          !Number.isFinite(row.monotonic_ms) ||
          typeof row.phase !== "string"
        )
          throw Error("invalid browser record");
        if (["plot.commit", "app.parse_available"].includes(row.phase)) {
          const data = Buffer.from(text);
          const hash = createHash("sha256").update(data).digest("hex");
          const reference = await bounded((signal) =>
            artifact(data, {
              kind:
                row.phase === "plot.commit"
                  ? "actual-chart"
                  : "parsed-network-history",
              sha256: hash,
              signal,
            }),
          );
          const { detail, ...header } = row;
          const snapshots = {};
          if (row.phase === "plot.commit")
            for (const name of ["retained", "projection", "plot"]) {
              const bytes = Buffer.from(JSON.stringify(detail[name]));
              const sha256 = createHash("sha256").update(bytes).digest("hex");
              const artifactRef = await bounded((signal) =>
                artifact(bytes, {
                  kind: name,
                  sha256,
                  signal,
                }),
              );
              snapshots[name] = { sha256, artifact: artifactRef };
            }
          return emit({
            origin: "browser",
            event: header,
            artifact: reference,
            sha256: hash,
            commit: detail.commit ?? null,
            metric: detail.metric ?? null,
            snapshots,
          });
        }
        return emit({ origin: "browser", event: row });
      }
      return true;
    } catch (error) {
      fail("binding-failure", error);
      assemblies.delete(`${message?.document}/${message?.seq}`);
      return false;
    } finally {
      bindingJobs--;
    }
  }
  const handlers = Object.fromEntries(
    Object.entries(listeners).map(([name, fn]) => [
      name,
      (...args) => {
        try {
          fn(...args);
        } catch (error) {
          fail("listener-failure", error);
        }
      },
    ]),
  );
  for (const [name, fn] of Object.entries(handlers)) page.on(name, fn);
  try {
    async function setupHandle(fn) {
      const work = Promise.resolve()
        .then(fn)
        .then(async (handle) => {
          if (closed) {
            if (handle) await handle.dispose();
            throw Error("closed during setup");
          }
          return handle;
        });
      // Page API completion can arrive after cancellation; dispose that handle.
      work.catch(() => {});
      return bounded(() => work);
    }
    bindingHandle = await setupHandle(() =>
      page.exposeBinding("__perf391Binding", binding),
    );
    initHandle = await setupHandle(() =>
      page.addInitScript(
        ({ run, page }) => {
          globalThis.__perf391Host = {
            run,
            page,
            document: crypto.randomUUID().replaceAll("-", "").slice(0, 16),
          };
        },
        { run, page: pageId },
      ),
    );
    initialized = true;
  } catch (error) {
    fail("setup-failure", error);
    await close();
    throw error;
  }
  async function metadata(ms) {
    return bounded(
      () => page.evaluate(() => globalThis.__perf391ReadCommit?.() ?? null),
      ms,
    );
  }
  function screenshot(panel) {
    return track(() => screenshotWork(panel));
  }
  async function screenshotWork(panel) {
    if (
      closed ||
      failed ||
      budget.busy ||
      budget.screenshots >= BOUNDS.screenshots
    )
      return { outcome: "unavailable", reason: "closed/busy/quota" };
    budget.busy = true;
    budget.screenshots++;
    const started = now();
    let result,
      before = null,
      after = null;
    let stage = "before-metadata";
    const until = Date.now() + deadlineMs;
    const remaining = () => {
      const ms = until - Date.now();
      if (ms <= 0) throw Error("deadline");
      return ms;
    };
    try {
      before = await metadata(remaining());
      const view = page.viewportSize();
      const a = before?.commits.find((c) => c.panel === panel),
        r = a?.rect;
      if (
        !a?.commit ||
        !a.mounted ||
        a.hidden ||
        a.visibility !== "visible" ||
        a.dpr !== 1 ||
        before.summary.failed ||
        before.summary.lost ||
        !view ||
        view.width > 1920 ||
        view.height > 1080 ||
        !r ||
        r.width <= 0 ||
        r.height <= 0 ||
        r.x < 0 ||
        r.y < 0 ||
        r.x + r.width > view.width ||
        r.y + r.height > view.height
      )
        throw Error("unavailable geometry/commit/loss");
      emit({
        phase: "paint.request",
        panel,
        commit: a.commit,
        started_ns: started,
      });
      stage = "native-screenshot";
      const ms = remaining();
      const png = await bounded(
        () =>
          page.screenshot({
            type: "png",
            clip: r,
            timeout: ms,
            animations: "allow",
            caret: "initial",
            scale: "css",
          }),
        ms,
      );
      if (png.length > BOUNDS.png) throw Error("png cap");
      stage = "after-metadata";
      after = await metadata(remaining());
      const b = after?.commits.find((c) => c.panel === panel);
      const stable =
        b?.mounted &&
        a.document === b.document &&
        typeof a.document === "string" &&
        a.commit === b.commit &&
        a.generation === b.generation &&
        a.accepted === b.accepted &&
        a.retained === b.retained &&
        JSON.stringify(a.rect) === JSON.stringify(b.rect) &&
        JSON.stringify(view) === JSON.stringify(page.viewportSize()) &&
        a.dpr === b.dpr &&
        b.visibility === "visible" &&
        !b.hidden &&
        !after.summary.failed &&
        !after.summary.lost &&
        !failed &&
        !closed;
      const sha256 = createHash("sha256").update(png).digest("hex");
      stage = "artifact";
      const reference = await bounded(
        (signal) =>
          artifact(png, {
            kind: "compositor-png",
            sha256,
            signal,
          }),
        remaining(),
      );
      result = {
        phase: "paint.artifact",
        panel,
        commit: a.commit,
        outcome: stable ? "ok" : "unavailable",
        reason: stable
          ? "sampled compositor bracket"
          : "generation/viewport/loss changed",
        started_ns: started,
        received_ns: now(),
        before: a,
        after: b ?? null,
        viewport: view,
        sha256,
        artifact: reference,
        renderer:
          "Playwright compositor screenshot; browser build supplied by later owner",
        physicalScanout: false,
      };
    } catch (error) {
      result = {
        phase: "paint.artifact",
        panel,
        outcome: "unavailable",
        reason: String(error.message).slice(0, 256),
        stage,
        code:
          error.message === "deadline" || error.name === "TimeoutError"
            ? stage.includes("metadata")
              ? "screenshot-metadata-timeout"
              : stage === "native-screenshot"
                ? "screenshot-native-timeout"
                : "screenshot-artifact-timeout"
            : stage === "native-screenshot"
              ? "screenshot-native-failure"
              : "screenshot-stage-failure",
        before,
        after,
        started_ns: started,
        received_ns: now(),
      };
    } finally {
      budget.busy = false;
    }
    emit(result);
    return result;
  }
  function close() {
    if (closePromise) return closePromise;
    preClose = stateSummary();
    closed = true;
    closePromise = (async () => {
      if (active.size || assemblies.size || queue.length)
        fail("close-incomplete");
      controller.abort();
      for (const [name, fn] of Object.entries(handlers)) page.off(name, fn);
      active.clear();
      assemblies.clear();
      known = new WeakMap();
      queue.length = 0;
      await Promise.allSettled([...writes, ...operations]);
      bytes = 0;
      for (const handle of [initHandle, bindingHandle])
        if (handle) {
          try {
            await bounded(() => handle.dispose(), deadlineMs, null);
          } catch (error) {
            fail("dispose-failure", error);
          }
        }
      initHandle = null;
      bindingHandle = null;
    })();
    return closePromise;
  }
  return {
    screenshot,
    close,
    summary: () => ({
      ...stateSummary(),
      failures: structuredClone(failures),
      failureOverflow,
      preClose: preClose ? { ...preClose } : null,
    }),
  };
}
