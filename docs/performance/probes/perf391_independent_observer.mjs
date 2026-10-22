// Disposable diagnostic consumer of the unchanged v2 monitor, never acceptance.
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
const [port, output, monitorPath] = process.argv.slice(2);
const { createMonitor } = await import(pathToFileURL(monitorPath));
const events = [];
let sequence = 0;
const start = performance.now();
const epoch = Date.now();
const monitor = createMonitor(
  {},
  async (path, method, body, headers, timeout) => {
    const request = sequence++;
    const sent = performance.now();
    const response = await fetch(`http://127.0.0.1:${port}${path}`, {
      headers: { "x-diagnostic-id": String(request) },
      signal: AbortSignal.timeout(timeout),
    });
    const result = await response.json();
    events.push({
      request,
      scheduled_ms: start + request * 1000,
      sent_ms: sent,
      done_ms: performance.now(),
      send_epoch: epoch + sent - start,
      result,
    });
    return result;
  },
  () => {},
  () => {},
);
monitor.start();
const blocker = setTimeout(() => {
  const began = performance.now();
  while (performance.now() - began < 800) {
    /* deliberate observer-only stall */
  }
}, 29800);
try {
  await delay(36000);
} finally {
  clearTimeout(blocker);
  await monitor.stop();
  writeFileSync(
    `${output}/observer.json`,
    JSON.stringify({ epoch, events }, null, 2),
  );
}
