import { expect, test, type Page } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import {
  installWeatherProbe,
  weatherSnapshot,
} from './support/overview-weather-probe';
import { windSnapshot } from './support/gfs-wind-probe';

test('display presets restore actual weather rendering and report real conflicts and unavailable settings', async ({
  browser,
  context,
  request,
}) => {
  const output = process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR!;
  const secondary = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const config = await context.newPage(),
    operator = await context.newPage(),
    overview = await context.newPage(),
    other = await secondary.newPage();
  const proof: Record<string, unknown> = {
    synthetic: true,
    realWorker: true,
    softwareRendering: true,
  };
  try {
    for (const page of [overview, other]) {
      await page.clock.setFixedTime(new Date('2026-10-06T06:00:00Z'));
      await installWeatherProbe(page);
      await page.goto('/overview');
    }
    await config.goto('/configuration');
    await config.getByRole('tab', { name: 'Weather', exact: true }).click();
    async function toggle(name: string, enabled: boolean) {
      const control = config.getByRole('switch', { name, exact: true });
      await expect(control).toBeEnabled();
      if ((await control.isChecked()) !== enabled) await control.click();
      await expect(control).toBeChecked({ checked: enabled });
    }
    const settings = async () => ({
      radar: await (await request.get('/api/overview-weather/settings')).json(),
      aviation: await (
        await request.get('/api/aviation-weather/v1/settings')
      ).json(),
    });
    const scene = async (page: Page, on: boolean) => {
      const visibilityBefore = await page.evaluate(
        () => document.visibilityState
      );
      // Hidden displays deliberately release native model resources. Activate
      // the real window before inspecting the foreground rendering contract.
      await page.bringToFront();
      try {
        await expect
          .poll(
            async () => {
              const current = await windSnapshot(page);
              return JSON.stringify({
                present: !!current?.present,
                wind: current?.wind,
                temperature: current?.temperature,
                sigmet: current?.bulletins?.[2],
              });
            },
            { timeout: 180000 }
          )
          .toBe(
            JSON.stringify({
              present: true,
              wind: on,
              temperature: !on,
              sigmet: on,
            })
          );
      } catch (error) {
        await writeFile(
          join(output, 'operator-display-scene-failure.json'),
          JSON.stringify(
            {
              visibilityBefore,
              visibilityAfter: await page.evaluate(
                () => document.visibilityState
              ),
              expectedWind: on,
              settings: await settings(),
              native: await windSnapshot(page),
              weather: await weatherSnapshot(page),
            },
            null,
            2
          )
        );
        throw error;
      }
      await expect
        .poll(async () => !!(await weatherSnapshot(page)).radar)
        .toBe(on);
    };
    await toggle('Precipitation radar', true);
    await toggle('International SIGMET advisories', true);
    await toggle('GFS winds', true);
    // The reverse bundle deliberately enables temperature, exercising exclusivity.
    const initial = await settings();
    await operator.goto('/operator?workspace=1');
    await operator
      .getByRole('button', { name: 'Display tools', exact: true })
      .click();
    const dialog = operator.getByRole('dialog', {
      name: 'Display tools',
      exact: true,
    });
    await dialog
      .getByRole('button', { name: 'Show display controls', exact: true })
      .click();
    await dialog
      .getByRole('button', { name: 'Save current as Weather', exact: true })
      .click();
    await expect(
      dialog.getByText('Weather preset saved', { exact: true })
    ).toBeVisible();
    await scene(overview, true);
    await scene(other, true);
    await toggle('Precipitation radar', false);
    await toggle('International SIGMET advisories', false);
    await toggle('GFS air temperature', true);
    await scene(overview, false);
    await dialog
      .getByRole('button', { name: 'Save current as Normal', exact: true })
      .click();
    await expect(
      dialog.getByText('Normal preset saved', { exact: true })
    ).toBeVisible();
    const presets = await (
      await request.get('/api/overview-links/presets')
    ).json();
    expect(presets.weather.weather_visibility).toMatchObject({
      radar: true,
      winds: true,
      temperature: false,
      sigmet: true,
    });
    expect(presets.normal.weather_visibility).toMatchObject({
      radar: false,
      winds: false,
      temperature: true,
      sigmet: false,
    });
    await dialog
      .getByRole('button', { name: 'Apply Weather', exact: true })
      .click();
    await expect(
      dialog.getByText('Weather preset applied', { exact: true })
    ).toBeVisible();
    await scene(overview, true);
    await scene(other, true);
    expect((await settings()).aviation.gfs_selection).toEqual(
      initial.aviation.gfs_selection
    );
    proof.restored = {
      settings: await settings(),
      scene: await windSnapshot(overview),
      radar: await weatherSnapshot(overview),
    };
    let conflict = false;
    await operator.route(
      '**/api/aviation-weather/v1/settings',
      async (route) => {
        if (route.request().method() === 'PUT' && !conflict) {
          conflict = true;
          const current = await (
            await request.get('/api/aviation-weather/v1/settings')
          ).json();
          const counterpart = await request.put(
            '/api/aviation-weather/v1/settings',
            {
              data: {
                metar: !current.metar,
                expected_revision: current.revision,
              },
            }
          );
          expect(counterpart.ok()).toBe(true);
        }
        await route.continue();
      }
    );
    await dialog
      .getByRole('button', { name: 'Apply Normal', exact: true })
      .click();
    await expect(dialog.getByRole('alert')).toContainText(
      /Confirmed: Panels and map, Radar.*Unconfirmed: Aviation weather/
    );
    expect(conflict).toBe(true);
    await expect(
      dialog.getByText('Normal preset applied', { exact: true })
    ).toHaveCount(0);
    proof.conflictPartial = {
      settings: await settings(),
      message: await dialog.getByRole('alert').textContent(),
    };
    await operator.unroute('**/api/aviation-weather/v1/settings');
    await dialog
      .getByRole('button', { name: 'Apply Normal', exact: true })
      .click();
    await expect(
      dialog.getByText('Normal preset applied', { exact: true })
    ).toBeVisible();
    await scene(overview, false);
    await scene(other, false);
    const beforeUnavailable = await settings();
    await operator.route('**/api/overview-weather/settings', (route) =>
      route.abort('connectionrefused')
    );
    await dialog
      .getByRole('button', { name: 'Apply Weather', exact: true })
      .click();
    await expect(dialog.getByRole('alert')).toContainText('not confirmed');
    expect(await settings()).toEqual(beforeUnavailable);
    await expect(
      dialog.getByText('Weather preset applied', { exact: true })
    ).toHaveCount(0);
    await operator.unroute('**/api/overview-weather/settings');
    await dialog
      .getByRole('button', { name: 'Apply Weather', exact: true })
      .click();
    await expect(
      dialog.getByText('Weather preset applied', { exact: true })
    ).toBeVisible();
    await scene(overview, true);
    proof.reverse = beforeUnavailable;
    proof.unavailablePreflightMadeNoChanges = true;
    proof.retry = await settings();
    proof.presets = presets;
    for (const viewport of [
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
      { width: 844, height: 390 },
    ]) {
      await overview.setViewportSize(viewport);
      const metrics = overview.getByRole('region', {
        name: 'Overview metric history',
        exact: true,
      });
      await expect(metrics.locator('[data-metric-panel]')).toHaveCount(5);
      await expect(
        metrics.getByText('Unavailable', { exact: true })
      ).toHaveCount(5);
      await expect(
        metrics.getByText('Simulation · network measurements unavailable', {
          exact: true,
        })
      ).toBeVisible();
      await overview.screenshot({
        path: join(output, `display-${viewport.width}x${viewport.height}.png`),
        fullPage: false,
        animations: 'disabled',
        timeout: 30_000,
      });
    }
    await writeFile(
      join(output, 'operator-display-proof.json'),
      JSON.stringify(proof, null, 2)
    );
  } finally {
    await writeFile(
      join(output, 'operator-display-last-observation.json'),
      JSON.stringify(proof, null, 2)
    );
    await secondary.close();
  }
});
