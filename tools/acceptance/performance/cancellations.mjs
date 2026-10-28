/** Derived proof only: never rewrite a raw cancellation's unknown cause. */
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { createHash } from "node:crypto";

const MISSION = "synthetic-mission-a";
const PREFIX = "/api/v2/operator/";
const CONTROL = [
  "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-2/activate",
  "/api/v2/missions/synthetic-mission-a/legs/deactivate",
  "/api/v2/missions/synthetic-mission-a/legs/synthetic-leg-1/activate",
];
const FILE_LIMIT = 128 * 1024 * 1024,
  LINE_LIMIT = 256 * 1024;
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const requireProof = (condition, reason) => {
  if (!condition) throw new Error(reason);
};

async function readRows(path) {
  requireProof(
    (await stat(path)).size <= FILE_LIMIT,
    "Input file exceeds 128 MiB",
  );
  const hash = createHash("sha256"),
    rows = [];
  let pending = Buffer.alloc(0),
    bytes = 0;
  const parse = (line) => {
    requireProof(line.length <= LINE_LIMIT, "Input line exceeds 256 KiB");
    if (!line.length) return;
    const row = JSON.parse(line.toString("utf8"));
    requireProof(
      row && typeof row === "object" && !Array.isArray(row),
      "Input row is not an object",
    );
    rows.push(row);
  };
  for await (const chunk of createReadStream(path, { highWaterMark: 65536 })) {
    bytes += chunk.length;
    requireProof(bytes <= FILE_LIMIT, "Input grew beyond 128 MiB");
    hash.update(chunk);
    pending = Buffer.concat([pending, chunk]);
    let boundary;
    while ((boundary = pending.indexOf(10)) !== -1) {
      parse(pending.subarray(0, boundary));
      pending = pending.subarray(boundary + 1);
    }
    requireProof(pending.length <= LINE_LIMIT, "Input line exceeds 256 KiB");
  }
  if (pending.length) parse(pending);
  return { rows, sha256: hash.digest("hex") };
}

function identity(value) {
  const parsed = JSON.parse(value);
  requireProof(
    Array.isArray(parsed) &&
      parsed.length === 4 &&
      parsed.every((item) => typeof item === "string" && item.length),
    "Malformed four-part source identity",
  );
  requireProof(
    ["live", "simulation"].includes(parsed[2]),
    "Invalid source mode",
  );
  return parsed;
}

function missionScope(start) {
  const url = new URL(start.url);
  return (
    url.pathname === start.path &&
    url.searchParams.getAll("mission_id").length === 1 &&
    url.searchParams.get("mission_id") === MISSION &&
    start.query?.mission_id === MISSION
  );
}

function transitions(rows) {
  const markers = new Map();
  for (const row of rows) {
    if (!["transition-begin", "transition-confirmed"].includes(row.stage))
      continue;
    requireProof(
      Number.isInteger(row.operation) &&
        CONTROL[row.operation] &&
        row.transition_id === `transition-${row.operation}`,
      "Unexpected transition identifier",
    );
    const pair = markers.get(row.transition_id) ?? {};
    requireProof(!pair[row.stage], "Duplicate transition marker");
    pair[row.stage] = row;
    markers.set(row.transition_id, pair);
  }
  return [...markers].map(([id, pair]) => {
    const begin = pair["transition-begin"],
      confirm = pair["transition-confirmed"];
    requireProof(begin && confirm, "Missing transition begin or confirmation");
    const before = identity(begin.before_identity),
      target = identity(confirm.target_identity);
    requireProof(
      begin.mission_id === MISSION &&
        confirm.mission_id === MISSION &&
        begin.operation === confirm.operation,
      "Transition mission/operation mismatch",
    );
    requireProof(
      typeof begin.records_active_after === "boolean" &&
        begin.records_active_after === confirm.records_active_after &&
        begin.records_active_after === (begin.operation !== 1),
      "Transition active-state mismatch",
    );
    requireProof(
      finite(begin.clock_seconds) &&
        finite(confirm.clock_seconds) &&
        begin.clock_seconds < confirm.clock_seconds &&
        confirm.clock_seconds <= begin.clock_seconds + 10,
      "Invalid transition clock interval",
    );
    requireProof(
      finite(begin.wall_time_ms) &&
        finite(confirm.wall_time_ms) &&
        begin.wall_time_ms < confirm.wall_time_ms,
      "Invalid transition wall interval",
    );
    requireProof(
      before.slice(0, 3).every((value, index) => value === target[index]) &&
        before[3] !== target[3],
      "Transition store/epoch/mode changed or source did not change",
    );
    requireProof(
      confirm.control_path === CONTROL[begin.operation] &&
        confirm.control_result?.ok === true &&
        Number.isInteger(confirm.control_result.status) &&
        confirm.control_result.status >= 200 &&
        confirm.control_result.status < 300,
      "Control path or actual HTTP success proof missing",
    );
    return { id, begin, confirm, target };
  });
}

