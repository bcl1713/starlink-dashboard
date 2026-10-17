import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect, type Page } from '@playwright/test';
import {
  control,
  evidence,
  noOverflow,
  origin,
  ready,
} from './operator-journal-helpers';

async function openControls(page: Page) {
  await page.goto('/operator?mission_id=synthetic-shell-preflight');
  await page.getByRole('button', { name: 'Show display controls' }).click();
  await expect(
    page.getByRole('button', { name: 'Save current as Normal' })
  ).toBeEnabled();
}
async function settings(page: Page) {
  const response = await page.request.get('/api/overview-links/settings');
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('Operator display controls use shared server settings and same-browser acknowledged commands', async ({
  browser,
}) => {
  const proof: Record<string, unknown> = {
    synthetic: true,
    clock: '2026-10-17T16:00:00Z',
    captures: [],
  };
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    timezoneId: 'UTC',
  });
  const counterpart = await browser.newContext({
    viewport: { width: 390, height: 844 },
    timezoneId: 'UTC',
  });
  try {
    for (const client of [context, counterpart]) {
      await client.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin ||
        route.request().url().startsWith('data:')
          ? route.continue()
          : route.abort()
      );
    }
    const page = await context.newPage();
    const other = await counterpart.newPage();
    const overview = await context.newPage();
    const errors: string[] = [];
    for (const tab of [page, other, overview]) {
      tab.on('pageerror', (error) => errors.push(error.message));
      await tab.clock.install({ time: new Date('2026-10-17T16:00:00Z') });
    }
    await page.goto('/operator');
    expect(
      (
        await page.request.put('/api/overview-links/settings', {
          data: {
            starshield_link_enabled: true,
            x_band_link_enabled: true,
            legend_enabled: true,
          },
        })
      ).ok()
    ).toBeTruthy();
    await overview.goto('/overview');
    await openControls(page);
    await openControls(other);
    const display = page.getByLabel('Overview display', { exact: true });
    await expect(
      page.getByRole('button', { name: 'Recenter view' })
    ).toBeEnabled();
    await expect(
      other.getByRole('button', { name: 'Recenter view' })
    ).toBeDisabled();
    await page.getByRole('button', { name: 'Recenter view' }).click();
    await expect(page.getByText(/Recenter accepted/)).toBeVisible();
    proof.sameBrowserRecenterAcknowledged = true;
    proof.separateBrowserCannotRecenter = true;

    // Two independently cached clients change disjoint fields without loss.
    await Promise.all([
      page.getByRole('switch', { name: 'Starshield data link' }).click(),
      other.getByRole('switch', { name: 'X-band data link' }).click(),
    ]);
    await expect
      .poll(async () => {
        const state = await settings(page);
        return [state.starshield_link_enabled, state.x_band_link_enabled];
      })
      .toEqual([false, false]);
    await expect(
      other.getByRole('switch', { name: 'Starshield data link' })
    ).not.toBeChecked();
    proof.disjointConcurrentChanges = true;

    // A stale browser cannot silently overwrite a counterpart's change.
    const stale = await settings(page);
    await other.route('**/api/overview-links/settings', (route) =>
      route.request().method() === 'GET'
        ? route.fulfill({ json: stale })
        : route.continue()
    );
    await openControls(other);
    await page.getByRole('switch', { name: 'Starshield data link' }).click();
    await expect(
      page.getByRole('switch', { name: 'Starshield data link' })
    ).toBeChecked();
    await other.getByRole('switch', { name: 'Starshield data link' }).click();
    await expect(
      other.getByRole('alert').filter({ hasText: 'Settings changed' })
    ).toBeVisible();
    expect((await settings(page)).starshield_link_enabled).toBe(true);
    await other.unroute('**/api/overview-links/settings');
    proof.conflictRejected = true;

    await page.getByLabel('Overview history window').selectOption('900');
    await expect(page.getByText('Overview history window saved')).toBeVisible();
    await expect(other.getByLabel('Overview history window')).toHaveValue(
      '900'
    );
    proof.historySynced = true;

    for (const name of ['Normal', 'Communications', 'Weather']) {
      await page
        .getByRole('button', { name: `Save current as ${name}` })
        .click();
      await expect(
        page.getByText(`${name} preset saved`, { exact: true })
      ).toBeVisible();
    }
    const saved = await (
      await page.request.get('/api/overview-links/presets')
    ).json();
    expect(Object.keys(saved.normal.settings)).not.toContain('window_seconds');
    await page.getByRole('switch', { name: 'Starshield data link' }).click();
    await expect(
      page.getByRole('switch', { name: 'Starshield data link' })
    ).not.toBeChecked();
    await page.getByRole('button', { name: 'Apply Normal' }).click();
    await expect(
      page.getByText('Normal preset applied', { exact: true })
    ).toBeVisible();
    expect((await settings(page)).starshield_link_enabled).toBe(true);
    proof.presetRoundtrip = true;

    // Hold an actual server receipt to verify the UI waits for acknowledgment.
    let release!: () => void;
    let received!: () => void;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    const fetched = new Promise<void>((resolve) => {
      received = resolve;
    });
    await page.route('**/api/overview-links/presets/weather', async (route) => {
      const response = await route.fetch();
      received();
      await held;
      await route.fulfill({ response });
    });
    await page.getByRole('button', { name: 'Save current as Weather' }).click();
    try {
      await fetched;
      await expect(
        page.getByText('Waiting for server acknowledgment…')
      ).toBeVisible();
      await expect(
        page.getByText('Weather preset saved', { exact: true })
      ).toHaveCount(0);
    } finally {
      release();
    }
    await expect(
      page.getByText('Weather preset saved', { exact: true })
    ).toBeVisible();
    await page.unroute('**/api/overview-links/presets/weather');
    proof.receiptRequired = true;

    await page.route('**/api/overview-links/settings', (route) =>
      route.request().method() === 'PUT'
        ? route.abort('internetdisconnected')
        : route.continue()
    );
    await page.getByRole('switch', { name: 'Starshield data link' }).click();
    await expect(
      page
        .getByRole('alert')
        .filter({ hasText: 'Unable to save layer settings' })
    ).toBeVisible();
    expect((await settings(page)).starshield_link_enabled).toBe(true);
    await page.unroute('**/api/overview-links/settings');
    proof.offlineFailureDoesNotConfirm = true;

    // A discovered, deliberately silent synthetic window times out, then expires.
    await page.evaluate(() => {
      const channel = new BroadcastChannel('starlink-overview-display-v1');
      channel.postMessage({
        v: 1,
        type: 'presence',
        sender: 'synthetic-silent-display',
        seq: 1,
        target: null,
        label: 'Synthetic silent display',
        actions: ['recenter'],
      });
      channel.close();
    });
    await display.selectOption('synthetic-silent-display');
    await page.getByRole('button', { name: 'Recenter view' }).click();
    await expect(page.getByText(/Request timed out/)).toBeVisible();
    await page.screenshot({
      path: join(evidence, 'display-unacknowledged-1920x1080.png'),
      fullPage: true,
    });
    await expect(page.getByText(/Selected display disconnected/)).toBeVisible({
      timeout: 25_000,
    });
    await expect(
      page.getByRole('button', { name: 'Recenter view' })
    ).toBeDisabled();
    proof.unacknowledgedTimeoutAndStaleTarget = true;

    const beforeRestart = await (
      await page.request.get('/api/overview-links/presets')
    ).json();
    control('restart');
    await ready(page);
    await openControls(page);
    expect(
      await (await page.request.get('/api/overview-links/presets')).json()
    ).toEqual(beforeRestart);
    expect((await settings(page)).starshield_link_enabled).toBe(true);
    await expect(page.getByLabel('Overview history window')).toHaveValue('900');
    proof.restartPersistence = true;

    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
      { width: 844, height: 390 },
    ]) {
      await page.setViewportSize(viewport);
      await noOverflow(page);
      await page.locator('#display-tools').scrollIntoViewIfNeeded();
      const name = `display-controls-${viewport.width}x${viewport.height}.png`;
      await page.screenshot({ path: join(evidence, name), fullPage: true });
      (proof.captures as string[]).push(name);
    }
    await overview.screenshot({
      path: join(evidence, 'display-overview-1920x1080.png'),
    });
    expect(errors).toEqual([]);
    proof.browserErrors = errors;
    writeFileSync(
      join(evidence, 'displays-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    await counterpart.close();
    await context.close();
  }
});
