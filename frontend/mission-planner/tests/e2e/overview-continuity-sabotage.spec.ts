import { expect, test, type Page } from '@playwright/test';

import { openOverview } from './support/overview-assertions';
import { assertContinuityEvidence } from './support/overview-cdp-assertions';
import { installElementIdentity } from './support/overview-cdp-capture';
import { installLifecycleObserver } from './support/overview-lifecycle-observer';
import type {
  CdpNetworkRecord,
  LifecycleLedger,
} from './support/overview-lifecycle-types';
import { installOverviewRouter } from './support/overview-router';

test.describe('Operations overview continuity sabotage detection', () => {
  test.describe.configure({ mode: 'serial' });

  for (const probe of [
    ['removal', /critical removals/i],
    ['pane-replacement', /critical removals|Object identity changed/i],
    ['path-replacement', /Rendered count regressed/i],
    ['tile-replacement', /Rendered count regressed/i],
    ['chart-replacement', /critical removals|Chart ownership/i],
    ['busy', /render-observable attribute aria-busy=true/i],
    ['zero-size', /Missing or empty summary/i],
    ['loading', /last-good signature regressed/i],
    ['layer-drop', /Rendered count regressed/i],
    ['focus', /Operator state changed/i],
    ['filter', /Operator state changed/i],
    ['disclosure', /Operator state changed/i],
    ['scroll', /Operator state changed/i],
  ] as const) {
    test(`rejects a real transient ${probe[0]} on the production page`, async ({
      page,
    }) => {
      await installOverviewRouter(page);
      await installElementIdentity(page);
      await openOverview(page);
      await openLayerDisclosure(page);
      await page.getByRole('button', { name: 'Overview controls' }).click();
      await page.getByRole('button', { name: 'Refresh overview' }).focus();
      const observer = await installLifecycleObserver(page);
      const started = request();
      await observer.observeCdp(started);

      await runSabotage(page, probe[0]);
      await observer.observeCdp({
        ...started,
        terminalOutcome: 'finished',
        terminalTimestamp: 2,
      });
      const ledger = await observer.stop();

      expect(() => assertContinuityEvidence(evidence(ledger))).toThrow(
        probe[1]
      );
    });
  }

  test('retains complete attribute mutation details with request context', async ({
    page,
  }) => {
    await installOverviewRouter(page);
    await installElementIdentity(page);
    await openOverview(page);
    const observer = await installLifecycleObserver(page);
    const started = request();
    await observer.observeCdp(started);

    await page.locator('.overview-map-region').evaluate((element) => {
      element.setAttribute('aria-busy', 'true');
      element.setAttribute('aria-busy', 'false');
    });
    await observer.observeCdp({
      ...started,
      terminalOutcome: 'finished',
      terminalTimestamp: 2,
    });

    const ledger = await observer.stop();
    const attributes = ledger.mutations.filter(
      (mutation) => mutation.type === 'attributes'
    ) as readonly ((typeof ledger.mutations)[number] & {
      readonly attributeName?: string | null;
      readonly oldValue?: string | null;
      readonly newValue?: string | null;
    })[];
    const busy = attributes.filter(
      (mutation) => mutation.attributeName === 'aria-busy'
    );
    expect(busy.length).toBeGreaterThan(0);
    expect(busy.some((mutation) => mutation.oldValue === null)).toBe(true);
    expect(busy.some((mutation) => mutation.newValue === 'false')).toBe(true);
    expect(busy.every((mutation) => mutation.activeRequestIds.length > 0)).toBe(
      true
    );
  });
});

type Sabotage =
  | 'removal'
  | 'pane-replacement'
  | 'path-replacement'
  | 'tile-replacement'
  | 'chart-replacement'
  | 'busy'
  | 'zero-size'
  | 'loading'
  | 'layer-drop'
  | 'focus'
  | 'filter'
  | 'disclosure'
  | 'scroll';

