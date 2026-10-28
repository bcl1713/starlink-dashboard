import { expect, test } from '@playwright/test';
import { compositionFixture } from './support/overview-composition';
import {
  observeOverviewCamera,
  settledOverviewCamera,
} from './support/overview-camera';
import type { RootState } from '@react-three/fiber';
import type { AmbientLight, Material, Mesh } from 'three';

test.use({
  launchOptions: {
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  },
});

// Production Overview and its real renderers; all API reads use local test data.
// No backend or saved settings are needed for this temporary tuning session.
test('tunes real Overview bloom and exports the current settings', async ({
  page,
}, info) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const fixture = await compositionFixture(page);
  fixture.now = Date.parse('2026-10-28T06:00:00Z');
  await page.clock.setFixedTime(fixture.now);
  await observeOverviewCamera(page);
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/overview?bloomDebug=1');
  const panel = page.getByLabel('Temporary bloom tuning');
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel('City light color')).toHaveValue('#ffbe6f');
  const camera = await settledOverviewCamera(page);
  const numeric = (name: string) =>
    panel.getByRole('spinbutton', { name, exact: true });
  await numeric('Ambient lighting').fill('0.15');
  await expect(
    panel.getByRole('slider', { name: 'Ambient lighting slider', exact: true })
  ).toHaveValue('0.15');
  await numeric('Cities emission').fill('36');
  await numeric('Bloom strength').fill('1.1');
  await numeric('Bloom threshold').fill('0.4');
  await numeric('Bloom radius').fill('0.3');
  await numeric('Routes & links emission').fill('6');
  await numeric('Particles emission').fill('7');
  await numeric('POI cores emission').fill('9');
  await numeric('Aircraft emission').fill('12');
  await panel.getByLabel('Bloom resolution bound').selectOption('1920');
  const applied = () =>
    page.evaluate(() => {
      const roots = (
        window as unknown as {
          __overviewEvidenceRoots: Array<{
            containerInfo?: { getState?: () => RootState };
          }>;
        }
      ).__overviewEvidenceRoots;
      const state = roots.find(
        (root) =>
          root.containerInfo?.getState &&
          document.contains(root.containerInfo.getState().gl.domElement)
      )!.containerInfo!.getState!();
      let city = -1;
      let ambientIntensity = -1;
      const aircraft: number[] = [];
      state.scene.traverse((object) => {
        if (object.type === 'AmbientLight')
          ambientIntensity = (object as AmbientLight).intensity;
        const material = (object as Mesh).material as Material | undefined;
        if (!material || Array.isArray(material)) return;
        const uniforms = state.gl.properties.get(material).uniforms;
        if (uniforms?.cityEmissionIntensity)
          city = uniforms.cityEmissionIntensity.value;
        const shader = material as Material & {
          uniforms?: { uEmission?: { value: number } };
        };
        if (shader.uniforms?.uEmission)
          aircraft.push(shader.uniforms.uEmission.value);
      });
      return {
        city,
        aircraft,
        ambientIntensity,
        renderOwners: state.internal.priority,
      };
    });
  await expect
    .poll(async () => (await applied()).city, { timeout: 30_000 })
    .toBe(36);
  await expect
    .poll(async () => (await applied()).aircraft, { timeout: 30_000 })
    .toContain(12);
  expect((await applied()).renderOwners).toBe(1);
  expect((await applied()).ambientIntensity).toBe(0.15);
  const after = await settledOverviewCamera(page);
  expect(after.position).toEqual(camera.position);
  expect(after.quaternion).toEqual(camera.quaternion);
  await panel
    .getByRole('button', { name: 'Copy settings', exact: true })
    .click();
  const json = panel.getByLabel('Feedback JSON');
  const report = JSON.parse(await json.inputValue());
  expect(report.scene).toBe('overview');
  expect(report.lighting).toEqual({ ambientIntensity: 0.15 });
  expect(report.settings).toMatchObject({
    strength: 1.1,
    threshold: 0.4,
    radius: 0.3,
    maxDimension: 1920,
  });
  expect(report.emissions).toEqual({
    cities: 36,
    cityColor: '#ffbe6f',
    lines: 6,
    particles: 7,
    pois: 9,
    aircraft: 12,
  });
  expect(report.frame.bloomTargets).not.toBeNull();
  await numeric('Cities emission').fill('38');
  expect(JSON.parse(await json.inputValue()).emissions.cities).toBe(38);
  await numeric('Ambient lighting').fill('0.12');
  expect(JSON.parse(await json.inputValue()).lighting.ambientIntensity).toBe(
    0.12
  );
  await panel.getByLabel('Bloom debug view').selectOption('bright');
  await page.screenshot({ path: info.outputPath('overview-bright-pass.png') });
  await panel.getByLabel('Bloom debug view').selectOption('bloom');
  await page.screenshot({ path: info.outputPath('overview-bloom-only.png') });
  await panel.getByLabel('Bloom debug view').selectOption('final');
  await page.screenshot({ path: info.outputPath('overview-live-tuning.png') });
  await panel.getByLabel('Rendering mode').selectOption('current');
  await expect
    .poll(async () => (await applied()).city, { timeout: 30_000 })
    .toBe(0.35);
  expect((await applied()).ambientIntensity).toBe(0.5);
  await panel.getByLabel('Rendering mode').selectOption('bloom');
  await expect
    .poll(async () => (await applied()).city, { timeout: 30_000 })
    .toBe(38);
  expect((await applied()).ambientIntensity).toBe(0.12);
  await page.goto('/overview');
  await expect(panel).toHaveCount(0);
  await settledOverviewCamera(page);
  expect((await applied()).renderOwners).toBe(0);
  expect((await applied()).ambientIntensity).toBe(0.5);
  expect(errors).toEqual([]);
});
