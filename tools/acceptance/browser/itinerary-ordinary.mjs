import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
const require = createRequire(
  new URL("../../../frontend/mission-planner/package.json", import.meta.url),
);
const { expect } = require("@playwright/test");
export async function ordinaryJourney(context, origin, seed, output) {
  const page = await context.newPage();
  const errors = [];
  const steps = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("dialog", (dialog) => dialog.accept());
  const json = async (path, method = "GET", data) => {
    const r = await context.request.fetch(origin + path, {
      method,
      data,
      timeout: 120000,
    });
    assert(r.ok(), await r.text());
    return r.json();
  };
  const save = async (name) => {
    await page.screenshot({
      path: join(output, name + ".png"),
      fullPage: true,
    });
    steps.push(name);
  };
  const proof = { candidate_sha: process.env.ACCEPTANCE_CANDIDATE_SHA };
  let mission;
  try {
    const migration = JSON.parse(
      await readFile(join(seed, "migration.json"), "utf8"),
    );
    const converted = await json(`/api/v2/missions/${migration.id}`);
    assert(converted.metadata.itinerary_import);
    assert(!converted.metadata.itinerary_planning);
    assert.equal(
      converted.legs[0].transports.initial_x_satellite_id,
      migration.satellite,
    );
    await page.goto(
      `${origin}/missions/${converted.id}/legs/${converted.legs[0].id}`,
    );
    await expect(
      page.getByText("Leg Configuration", { exact: true }),
    ).toBeVisible();
    proof.migration = true;
    await save("ordinary-migrated-editor");
    await page.goto(origin + "/missions");
    await page
      .getByRole("button", { name: "Create from itinerary", exact: true })
      .click();
    let dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Itinerary PDF", { exact: true })
      .setInputFiles(join(seed, "itinerary.pdf"));
    await dialog
      .getByLabel("Route KMLs", { exact: true })
      .setInputFiles([
        join(seed, "leg-3.kml"),
        join(seed, "leg-1-seconds.kml"),
        join(seed, "leg-2.kml"),
      ]);
    await dialog
      .getByRole("button", { name: "Generate mission", exact: true })
      .click();
    await page.waitForURL(/\/missions\/[^/]+$/, { timeout: 180000 });
    mission = page.url().split("/").at(-1);
    let current = await json(`/api/v2/missions/${mission}`);
    assert.equal(current.legs.length, 3);
    assert(current.legs.every((l) => !l.is_active));
    assert(!current.metadata.itinerary_planning);
    assert.equal(
      await page
        .getByRole("heading", { name: "Itinerary legs", exact: true })
        .count(),
      0,
    );
    assert.deepEqual(current.legs.map(l => l.name), ['AAAA–BBBB', 'BBBB–CCCC', 'CCCC–AAAA']);
    proof.chronological_legs = true;
    proof.automatic_import = true;
    await save("ordinary-generated-mission");
    const first = current.legs[0];
    const initial = await json(
      `/api/v2/missions/${mission}/legs/${first.id}/timeline`,
    );
    assert(initial.segments[0].start_time.includes("13:00:42"));
    assert(
      first.transports.aar_windows.every((w) => w.start_anchor && w.end_anchor),
    );
    assert(
      first.transports.aar_windows[0].start_anchor.source_time.includes(
        "13:20:42",
      ),
    );
    proof.precision_offsets = true;
    await page.goto(`${origin}/missions/${mission}/legs/${first.id}`);
    await expect(
      page.getByText("Leg Configuration", { exact: true }),
    ).toBeVisible();
    await page.locator("#departure-time").fill("13:10");
    const saved = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/legs/${first.id}`) && r.request().method() === "PUT",
    );
    await page.getByRole("button", { name: "Apply", exact: true }).click();
    assert.equal((await saved).status(), 200);
    current = await json(`/api/v2/missions/${mission}`);
    assert(current.legs[0].adjusted_departure_time.includes("13:10"));
    const changed = await json(
      `/api/v2/missions/${mission}/legs/${first.id}/timeline`,
    );
    assert(changed.segments[0].start_time.includes("13:10"));
    await save("ordinary-takeoff-edit");
    const second = current.legs[1];
    await page.goto(`${origin}/missions/${mission}/legs/${second.id}`);
    const replaced = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/legs/${second.id}/route`) &&
        r.request().method() === "PUT",
    );
    await page
      .locator("input[type=file]")
      .setInputFiles(join(seed, "replacement-2.kml"));
    assert.equal((await replaced).status(), 200);
    const afterReplacement = await json(`/api/v2/missions/${mission}`);
    assert.notEqual(afterReplacement.legs[1].route_id, second.route_id);
    proof.ordinary_editing = true;
    await save("ordinary-route-replacement");
    // Revisions do not require a second KML upload for unchanged routes.
    await page.goto(`${origin}/missions/${mission}`);
    await page
      .getByRole("button", { name: "Update from itinerary", exact: true })
      .click();
    dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Itinerary PDF", { exact: true })
      .setInputFiles(join(seed, "revision.pdf"));
    const beforeRevision = await json(`/api/v2/missions/${mission}`);
    await dialog.getByRole('button', {name: 'Update mission', exact: true}).click();
    await expect(dialog).not.toBeVisible({timeout: 180000});
    proof.automatic_revision = true;
    current = await json(`/api/v2/missions/${mission}`);
    assert.equal(current.id, beforeRevision.id);
    assert.equal(current.name, beforeRevision.name);
    assert.equal(
      current.legs[0].adjusted_departure_time,
      beforeRevision.legs[0].adjusted_departure_time,
    );
    assert.equal(current.metadata.itinerary_import.revision, 2);
    assert.equal(current.metadata.itinerary_import.history.length, 1);
    proof.revision_history = true;
    await save("ordinary-revision-applied");
    // Use the owned simulation runtime, then deactivate immediately after the guard check.
    await json(
      `/api/v2/missions/${mission}/legs/${second.id}/activate`,
      "POST",
    );
    try {
      const r = await context.request.put(
        `${origin}/api/v2/missions/${mission}/legs/${second.id}/route`,
        {
          multipart: {
            file: {
              name: "blocked.kml",
              mimeType: "application/xml",
              buffer: await readFile(join(seed, "replacement-2.kml")),
            },
          },
        },
      );
      assert.equal(r.status(), 409);
      proof.active_protection = true;
    } finally {
      await json(`/api/v2/missions/${mission}/legs/deactivate`, "POST");
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${origin}/missions/${mission}`);
    await expect(
      page.getByRole("heading", { name: "Mission Legs", exact: true }),
    ).toBeVisible();
    await save("ordinary-mobile-mission");
    await page.goto(`${origin}/missions/${mission}/legs/${first.id}`);
    await expect(
      page.getByText("Leg Configuration", { exact: true }),
    ).toBeVisible();
    await save("ordinary-mobile-editor");
    proof.desktop_mobile = true;
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(origin + "/missions");
    // Find this mission's export control, avoiding the separately migrated fixture.
    const row = page.locator('.cursor-pointer')
      .filter({ has: page.getByText(current.name, { exact: true }) })
      .filter({ has: page.getByText('3 legs', { exact: true }) });
    await expect(row).toHaveCount(1);
    await row.getByRole('button', { name: 'Export', exact: true }).click();
    dialog = page.getByRole("dialog");
    const download = page.waitForEvent("download", { timeout: 660000 });
    await dialog.getByRole("button", { name: "Export", exact: true }).click();
    const file = await download;
    assert.equal(await file.failure(), null);
    await file.saveAs(join(output, "synthetic-package.zip"));
    const archive = await readFile(join(output, "synthetic-package.zip"));
    const imported = await context.request.post(
      origin + "/api/v2/missions/import",
      {
        multipart: {
          file: {
            name: "synthetic-package.zip",
            mimeType: "application/zip",
            buffer: archive,
          },
        },
        timeout: 120000,
      },
    );
    assert(imported.ok(), await imported.text());
    const clone = await imported.json();
    const cloneMission = await json(`/api/v2/missions/${clone.mission_id}`);
    assert.notEqual(cloneMission.id, mission);
    assert.equal(cloneMission.legs.length, 3);
    assert.equal(cloneMission.metadata.itinerary_import.revision, 2);
    proof.package_roundtrip = true;
    await writeFile(
      join(output, "collision-views.json"),
      JSON.stringify(
        {
          beforeClone: { mission: current },
          cloneView: { mission: cloneMission },
        },
        null,
        2,
      ),
    );
    await writeFile(
      join(output, "ordinary-proof.json"),
      JSON.stringify(proof, null, 2),
    );
    assert.deepEqual(errors, []);
    return { passed: true, steps, candidate_sha: proof.candidate_sha, proof };
  } finally {
    if (mission)
      await context.request
        .post(`${origin}/api/v2/missions/${mission}/legs/deactivate`)
        .catch(() => {});
    await writeFile(
      join(output, "ordinary-browser-errors.json"),
      JSON.stringify(errors),
    );
    await page
      .screenshot({ path: join(output, "ordinary-final.png"), fullPage: true })
      .catch(() => {});
    await page.close();
  }
}
