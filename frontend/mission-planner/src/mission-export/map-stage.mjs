import { createHash } from 'node:crypto';
import { within } from './render-budget.mjs';
export async function renderMapInContext({ owner, budget, input, fault }) {
  let context,
    result,
    finishing = false;
  const mapCall = (fn) => {
    const ms = budget.mapRemainingMs();
    return within(Promise.resolve().then(fn), ms);
  };
  const unavailable = () => ({
    status: 'unavailable',
    pngs: [],
    viewIds: [],
    warnings,
    framing: null,
    markers: [],
  });
  const warnings = [];
  try {
    budget.mapRemainingMs();
    if (!input || fault === 'map') throw new Error('Map unavailable');
    const acquisition = owner.newContext(
      {
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
        locale: 'en-US',
        timezoneId: 'UTC',
        reducedMotion: 'reduce',
      },
      { remainingMs: budget.mapRemainingMs }
    );
    acquisition.then(
      (created) => {
        context = created;
        if (finishing) void created.close().catch(() => {});
      },
      () => {}
    );
    context = await mapCall(() => acquisition);
    await mapCall(() =>
      context.route('**/*', (route) => {
        const url = new URL(route.request().url());
        return url.origin === owner.origin
          ? route.continue()
          : route.abort('blockedbyclient');
      })
    );
    if (fault === 'map-new-page-hang')
      context.newPage = () => new Promise(() => {});
    const page = await mapCall(() => context.newPage());
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
    const readiness = await mapCall(() =>
      page.evaluate(() => window.missionMap.state)
    );
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
    result = {
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
    result = unavailable();
  } finally {
    finishing = true;
    if (context) {
      let remaining = 1;
      try {
        remaining = budget.mapRemainingMs();
      } catch {}
      try {
        await within(context.close(), remaining);
      } catch {
        warnings.push(
          'Map context disposal reached reserve cutoff; request owner retains cleanup'
        );
        result = unavailable();
      }
    }
  }
  return result;
}
