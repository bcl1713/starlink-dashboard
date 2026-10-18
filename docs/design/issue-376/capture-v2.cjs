// Run from a mission-planner directory with the repository Playwright installed.
const { chromium } = require(
  require.resolve("@playwright/test", { paths: [process.cwd()] }),
);
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = __dirname;
const results = [];
const ownership = {
  task: "issue-376-design-revision-2",
  pid: process.pid,
  processGroup: require("node:child_process")
    .execFileSync("ps", ["-o", "pgid=", "-p", String(process.pid)], {
      encoding: "utf8",
    })
    .trim(),
  command:
    "timeout --kill-after=10s 3m node <worktree>/docs/design/issue-376/capture-v2.cjs",
  started: new Date().toISOString(),
  temporaryPaths: [],
  servers: [],
  containers: [],
  networks: [],
  volumes: [],
  scope:
    "Local synthetic design prototype; not product acceptance or real mobile keyboard validation",
};
const reportPath = path.join(root, "preview-v2-check.json");
fs.writeFileSync(reportPath, JSON.stringify(ownership, null, 2));
let browser;
async function cleanup() {
  if (browser) {
    await browser.close();
    browser = undefined;
  }
}
process.once("SIGTERM", async () => {
  await cleanup();
  process.exit(124);
});
process.once("SIGINT", async () => {
  await cleanup();
  process.exit(130);
});
async function capture(page, name) {
  const bounds = await page.evaluate(() => ({
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    documentVerticalOverflow:
      document.documentElement.scrollHeight > innerHeight,
    nextWidth: document
      .querySelector(".awareness .next")
      .getBoundingClientRect().width,
    undersizedButtons: [...document.querySelectorAll(".app button")]
      .filter(
        (el) =>
          el.getClientRects().length &&
          el.getBoundingClientRect().height < 43.9,
      )
      .map((el) => el.textContent.trim()),
  }));
  assert.equal(
    bounds.horizontalOverflow,
    false,
    name + ": horizontal overflow",
  );
  assert.ok(bounds.nextWidth >= 150, name + ": next-call area too narrow");
  assert.equal(
    bounds.documentVerticalOverflow,
    false,
    name + ": document overflow",
  );
  assert.deepEqual(
    bounds.undersizedButtons,
    [],
    name + ": touch target height",
  );
  await page.screenshot({ path: path.join(root, name + ".png") });
  results.push({ name, viewport: page.viewportSize(), ...bounds });
}
async function goto(page, query) {
  await page.goto("file://" + path.join(root, "review-v2.html") + "?" + query);
}
async function visibleInApp(page, selector) {
  return page.locator(selector).evaluate((el) => {
    const a = document.querySelector(".app").getBoundingClientRect();
    const b = el.getBoundingClientRect();
    return b.top >= a.top - 1 && b.bottom <= a.bottom + 1 && b.height >= 44;
  });
}
(async () => {
  let failure;
  const scriptErrors = [];
  const assertions = [];
  try {
    browser = await chromium.launch({ headless: true });
    for (const [width, height] of [
      [1920, 1080],
      [390, 844],
      [844, 390],
    ]) {
      const context = await browser.newContext({ viewport: { width, height } });
      try {
        const page = await context.newPage();
        page.on("pageerror", (e) => scriptErrors.push(e.message));
        const size = width + "x" + height;
        for (const concept of width === 844 ? ["A"] : ["A", "B", "C"]) {
          await goto(page, "concept=" + concept);
          assert.equal(
            await page.evaluate(() => window.previewFixture.customers.length),
            5,
          );
          await capture(
            page,
            "v2-" + concept.toLowerCase() + "-stress-" + size,
          );
        }
        for (const view of [
          "comms",
          "transport",
          "issues",
          "mission",
          "down",
        ]) {
          await goto(page, "view=" + view);
          await capture(page, "v2-" + view + "-" + size);
        }
        await goto(page, "view=comms");
        await page
          .getByRole("button", { name: "Establish Bridge C", exact: true })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.bridges["Bridge C"]),
          "established",
        );
        await page
          .getByRole("button", { name: "Verify Bridge C", exact: true })
          .click();
        await page
          .getByRole("button", {
            name: "Customer joined Bridge C",
            exact: true,
          })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.customers.length),
          6,
        );
        await page
          .getByRole("button", { name: "Customer left Alpha", exact: true })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.bridges["Bridge A"]),
          "established",
        );
        assert.equal(
          await page.evaluate(() => window.previewFixture.customers[0].state),
          "left",
        );
        if (width !== 1920)
          await page.locator('[data-customer="0"]').scrollIntoViewIfNeeded();
        await capture(page, "v2-comms-after-leave-" + size);
        await page
          .getByRole("button", { name: "Interrupt Bravo", exact: true })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.customers[1].state),
          "interrupted",
        );
        if (width !== 1920)
          await page.locator('[data-customer="1"]').scrollIntoViewIfNeeded();
        await capture(page, "v2-comms-interrupted-" + size);
        await page
          .getByRole("button", {
            name: "Restore Bravo connection",
            exact: true,
          })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.history[0].state),
          "interrupted",
        );
        assert.equal(
          await page.evaluate(
            () => window.previewFixture.customers[1].restored,
          ),
          true,
        );
        if (width !== 1920)
          await page.locator('[data-customer="1"]').scrollIntoViewIfNeeded();
        await capture(page, "v2-comms-restored-" + size);
        assertions.push(
          size +
            ": establish/verify/join/leave/interrupt/restore; bridge persists and prior interval retained in preview",
        );
        await goto(page, "view=issues");
        await page
          .getByRole("button", { name: "Resolve issue", exact: true })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.followup),
          "Cleared",
        );
        await page
          .getByRole("button", { name: "Reopen issue", exact: true })
          .click();
        assert.equal(
          await page.evaluate(() => window.previewFixture.followup),
          "None · prior deadline not restored",
        );
        await page
          .getByRole("button", { name: "Correct this message", exact: true })
          .click();
        await capture(page, "v2-issue-correction-" + size);
        assert.equal(
          await page.evaluate(() => window.previewFixture.issue),
          "reopened",
        );
        assertions.push(
          size +
            ": issue resolve/reopen clears deadline; correction keeps lifecycle",
        );
        await goto(page, "view=transport");
        await page.locator("#service").fill("Protected executive voice");
        await page.locator("#save-action").click();
        assert.match(
          await page.locator("#status").textContent(),
          /no acknowledgment gate/,
        );
        await capture(page, "v2-transport-report-preview-" + size);
        await page.locator('.save-footer [data-view="ops"]').click();
        await page
          .getByRole("button", { name: "Review retained work" })
          .click();
        await page
          .getByRole("button", { name: "Resume move", exact: true })
          .click();
        assert.equal(
          await page.locator("#service").inputValue(),
          "Protected executive voice",
        );
        await goto(page, "view=call");
        await page.getByLabel("Shift minutes", { exact: true }).fill("5");
        await capture(page, "v2-call-reschedule-" + size);
        assertions.push(
          size +
            ": valid applied-only action without gate; preview draft retained through Operations/tray; reschedule controls",
        );
        if (width !== 1920) {
          for (const view of ["transport", "call"]) {
            await goto(page, "view=" + view + "&keyboard=1");
            const field =
              view === "transport"
                ? page.locator("#service")
                : page.locator(".fields input").first();
            const draft =
              "Executive coordination with long participant and service name";
            await field.fill(draft);
            await field.focus();
            await page.evaluate(() => window.injectLiveUpdate());
            assert.equal(await field.inputValue(), draft);
            assert.equal(
              await field.evaluate((el) => document.activeElement === el),
              true,
            );
            assert.equal(
              await visibleInApp(page, "#save-action"),
              true,
              "Save above simulated keyboard",
            );
            assert.equal(
              await visibleInApp(page, '.save-footer [data-view="ops"]'),
              true,
              "Keep draft above simulated keyboard",
            );
            assert.equal(
              await page.locator("#connected-count").textContent(),
              "4 reported connected",
            );
            assert.match(
              await page.locator(".awareness .next").textContent(),
              /14:35/,
            );
            await capture(page, "v2-keyboard-" + view + "-" + size);
            if (view === "transport") {
              assert.equal(
                await page.locator("#save-action").isEnabled(),
                true,
              );
              await field.fill("");
              await page.locator("#save-action").click();
              assert.equal(await field.getAttribute("aria-invalid"), "true");
              assert.equal(
                await field.evaluate((el) => document.activeElement === el),
                true,
              );
              await capture(page, "v2-keyboard-validation-" + size);
            }
            assertions.push(
              size +
                ": " +
                view +
                " simulated keyboard, live update preserves focus/input, Next and actions retained",
            );
          }
        }
        if (width === 1920) {
          for (const view of ["planned", "unavailable", "drafts"]) {
            await goto(page, "view=" + view);
            await capture(page, "v2-" + view + "-" + size);
          }
        }
      } finally {
        await context.close();
      }
    }
    assert.deepEqual(scriptErrors, []);
    ownership.assertions = assertions;
  } catch (e) {
    failure = e.stack;
    process.exitCode = 1;
  } finally {
    await cleanup();
    fs.writeFileSync(
      reportPath,
      JSON.stringify(
        {
          ...ownership,
          finished: new Date().toISOString(),
          browserClosed: true,
          results,
          scriptErrors,
          failure: failure ?? null,
        },
        null,
        2,
      ),
    );
  }
  if (failure) process.stderr.write(failure + "\n");
  else
    process.stdout.write(
      JSON.stringify({
        captures: results.length,
        assertions: ownership.assertions.length,
        scriptErrors: 0,
        browserClosed: true,
      }) + "\n",
    );
})();
