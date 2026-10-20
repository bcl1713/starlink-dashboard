import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import {
  control,
  evidence,
  noOverflow,
  origin,
} from './operator-journal-helpers';

test('synthetic Operator shell at desktop, portrait and landscape with failure/restart recovery', async ({
  browser,
}) => {
  const proof: Record<string, unknown> = {
    synthetic: true,
    clock: '2026-10-17T16:00:00Z',
    captures: [],
    requirementOrdering: {
      future: 'Synthetic customer coordination',
      overdueAttention: 'Synthetic overdue coordination',
      bothVisibleAtAllViewports: true,
    },
  };
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
    { width: 844, height: 390 },
  ]) {
    const context = await browser.newContext({
      viewport,
      hasTouch: viewport.width !== 1920,
      isMobile: viewport.width !== 1920,
      timezoneId: 'Pacific/Honolulu',
    });
    try {
      await context.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin ||
        route.request().url().startsWith('data:')
          ? route.continue()
          : route.abort()
      );
      const page = await context.newPage();
      const errors: string[] = [];
      page.on('pageerror', (e) => errors.push(e.message));
      for (const scope of ['preflight', 'leg', 'between-legs']) {
        await page.goto(
          `${origin}/operator?mission_id=synthetic-shell-${scope}`
        );
        await expect(
          page.getByRole('heading', { name: 'Operator', exact: true })
        ).toBeVisible();
        await expect(
          page
            .getByRole('region', { name: 'Next requirement', exact: true })
            .getByText('Synthetic customer coordination', { exact: true })
        ).toBeVisible();
        await expect(
          page.getByText('Synthetic transition advisory', { exact: true })
        ).toBeVisible();
        await expect(
          page
            .getByRole('region', { name: 'Mission workspace', exact: true })
            .getByText('Synthetic audio follow-up', { exact: true })
        ).toBeVisible();
        await expect(page.getByText(/Latest recorded context:/)).toContainText(
          scope.replaceAll('-', ' ')
        );
        await expect(
          page.getByText(/Snapshot.*2026-10-17 16:00:00 UTC/)
        ).toBeVisible();
        const attention = page.getByRole('region', {
          name: 'Attention needed',
          exact: true,
        });
        await expect(
          attention.getByText('Synthetic overdue coordination', { exact: true })
        ).toBeVisible();
        await expect(
          attention.getByText('Past planned start · still scheduled.', {
            exact: true,
          })
        ).toBeVisible();
        await expect(
          page
            .getByRole('region', { name: 'Next requirement', exact: true })
            .getByText('Synthetic overdue coordination', { exact: true })
        ).toHaveCount(0);
        await noOverflow(page);
        const name = `shell-${viewport.width}x${viewport.height}-${scope}.png`;
        await page.screenshot({ path: join(evidence, name), fullPage: true });
        (proof.captures as string[]).push(name);
      }
      const quick = page.getByRole('button', {
        name: 'Record observation',
        exact: true,
      });
      await quick.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByLabel('Title', { exact: true })).toBeFocused();
      await page
        .getByLabel('Title', { exact: true })
        .fill('Synthetic retained shell draft');
      await expect(quick).toBeDisabled();
      await page
        .getByRole('link', { name: 'Display tools', exact: true })
        .click();
      await expect(
        page.getByRole('link', { name: 'Display settings', exact: true })
      ).toBeVisible();
      await expect(
        page.getByRole('link', { name: 'Display settings', exact: true })
      ).toHaveAttribute('href', '/configuration');
      await page
        .getByRole('button', { name: 'Refresh summary', exact: true })
        .click();
      await expect(page.getByLabel('Title', { exact: true })).toHaveValue(
        'Synthetic retained shell draft'
      );
      await page.goto(`${origin}/operator`);
      await expect(
        page.getByRole('heading', { name: 'Choose a mission' })
      ).toBeVisible();
      await expect(
        page.getByRole('link', { name: 'Browse missions' })
      ).toHaveAttribute('href', '/missions');
      await noOverflow(page);
      await page.screenshot({
        path: join(
          evidence,
          `shell-${viewport.width}x${viewport.height}-empty.png`
        ),
        fullPage: true,
      });
      if (viewport.width === 1920) {
        await page.goto(
          `${origin}/operator?mission_id=synthetic-shell-preflight`
        );
        await expect(
          page
            .getByRole('region', { name: 'Next requirement', exact: true })
            .getByText('Synthetic customer coordination', { exact: true })
        ).toBeVisible();
        let reads = 0;
        page.on('request', (r) => {
          if (r.url().includes('/operator/records') && r.method() === 'GET')
            reads++;
        });
        await page.waitForTimeout(16000); // Cross the existing health cadence: summaries must not poll.
        expect(reads).toBe(0);
        const idleReads = reads;
        const block =
          '**/api/v2/operator/records?mission_id=synthetic-shell-preflight';
        await page.route(block, (route) => route.abort());
        await page.getByRole('button', { name: 'Refresh summary' }).click();
        await expect(
          page.getByText(/Summary unavailable/).first()
        ).toBeVisible();
        await page.screenshot({
          path: join(evidence, 'shell-summary-unavailable.png'),
          fullPage: true,
        });
        await page.unroute(block);
        await page.getByRole('button', { name: 'Refresh summary' }).click();
        await expect(
          page
            .getByRole('region', { name: 'Next requirement', exact: true })
            .getByText('Synthetic customer coordination', { exact: true })
        ).toBeVisible();
        const before = await (
          await page.request.get(
            `${origin}/api/v2/operator/records?mission_id=synthetic-shell-preflight`
          )
        ).json();
        control('restart');
        await expect
          .poll(
            async () =>
              (
                await page.request.get(`${origin}/api/v2/operator/health`)
              ).status(),
            { timeout: 30000 }
          )
          .toBe(200);
        await page.reload();
        await expect(
          page
            .getByRole('region', { name: 'Next requirement', exact: true })
            .getByText('Synthetic customer coordination', { exact: true })
        ).toBeVisible();
        const after = await (
          await page.request.get(
            `${origin}/api/v2/operator/records?mission_id=synthetic-shell-preflight`
          )
        ).json();
        expect(
          after.items.map(
            (i: { record: { record_id: string; version: number } }) => [
              i.record.record_id,
              i.record.version,
            ]
          )
        ).toEqual(
          before.items.map(
            (i: { record: { record_id: string; version: number } }) => [
              i.record.record_id,
              i.record.version,
            ]
          )
        );
        proof.recovery = {
          failedReadVisible: true,
          reconnect: true,
          restart: true,
          unchangedRecords: after.items.length,
          summaryRequestsOver16Seconds: idleReads,
        };
      }
      expect(errors).toEqual([]);
    } finally {
      await context.close();
    }
  }
  writeFileSync(
    join(evidence, 'shell-proof.json'),
    JSON.stringify(proof, null, 2)
  );
});
