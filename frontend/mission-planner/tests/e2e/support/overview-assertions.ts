import { expect, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { OVERVIEW_CONTRACT } from '../fixtures/overview';
import type { OverviewRouter } from './overview-router';
import { installFixedBrowserTime } from './overview-time';

export const viewports = [
  { name: '1920x1080', width: 1920, height: 1080, mapHeight: 660 },
  { name: '1280x800', width: 1280, height: 800, mapHeight: 368 },
  { name: '1024x768', width: 1024, height: 768, mapHeight: 320 },
  { name: '768x1024', width: 768, height: 1024, mapHeight: 384 },
  { name: '390x844', width: 390, height: 844, mapHeight: 320 },
  { name: '320x568', width: 320, height: 568, mapHeight: 280 },
] as const;

export async function openOverview(
  page: Page,
  nowIso = '2026-02-03T15:30:00Z'
) {
  await page.addInitScript(() => {
    window.matchMedia = (query) => ({
      matches:
        query.includes('prefers-reduced-motion') ||
        (query.includes('min-width: 768px') && window.innerWidth >= 768),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => true,
    });
  });
  await installFixedBrowserTime(page, nowIso);
  await page.goto('/overview');
  await expect(
    page.getByRole('heading', { name: 'Operations Overview' })
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Current Position' })
  ).toHaveCount(1);
}

export async function expectCoreOverview(page: Page, router: OverviewRouter) {
  await expect(page.locator('main')).toHaveCount(1);
  await expect(page.getByText(/latency/i).first()).toBeVisible();
  await expect(page.getByText(/throughput/i).first()).toBeVisible();
  await expect(page.getByText(/packet loss/i).first()).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Ground Entry Point' })
  ).toBeVisible();
  await expect(page.getByText(/obstruction/i).first()).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'POI Quick Reference (Top 5)' })
  ).toBeVisible();
  await expect(page.locator('.overview-priority-summary')).toBeVisible();

  await openLayerDisclosure(page);
  for (const layer of OVERVIEW_CONTRACT.mapLayers) {
    await expect(
      page.getByRole('checkbox', { name: layer.concept, exact: true })
    ).toHaveCount(1);
  }
  await expect(
    page.getByRole('checkbox', { name: 'Weather Radar', exact: true })
  ).toHaveCount(1);
  expect(OVERVIEW_CONTRACT.panels).toHaveLength(11);
  expect(OVERVIEW_CONTRACT.mapLayers).toHaveLength(12);
  expect(router.records.filter((record) => record.event === 'failed')).toEqual(
    []
  );
}

async function openLayerDisclosure(page: Page) {
  await page.locator('details.operational-map__panel').evaluate((details) => {
    if (details instanceof HTMLDetailsElement) details.open = true;
  });
}

export async function expectNoGrafana(records: OverviewRouter['records']) {
  const grafana = records.filter((record) =>
    /grafana|:3000|datasources|plugins|dashboards|session/i.test(record.url)
  );
  expect(grafana).toEqual([]);
}

export async function expectSameOriginApi(page: Page) {
  const origin = new URL(page.url()).origin;
  const urls = await page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .map((entry) => entry.name)
      .filter((name) => name.includes('/api/'))
  );
  expect(urls.every((url) => url.startsWith(`${origin}/api/`))).toBe(true);
}

export async function expectViewportLayout(page: Page, mapHeight: number) {
  const metrics = await page.evaluate(() => {
    const root = document.documentElement;
    const map = document.querySelector('.overview-map-region');
    const buttons = [...document.querySelectorAll('button, select, input')];
    const visibleButtons = buttons.filter((button) => {
      const box = button.getBoundingClientRect();
      return box.width > 0 && box.height > 0;
    });
    return {
      overflow: root.scrollWidth - root.clientWidth,
      mapHeight: map?.getBoundingClientRect().height ?? 0,
      minTarget: Math.min(
        ...visibleButtons.map((button) => {
          const box = button.getBoundingClientRect();
          return Math.min(box.width, box.height);
        })
      ),
      scrollable: root.scrollHeight > root.clientHeight,
    };
  });
  expect(metrics.overflow).toBeLessThanOrEqual(1);
  expect(Math.round(metrics.mapHeight)).toBe(mapHeight);
  expect(metrics.minTarget).toBeGreaterThanOrEqual(44);
  expect(metrics.scrollable).toBe(true);
}

export async function attachScreenshots(
  page: Page,
  testInfo: TestInfo,
  name: string
) {
  const initial = await page.screenshot({ fullPage: false });
  await testInfo.attach(`${name}-initial`, {
    body: initial,
    contentType: 'image/png',
  });
  await writeArtifact(`${name}-initial.png`, initial);
  const fullPage = await page.screenshot({ fullPage: true });
  await testInfo.attach(`${name}-full-page`, {
    body: fullPage,
    contentType: 'image/png',
  });
  await writeArtifact(`${name}-full-page.png`, fullPage);
}

export async function expectAxe(page: Page, testInfo: TestInfo) {
  const results = await new AxeBuilder({ page })
    .disableRules(['color-contrast'])
    .analyze();
  const violations = results.violations.filter((violation) =>
    ['serious', 'critical'].includes(violation.impact ?? '')
  );
  await testInfo.attach('accessibility-coverage-gap', {
    body: [
      'Automated axe checks ran with serious/critical gating.',
      'Manual screen-reader smoke and true rendered contrast remain coverage gaps.',
    ].join('\n'),
    contentType: 'text/plain',
  });
  expect(violations).toEqual([]);
}

export async function writeArtifact(name: string, body: Buffer | string) {
  const dir = process.env.OVERVIEW_ARTIFACT_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, name), body);
}
