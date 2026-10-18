const { chromium } = require(
  require.resolve("@playwright/test", { paths: [process.cwd()] }),
);
const fs = require("node:fs");
const path = require("node:path");
const root = __dirname;
const ownership = {
  task: "issue-376-design",
  pid: process.pid,
  processGroup: require("node:child_process")
    .execFileSync("ps", ["-o", "pgid=", "-p", String(process.pid)], {
      encoding: "utf8",
    })
    .trim(),
  command:
    "timeout --kill-after=10s 2m node <worktree>/docs/design/issue-376/capture.cjs",
  temporaryPaths: [],
  servers: [],
  containers: [],
  volumes: [],
  started: new Date().toISOString(),
};
fs.writeFileSync(
  path.join(root, "preview-check.json"),
  JSON.stringify(ownership, null, 2),
);
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
(async () => {
  try {
    browser = await chromium.launch({ headless: true });
    const results = [];
    for (const [w, h] of [
      [1920, 1080],
      [390, 844],
      [844, 390],
    ]) {
      const context = await browser.newContext({
        viewport: { width: w, height: h },
        deviceScaleFactor: 1,
      });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      for (const state of ["normal", "busy", "failure"]) {
        await page.goto("file://" + root + "/mockups.html?state=" + state);
        await page.screenshot({
          path: root + "/" + state + "-" + w + "x" + h + ".png",
        });
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        );
        results.push({ state, w, h, overflow, errors: [...errors] });
        if (overflow || errors.length)
          throw Error(JSON.stringify(results.at(-1)));
      }
      for (const editor of [
        "call",
        "transport",
        "followup",
        "note",
        "display",
      ]) {
        await page.goto(
          "file://" + root + "/mockups.html?state=busy&editor=" + editor,
        );
        await page.screenshot({
          path: root + "/" + editor + "-" + w + "x" + h + ".png",
        });
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        );
        results.push({ editor, w, h, overflow, errors: [...errors] });
        if (overflow || errors.length)
          throw Error(JSON.stringify(results.at(-1)));
      }
      await page.getByRole("button", { name: "Close editor preview" }).click();
      await page.getByRole("button", { name: "More ▾" }).click();
      await page
        .getByRole("button", { name: "History & observations" })
        .click();
      await page
        .getByRole("heading", { name: "Mission records and observations" })
        .waitFor();
      await context.close();
    }
    await cleanup();
    fs.writeFileSync(
      path.join(root, "preview-check.json"),
      JSON.stringify(
        {
          ...ownership,
          finished: new Date().toISOString(),
          browserClosed: true,
          results,
        },
        null,
        2,
      ),
    );
    process.stdout.write(
      JSON.stringify({
        captures: results.length,
        overflowFailures: 0,
        scriptErrors: 0,
        browserClosed: true,
      }) + "\n",
    );
  } catch (e) {
    await cleanup();
    process.stderr.write(e.stack + "\n");
    process.exitCode = 1;
  }
})();
