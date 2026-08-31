import type { Page } from '@playwright/test';

import { assertRetainedRenderSample } from './overview-cdp-assertions';
import { installLifecycleObserver } from './overview-lifecycle-observer';
import type { OverviewRouter } from './overview-router';

export async function observeRetainedTransition(
  page: Page,
  router: OverviewRouter,
  run: () => Promise<void>
) {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      )
  );
  const observer = await installLifecycleObserver(page);
  router.setLifecycleReporter(observer.report);
  await run();
  await page.waitForTimeout(75);
  router.setLifecycleReporter(null);
  const ledger = await observer.stop();
  const baseline = ledger.samples.find((sample) => sample.phase === 'baseline');
  if (!baseline) throw new Error('Missing transition lifecycle baseline');
  const retained = ledger.samples.filter((sample) =>
    ['baseline', 'request-start', 'pending'].includes(sample.phase)
  );
  for (const sample of retained) assertRetainedRenderSample(sample, baseline);
}
