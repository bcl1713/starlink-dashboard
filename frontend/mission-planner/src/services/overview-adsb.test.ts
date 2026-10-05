import { beforeEach, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import { overviewAdsbApi } from './overview-adsb';
import { adsbBundle, adsbSettings } from '@/test/adsb-fixtures';
vi.mock('./api-client', () => ({ default: { get: vi.fn(), put: vi.fn() } }));
beforeEach(() => vi.resetAllMocks());
it('uses exact API paths, complete confirmed settings and abort signal', async () => {
  const signal = new AbortController().signal;
  vi.mocked(apiClient.get)
    .mockResolvedValueOnce({ data: adsbSettings() })
    .mockResolvedValueOnce({ data: adsbBundle() });
  expect(await overviewAdsbApi.getSettings(signal)).toEqual(adsbSettings());
  expect(await overviewAdsbApi.getTraffic(signal)).toEqual(adsbBundle());
  expect(apiClient.get).toHaveBeenNthCalledWith(
    1,
    '/api/overview-adsb/settings',
    { signal }
  );
  expect(apiClient.get).toHaveBeenNthCalledWith(
    2,
    '/api/overview-adsb/traffic',
    { signal }
  );
  vi.mocked(apiClient.put).mockResolvedValue({
    data: adsbSettings({ enabled: false, revision: 2 }),
  });
  expect(
    (await overviewAdsbApi.updateSettings({ enabled: false })).revision
  ).toBe(2);
  expect(apiClient.put).toHaveBeenCalledWith('/api/overview-adsb/settings', {
    enabled: false,
  });
});
it.each([
  { revision: -1 },
  { revision: 1.5 },
  { enabled: 'true' },
  { include_hexes: ['00ab12'] },
  { mode: 'all' },
  { exclude_hexes: null },
])('rejects malformed settings %j', async (changes) => {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { ...adsbSettings(), ...changes },
  });
  await expect(overviewAdsbApi.getSettings()).rejects.toThrow();
});
it.each([
  { latitude: 91 },
  { position_observed_at_ms: Infinity },
  { position_observed_at_ms: '1' },
  { military: 1 },
  { track_degrees: 360 },
  { acquired_at_ms: -1 },
  { altitude: { value: 2, unit: 'm', source: 'barometric' } },
])('rejects malformed contact %j', async (changes) => {
  const bundle = adsbBundle();
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { ...bundle, contacts: [{ ...bundle.contacts[0], ...changes }] },
  });
  await expect(overviewAdsbApi.getTraffic()).rejects.toThrow();
});
