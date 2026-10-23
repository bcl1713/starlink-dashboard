/** Diagnostic owner facts, factored for offline fake-Page qualification. */
import { setTimeout as sleep } from "node:timers/promises";

async function bounded(fn, until, code) {
  const ms = until - Date.now();
  if (ms <= 0) throw Error(code);
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(fn),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(Error(code)), ms);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
function record(save, name, value) {
  if (Buffer.byteLength(JSON.stringify(value)) > 65536)
    throw Error("owner-evidence-cap");
  save(name, value);
}
export async function selectPanel(page, save) {
  const until = Date.now() + 10000;
  let handle, selectionError;
  try {
    handle = await page.waitForFunction(
      () => {
        const state = globalThis.__perf391ReadCommit?.();
        return state?.commits?.some((c) => c.commit) ? state : false;
      },
      undefined,
      { timeout: 10000 },
    );
    const metadata = await bounded(
      () => handle.jsonValue(),
      until,
      "panel-metadata-timeout",
    );
    const selected =
      metadata?.commits?.find((c) => c.commit && c.mounted && !c.hidden) ??
      null;
    record(save, "panel-selection.json", { metadata, selected });
    if (!selected) throw Error("incomplete-commits");
    return selected.panel;
  } catch (error) {
    selectionError = error;
    record(save, "panel-readiness-error.json", {
      reason: String(error.message).slice(0, 256),
    });
    throw error;
  } finally {
    if (handle) {
      try {
        await bounded(
          () => handle.dispose(),
          Date.now() + 2000,
          "panel-handle-disposal-timeout",
        );
      } catch (error) {
        record(save, "panel-disposal-error.json", {
          reason: String(error.message).slice(0, 256),
        });
        if (!selectionError) throw error;
      }
    }
  }
}
const validSummary = (s) =>
  s &&
  Number.isSafeInteger(s.seq) &&
  s.seq > 0 &&
  s.failed === false &&
  s.lost === 0 &&
  s.pending === 0 &&
  s.inflight === 0;
export async function finishFrontend(
  page,
  observer,
  save,
  { deadlineMs = 2000 } = {},
) {
  if (!Number.isInteger(deadlineMs) || deadlineMs < 1 || deadlineMs > 2000)
    throw Error("invalid finalization deadline");
  const until = Date.now() + deadlineMs;
  const trace = {
    finishAdmitted: false,
    last: null,
    final: null,
    reason: null,
  };
  try {
    while (Date.now() < until) {
      const frontend = await bounded(
        () => page.evaluate(() => globalThis.__perf391ReadCommit?.()),
        until,
        "frontend-metadata-timeout",
      );
      const node = observer.summary();
      trace.last = { frontend: frontend ?? null, observer: node };
      if (frontend?.summary?.failed || frontend?.summary?.lost)
        throw Error("frontend-loss");
      if (node.failed || node.lost) throw Error("browser-observer-loss");
      if (frontend && !frontend.commits?.some((c) => c.commit))
        throw Error("incomplete-commits");
      const s = frontend?.summary;
      if (
        s &&
        !s.pending &&
        !s.inflight &&
        !node.active &&
        !node.pending &&
        !node.jobs &&
        !node.bindingJobs &&
        !node.ownedOperations &&
        !node.assemblies
      ) {
        trace.finishAdmitted = true;
        const result = await bounded(
          () =>
            page.evaluate(() => ({
              available: typeof globalThis.__perf391Finish === "function",
              value: globalThis.__perf391Finish?.(),
            })),
          until,
          "finish-timeout",
        );
        trace.final = result?.value ?? null;
        if (!result?.available) throw Error("finish-absent");
        const final = trace.final;
        if (
          !validSummary(final?.before) ||
          !validSummary(final?.after) ||
          final.before.closed !== false ||
          final.after.closed !== true ||
          final.before.seq !== final.after.seq
        )
          throw Error("finish-invalid");
        record(save, "frontend-final.json", final);
        return final;
      }
      await sleep(Math.min(20, Math.max(0, until - Date.now())));
    }
    throw Error("finish-not-admitted");
  } catch (error) {
    trace.reason = String(error.message).slice(0, 256);
    throw error;
  } finally {
    record(save, "frontend-finalization.json", trace);
  }
}
