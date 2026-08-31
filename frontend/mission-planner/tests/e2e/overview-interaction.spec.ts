import { expect, test, type Locator, type Page } from '@playwright/test';

import { openOverview, viewports } from './support/overview-assertions';
import { installOverviewRouter } from './support/overview-router';

test.describe('Operations overview interaction acceptance', () => {
  for (const viewport of viewports) {
    test(`keeps controls directly reachable at ${viewport.name}`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await installOverviewRouter(page);
      await openOverview(page);

      await expectReachable(page, 'Overview controls');
      await openControls(page);
      await expectReachable(page, 'Refresh overview');
      await expectTargetSizes(page);
      await expectLayerReach(page);
      await expectMapSummaryKeyboardScroll(page);
      await expectTableKeyboardScroll(page);
      await expectMapWheelBehavior(page, viewport.width < 768);
    });
  }

  test('supports real Tab traversal and computed reduced motion', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await installOverviewRouter(page);
    await openOverview(page);

    await tabTo(page, page.getByRole('link', { name: 'Skip to main content' }));
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    await tabTo(page, page.getByRole('button', { name: 'Toggle navigation' }));
    await page.keyboard.press('Enter');
    await tabTo(page, page.getByRole('link', { name: 'Overview' }));
    await tabTo(page, page.getByRole('button', { name: 'Overview controls' }));
    await expectFocusVisible(page);
    await page.keyboard.press('Enter');
    await tabTo(page, page.getByRole('button', { name: 'Refresh overview' }));
    await tabTo(page, page.getByRole('button', { name: 'Clock settings' }));
    await tabTo(page, page.getByRole('button', { name: 'Additional clocks' }));
    await expect(
      page.getByRole('button', { name: 'Additional clocks' })
    ).toBeFocused();
    await page.keyboard.press('Space');
    await expect(page.getByLabel(/^Tokyo:/)).toBeVisible();
    await tabTo(page, page.getByRole('button', { name: 'Enter fullscreen' }));
    await page.keyboard.press('Shift+Tab');
    await expectVisibleFocus(page);

    const reduced = await page.evaluate(() => {
      const root = document.querySelector('.overview-page');
      const values = [...(root?.querySelectorAll('*') ?? [])].map((element) => {
        const style = getComputedStyle(element);
        return {
          transition: style.transitionDuration,
          animation: style.animationDuration,
        };
      });
      return {
        media: matchMedia('(prefers-reduced-motion: reduce)').matches,
        scroll: getComputedStyle(document.body).scrollBehavior,
        values,
      };
    });
    expect(reduced.media).toBe(true);
    expect(reduced.scroll).toBe('auto');
    expect(
      reduced.values.filter((item) => !durationOk(item.transition))
    ).toEqual([]);
    expect(
      reduced.values.filter((item) => !durationOk(item.animation))
    ).toEqual([]);
  });
});

async function expectReachable(page: Page, name: string) {
  const button = page.getByRole('button', { name }).first();
  await button.scrollIntoViewIfNeeded();
  await expect(button).toBeVisible();
}

async function expectLayerReach(page: Page) {
  const disclosure = page.locator('summary', {
    hasText: 'Operational layers',
  });
  await disclosure.scrollIntoViewIfNeeded();
  await disclosure.click();
  await expect(
    page.getByRole('checkbox', { name: 'Current position' })
  ).toBeVisible();
}

async function expectMapSummaryKeyboardScroll(page: Page) {
  const summary = page.getByLabel('Map status and layer summary');
  await summary.scrollIntoViewIfNeeded();
  await summary.focus();
  const maximum = await summary.evaluate(
    (element) => element.scrollHeight - element.clientHeight
  );
  expect(maximum).toBeGreaterThan(0);
  await page.keyboard.press('End');
  await expect
    .poll(() => summary.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0);
  await page.keyboard.press('Tab');
  await expectVisibleFocus(page);
}

async function expectTableKeyboardScroll(page: Page) {
  const table = page.getByLabel('POI quick reference table scroll area');
  await table.scrollIntoViewIfNeeded();
  await table.focus();
  const before = await table.evaluate((element) => element.scrollLeft);
  await page.keyboard.press('End');
  await expect
    .poll(() => table.evaluate((element) => element.scrollLeft))
    .toBeGreaterThanOrEqual(before);
}

async function expectMapWheelBehavior(page: Page, mobile: boolean) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.locator('.overview-map-region').scrollIntoViewIfNeeded();
  await page.mouse.wheel(0, 240);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(0);
  if (!mobile) return;
  await page.getByRole('button', { name: 'Enable map interaction' }).click();
  await expect(
    page.getByRole('button', { name: 'Return to page scrolling' })
  ).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('button', { name: 'Enable map interaction' })
  ).toBeFocused();
}

async function expectTargetSizes(page: Page) {
  const small = await page.evaluate(() =>
    [...document.querySelectorAll('button,a,summary,[tabindex="0"]')]
      .filter((element) => {
        if (element.closest('.leaflet-control')) return false;
        const name =
          element.getAttribute('aria-label') ??
          element.textContent?.trim() ??
          '';
        if (!name) return false;
        const box = element.getBoundingClientRect();
        return box.width > 0 && box.height > 0;
      })
      .map((element) => {
        const box = element.getBoundingClientRect();
        return {
          text: element.textContent?.trim() ?? element.tagName,
          size: Math.min(box.width, box.height),
        };
      })
      .filter((item) => item.size < 44)
  );
  expect(small).toEqual([]);
}

async function openControls(page: Page) {
  const button = page.getByRole('button', { name: 'Overview controls' });
  if ((await button.getAttribute('aria-expanded')) !== 'true') {
    await button.click();
  }
}

async function tabTo(page: Page, target: Locator) {
  for (let index = 0; index < 80; index += 1) {
    await page.keyboard.press('Tab');
    if (await target.evaluate((element) => element === document.activeElement))
      return;
  }
  throw new Error('Could not reach target by Tab');
}

async function expectFocusVisible(page: Page) {
  const visible = await page.evaluate(() => {
    const element = document.activeElement;
    return element instanceof HTMLElement && element.matches(':focus-visible');
  });
  expect(visible).toBe(true);
}

async function expectVisibleFocus(page: Page) {
  const visible = await page.evaluate(() => {
    const element = document.activeElement;
    if (!(element instanceof HTMLElement)) return false;
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  });
  expect(visible).toBe(true);
}

function durationOk(value: string): boolean {
  return value
    .split(',')
    .map((item) => item.trim())
    .every((item) => {
      if (item === '0s' || item === '0ms') return true;
      const match = item.match(/^([\deE+.-]+)(ms|s)$/);
      if (!match) return false;
      const amount = Number(match[1]);
      const milliseconds = match[2] === 's' ? amount * 1000 : amount;
      return milliseconds <= 0.01;
    });
}
