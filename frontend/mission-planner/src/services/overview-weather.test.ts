import { afterEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { overviewWeatherApi } from './overview-weather';
import { readyWeather } from '@/test/weather-fixtures';
vi.mock('./api-client', () => ({ default: { get: vi.fn(), put: vi.fn() } }));
afterEach(() => vi.resetAllMocks());

it('accepts the exact admitted same-origin frame contract', async () => {
  vi.mocked(apiClient.get).mockResolvedValue({ data: readyWeather() });
  expect((await overviewWeatherApi.getFrame()).frame_time_ms).toBe(
    1791244200000
  );
  expect(apiClient.get).toHaveBeenCalledWith('/api/overview-weather/frame', {
    signal: undefined,
  });
});
it.each([
  { radar_tile_template: 'https://evil.test/tile.png' },
  {
    coverage_tile_template:
      '/api/overview-weather/coverage/20731/{z}/{x}/{y}.png',
  },
  { frame_time_ms: null },
  { state: 'off' },
  { zoom: 3 },
  { coverage_expires_at_ms: 1791331200001 },
  { settings_revision: true },
  { extra: 'unexpected' },
])('rejects unsafe or incoherent frame fields %j', async (change) => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { ...readyWeather(), ...change },
  });
  await expect(overviewWeatherApi.getFrame()).rejects.toThrow();
});
it.each([
  { enabled: 1, revision: 0 },
  { enabled: false, revision: -1 },
  { enabled: false, revision: 0, extra: 1 },
])('rejects invalid settings %j', async (data) => {
  vi.mocked(apiClient.get).mockResolvedValue({ data });
  await expect(overviewWeatherApi.getSettings()).rejects.toThrow();
});
