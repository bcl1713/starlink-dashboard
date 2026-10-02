import { expect, test } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
  expectSameCamera,
} from './support/overview-camera';
test.use({ video: 'on' });
test.beforeEach(async ({ page }) => {
  await observeOverviewCamera(page);
  await compositionFixture(page);
});
for (const viewport of [
  { width: 390, height: 844 },
  { width: 844, height: 390 },
  { width: 2000, height: 900 },
]) {
  test(`scroll over panels gaps and globe preserves pose at ${viewport.width}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.goto('/overview');
    await expect(page.locator('.uplot')).toHaveCount(5);
    if (viewport.width === 2000)
      await page.evaluate(
        () => (document.documentElement.style.fontSize = '24px')
      );
    const owner = page.locator(
      viewport.width === 844
        ? '.overview-metrics-overlays'
        : '.app-route-content'
    );
    const before = await settledOverviewCamera(page);
    const stage = await page.locator('.overview-map-stage').boundingBox();
    await page.mouse.move(
      stage!.x + stage!.width * 0.45,
      stage!.y + stage!.height * 0.5
    );
    await page.mouse.wheel(0, 140);
    await expect
      .poll(() => owner.evaluate((el) => el.scrollTop))
      .toBeGreaterThan(0);
    expectSameCamera(before, await settledOverviewCamera(page));
    await owner.evaluate((el) => (el.scrollTop = 0));
    const card = page.locator('[data-metric-panel]').first();
    await card.scrollIntoViewIfNeeded();
    const box = await card.boundingBox();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.mouse.wheel(0, 140);
    expectSameCamera(before, await settledOverviewCamera(page));
  });
}
test('Explore scopes map gestures and preserves manual camera through rotation', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await expect(page.locator('.uplot')).toHaveCount(5);
  const canvas = await page.locator('.overview-globe canvas').elementHandle();
  const plots = await page.locator('.uplot').elementHandles();
  const explore = page.getByRole('button', {
    name: 'Explore map',
    exact: true,
  });
  await explore.click();
  await expect(
    page.getByRole('button', { name: 'Exit map exploration' })
  ).toHaveAttribute('aria-pressed', 'true');
  const box = await page.locator('.overview-globe canvas').boundingBox();
  const before = await settledOverviewCamera(page);
  await page.mouse.move(box!.x + box!.width * 0.4, box!.y + box!.height * 0.6);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width * 0.6, box!.y + box!.height * 0.5, {
    steps: 10,
  });
  await page.mouse.up();
  const manual = await settledOverviewCamera(page);
  expect(manual.position).not.toEqual(before.position);
  await page.keyboard.press('Escape');
  await expect(explore).toBeFocused();
  await expect(explore).toHaveAttribute('aria-pressed', 'false');
  await page.setViewportSize({ width: 844, height: 390 });
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'landscape'
  );
  expectSameCamera(manual, await settledOverviewCamera(page));
  await page.setViewportSize({ width: 390, height: 800 });
  expectSameCamera(manual, await settledOverviewCamera(page));
  expect(
    await canvas!.evaluate(
      (node) => node === document.querySelector('.overview-globe canvas')
    )
  ).toBe(true);
  for (let i = 0; i < 5; i++)
    expect(
      await plots[i].evaluate(
        (node, index) => node === document.querySelectorAll('.uplot')[index],
        i
      )
    ).toBe(true);
});
test('default touch scroll moves the page without rotating the globe', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await expect(page.locator('.uplot')).toHaveCount(5);
  const before = await settledOverviewCamera(page);
  const box = await page.locator('.overview-globe canvas').boundingBox();
  const cdp = await context.newCDPSession(page);
  const x = Math.round(box!.x + box!.width * 0.4),
    y = Math.round(box!.y + box!.height * 0.65);
  await cdp.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x, y }],
  });
  for (let i = 1; i <= 8; i++)
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x, y: y - i * 15 }],
    });
  await cdp.send('Input.dispatchTouchEvent', {
    type: 'touchEnd',
    touchPoints: [],
  });
  await expect
    .poll(() =>
      page.locator('.app-route-content').evaluate((el) => el.scrollTop)
    )
    .toBeGreaterThan(0);
  expectSameCamera(before, await settledOverviewCamera(page));
});
test('reduced motion removes continuous plot transitions without remounting', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await expect(page.locator('.uplot')).toHaveCount(5);
  const plots = await page.locator('.uplot').elementHandles();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect
    .poll(() =>
      page
        .locator('.overview-metric-history__surface')
        .evaluateAll((nodes) =>
          nodes.every((el) => getComputedStyle(el).transitionDuration === '0s')
        )
    )
    .toBe(true);
  for (let i = 0; i < 5; i++)
    expect(
      await plots[i].evaluate(
        (node, index) => node === document.querySelectorAll('.uplot')[index],
        i
      )
    ).toBe(true);
  await expect(page.getByLabel('Network history context')).toContainText(
    'LAST 5 MIN'
  );
});

test('landscape gaps scroll the rail while browser zoom gestures remain available', async ({
  page,
}) => {
  await page.setViewportSize({ width: 844, height: 390 });
  await page.goto('/overview');
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'landscape'
  );
  const stage = await page.locator('.overview-map-stage').boundingBox();
  const rail = page.locator('.overview-metrics-overlays');
  const box = await rail.boundingBox();
  const before = await settledOverviewCamera(page);
  await page.mouse.move((stage!.x + stage!.width + box!.x) / 2, box!.y + 80);
  await page.mouse.wheel(0, 140);
  await expect
    .poll(() => rail.evaluate((el) => el.scrollTop))
    .toBeGreaterThan(0);
  expectSameCamera(before, await settledOverviewCamera(page));
  for (const modifier of ['ctrlKey', 'metaKey']) {
    expect(
      await page
        .locator('.overview-globe canvas')
        .evaluate((canvas, modifier) => {
          const event = new WheelEvent('wheel', {
            bubbles: true,
            cancelable: true,
            deltaY: 140,
            [modifier]: true,
          });
          canvas.dispatchEvent(event);
          return event.defaultPrevented;
        }, modifier)
    ).toBe(false);
  }
});

for (const deviceScaleFactor of [1, 1.5, 2]) {
  test.describe(`responsive buffers at DPR ${deviceScaleFactor}`, () => {
    test.use({ deviceScaleFactor });
    test('retains renderer and five correctly sized plots through repeated rotation', async ({
      page,
    }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto('/overview');
      await settledOverviewCamera(page);
      const canvas = await page
        .locator('.overview-globe canvas')
        .elementHandle();
      const plots = await page.locator('.uplot').elementHandles();
      for (const viewport of [
        { width: 390, height: 844 },
        { width: 844, height: 390 },
        { width: 390, height: 800 },
        { width: 844, height: 390 },
      ]) {
        await page.setViewportSize(viewport);
        await expect(page.locator('.overview-page')).toHaveAttribute(
          'data-layout',
          viewport.width === 844 ? 'landscape' : 'stacked'
        );
        await expect
          .poll(() =>
            page
              .locator('.overview-globe canvas, .uplot canvas')
              .evaluateAll((nodes) =>
                nodes.every((node) => {
                  const canvas = node as HTMLCanvasElement;
                  const box = canvas.getBoundingClientRect();
                  return (
                    Math.abs(canvas.width - box.width * devicePixelRatio) < 2 &&
                    Math.abs(canvas.height - box.height * devicePixelRatio) < 2
                  );
                })
              )
          )
          .toBe(true);
        expect(
          await canvas!.evaluate(
            (node) => node === document.querySelector('.overview-globe canvas')
          )
        ).toBe(true);
        for (let i = 0; i < 5; i++)
          expect(
            await plots[i].evaluate(
              (node, index) =>
                node === document.querySelectorAll('.uplot')[index],
              i
            )
          ).toBe(true);
      }
    });
  });
}

test('interrupted pointers release capture on Escape blur and rotation and allow reentry', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await settledOverviewCamera(page);
  for (const interruption of ['Escape', 'blur', 'rotation']) {
    await page
      .getByRole('button', { name: 'Explore map', exact: true })
      .click();
    const box = await page.locator('.overview-globe canvas').boundingBox();
    await page.mouse.move(
      box!.x + box!.width * 0.4,
      box!.y + box!.height * 0.5
    );
    await page.mouse.down();
    await page.mouse.move(
      box!.x + box!.width * 0.55,
      box!.y + box!.height * 0.6,
      { steps: 4 }
    );
    if (interruption === 'Escape') await page.keyboard.press('Escape');
    else if (interruption === 'blur')
      await page.evaluate(() => window.dispatchEvent(new Event('blur')));
    else await page.setViewportSize({ width: 844, height: 390 });
    await expect(
      page.getByRole('button', { name: 'Explore map', exact: true })
    ).toHaveAttribute('aria-pressed', 'false');
    await page.mouse.up();
    const before = await settledOverviewCamera(page);
    await page.mouse.move(100, 200);
    expectSameCamera(before, await settledOverviewCamera(page));
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await page.getByRole('button', { name: 'Explore map', exact: true }).click();
  const before = await settledOverviewCamera(page);
  const box = await page.locator('.overview-globe canvas').boundingBox();
  await page.mouse.move(box!.x + 80, box!.y + 150);
  await page.mouse.down();
  await page.mouse.move(box!.x + 150, box!.y + 180, { steps: 6 });
  await page.mouse.up();
  expect((await settledOverviewCamera(page)).position).not.toEqual(
    before.position
  );
});

test('Configuration opt-in follows fresh positions while default framing remains static', async ({
  page,
}) => {
  const source = await compositionFixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  const initial = await settledOverviewCamera(page);
  source.position = { latitude: -25, longitude: 80, altitude: 35000 };
  await page.waitForResponse((r) => r.url().endsWith('/api/status') && r.ok());
  expectSameCamera(initial, await settledOverviewCamera(page));
  await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await page.getByRole('link', { name: 'Configuration', exact: true }).click();
  await page
    .getByRole('checkbox', { name: 'Follow aircraft on Overview' })
    .check();
  await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page.locator('#overview-follow-status')).toHaveText(
    'Following aircraft'
  );
  const following = await settledOverviewCamera(page);
  expect(following.position).not.toEqual(initial.position);
  source.position = { latitude: 45, longitude: 120, altitude: 35000 };
  await expect
    .poll(async () => (await settledOverviewCamera(page)).position)
    .not.toEqual(following.position);
  for (const failure of ['stale', 'errors', 'missing']) {
    if (failure === 'stale') source.stale = true;
    else if (failure === 'errors') source.errors = true;
    else {
      source.errors = false;
      source.stale = false;
      source.position = null;
    }
    await expect(page.locator('#overview-follow-status')).toContainText(
      'Follow paused',
      { timeout: 20000 }
    );
    await expect(page.locator('#overview-follow-status')).toContainText(
      failure === 'stale'
        ? 'stale'
        : failure === 'errors'
          ? 'refresh unavailable'
          : 'position unavailable',
      { timeout: 20000 }
    );
    const before = await settledOverviewCamera(page);
    await page.waitForResponse((r) => r.url().endsWith('/api/status'));
    expectSameCamera(before, await settledOverviewCamera(page));
  }
});

test('desktop keeps deliberate globe input and its accepted composition', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/overview');
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'desktop'
  );
  await expect(
    page.getByRole('button', { name: 'Explore map', exact: true })
  ).not.toBeVisible();
  const before = await settledOverviewCamera(page);
  const box = await page.locator('.overview-globe canvas').boundingBox();
  await page.mouse.move(box!.x + box!.width * 0.55, box!.y + box!.height * 0.5);
  await page.mouse.wheel(0, 140);
  expect((await settledOverviewCamera(page)).position).not.toEqual(
    before.position
  );
});

test('desktop Reset resumes configured following and exposes source pause reasons', async ({
  page,
}) => {
  const source = await compositionFixture(page);
  await page.addInitScript(() =>
    localStorage.setItem('overview.follow-aircraft', 'true')
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/overview');
  await expect(page.locator('.overview-page')).toHaveAttribute(
    'data-layout',
    'desktop'
  );
  const reset = page.getByRole('button', { name: 'Reset map view' });
  const status = page.locator('#overview-follow-status');
  await expect(reset).toBeVisible();
  await expect(status).toBeVisible();
  await expect(status).toHaveText('Following aircraft');
  await settledOverviewCamera(page);
  const box = await page.locator('.overview-globe canvas').boundingBox();
  await page.mouse.move(box!.x + box!.width * 0.55, box!.y + box!.height * 0.5);
  await page.mouse.wheel(0, 140);
  await settledOverviewCamera(page);
  await expect(status).not.toBeVisible();
  await reset.click();
  await expect(status).toHaveText('Following aircraft');
  await settledOverviewCamera(page);
  for (const failure of ['stale', 'errors', 'missing']) {
    source.stale = failure === 'stale';
    source.errors = failure === 'errors';
    if (failure === 'missing') source.position = null;
    await expect(status).toContainText(
      failure === 'stale'
        ? 'stale'
        : failure === 'errors'
          ? 'refresh unavailable'
          : 'position unavailable',
      { timeout: 20000 }
    );
    await expect(status).toBeInViewport();
    await expect(reset).toBeInViewport();
  }
});

test('automatic reset moves through eased intermediate camera poses', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/overview');
  await settledOverviewCamera(page);
  await page.getByRole('button', { name: 'Explore map', exact: true }).click();
  const box = await page.locator('.overview-globe canvas').boundingBox();
  await page.mouse.move(box!.x + 70, box!.y + 150);
  await page.mouse.down();
  await page.mouse.move(box!.x + 160, box!.y + 200, { steps: 8 });
  await page.mouse.up();
  await settledOverviewCamera(page);
  await page.evaluate(() => {
    const state = (
      window as unknown as {
        __overviewEvidenceRoots: Array<{
          containerInfo?: {
            getState?: () => {
              camera: { position: { toArray: () => number[] } };
            };
          };
        }>;
      }
    ).__overviewEvidenceRoots.find(
      (root) => root.containerInfo?.getState
    )?.containerInfo;
    if (!state?.getState) throw new Error('Renderer store unavailable');
    const evidence = window as unknown as { __cameraResetSamples: number[][] };
    evidence.__cameraResetSamples = [
      state.getState!().camera.position.toArray(),
    ];
    let remaining = 30;
    const sample = () => {
      evidence.__cameraResetSamples.push(
        state.getState!().camera.position.toArray()
      );
      if (--remaining) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await page.getByRole('button', { name: 'Reset map view' }).click();
  await expect
    .poll(
      () =>
        page.evaluate(
          () =>
            (window as unknown as { __cameraResetSamples: number[][] })
              .__cameraResetSamples.length
        ),
      { timeout: 15000 }
    )
    .toBe(31);
  const samples = await page.evaluate(
    () =>
      (window as unknown as { __cameraResetSamples: number[][] })
        .__cameraResetSamples
  );
  const distinct = new Set(
    samples.map((p) => p.map((v) => v.toFixed(3)).join(','))
  );
  expect(distinct.size).toBeGreaterThan(3);
  const distance = (a: number[], b: number[]) =>
    Math.hypot(...a.map((v, i) => v - b[i]));
  const travel = distance(samples[0], samples.at(-1)!);
  expect(travel).toBeGreaterThan(0.1);
  expect(
    Math.max(...samples.slice(1).map((p, i) => distance(p, samples[i])))
  ).toBeLessThan(travel * 0.75);
});
