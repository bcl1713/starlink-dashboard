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
it('accepts normalized alternate source capabilities and informational provenance', async () => {
  const fixture = {
    ...readyWeather(),
    source: 'fixture-radar',
    provenance: 'Alternate observed radar',
    product: 'observed-precipitation',
    product_id: 'b'.repeat(64),
    tile_schema: 'xyz-rgba-pair-v1',
    coverage_encoding: 'absence-rgba-v1',
    max_zoom: 5,
    attribution: { label: 'Fixture radar', url: 'https://example.com/radar' },
    radar_tile_template:
      '/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png?product_id=' +
      'b'.repeat(64),
    coverage_tile_template:
      '/api/overview-weather/coverage/20732/{z}/{x}/{y}.png?product_id=' +
      'b'.repeat(64),
  };
  vi.mocked(apiClient.get).mockResolvedValue({ data: fixture });
  expect((await overviewWeatherApi.getFrame()).source).toBe('fixture-radar');
});
