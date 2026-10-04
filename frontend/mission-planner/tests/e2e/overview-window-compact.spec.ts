import { expect, test, type Page } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { installOverviewWindowFixture } from './support/overview-window-fixture';

// Catch feedback growth omitted from layout measurement, squeezed identity,
// and fallback/arrival overlap without changing the existing one-pixel budget.
async function displayBounds(page: Page) {
  return page.evaluate(() => {
    const stage = document.querySelector('.overview-map-stage')!;
    const selectors = [
      '.overview-satellite-overlays',
      '.overview-map-controls',
      '.overview-display-controls',
      '.overview-map-overlays',
      '.overview-arrival',
    ];
    const panels = selectors.map((selector) => {
      const node = document.querySelector<HTMLElement>(selector)!;
      return { selector, rect: node.getBoundingClientRect().toJSON() };
    });
    const issues: string[] = [];
    const stageRect = stage.getBoundingClientRect();
    for (const { selector, rect } of panels) {
      if (
        rect.left < stageRect.left - 1 ||
        rect.right > stageRect.right + 1 ||
        rect.top < stageRect.top - 1 ||
        rect.bottom > stageRect.bottom + 1
      )
        issues.push(`${selector} exceeds map stage`);
    }
    for (let i = 0; i < panels.length; i++) {
      const a = panels[i];
      for (const b of panels.slice(i + 1)) {
        if (
          a.rect.left < b.rect.right - 1 &&
          a.rect.right > b.rect.left + 1 &&
          a.rect.top < b.rect.bottom - 1 &&
          a.rect.bottom > b.rect.top + 1
        )
          issues.push(`${a.selector} overlaps ${b.selector}`);
      }
    }
    for (const selector of [
      '.overview-display-label',
      '.overview-fullscreen-feedback',
    ]) {
      const node = document.querySelector<HTMLElement>(selector);
      if (!node) continue;
      const rect = node.getBoundingClientRect();
      const container = panels.find(
        (panel) => panel.selector === '.overview-display-controls'
      )!.rect;
      const range = document.createRange();
      range.selectNodeContents(node);
      const text = range.getBoundingClientRect();
      if (
        node.scrollWidth > node.clientWidth + 1 ||
        node.scrollHeight > node.clientHeight + 1 ||
        text.left < rect.left - 1 ||
        text.right > rect.right + 1 ||
        text.top < rect.top - 1 ||
        text.bottom > rect.bottom + 1 ||
        rect.left < container.left - 1 ||
        rect.right > container.right + 1 ||
        rect.top < container.top - 1 ||
        rect.bottom > container.bottom + 1
      )
        issues.push(`${selector} text is clipped or exceeds display controls`);
    }
    return {
      layout: document
        .querySelector('.overview-page')
        ?.getAttribute('data-layout'),
      flow: stage.getAttribute('data-flow'),
      panels,
      issues,
    };
  });
}

test('compact paused follow and real fullscreen rejection keep guidance and identity contained through native entry and exit', async ({
  context,
}, info) => {
  const fixture = await installOverviewWindowFixture(context);
  const overview = await context.newPage();
  await overview.setViewportSize({ width: 844, height: 390 });
  await overview.goto('/overview');
  await expect(overview.locator('.uplot')).toHaveCount(5);
  const identity = overview.getByLabel('Overview display identity');
  await expect(identity).toHaveText(/^Overview [a-f0-9]{6}$/);
  const displayLabel = (await identity.textContent())!;
  const editing = await context.newPage();
  await editing.goto('/configuration');
  await editing.getByLabel('Follow aircraft on Overview').check();
  fixture.state.positionAvailable = false;
  await expect(
    overview.getByText('Follow paused · Aircraft position unavailable', {
      exact: true,
    })
  ).toBeVisible();
  await expect
    .poll(async () => (await displayBounds(overview)).issues)
    .toEqual([]);
  const paused = await displayBounds(overview);
  const probe = await context.newCDPSession(overview);
  const read = async (expression: string) =>
    (
      await probe.send('Runtime.evaluate', {
        expression,
        returnByValue: true,
        userGesture: false,
      })
    ).result.value;
  await expect
    .poll(() => read('navigator.userActivation.isActive'), { timeout: 10000 })
    .toBe(false);
  await editing.bringToFront();
  const card = editing.getByRole('region', { name: 'Overview displays' });
  await expect(
    card.getByRole('option', { name: displayLabel, exact: true })
  ).toHaveCount(1);
  await card.getByRole('button', { name: 'Fullscreen', exact: true }).click();
  await expect(card.getByRole('status')).toHaveText(
    'Click Fullscreen in the Overview window to finish.'
  );
  await expect(overview.locator('.overview-fullscreen-feedback')).toBeVisible();
  expect(await read('!!document.fullscreenElement')).toBe(false);
  expect(await editing.evaluate(() => document.hasFocus())).toBe(true);
  const rejected = await displayBounds(overview);
  await writeFile(
    info.outputPath('compact-bounds.json'),
    JSON.stringify({ paused, rejected }, null, 2)
  );
  await expect
    .poll(async () => (await displayBounds(overview)).issues)
    .toEqual([]);
  await expect(identity).toHaveText(displayLabel);
  await overview
    .locator('.overview-fullscreen-feedback')
    .scrollIntoViewIfNeeded();
  await overview.screenshot({
    path: info.outputPath('fullscreen-rejected.png'),
  });
  await overview.bringToFront();
  await overview
    .getByRole('button', { name: 'Enter fullscreen overview' })
    .click();
  await expect
    .poll(() => read('document.fullscreenElement === document.documentElement'))
    .toBe(true);
  await expect(
    card.getByText('Fullscreen active', { exact: true })
  ).toBeVisible();
  await expect(overview.locator('.overview-fullscreen-feedback')).toHaveCount(
    0
  );
  await expect
    .poll(async () => (await displayBounds(overview)).issues)
    .toEqual([]);
  await overview.evaluate(() => document.exitFullscreen());
  await expect.poll(() => read('!!document.fullscreenElement')).toBe(false);
  await expect(card.getByText('Windowed', { exact: true })).toBeVisible();
  await expect(identity).toHaveText(displayLabel);
  await expect
    .poll(async () => (await displayBounds(overview)).issues)
    .toEqual([]);
});
