import { createHash } from 'node:crypto';
import { within } from './render-budget.mjs';
export async function renderMapInContext({ owner, budget, input, fault }) {
  let context;
  const warnings = [];
  try {
    budget.mapRemainingMs();
    if (!input || fault === 'map') throw new Error('Map unavailable');
    context = await owner.newContext({
      viewport: { width: 1920, height: 1080 },
      deviceScaleFactor: 1,
      locale: 'en-US',
      timezoneId: 'UTC',
      reducedMotion: 'reduce',
    });
    await context.route('**/*', (route) => {
      const url = new URL(route.request().url());
      return url.origin === owner.origin
        ? route.continue()
        : route.abort('blockedbyclient');
    });
    const page = await context.newPage();
    let sceneError;
    page.on('pageerror', (e) => {
      sceneError = String(e);
    });
    if (fault === 'map-hang')
      await within(new Promise(() => {}), budget.mapRemainingMs());
    await page.goto(`${owner.origin}/mission-export.html`, {
      waitUntil: 'domcontentloaded',
      timeout: budget.mapRemainingMs(),
    });
    await page.waitForFunction(() => !!window.missionMap, undefined, {
      timeout: budget.mapRemainingMs(),
    });
    const plan = await within(
      page.evaluate((raw) => window.missionMap.plan(raw), input),
      budget.mapRemainingMs()
    );
    if (plan.length !== 1)
      throw new Error('Checkpoint needs one complete map view');
    const digest = createHash('sha256')
      .update(JSON.stringify(input))
      .digest('hex');
    await within(
      page.evaluate(
        ({ input, digest }) => window.missionMap.render(input, 0, digest),
        { input, digest }
      ),
      budget.mapRemainingMs()
    );
    await page.waitForFunction(
      () => window.missionMap.state.status !== 'loading',
      undefined,
      { timeout: budget.mapRemainingMs() }
    );
    const readiness = await page.evaluate(() => window.missionMap.state);
    if (
      sceneError ||
      readiness.status !== 'ready' ||
      readiness.digest !== digest ||
      readiness.viewId !== plan[0].id
    )
      throw new Error(
        sceneError || readiness.error || 'Map readiness identity mismatch'
      );
    await page.waitForFunction(
      () =>
        document.querySelectorAll('[data-map-label]').length ===
        window.missionMap.state.labels.length,
      undefined,
      { timeout: budget.mapRemainingMs() }
    );
    const png = await page.screenshot({
      type: 'png',
      animations: 'disabled',
      timeout: budget.mapRemainingMs(),
    });
    return {
      status: 'primary',
      pngs: [`data:image/png;base64,${png.toString('base64')}`],
      viewIds: plan.map((v) => v.id),
      warnings,
      framing: readiness.framing,
      markers: readiness.labels,
      inputDigest: digest,
      pngHash: createHash('sha256').update(png).digest('hex'),
    };
  } catch (error) {
    warnings.push(
      error.code === 'deadline' ? 'Map reserve cutoff' : String(error)
    );
    return {
      status: 'unavailable',
      pngs: [],
      viewIds: [],
      warnings,
      framing: null,
      markers: [],
    };
  } finally {
    if (context) await context.close();
  }
}
