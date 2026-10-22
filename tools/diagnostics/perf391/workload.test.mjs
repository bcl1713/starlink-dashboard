import { test } from "node:test";
import assert from "node:assert/strict";
import { validateWorkload } from "./workload.mjs";
const traffic = [0, 1].flatMap((page) =>
  [10, 20].flatMap((ns) =>
    ["/api/status", "/api/overview-history"].map((path) => ({
      page,
      ns,
      path,
      status: 200,
    })),
  ),
);
traffic.push(
  ...[10, 20].map((ns) => ({
    page: 2,
    ns,
    path: "/api/v2/operator/health",
    status: 200,
  })),
);
test("requires recurring measured traffic from each browser context", () => {
  assert.equal(validateWorkload(traffic, [], 2, true, 0, 30).length, 3);
  assert.throws(
    () =>
      validateWorkload(
        traffic.filter((x) => x.page !== 1),
        [],
        2,
        true,
        0,
        30,
      ),
    /page 1/,
  );
});
test("renderer and request failures reject the workload", () => {
  assert.throws(
    () => validateWorkload(traffic, [{ kind: "pageerror" }], 2, true, 0, 30),
    /Browser errors/,
  );
});
test("setup-only successes do not establish measured workload", () => {
  assert.throws(() => validateWorkload(traffic, [], 2, true, 25, 30), /page 0/);
});

test("extracts correlation ID from the installed Undici wire event", async () => {
  const { channel } = await import("node:diagnostics_channel");
  const { createServer } = await import("node:http");
  const { wireRequestId } = await import("./workload.mjs");
  const server = createServer((q, r) => r.end("{}"));
  const ids = [];
  const handler = ({ headers }) => ids.push(wireRequestId(headers));
  try {
    server.listen(0, "127.0.0.1");
    await new Promise((r) => server.once("listening", r));
    channel("undici:client:sendHeaders").subscribe(handler);
    await (
      await fetch("http://127.0.0.1:" + server.address().port, {
        headers: { "x-diagnostic-id": "diag-123" },
        signal: AbortSignal.timeout(1000),
      })
    ).json();
    assert.deepEqual(ids, ["diag-123"]);
  } finally {
    channel("undici:client:sendHeaders").unsubscribe(handler);
    server.close();
    server.closeAllConnections();
  }
});
