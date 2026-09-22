import { expect, test } from '@playwright/test';

test('keeps a narrow upcoming-POI panel clear of the native fullscreen control', async ({
  page,
}) => {
  await page.setViewportSize({ width: 704, height: 900 });

  await page.route('**/api/overview/upcoming-pois', async (route) => {
    await route.fulfill({
      json: {
        state: 'available',
        calculated_at: '2026-09-22T12:00:00.000Z',
        pois: Array.from({ length: 5 }, (_, index) => ({
          poi_id: `fixture-poi-${index + 1}`,
          name: `Fixture POI ${index + 1}`,
          kind: 'x_band_transition',
          latitude: 41.2 + index,
          longitude: -95.9 + index,
          expected_arrival_time: '2026-09-22T12:00:00.000Z',
          eta_seconds: (index + 1) * 60,
          estimated_arrival_time: new Date(
            Date.parse('2026-09-22T12:00:00.000Z') + (index + 1) * 60_000
          ).toISOString(),
          eta_type: 'estimated',
          upcoming: true,
          map_retained: true,
        })),
      },
    });
  });

  await page.goto('/overview');

  const fullscreenControl = page.getByRole('button', {
    name: 'Enter fullscreen overview',
  });
  const poiPanel = page.getByLabel('Upcoming POIs');

  await expect(fullscreenControl).toBeVisible();
  await expect(poiPanel).toBeVisible();
  await expect(poiPanel.getByRole('row')).toHaveCount(6);

  const geometry = await page.evaluate(() => {
    const control = document.querySelector('.overview-fullscreen-control');
    const panel = document.querySelector('[aria-label="Upcoming POIs"]');
    const canvas = document.querySelector('canvas');
    const panelBody = panel?.querySelector('.upcoming-pois__body');

    if (!control || !panel || !canvas || !panelBody) {
      return null;
    }

    const controlBox = control.getBoundingClientRect();
    const panelBox = panel.getBoundingClientRect();
    const panelBodyBox = panelBody.getBoundingClientRect();
    const panelHitX = panelBox.left + panelBox.width / 2;
    const panelHitY = Math.min(panelBox.top + 20, window.innerHeight - 1);
    const panelVisualTop = Math.min(panelBox.top, panelBodyBox.top);
    const panelVisualBottom = Math.max(panelBox.bottom, panelBodyBox.bottom);

    return {
      control: controlBox.toJSON(),
      panel: panelBox.toJSON(),
      panelBody: panelBodyBox.toJSON(),
      panelBodyHeight: (panelBody as HTMLElement).style.height,
      panelPointerEvents: getComputedStyle(panel.parentElement!).pointerEvents,
      panelHitIsWithinPanel: panel.contains(document.elementFromPoint(panelHitX, panelHitY)),
      separated:
        controlBox.bottom <= panelVisualTop || panelVisualBottom <= controlBox.top,
    };
  });

  expect(geometry).not.toBeNull();
  expect(geometry?.panelBodyHeight).toBe('14rem');
  expect(geometry?.separated).toBe(true);
  expect(geometry?.panelPointerEvents).toBe('none');
  expect(geometry?.panelHitIsWithinPanel).toBe(false);
});
