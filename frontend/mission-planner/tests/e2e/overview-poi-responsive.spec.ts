import { expect, test } from '@playwright/test';

test('keeps a narrow arrival panel clear of the native fullscreen control', async ({
  page,
}) => {
  await page.setViewportSize({ width: 704, height: 900 });
  await page.route('**/api/overview/upcoming-pois', (route) =>
    route.fulfill({
      json: {
        state: 'no_generated_pois',
        calculated_at: new Date().toISOString(),
        flight_phase: 'in_flight',
        position_state: 'unavailable',
        position_observed_at: null,
        scheduled_departure_time: null,
        pois: [],
      },
    })
  );
  await page.goto('/overview');
  const control = page.getByRole('button', {
    name: 'Enter fullscreen overview',
  });
  const panel = page.getByLabel('Departure and arrival');
  await expect(control).toBeVisible();
  await expect(panel).toBeVisible();
  const geometry = await page.evaluate(() => {
    const control = document
      .querySelector('.overview-fullscreen-control')!
      .getBoundingClientRect();
    const panel = document.querySelector('.overview-arrival')!;
    const rect = panel.getBoundingClientRect();
    return {
      separated: control.bottom <= rect.top || rect.bottom <= control.top,
      scroll:
        panel.scrollWidth > panel.clientWidth ||
        panel.scrollHeight > panel.clientHeight,
      pointerEvents: getComputedStyle(panel.parentElement!).pointerEvents,
    };
  });
  expect(geometry).toEqual({
    separated: true,
    scroll: false,
    pointerEvents: 'none',
  });
});
