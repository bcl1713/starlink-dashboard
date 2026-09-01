import { expect, test } from '@playwright/test';

import { openOverview } from './support/overview-assertions';
import {
  captureCdpContinuity,
  installElementIdentity,
} from './support/overview-cdp-capture';
import { startCdpNetworkCapture } from './support/overview-cdp-network';
import { installOverviewRouter } from './support/overview-router';

test.describe('Operations overview CDP network capture', () => {
  test('records browser terminal success and failure events', async ({
    page,
  }) => {
    await page.goto('/');
    await page.route('**/api/cdp-network-success**', (route) =>
      route.fulfill({ status: 200, body: 'ok' })
    );
    await page.route('**/api/cdp-network-failure', (route) =>
      route.abort('failed')
    );
    const capture = await startCdpNetworkCapture(page, async () => undefined);

    await page.evaluate(async () => {
      await fetch('/api/cdp-network-success?secret=not-retained');
      await fetch('/api/cdp-network-failure').catch(() => undefined);
    });
    await page.waitForTimeout(100);
    await capture.stop();

    const success = capture
      .records()
      .find((record) => record.url.endsWith('/api/cdp-network-success'));
    const failure = capture
      .records()
      .find((record) => record.url.endsWith('/api/cdp-network-failure'));
    expect(success).toMatchObject({
      method: 'GET',
      terminalOutcome: 'finished',
      status: 200,
    });
    expect(success?.terminalTimestamp).toBeGreaterThanOrEqual(
      success?.requestTimestamp ?? Number.POSITIVE_INFINITY
    );
    expect(failure).toMatchObject({
      method: 'GET',
      terminalOutcome: 'failed',
    });
    expect(failure?.failureText).toBeTruthy();
    expect(success?.url).toBe('/api/cdp-network-success');
    expect(JSON.stringify(capture.records())).not.toContain('not-retained');
    expect(capture.retention()).toMatchObject({ status: 'complete' });
    const eventNames = new Set(capture.events().map((event) => event.name));
    expect(eventNames).toEqual(
      new Set([
        'Network.requestWillBeSent',
        'Network.responseReceived',
        'Network.loadingFinished',
        'Network.loadingFailed',
      ])
    );
  });

  test('detaches after observer rejection and makes teardown idempotent', async ({
    page,
  }) => {
    await page.goto('/');
    await page.route('**/api/cdp-rejection', (route) =>
      route.fulfill({ status: 200, body: 'ok' })
    );
    const capture = await startCdpNetworkCapture(page, async () => {
      throw new Error('observer rejected');
    });

    await page.evaluate(() => fetch('/api/cdp-rejection'));
    await expect(capture.stop()).rejects.toThrow('observer rejected');
    await expect(capture.stop()).rejects.toThrow('observer rejected');

    const verification = await page.context().newCDPSession(page);
    await verification.detach();
  });

  test('settles integrated observer cleanup after rejection before a clean capture', async ({
    page,
  }, testInfo) => {
    const listenerCount = page as typeof page & {
      listenerCount(event: string): number;
    };
    const consoleListeners = listenerCount.listenerCount('console');
    const pageErrorListeners = listenerCount.listenerCount('pageerror');
    const router = await installOverviewRouter(page);
    await installElementIdentity(page);
    await openOverview(page);

    await expect(
      captureCdpContinuity(page, router, testInfo, 'rejected', {
        observeCdp: (observe) => async (record) => {
          await observe(record);
          throw new Error('integrated observer rejected');
        },
      })
    ).rejects.toThrow('integrated observer rejected');

    await expect
      .poll(() =>
        page.evaluate(() =>
          Boolean(
            (window as typeof window & { __overviewLifecycle?: unknown })
              .__overviewLifecycle
          )
        )
      )
      .toBe(false);
    expect(listenerCount.listenerCount('console')).toBe(consoleListeners);
    expect(listenerCount.listenerCount('pageerror')).toBe(pageErrorListeners);
    const verification = await page.context().newCDPSession(page);
    await verification.detach();

    const clean = await captureCdpContinuity(page, router, testInfo, 'clean');
    expect(clean.eventLedger.consoleErrors).toEqual([]);
    expect(clean.eventLedger.pageErrors).toEqual([]);
    expect(clean.cdpRetention.status).toBe('complete');
  });
});
