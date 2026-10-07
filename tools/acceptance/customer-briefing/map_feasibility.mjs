/** Disposable Task 3A gate. Never starts the application or a shared Compose project. */
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function evaluateGate(runs, expectedViewIds) {
  const reasons = [];
  if (runs.length !== 3)
    reasons.push("Exactly three cold mission runs required");
  if (expectedViewIds.length < 4)
    reasons.push("At least four primary views required");
  for (const [i, run] of runs.entries()) {
    if (run.status !== "primary" || run.exitCode !== 0)
      reasons.push(`Run ${i + 1}: primary renderer failed/fell back`);
    if (!Number.isFinite(run.elapsedSeconds) || run.elapsedSeconds > 50)
      reasons.push(`Run ${i + 1}: whole stage exceeds 50 seconds`);
    if (
      JSON.stringify(run.views?.map((v) => v.id)) !==
      JSON.stringify(expectedViewIds)
    )
      reasons.push(`Run ${i + 1}: missing/reordered primary views`);
    if (
      run.views?.some(
        (v) =>
          !/^[a-f0-9]{64}$/.test(v.pngHash) ||
          !/^[a-f0-9]{64}$/.test(v.pixelHash),
      )
    )
      reasons.push(`Run ${i + 1}: missing PNG/pixel evidence`);
    if (
      !run.cleanupVerified ||
      !run.cleanup?.listenerClosed ||
      !run.cleanup?.browserExited ||
      !run.cleanup?.contextsClosed ||
      run.cleanup?.errors?.length
    )
      reasons.push(`Run ${i + 1}: cleanup incomplete`);
  }
  return { pass: reasons.length === 0, reasons };
}

