import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateGate } from "../acceptance/customer-briefing/map_feasibility.mjs";
const expected = ["short/view-1", "polar/view-1", "long/view-1", "long/view-2"];
const good = () => ({
  status: "primary",
  elapsedSeconds: 40,
  exitCode: 0,
  cleanupVerified: true,
  cleanup: {
    listenerClosed: true,
    browserExited: true,
    contextsClosed: true,
    errors: [],
  },
  views: expected.map((id) => ({
    id,
    pngHash: "a".repeat(64),
    pixelHash: "b".repeat(64),
  })),
});
test("releases only three complete cold primary missions with cleanup and ten seconds margin", () => {
  assert.equal(evaluateGate([good(), good(), good()], expected).pass, true);
  for (const mutation of [
    (run) => {
      run.views.pop();
    },
    (run) => {
      run.elapsedSeconds = 50.01;
    },
    (run) => {
      run.status = "fallback";
    },
    (run) => {
      run.cleanupVerified = false;
    },
    (run) => {
      run.cleanup.browserExited = false;
    },
    (run) => {
      run.views[0].pngHash = "";
    },
  ]) {
    const runs = [good(), good(), good()];
    mutation(runs[1]);
    assert.equal(evaluateGate(runs, expected).pass, false);
  }
  assert.equal(evaluateGate([good(), good()], expected).pass, false);
});
