/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { overviewWeatherApi } from '@/services/overview-weather';
import { readyWeather } from '@/test/weather-fixtures';
import { WeatherAtlasLoader, type WeatherAtlasPair } from './weather-atlas';
import { WeatherController } from './weather-controller';

const controllers: WeatherController[] = [];
afterEach(() => {
  controllers.splice(0).forEach((c) => c.dispose());
  vi.useRealTimers();
  vi.restoreAllMocks();
});
function harness() {
  vi.useFakeTimers();
  const clock = { nowMono: () => performance.now() };
  const api = {
    ...overviewWeatherApi,
    getFrame: vi.fn().mockResolvedValue(readyWeather()),
  };
  const loader = new WeatherAtlasLoader(fetch, clock);
  const pair: WeatherAtlasPair = {
    radar: document.createElement('canvas'),
    coverage: document.createElement('canvas'),
    frameTimeMs: 1791244200000,
    coverageToken: 20732,
    coverageExpiresAtMs: 1791331200000,
    dispose: vi.fn(),
  };
  vi.spyOn(loader, 'load').mockResolvedValue(pair);
  const controller = new WeatherController(api, loader, clock);
  controllers.push(controller);
  const observe = (enabled = true, revision = 1) =>
    controller.setSettings({
      settings: { enabled, revision },
      receivedAtMono: clock.nowMono(),
    });
  return { controller, api, loader, pair, observe };
}

it('does no default-off work and settings polls do not restart radar checks', async () => {
  const h = harness();
  await vi.advanceTimersByTimeAsync(300000);
  expect(h.api.getFrame).not.toHaveBeenCalled();
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  expect(h.controller.snapshot().state).toBe('current');
  for (let n = 0; n < 60; n++) {
    await vi.advanceTimersByTimeAsync(5000);
    h.observe();
  }
  expect(h.api.getFrame).toHaveBeenCalledTimes(2);
  expect(h.loader.load).toHaveBeenCalledTimes(1);
});
it('hides after 15 seconds without confirmed settings and resumes with confirmation', async () => {
  const h = harness();
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  await vi.advanceTimersByTimeAsync(15000);
  expect(h.controller.snapshot().visible).toBe(false);
  expect(h.controller.snapshot().state).toBe('unavailable');
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  expect(h.api.getFrame).toHaveBeenCalledTimes(2);
  h.observe(false, 2);
  expect(h.controller.snapshot().state).toBe('off');
  expect(h.pair.dispose).toHaveBeenCalledTimes(1);
});
it('does not let an older settings revision restore disabled imagery', async () => {
  const h = harness();
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  h.observe(false, 2);
  h.observe(true, 1);
  await vi.advanceTimersByTimeAsync(0);
  expect(h.controller.snapshot().state).toBe('off');
  expect(h.api.getFrame).toHaveBeenCalledTimes(1);
});
it('retains eligible imagery as stale on failure, but never extends expiry', async () => {
  const h = harness();
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  h.api.getFrame.mockRejectedValue(new Error('provider unavailable'));
  h.controller.reconnect();
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  expect(h.controller.snapshot().state).toBe('stale');
  vi.setSystemTime(new Date('2050-01-01'));
  expect(h.controller.snapshot().ageMs).toBe(600000);
  for (let n = 0; n < 600; n++) {
    await vi.advanceTimersByTimeAsync(5000);
    h.observe();
  }
  expect(h.controller.snapshot().visible).toBe(false);
  expect(h.controller.snapshot().state).toBe('unavailable');
});
it('waits for fresh settings on foreground and discards a late atlas after disable', async () => {
  const h = harness();
  let resolve!: (pair: WeatherAtlasPair) => void;
  vi.mocked(h.loader.load).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      })
  );
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  h.observe(false, 2);
  resolve(h.pair);
  await vi.advanceTimersByTimeAsync(0);
  expect(h.pair.dispose).toHaveBeenCalledTimes(1);
  expect(h.controller.snapshot().visible).toBe(false);
  h.observe(true, 3);
  await vi.advanceTimersByTimeAsync(0);
  h.controller.setVisible(false);
  await vi.advanceTimersByTimeAsync(1000);
  h.controller.setVisible(true);
  const count = h.api.getFrame.mock.calls.length;
  await vi.advanceTimersByTimeAsync(0);
  expect(h.api.getFrame).toHaveBeenCalledTimes(count);
  h.observe(true, 3);
  await vi.advanceTimersByTimeAsync(0);
  expect(h.api.getFrame).toHaveBeenCalledTimes(count + 1);
});
it('expires midnight coverage during loading and immediately checks a new manifest', async () => {
  const h = harness();
  const manifest = {
    ...readyWeather(),
    generated_at_ms: 1791331199000,
    frame_time_ms: 1791330600000,
    radar_tile_template:
      '/api/overview-weather/radar/1791330600/{z}/{x}/{y}.png',
  };
  h.api.getFrame.mockResolvedValue(manifest);
  vi.mocked(h.loader.load).mockImplementation(() => new Promise(() => {}));
  h.observe();
  await vi.advanceTimersByTimeAsync(0);
  await vi.advanceTimersByTimeAsync(1000);
  expect(h.api.getFrame).toHaveBeenCalledTimes(2);
  expect(h.controller.snapshot().visible).toBe(false);
});