export async function qualifyCancellations({
  apiPath,
  abortPath,
  transitionPath,
}) {
  const result = {
    protocol: "issue393-client-abort-v2",
    clean: false,
    expected: [],
    unexpected: [],
    counts: {
      starts: 0,
      terminals: 0,
      measured_cancellations: 0,
      expected: 0,
      unexpected: 0,
    },
    source_sha256: createHash("sha256")
      .update(await readFile(new URL(import.meta.url)))
      .digest("hex"),
    input_sha256: {},
  };
  const fail = (request_id, reason) =>
    result.unexpected.push({ request_id, reason });
  try {
    const inputs = {};
    for (const [name, path] of Object.entries({
      api: apiPath,
      abort: abortPath,
      transition: transitionPath,
    })) {
      const input = await readRows(path);
      result.input_sha256[name] = input.sha256;
      inputs[name] = input.rows;
    }
    const starts = new Map(),
      terminals = new Map();
    for (const row of inputs.api) {
      if (row.event === "capture-end") continue;
      requireProof(
        ["start", "terminal"].includes(row.event) &&
          typeof row.id === "string" &&
          row.id.length,
        "Unknown API event or missing request ID",
      );
      const target = row.event === "start" ? starts : terminals;
      requireProof(
        !target.has(row.id),
        `Duplicate API ${row.event}: ${row.id}`,
      );
      target.set(row.id, row);
    }
    result.counts.starts = starts.size;
    result.counts.terminals = terminals.size;
    for (const [id, start] of starts) {
      const end = terminals.get(id);
      requireProof(end, `Missing terminal: ${id}`);
      requireProof(
        ["page", "path", "method", "url", "startedPhase"].every(
          (key) => start[key] === end[key],
        ),
        `API start/terminal scope mismatch: ${id}`,
      );
      requireProof(
        finite(start.at) && finite(end.at) && start.at <= end.at,
        `Invalid API timing: ${id}`,
      );
    }
    for (const id of terminals.keys())
      requireProof(starts.has(id), `Terminal without start: ${id}`);
    const pairs = transitions(inputs.transition),
      usedAborts = new Set(),
      usedScopes = new Set(),
      abortIds = new Set();
    for (const abort of inputs.abort) {
      requireProof(
        typeof abort.id === "string" &&
          abort.id.length &&
          !abortIds.has(abort.id),
        "Missing or duplicate abort ID",
      );
      abortIds.add(abort.id);
    }
    const cancels = [...terminals.values()].filter(
      (end) =>
        end.startedPhase === "measured" &&
        end.outcome === "client_cancellation",
    );
    result.counts.measured_cancellations = cancels.length;
    for (const end of cancels) {
      const start = starts.get(end.id);
      try {
        requireProof(
          start.method === "GET" &&
            start.path === `${PREFIX}events` &&
            start.resourceType === "xhr" &&
            end.errorText === "net::ERR_ABORTED" &&
            missionScope(start) &&
            missionScope(end),
          "Cancellation is outside the declared measured GET/events XHR mission scope",
        );
        const requestWallStart = end.wallStartTimeMs;
        requireProof(
          finite(requestWallStart) &&
            requestWallStart > 0 &&
            end.wallStartTimeSource === "cdp" &&
            finite(end.wallTimeMs),
          "Missing authoritative positive CDP cancellation wall timing",
        );
        const candidates = pairs.filter(
          ({ begin }) =>
            start.at >= begin.clock_seconds - 2 &&
            start.at <= begin.clock_seconds + 10 &&
            end.at >= begin.clock_seconds &&
            end.at <= begin.clock_seconds + 10,
        );
        requireProof(
          candidates.length === 1,
          "Cancellation has no unique planned transition window",
        );
        const transition = candidates[0],
          { begin, confirm } = transition;
        requireProof(
          end.wallTimeMs >= begin.wall_time_ms &&
            end.wallTimeMs <= begin.wall_time_ms + 10000,
          "Cancellation terminal wall time is outside the transition window",
        );
        if (start.sourceIdentity != null)
          requireProof(
            start.sourceIdentity === begin.before_identity,
            "Canceled request source does not match the prior source",
          );
        const aborts = inputs.abort.filter(
          (abort) =>
            abort.page === start.page &&
            abort.method === start.method &&
            abort.url === start.url &&
            abort.mechanism === "xhr.abort" &&
            finite(abort.sendWallTimeMs) &&
            Math.abs(abort.sendWallTimeMs - requestWallStart) <= 100 &&
            finite(abort.abortWallTimeMs) &&
            abort.abortWallTimeMs >= requestWallStart &&
            abort.abortWallTimeMs <= end.wallTimeMs + 100 &&
            finite(abort.at) &&
            abort.at >= begin.clock_seconds &&
            abort.at <= begin.clock_seconds + 10 &&
            abort.abortWallTimeMs >= begin.wall_time_ms &&
            abort.abortWallTimeMs <= begin.wall_time_ms + 10000,
        );
        requireProof(
          aborts.length === 1,
          "Missing or ambiguous actual xhr.abort proof",
        );
        const abort = aborts[0],
          scope = `${start.page}:${transition.id}`;
        requireProof(
          !usedAborts.has(abort.id),
          "One abort cannot qualify two requests",
        );
        requireProof(
          !usedScopes.has(scope),
          "More than one cancellation per page/transition",
        );
        const recovery = (page, path, predicate, fresh = false) =>
          [...terminals.values()].find((row) => {
            const request = starts.get(row.id);
            return (
              request.page === page &&
              request.method === "GET" &&
              request.path === PREFIX + path &&
              row.status === 200 &&
              row.outcome === "success" &&
              !row.body?.error &&
              row.at >= begin.clock_seconds &&
              row.at <= begin.clock_seconds + 10 &&
              (!fresh || request.at > end.at) &&
              predicate(row, request)
            );
          });
        const active = begin.records_active_after,
          target = confirm.target_identity;
        const contextMatches = (row) =>
          row.context?.missionId === (active ? MISSION : null) &&
          row.context?.operatingContextId ===
            (active ? transition.target[3] : null);
        const health = recovery(
          start.page,
          "health",
          (row) => row.healthIdentity === target,
        );
        const context = recovery(start.page, "context", contextMatches);
        const fresh = active
          ? recovery(
              start.page,
              "events",
              (row, request) =>
                missionScope(request) &&
                row.eventSource?.identity === target &&
                row.eventSource?.missionId === MISSION,
              true,
            )
          : recovery(start.page, "context", contextMatches, true);
        const operatorHealth = recovery(
          1,
          "health",
          (row) => row.healthIdentity === target,
        );
        const operatorContext = recovery(1, "context", contextMatches);
        const operatorRecords = active
          ? recovery(
              1,
              "records",
              (row, request) =>
                missionScope(request) && row.responseSourceIdentity === target,
            )
          : null;
        requireProof(
          health &&
            context &&
            fresh &&
            operatorHealth &&
            operatorContext &&
            (!active || operatorRecords),
          "Missing successful fresh source recovery on canceled page and Operator page",
        );
        usedAborts.add(abort.id);
        usedScopes.add(scope);
        result.expected.push({
          request_id: end.id,
          abort_id: abort.id,
          transition_id: transition.id,
          page: start.page,
          recovery_ids: {
            health: health.id,
            context: context.id,
            fresh_source: fresh.id,
            operator_health: operatorHealth.id,
            operator_context: operatorContext.id,
            operator_records: operatorRecords?.id ?? null,
          },
          proof: {
            before_identity: begin.before_identity,
            target_identity: target,
            records_active_after: active,
            request_start: start.at,
            request_wall_start_time_ms: requestWallStart,
            request_wall_start_source: end.wallStartTimeSource,
            cancellation_terminal: end.at,
            abort_at: abort.at,
            transition_begin: begin.clock_seconds,
            transition_confirmed: confirm.clock_seconds,
            send_wall_time_ms: abort.sendWallTimeMs,
            abort_wall_time_ms: abort.abortWallTimeMs,
            terminal_wall_time_ms: end.wallTimeMs,
            mechanism: abort.mechanism,
          },
        });
      } catch (error) {
        fail(end.id, error.message);
      }
    }
  } catch (error) {
    fail(null, `Evidence integrity: ${error.message}`);
  }
  result.counts.expected = result.expected.length;
  result.counts.unexpected = result.unexpected.length;
  result.clean =
    result.unexpected.length === 0 &&
    result.expected.length === result.counts.measured_cancellations;
  return result;
}