async function runSabotage(page: Page, kind: Sabotage) {
  await page.evaluate(async (probe) => {
    const mutationTurn = () =>
      new Promise<void>((resolve) => queueMicrotask(resolve));
    const replaceTemporarily = async (target: Element | null) => {
      if (!target?.parentNode) throw new Error(`Missing ${probe} target`);
      const parent = target.parentNode;
      const next = target.nextSibling;
      const clone = target.cloneNode(true);
      parent.replaceChild(clone, target);
      await mutationTurn();
      parent.insertBefore(target, next);
      parent.removeChild(clone);
      await mutationTurn();
    };
    const summary = document.querySelector<HTMLElement>(
      '.overview-summary-region'
    );
    if (probe === 'removal') {
      const target = document.querySelector('.overview-map-region');
      if (!target?.parentNode) throw new Error('Missing map region');
      const parent = target.parentNode;
      const next = target.nextSibling;
      target.remove();
      await mutationTurn();
      parent.insertBefore(target, next);
      return;
    }
    if (probe === 'pane-replacement') {
      return replaceTemporarily(
        document.querySelector('.leaflet-planned-route-west-pane')
      );
    }
    if (probe === 'path-replacement') {
      return replaceTemporarily(
        document.querySelector('.leaflet-planned-route-west-pane path')
      );
    }
    if (probe === 'tile-replacement') {
      return replaceTemporarily(
        document.querySelector('.leaflet-weather-radar-pane img')
      );
    }
    if (probe === 'chart-replacement') {
      return replaceTemporarily(document.querySelector('canvas'));
    }
    if (probe === 'busy') {
      const target = document.querySelector('.overview-map-region');
      target?.setAttribute('aria-busy', 'true');
      await mutationTurn();
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve())
      );
      target?.setAttribute('aria-busy', 'false');
      await mutationTurn();
      return;
    }
    if (probe === 'zero-size') {
      const old = summary?.getAttribute('style') ?? null;
      summary?.setAttribute('style', 'width:0;height:0;overflow:hidden');
      await mutationTurn();
      if (old === null) summary?.removeAttribute('style');
      else summary?.setAttribute('style', old);
      return;
    }
    if (probe === 'loading') {
      const leaf = summary?.querySelector('p');
      const old = leaf?.textContent ?? '';
      if (leaf) leaf.textContent = 'Loading';
      await mutationTurn();
      if (leaf) leaf.textContent = old;
      return;
    }
    if (probe === 'layer-drop') {
      const pane = document.querySelector('.leaflet-planned-route-west-pane');
      const retained = pane ? [...pane.childNodes] : [];
      pane?.replaceChildren();
      await mutationTurn();
      pane?.replaceChildren(...retained);
      return;
    }
    const root = document.querySelector<HTMLElement>('.overview-page');
    if (probe === 'focus') root?.focus();
    if (probe === 'filter') {
      const filter = document.querySelector<HTMLSelectElement>(
        '[aria-label="POI category"]'
      );
      if (filter) filter.value = 'alternate';
    }
    if (probe === 'disclosure') {
      document
        .querySelector<HTMLDetailsElement>('details.operational-map__panel')
        ?.removeAttribute('open');
    }
    if (probe === 'scroll') window.scrollTo(0, 40);
    root?.setAttribute('data-observer-turn', probe);
    await mutationTurn();
    root?.removeAttribute('data-observer-turn');
  }, kind);
}

function request() {
  return {
    cdpRequestId: 'sabotage-request',
    event: 'Network.requestWillBeSent',
    method: 'GET',
    url: 'http://localhost/api/status',
    type: 'Fetch',
    requestTimestamp: 1,
    responseTimestamp: null,
    terminalTimestamp: null,
    terminalOutcome: 'pending',
    status: null,
    failureText: null,
  } satisfies CdpNetworkRecord;
}

function evidence(ledger: LifecycleLedger) {
  return {
    eventLedger: ledger,
    frames: [
      {
        index: 0,
        startMs: 1,
        endMs: 2,
        gapMs: 0,
        sha256: 'fixture',
        metadata: {
          source: 'page-screenshot',
          viewport: { width: 1280, height: 800 },
        },
      },
    ],
    cdpNetworkLedger: [],
    cdpNetworkEvents: [],
    fixtureRequestLedger: [],
    cycles: [],
  };
}

async function openLayerDisclosure(page: import('@playwright/test').Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}
