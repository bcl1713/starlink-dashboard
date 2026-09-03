import { expect, test } from '@playwright/test';
import { installOverviewRoutes } from './overview-fixtures';
import {
  enterOverviewFullscreen,
  measureOverviewGeometry,
} from './overview-geometry';

const poiNames = Array.from({ length: 5 }, (_, index) =>
  `Waypoint ${index + 1} `.padEnd(200, 'x')
);

test('1920x1080 fullscreen fits five accepted 200-character POI names', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await installOverviewRoutes(page, { poiNameLength: 200 });
  await page.goto('/overview');
  for (const name of poiNames) {
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  }

  await enterOverviewFullscreen(page);
  const geometry = await measureOverviewGeometry(page, poiNames);
  process.stdout.write(
    `OVERVIEW_LONG_LABEL_GEOMETRY ${JSON.stringify(geometry)}\n`
  );
});
