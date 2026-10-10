import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const root = resolve(dirname(new URL(import.meta.url).pathname), "../../..");
const require = createRequire(
  join(root, "frontend/mission-planner/package.json"),
);
const { chromium, expect } = require("@playwright/test");

export async function journey(context, origin, seed, output) {
  const page = await context.newPage();
  const steps = [],
    consoleErrors = [],
    networkErrors = [],
    writes = [];
  const observed = [];
  const record = async (name, value = {}) => {
    const screenshot = `${String(steps.length + 1).padStart(2, "0")}-${name}.png`;
    await page.screenshot({ path: join(output, screenshot), fullPage: true });
    steps.push({ name, screenshot, ...value });
    await writeFile(join(output, "steps.json"), JSON.stringify(steps, null, 2));
  };
  context.on("page", observe);
  observe(page);
  function observe(target) {
    target.on("pageerror", (error) => consoleErrors.push(String(error)));
    target.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    target.on("requestfailed", (request) =>
      networkErrors.push({
        url: request.url(),
        error: request.failure()?.errorText,
      }),
    );
    target.on("response", async (response) => {
      if (response.status() >= 400)
        networkErrors.push({ url: response.url(), status: response.status() });
      if (
        response.url().includes("/planning/") &&
        response.request().method() !== "GET"
      ) {
        try {
          observed.push({
            url: response.url(),
            status: response.status(),
            value: await response.json(),
          });
        } catch {
          /* non-JSON failures retained separately */
        }
      }
    });
    target.on("request", (request) => {
      if (!["GET", "HEAD"].includes(request.method()))
        writes.push({ method: request.method(), url: request.url() });
    });
  }
  const api = context.request;
  const json = async (path) => {
    const response = await api.get(origin + path);
    assert(response.ok(), `${response.status()} ${await response.text()}`);
    return response.json();
  };
  let mission, cards;
  const read = () => json(`/api/v2/missions/planning/missions/${mission}`);
  const clickResponse = async (target, label, suffix, status = 200) => {
    const response = target.waitForResponse(
      (r) => r.url().endsWith(suffix) && r.request().method() !== "GET",
    );
    await target.getByRole("button", { name: label, exact: true }).click();
    const result = await response;
    assert.equal(result.status(), status, await result.text());
    return result.json();
  };
  const save = (target) => clickResponse(target, "Save draft", "/draft");
  const bind = async (ordinal, filename = `leg-${ordinal}.kml`) => {
    await page
      .getByLabel(`KML for leg ${ordinal}`, { exact: true })
      .setInputFiles(join(seed, filename));
    const before = await read();
    await clickResponse(page, "Preview selected-leg KML", "/route-previews");
    assert.deepEqual(
      await read(),
      before,
      "route preview must not mutate mission",
    );
    for (const checkbox of await page
      .getByRole("checkbox", { name: /^Acknowledge:/ })
      .all())
      await checkbox.check();
    await clickResponse(page, "Accept route and review AR windows", "/route");
    await expect(
      page.getByRole("tab", { name: "AR windows", exact: true }),
    ).toHaveAttribute("aria-selected", "true");
  };
  const reviewAR = async (tracks) => {
    for (const track of tracks) {
      await page
        .getByLabel(`Altitude units ${track}`, { exact: true })
        .selectOption("flight_level");
      await page.getByLabel(`Confirm ${track}`, { exact: true }).check();
    }
  };
  const prepareX = async (manual = false) => {
    await page.getByRole("tab", { name: "X-band plan", exact: true }).click();
    await page
      .getByLabel("Initial X-band satellite", { exact: true })
      .selectOption("X-SYNTH-A");
    if (manual) {
      await page.getByLabel("Lock initial satellite", { exact: true }).check();
      await page
        .getByLabel("New swap route occurrence", { exact: true })
        .selectOption("9");
      await page
        .getByLabel("New swap satellite", { exact: true })
        .selectOption("X-SYNTH-B");
      await page
        .getByRole("button", { name: "Add manual swap", exact: true })
        .click();
      await page.getByLabel("Lock swap 1", { exact: true }).check();
    }
    return save(page);
  };
  const reviewed = async (next) => {
    await page
      .getByLabel("I confirm this satellite plan and Starshield enablement")
      .check();
    await page
      .getByLabel("I acknowledge the X-band outages and backup gaps")
      .check();
    return clickResponse(
      page,
      next ? "Save reviewed plan and upload next leg" : "Save reviewed plan",
      "/reviewed",
    );
  };
  try {
    await page.goto(origin + "/missions");
    const create = page.getByRole("button", {
      name: "Create from itinerary",
      exact: true,
    });
    await create.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(create).toBeFocused();
    await page.keyboard.press("Enter");
    await page
      .getByLabel("Itinerary PDF", { exact: true })
      .setInputFiles(join(seed, "itinerary.pdf"));
    const preview = await clickResponse(
      page,
      "Extract itinerary",
      "/itinerary-previews",
    );
    assert.equal(preview.parsed_values.expected_legs.length, 3);
    assert.equal(
      preview.parsed_values.expected_legs.flatMap((l) => l.ar_rows).length,
      5,
    );
    await expect(
      page.getByLabel("I confirm no AR windows for this leg"),
    ).toHaveCount(1);
    await record("itinerary-first-keyboard", { preview });
    await page.getByLabel("I confirm no AR windows for this leg").check();
    const created = await clickResponse(
      page,
      "Confirm itinerary and create draft",
      "/planning/missions",
      201,
    );
    mission = created.mission.id;
    cards = created.expected_legs;
    assert.equal(created.mission.legs.length, 0);
    await expect(
      page.getByRole("region", { name: "Itinerary expected legs" }),
    ).toBeVisible();
    await record("three-expected-legs", { view: created });
    await page
      .getByRole("link", { name: "Upload KML", exact: true })
      .first()
      .click();
    await bind(1);
    await expect(page.getByText(/Provisional plan:/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Save reviewed plan", exact: true }),
    ).toBeDisabled();
    await record("selected-kml-provisional");
    await page
      .getByLabel("I confirm service access to the selected satellites")
      .check();
    await reviewAR(["ALPHA", "BRAVO", "CHARLIE"]);
    let saved = await prepareX(true);
    const locked = saved.expected_legs[0].leg.draft;
    await expect(
      page.getByLabel("Initial X-band satellite", { exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByLabel("Swap 1 satellite", { exact: true }),
    ).toBeDisabled();
    const proposal = await clickResponse(page, "Re-optimize", "/proposals");
    assert.equal(proposal.state, "ready");
    assert(
      proposal.baseline_evaluation.intervals.some(
        (i) =>
          i.physical_x_state === "available" && i.policy_x_state === "offline",
      ),
      "policy outage retains physical X capability",
    );
    assert.deepEqual(proposal.proposed_draft.locks, locked.locks);
    await expect(
      page.getByText("X-band outage under Starshield preference", {
        exact: true,
      }),
    ).toBeVisible();
    await page
      .getByText(
        "Physical capability and operating policy · exact UTC intervals",
        { exact: true },
      )
      .click();
    await expect(
      page.getByText(/Physical X: available · Policy X: offline/).first(),
    ).toBeVisible();
    await record("manual-lock-policy-proposal", { proposal });
    saved = await clickResponse(page, "Apply proposal", "/apply");
    assert.deepEqual(
      saved.expected_legs[0].leg.draft.evaluation_context,
      proposal.context,
    );
    assert.deepEqual(saved.expected_legs[0].leg.draft.locks, locked.locks);
    await page
      .getByRole("button", { name: "Reload saved draft", exact: true })
      .click();
    await expect(page.getByText("Saved draft reloaded.")).toBeVisible();
    assert.deepEqual(
      (await read()).expected_legs[0].leg.draft.evaluation_context,
      proposal.context,
    );
    await record("apply-exact-context-reload");
    const second = await context.newPage();
    await second.goto(page.url());
    await expect(
      second.getByRole("button", { name: "Save draft", exact: true }),
    ).toBeVisible();
    await save(page);
    await clickResponse(second, "Save draft", "/draft", 409);
    await expect(
      second.getByRole("alert").filter({ hasText: "Planning state changed" }),
    ).toBeVisible();
    await second.screenshot({
      path: join(output, "second-tab-conflict.png"),
      fullPage: true,
    });
    await second.close();
    await record("second-tab-409");
    saved = await reviewed(true);
    assert.equal(saved.mission.legs.length, 1);
    assert(saved.mission.legs.every((l) => l.is_active === false));
    await expect(
      page.getByLabel("KML for leg 2", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByLabel("I confirm no AR windows for this leg"),
    ).toBeChecked();
    await record("reviewed-inactive-next-no-ar", { view: saved });
    await bind(2);
    await page
      .getByLabel("I confirm service access to the selected satellites")
      .check();
    await prepareX();
    const noAR = await clickResponse(page, "Re-optimize", "/proposals");
    assert.equal(noAR.state, "ready");
    assert.equal(noAR.candidate_evaluation.errors.length, 0);
    await record("no-ar-leg-evaluation", { proposal: noAR });
    await page.goto(`${origin}/missions/${mission}/legs/${cards[2].leg.id}`);
    await bind(3);
    await page
      .getByLabel("I confirm service access to the selected satellites")
      .check();
    await reviewAR(["DELTA", "ECHO"]);
    await prepareX();
    await clickResponse(page, "Re-optimize", "/proposals");
    await clickResponse(page, "Apply proposal", "/apply");
    await reviewed(false);
    await page.goto(`${origin}/missions/${mission}`);
    await page.reload();
    await expect(
      page.getByRole("link", { name: "Open reviewed plan" }),
    ).toHaveCount(2);
    await expect(page.getByText("Leg 3 of 3", { exact: true })).toBeVisible();
    await record("resume-partial-1-and-3");
    const exported = await api.post(
      `${origin}/api/v2/missions/${mission}/export`,
      { data: {}, timeout: 120000 },
    );
    assert(exported.ok(), await exported.text());
    const zip = await exported.body();
    await writeFile(join(output, "synthetic-package.zip"), zip);
    const imported = await api.post(`${origin}/api/v2/missions/import`, {
      multipart: {
        file: {
          name: "synthetic-package.zip",
          mimeType: "application/zip",
          buffer: zip,
        },
      },
      timeout: 120000,
    });
    assert(imported.ok(), await imported.text());
    const clone = await imported.json();
    assert(clone.success && clone.mission_id !== mission);
    const cloneView = await json(
      `/api/v2/missions/planning/missions/${clone.mission_id}`,
    );
    assert.equal(cloneView.expected_legs.length, 3);
    assert.equal(cloneView.mission.legs.length, 2);
    assert(
      cloneView.expected_legs.every(
        (c) => !cards.some((old) => old.leg.id === c.leg.id),
      ),
    );
    const reexport = await api.post(
      `${origin}/api/v2/missions/${clone.mission_id}/export`,
      { data: {}, timeout: 120000 },
    );
    assert(reexport.ok());
    const roundtrip = await api.post(`${origin}/api/v2/missions/import`, {
      multipart: {
        file: {
          name: "roundtrip.zip",
          mimeType: "application/zip",
          buffer: await reexport.body(),
        },
      },
      timeout: 120000,
    });
    assert(roundtrip.ok(), await roundtrip.text());
    const round = await roundtrip.json();
    assert(round.success && round.mission_id !== clone.mission_id);
    await page.goto(`${origin}/missions/${clone.mission_id}`);
    await expect(
      page.getByRole("link", { name: "Open reviewed plan" }),
    ).toHaveCount(2);
    await record("package-collision-roundtrip", { clone, cloneView, round });
    await page.goto(`${origin}/missions/${mission}/legs/${cards[0].leg.id}`);
    const beforeReplacement = await read();
    await bind(1, "replacement.kml");
    const replaced = await read();
    assert(
      replaced.mission.metadata.itinerary_planning.route_history.length >
        beforeReplacement.mission.metadata.itinerary_planning.route_history
          .length,
    );
    assert(
      replaced.mission.metadata.itinerary_planning.review_records.length >= 2,
    );
    await record("route-replacement-retains-history", { view: replaced });
    await page.goto(`${origin}/missions/${mission}`);
    for (const [filename, name] of [
      ["revision.pdf", "revision"],
      ["retirement.pdf", "retirement"],
    ]) {
      await page
        .getByLabel("Revised itinerary PDF", { exact: true })
        .setInputFiles(join(seed, filename));
      const staged = await clickResponse(
        page,
        "Preview itinerary revision",
        "/itinerary-previews",
      );
      for (const issue of staged.conflicts ?? []) {
        const select = page.getByLabel(issue.message, { exact: true });
        if (await select.count()) await select.selectOption("retain");
      }
      await page.getByLabel("I confirm the complete leg mapping").check();
      await clickResponse(page, "Apply itinerary revision", "/revision");
      await record(name, { view: await read() });
    }
    const retired = await read();
    assert.equal(retired.expected_legs.filter((c) => !c.leg.retired).length, 2);
    assert(retired.mission.metadata.itinerary_planning.leg_history.length > 0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${origin}/missions/${mission}/legs/${cards[1].leg.id}`);
    await expect(
      page.getByLabel("KML for leg 2", { exact: true }),
    ).toBeVisible();
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "mobile review must fit viewport",
    );
    await record("mobile-review");
    assert(
      !writes.some((w) =>
        /\/(activate|deactivate|command|terminal)(?:\/|$)/.test(w.url),
      ),
      "planning must never activate or send terminal commands",
    );
    assert((await read()).mission.legs.every((l) => !l.is_active));
    assert.equal(
      consoleErrors.filter((e) => !e.includes("409 (Conflict)")).length,
      0,
      consoleErrors.join("\n"),
    );
    assert.equal(
      networkErrors.filter(
        (e) => e.status !== 409 && e.error !== "net::ERR_ABORTED",
      ).length,
      0,
      JSON.stringify(networkErrors),
    );
    await record("no-activation-or-terminal-side-effects", { writes });
    return {
      passed: true,
      steps: steps.map((s) => s.name),
      candidate_sha: process.env.ACCEPTANCE_CANDIDATE_SHA,
    };
  } finally {
    await writeFile(
      join(output, "browser-events.json"),
      JSON.stringify(
        { consoleErrors, networkErrors, writes, observed },
        null,
        2,
      ),
    );
    await page
      .screenshot({ path: join(output, "final-page.png"), fullPage: true })
      .catch(() => {});
    await page.close();
  }
}

async function main() {
  const output = process.env.ITINERARY_EVIDENCE_DIR;
  assert(
    output &&
      process.env.ITINERARY_CHROME &&
      process.env.ITINERARY_SEED_DIR &&
      process.env.ITINERARY_ORIGIN,
  );
  await mkdir(output, { recursive: true });
  const provenance = JSON.parse(
    await readFile(join(output, "browser-provenance.json"), "utf8"),
  );
  assert.equal(provenance.executable.path, process.env.ITINERARY_CHROME);
  const browser = await chromium.launch({
    executablePath: process.env.ITINERARY_CHROME,
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const stop = async () => {
    await context.close();
    await browser.close();
  };
  const interrupted = () => {
    void stop().finally(() => {
      process.exitCode = 1;
    });
  };
  process.once("SIGTERM", interrupted);
  process.once("SIGINT", interrupted);
  try {
    await context.tracing.start({ screenshots: true, snapshots: true });
    const result = await journey(
      context,
      process.env.ITINERARY_ORIGIN,
      process.env.ITINERARY_SEED_DIR,
      output,
    );
    await writeFile(
      join(output, "browser-summary.json"),
      JSON.stringify(result, null, 2),
    );
  } finally {
    await context.tracing
      .stop({ path: join(output, "trace.zip") })
      .catch(() => {});
    await stop();
    process.removeListener("SIGTERM", interrupted);
    process.removeListener("SIGINT", interrupted);
  }
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
