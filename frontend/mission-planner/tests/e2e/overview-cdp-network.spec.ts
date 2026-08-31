import { expect, test } from '@playwright/test';

import { startCdpNetworkCapture } from './support/overview-cdp-capture';

test.describe('Operations overview CDP network capture', () => {
  test('records browser terminal success and failure events', async ({
    page,
  }) => {
    await page.goto('/');
    await page.route('**/cdp-network-success', (route) =>
      route.fulfill({ status: 200, body: 'ok' })
    );
    await page.route('**/cdp-network-failure', (route) =>
      route.abort('failed')
    );
    const capture = await startCdpNetworkCapture(page, async () => undefined);

    await page.evaluate(async () => {
      await fetch('/cdp-network-success');
      await fetch('/cdp-network-failure').catch(() => undefined);
    });
    await page.waitForTimeout(100);
    await capture.stop();

    const success = capture
      .records()
      .find((record) => record.url.endsWith('/cdp-network-success'));
    const failure = capture
      .records()
      .find((record) => record.url.endsWith('/cdp-network-failure'));
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
});
