/** Real Nginx concurrency/disconnect controls with private phase observations. */
import { readdir, readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const [origin, mode, firstMission, secondMission, output] =
  process.argv.slice(2);
await mkdir(output, { recursive: true });
const controllers = new Set();
const stop = () => {
  for (const controller of controllers) controller.abort();
};
process.once("SIGINT", stop);
process.once("SIGTERM", stop);
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const read = async (file) => {
  try {
    return JSON.parse(await readFile(file, "utf8"));
  } catch {
    return null;
  }
};
async function phase(wanted, mission) {
  const deadline = Date.now() + 85000;
  while (Date.now() < deadline) {
    for (const name of await readdir("/tmp")) {
      if (!name.startsWith("customer-briefing-")) continue;
      const root = path.join("/tmp", name);
      const payload = await read(path.join(root, "payload.json"));
      const stage = await read(path.join(root, "stage-progress.json"));
      if (
        payload?.missionId === mission &&
        stage &&
        !stage.completed &&
        (wanted === "map"
          ? stage.stage.startsWith("map:")
          : stage.stage === wanted)
      ) {
        return {
          root,
          stage,
          ownership: await read(path.join(root, "ownership.json")),
          pythonOwner: await read(path.join(root, "python-owner.json")),
        };
      }
    }
    await pause(2);
  }
  throw Error("Target request never entered " + wanted);
}
async function download(mission, label, controller) {
  const started = performance.now();
  const response = await fetch(`${origin}/api/v2/missions/${mission}/export`, {
    method: "POST",
    signal: controller.signal,
  });
  const body = Buffer.from(await response.arrayBuffer());
  await writeFile(path.join(output, label + ".zip"), body);
  return {
    status: response.status,
    headers: Object.fromEntries(response.headers),
    totalMs: performance.now() - started,
  };
}
const report = { mode, status: "failed" };
try {
  const firstController = new AbortController();
  controllers.add(firstController);
  const first = download(firstMission, "first", firstController);
  // Attach rejection before observing to avoid an unhandled disconnect promise.
  const outcome = first.then(
    (value) => ({ value }),
    (error) => ({ error: String(error) }),
  );
  const wanted = mode === "concurrent" ? "map" : mode;
  report.observed = await phase(wanted, firstMission);
  if (mode === "concurrent") {
    const secondController = new AbortController();
    controllers.add(secondController);
    const second = download(secondMission, "second", secondController);
    const healthStarted = performance.now();
    const health = await fetch(`${origin}/api/v2/missions/${firstMission}`);
    if ((await health.json()).id !== firstMission)
      throw Error("health did not reach application");
    report.healthMs = performance.now() - healthStarted;
    report.healthStatus = health.status;
    report.second = await second;
    report.first = await outcome;
    if (
      report.first.error ||
      report.first.value.status !== 200 ||
      report.second.status !== 200 ||
      report.second.headers["x-customer-briefing-warning"] !== "busy"
    )
      throw Error("concurrency did not return real legacy busy fallback");
    if (report.healthMs > 2000)
      throw Error("event loop health response stalled");
  } else {
    firstController.abort();
    report.first = await outcome;
    if (!report.first.error)
      throw Error("disconnect unexpectedly completed a download");
    const deadline = Date.now() + 12000;
    while (
      Date.now() < deadline &&
      (await readdir("/tmp")).some(
        (name) => path.join("/tmp", name) === report.observed.root,
      )
    )
      await pause(20);
    if (
      (await readdir("/tmp")).some(
        (name) => path.join("/tmp", name) === report.observed.root,
      )
    )
      throw Error("disconnected request staging/worker did not drain");
    report.drained = true;
  }
  report.status = "passed";
} finally {
  stop();
  process.removeListener("SIGINT", stop);
  process.removeListener("SIGTERM", stop);
  await writeFile(
    path.join(output, "lifecycle.json"),
    JSON.stringify(report, null, 2),
  );
}
console.log(JSON.stringify(report));
