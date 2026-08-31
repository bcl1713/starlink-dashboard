import { expect, test } from '@playwright/test';

import { startCdpNetworkCapture } from './support/overview-cdp-network';

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
});
