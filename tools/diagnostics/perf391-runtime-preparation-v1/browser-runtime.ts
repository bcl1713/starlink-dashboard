/** Diagnostic build alias: adds an owner-only quiescence control, no UI. */
import { diagnostic } from "./browser-probe";
export { diagnostic };

(
  globalThis as typeof globalThis & { __perf391Finish?: () => unknown }
).__perf391Finish = () => {
  if (!diagnostic) throw Error("diagnostic handshake absent");
  const before = diagnostic.summary();
  if (before.pending || before.inflight || before.failed || before.lost)
    throw Error("frontend not drained");
  diagnostic.close();
  return { before, after: diagnostic.summary() };
};
