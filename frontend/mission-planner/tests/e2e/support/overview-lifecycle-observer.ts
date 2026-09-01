import type { Page } from '@playwright/test';

import { collectBrowserErrors } from './overview-browser-errors';
import { installBrowserLifecycleObserver } from './overview-lifecycle-browser-observer';
import { EVIDENCE_LIMITS } from './overview-evidence-limits';
import {
  LIFECYCLE_LAYER_PANES,
  LIFECYCLE_OWNERSHIP_SELECTOR,
} from './overview-lifecycle-contract';
import {
  NOMINAL_CHART_SERIES_COUNTS,
  NOMINAL_FEATURE_COUNTS,
} from './overview-nominal-layer-contract';
import type {
  CdpNetworkRecord,
  LedgerWindow,
  LifecycleLedger,
} from './overview-lifecycle-types';

export async function installLifecycleObserver(page: Page) {
  const { consoleErrors, pageErrors, dispose } = collectBrowserErrors(page);
  await page.evaluate(installBrowserLifecycleObserver, {
    chartSeriesCounts: NOMINAL_CHART_SERIES_COUNTS,
    featureCounts: NOMINAL_FEATURE_COUNTS,
    panes: LIFECYCLE_LAYER_PANES,
    ownershipSelector: LIFECYCLE_OWNERSHIP_SELECTOR,
    limits: EVIDENCE_LIMITS,
  });

  let stopped:
    | Promise<
        LifecycleLedger & { consoleErrors: string[]; pageErrors: string[] }
      >
    | undefined;
  return {
    observeCdp: (record: CdpNetworkRecord) =>
      page.evaluate((value) => {
        const lifecycle = (window as LedgerWindow).__overviewLifecycle;
        if (!lifecycle) throw new Error('Lifecycle observer was not installed');
        lifecycle.cdp(value);
      }, record),
    stop: () =>
      (stopped ??= page
        .evaluate(() => (window as LedgerWindow).__overviewLifecycle?.stop())
        .then((ledger) => {
          if (!ledger) throw new Error('Lifecycle observer was not installed');
          return { ...ledger, consoleErrors, pageErrors };
        })
        .finally(dispose)),
  };
}
