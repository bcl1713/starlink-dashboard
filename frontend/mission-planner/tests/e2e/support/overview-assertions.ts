import { expect, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

import { OVERVIEW_CONTRACT } from '../fixtures/overview';
import { writeOverviewArtifact } from './overview-artifacts';
import { nominalLayerSummaryPattern } from './overview-nominal-layer-contract';
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
    const nativeMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = (query) => {
      if (!query.includes('prefers-reduced-motion')) {
        return nativeMatchMedia(query);
      }
      return {
        matches: true,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => true,
      };
    };
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
  await expect(page.locator('.overview-page')).toHaveCount(1);
  await expect(
    page.getByRole('heading', { name: 'Operations Overview' })
  ).toHaveCount(1);
  for (const panel of OVERVIEW_CONTRACT.panels) {
    await expectPanelConcept(page, panel.concept);
  }
  await expect(page.locator('.overview-priority-summary')).toBeVisible();
  await expectClockContract(page);

  await openLayerDisclosure(page);
  await expect(page.getByRole('button', { name: 'Weather Radar' })).toHaveCount(
    0
  );
  await expect(
    page.getByRole('checkbox', { name: 'Weather Radar' })
  ).toHaveCount(1);
  const labels = await page
    .locator('.operational-map__layer-row input')
    .evaluateAll((inputs) =>
      inputs.map((input) => input.getAttribute('aria-label') ?? '')
    );
  expect(labels).toEqual(
    OVERVIEW_CONTRACT.mapLayers.map((layer) => layer.concept)
  );
  for (const [index, layer] of OVERVIEW_CONTRACT.mapLayers.entries()) {
    const checkbox = page.getByRole('checkbox', {
      name: layer.concept,
      exact: true,
    });
    await expect(checkbox).toHaveCount(1);
    await expect(checkbox).toBeChecked({ checked: layer.enabledByDefault });
    await expect(
      page.locator('.operational-map__layer-row').nth(index)
    ).toContainText(/Ready|Loading|last-good|Unavailable|error|stale/i);
    await expect(
      page.getByText(nominalLayerSummaryPattern(layer.concept, index))
    ).toBeVisible();
  }
  const satellites = page.getByRole('checkbox', { name: 'Satellites' });
  await satellites.focus();
  await page.keyboard.press('Space');
  await expect(
    page.getByRole('checkbox', { name: 'Satellites' })
  ).not.toBeChecked();
  await page.keyboard.press('Space');
  expect(router.records.filter((record) => record.event === 'failed')).toEqual(
    []
  );
}

async function expectPanelConcept(page: Page, concept: string) {
  if (concept.includes('clock')) {
    const clock = page.getByLabel(
      new RegExp(`^${escapeRegExp(concept.replace(' clock', ''))}:`)
    );
    if (
      concept.startsWith('UTC') ||
      (page.viewportSize()?.width ?? 1280) >= 1024
    ) {
      await expect(clock).toBeVisible();
    } else {
      await expect(clock).toHaveCount(1);
    }
    return;
  }
  if (concept.includes('map')) {
    await expect(page.locator('.overview-map-region')).toBeVisible();
    return;
  }
  const name = concept.replace(
    ' (top five applicable future POIs)',
    ' (Top 5)'
  );
  await expect(page.getByRole('heading', { name })).toBeVisible();
}

async function expectClockContract(page: Page) {
  const clockLabels = await page
    .locator('.overview-world-clocks time')
    .evaluateAll((times) =>
      times.flatMap((time) => {
        const box = time.getBoundingClientRect();
        return box.width > 0 && box.height > 0
          ? [time.getAttribute('aria-label') ?? '']
          : [];
      })
    );
  expect(clockLabels[0]).toMatch(/^UTC \(Zulu\):/);
  const width = page.viewportSize()?.width ?? 1280;
  if (width >= 1024) {
    expect(clockLabels).toHaveLength(4);
    await expect(
      page.getByRole('button', { name: 'Additional clocks' })
    ).toBeHidden();
  } else {
    expect(clockLabels).toHaveLength(1);
    await expect(
      page.getByRole('button', { name: 'Additional clocks' })
    ).toBeVisible();
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
      bodyOverflow: document.body.scrollWidth - document.body.clientWidth,
      mapHeight: map?.getBoundingClientRect().height ?? 0,
      minTarget: Math.min(
        ...visibleButtons.map((button) => {
          const box = button.getBoundingClientRect();
          return Math.min(box.width, box.height);
        })
      ),
      scrollable: root.scrollHeight > root.clientHeight,
      headings: [...document.querySelectorAll('h1,h2,h3')]
        .map((heading) => heading.textContent?.trim() ?? '')
        .filter(Boolean)
        .slice(0, 8),
      tableContained: [...document.querySelectorAll('table')].every((table) => {
        const parentBox = table.parentElement?.getBoundingClientRect();
        const regionBox = table
          .closest('.overview-poi-region')
          ?.getBoundingClientRect();
        return (
          !parentBox || !regionBox || parentBox.width <= regionBox.width + 1
        );
      }),
    };
  });
  expect(metrics.overflow).toBeLessThanOrEqual(1);
  expect(metrics.bodyOverflow).toBeLessThanOrEqual(1);
  expect(Math.round(metrics.mapHeight)).toBe(mapHeight);
  expect(metrics.minTarget).toBeGreaterThanOrEqual(44);
  expect(metrics.scrollable).toBe(true);
  expect(metrics.tableContained).toBe(true);
  expect(metrics.headings[0]).toBe('Operations Overview');
  await page.mouse.wheel(0, 300);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(0);
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
  await writeOverviewArtifact(`${name}-initial.png`, initial);
  const fullPage = await page.screenshot({ fullPage: true });
  await testInfo.attach(`${name}-full-page`, {
    body: fullPage,
    contentType: 'image/png',
  });
  await writeOverviewArtifact(`${name}-full-page.png`, fullPage);
}

export async function attachResponsiveScreenshots(
  page: Page,
  testInfo: TestInfo,
  name: string
) {
  const initial = await page.screenshot({ fullPage: false });
  await testInfo.attach(`${name}-initial`, {
    body: initial,
    contentType: 'image/png',
  });
  await writeOverviewArtifact(`${name}-initial.png`, initial);
  await page
    .locator('summary', { hasText: 'Operational layers' })
    .scrollIntoViewIfNeeded();
  await openLayerDisclosure(page);
  const opened = await page.screenshot({ fullPage: false });
  await testInfo.attach(`${name}-opened`, {
    body: opened,
    contentType: 'image/png',
  });
  await writeOverviewArtifact(`${name}-opened.png`, opened);
  const fullPage = await page.screenshot({ fullPage: true });
  await testInfo.attach(`${name}-full-page`, {
    body: fullPage,
    contentType: 'image/png',
  });
  await writeOverviewArtifact(`${name}-full-page.png`, fullPage);
}

export async function expectAxe(page: Page, testInfo: TestInfo) {
  const results = await new AxeBuilder({ page })
    .include('.overview-page')
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