async function main() {
  const repo = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../..",
  );
  const image =
    process.env.MISSION_MAP_IMAGE ?? "starlink-customer-briefing-task3a:local";
  const evidence = path.resolve(
    process.env.MISSION_MAP_EVIDENCE ??
      path.join(
        repo,
        ".superpowers/sdd/2026-10-07-customer-mission-briefing-phase-one/evidence/task-3a",
      ),
  );
  const fixturePath = path.join(
    repo,
    "backend/starlink-location/tests/fixtures/customer_briefing/f08_map_inputs.json",
  );
  const fixtureBytes = await readFile(fixturePath);
  const fixture = JSON.parse(fixtureBytes);
  await mkdir(evidence, { recursive: true });
  const owner = `mission-map-3a-${randomBytes(6).toString("hex")}`;
  const ownership = {
    owner,
    pid: process.pid,
    image,
    compose: null,
    volumes: [],
    containers: [],
    commands: [],
    temporaryPaths: [evidence],
    listeners: "container-private loopback only; no host ports",
  };
  const ownershipFile = path.join(evidence, "ownership.json");
  const save = () =>
    writeFile(ownershipFile, JSON.stringify(ownership, null, 2));
  await save();
  let interrupted = false;
  const stop = () => {
    interrupted = true;
    for (const command of ownership.commands.filter((c) => c.running)) {
      try {
        process.kill(-command.pgid, "SIGTERM");
      } catch {}
    }
  };
  process.once("SIGTERM", stop);
  process.once("SIGINT", stop);
  async function command(args, seconds = 30, onOutput) {
    const entry = {
      command: [
        "timeout",
        "--kill-after=10s",
        `${Math.max(1, Math.floor(seconds))}s`,
        ...args,
      ],
      pid: null,
      pgid: null,
      running: false,
    };
    ownership.commands.push(entry);
    await save();
    const child = spawn(entry.command[0], entry.command.slice(1), {
      cwd: repo,
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    entry.pid = child.pid;
    entry.pgid = child.pid;
    entry.running = true;
    await save();
    let stdout = "",
      stderr = "";
    child.stdout.on("data", (chunk) => {
      const data = chunk.toString();
      stdout += data;
      onOutput?.(data);
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    const exitCode = await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("close", resolve);
    });
    entry.running = false;
    entry.exitCode = exitCode;
    await save();
    return { exitCode, stdout, stderr };
  }
  async function removeContainer(entry) {
    const state = await command([
      "docker",
      "inspect",
      "-f",
      "{{.State.Running}}",
      entry.name,
    ]);
    if (state.exitCode === 0 && state.stdout.trim() === "true")
      await command(["docker", "stop", "--time", "3", entry.name], 10);
    await command(["docker", "rm", "-f", entry.name], 10);
    const check = await command([
      "docker",
      "ps",
      "-aq",
      "--filter",
      `name=^/${entry.name}$`,
    ]);
    entry.removed = check.exitCode === 0 && !check.stdout.trim();
    return entry.removed;
  }
  async function run(name, { fault, input = fixture, testSuite = false } = {}) {
    if (interrupted) throw new Error("Feasibility interrupted");
    const output = path.join(evidence, name);
    await mkdir(output, { recursive: true });
    const container = {
      name: `${owner}-${name}`,
      removed: false,
      purpose: name,
      privateVolumes: [],
      hostPorts: [],
    };
    ownership.containers.push(container);
    await save();
    const started = performance.now();
    const deadline = started + 60_000;
    const remaining = () => Math.max(1, (deadline - performance.now()) / 1000);
    let execution, result, entrySeconds;
    try {
      // Record command/name before startup; --init reaps browser descendants.
      const argv = [
        "docker",
        "create",
        "--name",
        container.name,
        "--label",
        `mission-map-owner=${owner}`,
        "--init",
        "--network",
        "none",
        "--cpus",
        "4",
        "--memory",
        "4g",
        "--entrypoint",
        "node",
        "-e",
        "MISSION_MAP_BROWSER_EVIDENCE=/evidence/browser-contracts",
        image,
      ];
      if (testSuite)
        argv.push(
          "node_modules/playwright/cli.js",
          "test",
          "--config",
          "playwright.mission-export.config.ts",
          "--output",
          "/evidence/browser-tests",
        );
      else
        argv.push(
          "src/mission-export/render.mjs",
          "/tmp/map-input.json",
          "/evidence",
          "/renderer/frontend/mission-planner/dist-mission-export",
          ...(fault ? [fault] : []),
        );
      const created = await command(argv, remaining());
      if (created.exitCode)
        throw new Error(`Container creation failed: ${created.stderr}`);
      container.id = created.stdout.trim();
      await save();
      const privateInput = path.join(output, "input.json");
      await writeFile(privateInput, JSON.stringify(input));
      const copied = await command(
        ["docker", "cp", privateInput, `${container.name}:/tmp/map-input.json`],
        remaining(),
      );
      if (copied.exitCode)
        throw new Error(`Input copy failed: ${copied.stderr}`);
      execution = await command(
        ["docker", "start", "-a", container.name],
        testSuite ? 120 : remaining(),
        (data) => {
          if (data.includes("renderer-entry") && entrySeconds === undefined)
            entrySeconds = (performance.now() - started) / 1000;
        },
      );
      await writeFile(
        path.join(output, "stdout.log"),
        execution.stdout + execution.stderr,
      );
      const collected = await command(
        ["docker", "cp", `${container.name}:/evidence/.`, output],
        remaining(),
      );
      if (collected.exitCode)
        throw new Error(`Evidence collection failed: ${collected.stderr}`);
      if (!testSuite)
        result = JSON.parse(
          await readFile(path.join(output, "result.json"), "utf8"),
        );
      else
        result = {
          status: execution.exitCode === 0 ? "passed" : "failed",
          views: [],
          cleanup: {
            listenerClosed: true,
            browserExited: true,
            contextsClosed: true,
            errors: [],
          },
        };
    } catch (err) {
      result = { status: "failed", error: String(err), views: [], cleanup: {} };
    } finally {
      await removeContainer(container);
    }
    const elapsedSeconds = (performance.now() - started) / 1000;
    result.rendererElapsedSeconds = result.elapsedSeconds;
    result.elapsedSeconds = elapsedSeconds;
    result.marginSeconds = 60 - elapsedSeconds;
    result.entrySeconds = entrySeconds;
    result.coldStartupSeconds =
      entrySeconds !== undefined && result.startupSeconds !== undefined
        ? entrySeconds + result.startupSeconds
        : undefined;
    result.exitCode = execution?.exitCode;
    result.cleanupVerified = container.removed;
    result.container = container;
    // docker cp rewrites local paths; verify collected PNGs independently.
    for (const view of result.views ?? []) {
      view.path = path.join(output, path.basename(view.path));
      const actualHash = createHash("sha256")
        .update(await readFile(view.path))
        .digest("hex");
      if (actualHash !== view.pngHash) {
        result.status = "failed";
        result.error = "Collected PNG digest mismatch";
      }
    }
    await writeFile(
      path.join(output, "stage.json"),
      JSON.stringify(result, null, 2),
    );
    console.log(
      `${name}: ${result.status}, ${elapsedSeconds.toFixed(3)}s, ${result.views?.length ?? 0} views, cleanup ${container.removed}`,
    );
    return result;
  }
  const runs = [];
  let report;
  try {
    const identity = await command(["docker", "image", "inspect", image]);
    if (identity.exitCode)
      throw new Error(`Build the disposable image first: ${identity.stderr}`);
    const imageInfo = JSON.parse(identity.stdout)[0];
    const revision = await command(["git", "rev-parse", "HEAD"]);
    const sourceRevision = revision.stdout.trim();
    if (
      imageInfo.Config.Labels?.["org.opencontainers.image.revision"] !==
      sourceRevision
    )
      throw new Error(
        "Disposable image revision must match checked-out source HEAD",
      );
    const runtimeInputs = {};
    for (const file of [
      "frontend/mission-planner/package-lock.json",
      "tools/acceptance/customer-briefing/Dockerfile.renderer-feasibility",
      "frontend/mission-planner/src/mission-export/main.tsx",
      "frontend/mission-planner/src/mission-export/scene.tsx",
      "frontend/mission-planner/src/mission-export/framing.ts",
      "frontend/mission-planner/src/mission-export/protocol.ts",
      "frontend/mission-planner/src/mission-export/render.mjs",
      "frontend/mission-planner/public/earth-day-hi.jpg",
      "frontend/mission-planner/public/city-lights-mask.png",
    ])
      runtimeInputs[file] = createHash("sha256")
        .update(await readFile(path.join(repo, file)))
        .digest("hex");
    const browserChecks = await run("packaged-browser-checks", {
      testSuite: true,
    });
    if (browserChecks.status !== "passed")
      throw new Error("Packaged readiness/pixel/failure/cleanup checks failed");
    for (let i = 1; i <= 3; i++) runs.push(await run(`cold-${i}`));
    const gate = evaluateGate(runs, fixture.expectedViewIds);
    for (const run of runs) {
      for (const [name, digest] of Object.entries(
        run.runtime?.sourceDigests ?? {},
      ))
        if (runtimeInputs[name] !== digest)
          gate.reasons.push(`Image/source mismatch: ${name}`);
    }
    gate.pass = gate.reasons.length === 0;
    browserChecks.contracts = {};
    for (const name of [
      "identical",
      "startup",
      "texture",
      "context-loss",
      "slow",
    ])
      browserChecks.contracts[name] = JSON.parse(
        await readFile(
          path.join(
            evidence,
            "packaged-browser-checks/browser-contracts",
            `${name}.json`,
          ),
          "utf8",
        ),
      );
    report = {
      schema: "RendererFeasibilityReport/v1",
      status: gate.pass ? "pass" : "no-go",
      reasons: gate.reasons,
      dependenciesReleased: gate.pass ? ["Task 2"] : [],
      blockedOnFailure: ["Task 2", "Task 3B", "Task 4"],
      sourceRevision,
      fixture: fixture.fixture,
      fixtureDigest: createHash("sha256").update(fixtureBytes).digest("hex"),
      expectedViewIds: fixture.expectedViewIds,
      runtimeInputs,
      image: {
        id: imageInfo.Id,
        digests: imageInfo.RepoDigests,
        user: imageInfo.Config.User,
        sizeBytes: imageInfo.Size,
      },
      hardware: {
        host: os.hostname(),
        platform: os.platform(),
        architecture: os.arch(),
        kernel: os.release(),
        cpu: os.cpus()[0].model,
        logicalCpus: os.cpus().length,
        totalMemoryBytes: os.totalmem(),
        containerCpus: 4,
        containerMemoryBytes: 4294967296,
        rendering: "CPU ANGLE SwiftShader; no GPU assumed",
        qualification:
          "Managed deployment host and representative constrained container allocation; final production image must repeat gate in Task 3B.",
      },
      limits: {
        sharedStageSeconds: 60,
        screeningSeconds: 50,
        coldProcesses: true,
        requestCacheHits: 0,
        includes: [
          "container/Node/browser startup",
          "asset decoding",
          "shader compilation",
          "camera/labels",
          "every required primary PNG",
          "collection",
          "browser/listener/container cleanup",
        ],
      },
      browserChecks,
      runs,
    };
  } catch (err) {
    report = {
      schema: "RendererFeasibilityReport/v1",
      status: "no-go",
      reasons: [String(err)],
      runs,
      dependenciesReleased: [],
    };
  } finally {
    for (const container of ownership.containers.filter((c) => !c.removed))
      await removeContainer(container);
    const survivors = await command([
      "docker",
      "ps",
      "-aq",
      "--filter",
      `label=mission-map-owner=${owner}`,
    ]);
    report.cleanup = {
      containersGone: survivors.exitCode === 0 && !survivors.stdout.trim(),
      privateVolumes: [],
      networks: [],
      hostListeners: [],
      retainedEvidence: evidence,
      ownedContainerNames: ownership.containers.map((c) => c.name),
    };
    if (!report.cleanup.containersGone) {
      report.status = "no-go";
      report.reasons.push("Owned containers remain");
    }
    process.removeListener("SIGTERM", stop);
    process.removeListener("SIGINT", stop);
    await save();
    await writeFile(
      path.join(evidence, "RendererFeasibilityReport.json"),
      JSON.stringify(report, null, 2),
    );
  }
  console.log(
    `Task 3A: ${report.status}; report ${path.join(evidence, "RendererFeasibilityReport.json")}`,
  );
  process.exitCode = report.status === "pass" ? 0 : 1;
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  await main();
