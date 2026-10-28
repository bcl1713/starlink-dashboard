/** Short-preflight negative controls; never enable for the sustained soak. */
import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { createApiCapture } from "./capture.mjs";

export async function qualifyCapture(browser, origin, append) {
  const context = await browser.newContext();
  const terminal = new Map();
  let abortInvocation = null;
  let abortInvocationCount = 0;
  const capture = createApiCapture({
    append(name, value) {
      append(`negative-control-${name}`, value);
      if (value.event === "terminal" && terminal.size < 2)
        terminal.set(value.path, value);
      if (name === "client-aborts.jsonl") {
        abortInvocation = value;
        abortInvocationCount++;
      }
    },
    clock: () => performance.now() / 1000,
  });
  const slowURL = `${origin}/api/__capture_slow__`;
  let releaseSlow;
  const slowGate = new Promise((resolve) => {
    releaseSlow = resolve;
  });
  let slowTimer;
  let slowHandler = Promise.resolve();
  let cancellationXHR;
  let slowReleaseError = null;
  try {
    const page = await context.newPage();
    capture.attach(page, 0);
    assert.equal(await capture.observeClientAborts(page, 0), true);
    capture.phase("measured");
    await page.route(`${origin}/__capture_probe__`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/html",
        body: "<!doctype html><title>Capture negative controls</title>",
      }),
    );
    await page.goto(`${origin}/__capture_probe__`, {
      waitUntil: "domcontentloaded",
      timeout: 10000,
    });
    const staleIdentity = JSON.stringify([
      "stale-store",
      "stale-epoch",
      "simulation",
      "stale-context",
    ]);
    const staleURL =
      `${origin}/api/v2/operator/records?mission_id=synthetic-mission-a` +
      `&source_identity=${encodeURIComponent(staleIdentity)}`;
    // No route intercepts this URL: this exercises the real backend admission.
    const staleResult = await page.evaluate(async (url) => {
      const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
      return { status: response.status, body: await response.json() };
    }, staleURL);
    assert.equal(staleResult.status, 409);
    assert.equal(staleResult.body.error.code, "store_context_changed");
    await capture.drain(10000);
    const stale = terminal.get("/api/v2/operator/records");
    assert.ok(stale, "Real 409 terminal evidence was not captured");
    assert.equal(stale.status, 409);
    assert.equal(stale.sourceIdentity, staleIdentity);
    assert.equal(stale.classification, "store_context_changed");
    assert.equal(stale.body.truncated, false);
    assert.equal(stale.body.error, null);
    assert.deepEqual(JSON.parse(stale.body.text), staleResult.body);
    assert.equal(capture.summary().phases.measured.http_errors, 1);
    assert.equal(capture.summary().qualification_clean, false);
    assert.throws(() => capture.assertHealthy(), /HTTP/);

    // Only this synthetic slow fixture is intercepted. Releasing its bounded
    // gate in finally also closes the handler after an assertion failure.
    await page.route(slowURL, (route) => {
      slowHandler = (async () => {
        await slowGate;
        try {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: '{"synthetic_capture_probe":true}',
          });
        } catch (error) {
          // Chromium may already have canceled this intercepted request.
          slowReleaseError = String(error.message ?? error).slice(0, 2048);
        }
      })();
      return slowHandler;
    });
    const requestObserved = page.waitForRequest(slowURL, { timeout: 5000 });
    const failureObserved = page.waitForEvent("requestfailed", {
      predicate: (req) => req.url() === slowURL,
      timeout: 5000,
    });
    // If an earlier assertion fails, finally closes the context; retain these
    // promises without allowing an unhandled rejection during cleanup.
    void requestObserved.catch(() => {});
    void failureObserved.catch(() => {});
    slowTimer = setTimeout(releaseSlow, 5000);
    cancellationXHR = page.evaluate(
      (url) =>
        new Promise((resolve) => {
          const xhr = new XMLHttpRequest();
          window.__captureProbeXHR = xhr;
          xhr.open("GET", url, true);
          xhr.onabort = () => resolve({ aborted: true });
          xhr.onload = () => resolve({ aborted: false, status: xhr.status });
          xhr.onerror = () =>
            resolve({ aborted: false, error: "network_error" });
          xhr.send();
        }),
      slowURL,
    );
    void cancellationXHR.catch(() => {});
    await requestObserved;
    await page.evaluate(() => window.__captureProbeXHR.abort());
    releaseSlow();
    clearTimeout(slowTimer);
    const canceled = await failureObserved;
    assert.equal(canceled.failure()?.errorText, "net::ERR_ABORTED");
    assert.deepEqual(await cancellationXHR, { aborted: true });
    await slowHandler;
    await capture.drain(10000);
    const cancellation = terminal.get("/api/__capture_slow__");
    assert.ok(cancellation, "Cancellation terminal evidence was not captured");
    assert.equal(cancellation.outcome, "client_cancellation");
    assert.equal(cancellation.errorText, "net::ERR_ABORTED");
    assert.equal(cancellation.cancellationCause, "unknown");
    const abortDeadline = performance.now() + 1000;
    while (!abortInvocation && performance.now() < abortDeadline)
      await new Promise((resolve) => setTimeout(resolve, 5));
    assert.equal(abortInvocationCount, 1);
    assert.equal(abortInvocation.mechanism, "xhr.abort");
    assert.equal(abortInvocation.page, cancellation.page);
    assert.equal(abortInvocation.method, cancellation.method);
    assert.equal(abortInvocation.url, cancellation.url);
    assert.equal(cancellation.resourceType, "xhr");
    assert.ok(
      Math.abs(abortInvocation.sendWallTimeMs - cancellation.wallStartTimeMs) <=
        100,
    );
    assert.ok(abortInvocation.abortWallTimeMs >= cancellation.wallStartTimeMs);
    assert.ok(abortInvocation.abortWallTimeMs <= cancellation.wallTimeMs + 100);
    capture.phase("post");
    capture.stop();
    await capture.drain(10000);
    const summary = capture.summary();
    assert.equal(summary.phases.measured.started, 2);
    assert.equal(summary.phases.measured.terminal, 2);
    assert.equal(summary.phases.measured.inflight, 0);
    assert.equal(summary.phases.measured.http_errors, 1);
    assert.equal(summary.phases.measured.cancellations, 1);
    assert.equal(summary.phases.measured.network_errors, 0);
    assert.equal(summary.capture_errors, 0);
    assert.equal(summary.unknown_terminal, 0);
    assert.equal(summary.qualification_clean, false);
    assert.throws(() => capture.assertHealthy(), /HTTP|cancellation/);
    const result = {
      negative_controls_passed: true,
      http409_body: JSON.parse(stale.body.text),
      request_ids: {
        stale_source_409: stale.id,
        client_abort: cancellation.id,
      },
      summary,
      abort_invocation_proof: abortInvocation,
      fixture: {
        intercepted_paths: ["/__capture_probe__", "/api/__capture_slow__"],
        stale_source_request_intercepted: false,
        cancellation_trigger: "deliberate qualification XMLHttpRequest.abort",
        cancellation_cause_in_network_evidence: "unknown",
        slow_route_release_error: slowReleaseError,
      },
    };
    append("negative-control-summary.jsonl", result);
    return result;
  } finally {
    clearTimeout(slowTimer);
    releaseSlow();
    await slowHandler;
    await context.close();
    await cancellationXHR?.catch(() => {});
  }
}
