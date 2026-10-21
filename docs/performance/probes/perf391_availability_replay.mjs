/** Replay real v2 evidence offline; input files are never modified. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
const [harness, directory] = process.argv.slice(2);
if (!harness || !directory)
  throw new Error(
    "Usage: node perf391_availability_replay.mjs FROZEN_HARNESS CASE_DIRECTORY",
  );
const modulePath = resolve(
  harness,
  "tools/acceptance/performance_availability/availability.mjs",
);
const {
  validateHistory,
  validateCadence,
  validateMeasuredSamples,
  validateRecovery,
} = await import(pathToFileURL(modulePath));
const load = (name) =>
  JSON.parse(readFileSync(resolve(directory, name), "utf8"));
const run = load("run.json"),
  result = load("availability-result.json");
const actualHash = createHash("sha256")
  .update(readFileSync(modulePath))
  .digest("hex");
assert.equal(
  run.harness_files_sha256[
    "tools/acceptance/performance_availability/availability.mjs"
  ],
  actualHash,
);
const input = {
  history: load("final-history-full.json"),
  evaluated: load("final-raw-evaluated.json"),
  stored: load("final-raw-stored.json"),
  events: result.events,
  measurement: result.measurement,
  workload: "steady",
};
const outcomes = [];
const accept = (name, action) => {
  action();
  outcomes.push({ name, outcome: "accepted" });
};
const reject = (name, action, pattern) => {
  let message;
  assert.throws(action, (error) => {
    message = error.message;
    return pattern.test(message);
  });
  outcomes.push({ name, outcome: "rejected", reason: message });
};
accept("unchanged_real_capture", () => {
  validateHistory(input);
  validateCadence(load("final-scrapes.json"), input.stored, result.measurement);
  validateMeasuredSamples(
    input.stored,
    result.measurement,
    result.events,
    "steady",
  );
});
reject(
  "missing_actual_scrape",
  () => {
    const up = load("final-scrapes.json");
    const values = up.data.result[0].values;
    const i = values.findIndex((p) => p[0] > result.measurement.start + 3);
    assert(i > 0);
    values.splice(i, 1);
    validateCadence(up, input.stored, result.measurement);
  },
  /scrape.*gap/,
);
reject(
  "unexplained_measured_nan",
  () => {
    const stored = structuredClone(input.stored);
    const p = stored.data.result[0].values.find(
      (p) =>
        p[0] > result.measurement.start + 3 && p[0] < result.measurement.end,
    );
    assert(p);
    p[1] = "NaN";
    validateMeasuredSamples(
      stored,
      result.measurement,
      result.events,
      "steady",
    );
  },
  /steady/,
);
reject(
  "deleted_finite_api_timestamp",
  () => {
    const changed = structuredClone(input);
    const metric = Object.keys(changed.history.series)[0];
    changed.history.series[metric].splice(100, 1);
    validateHistory(changed);
  },
  /API.*filter|projection/,
);
reject(
  "shifted_raw_timestamp",
  () => {
    const changed = structuredClone(input);
    changed.evaluated.data.result[0].values[100][0] += 0.1;
    validateHistory(changed);
  },
  /grid/,
);
reject(
  "missing_raw_series",
  () => {
    const changed = structuredClone(input);
    changed.evaluated.data.result.pop();
    validateHistory(changed);
  },
  /missing.*series/,
);
reject(
  "persistent_startup_failure",
  () => {
    const event = structuredClone(result.events[0]);
    event.recovered.fields[event.required_fields[0]].available = false;
    validateRecovery(event, event.recovered);
  },
  /unavailable/,
);
reject(
  "late_recovery",
  () => {
    const event = structuredClone(result.events[0]);
    event.recovered.at = event.completed_at + 2.001;
    validateRecovery(event, event.recovered);
  },
  /deadline/,
);
reject(
  "wrong_route_provenance",
  () => {
    const event = structuredClone(result.events[0]);
    event.recovered.source.active_route_id = "wrong-route";
    validateRecovery(event, event.recovered);
  },
  /identity/,
);
console.log(
  JSON.stringify(
    {
      harness_sha: run.harness_sha,
      contract_version: run.availability_contract,
      application_sha: run.candidate_sha,
      validator_sha256: actualHash,
      outcomes,
    },
    null,
    2,
  ),
);
