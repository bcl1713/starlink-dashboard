import { afterEach, expect, it, vi } from 'vitest';
import { overviewLinkSettingsApi } from '@/services/overview-link-settings';
import { overviewWeatherApi } from '@/services/overview-weather';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { readTrainingDisplayEvidence } from './trainingDisplayEvidence';
vi.mock('@/services/overview-link-settings', () => ({
  overviewLinkSettingsApi: { get: vi.fn() },
}));
vi.mock('@/services/overview-weather', () => ({
  overviewWeatherApi: { getSettings: vi.fn() },
}));
vi.mock('@/services/aviation-weather', () => ({
  aviationWeatherApi: { getSettings: vi.fn() },
}));
afterEach(() => vi.resetAllMocks());
const reads = [
  overviewLinkSettingsApi.get,
  overviewWeatherApi.getSettings,
  aviationWeatherApi.getSettings,
];
it('requires confirmed ordinary reads from all three independent stores', async () => {
  for (const read of reads) vi.mocked(read).mockResolvedValue({} as never);
  expect(await readTrainingDisplayEvidence()).toEqual([
    'display-settings-read',
  ]);
  for (const read of reads) expect(read).toHaveBeenCalledTimes(1);
});
it.each([0, 1, 2])(
  'does not credit a partial settings read when store %i is unavailable',
  async (missing) => {
    for (const read of reads) vi.mocked(read).mockResolvedValue({} as never);
    vi.mocked(reads[missing]).mockRejectedValue(
      new Error('Settings unavailable')
    );
    expect(await readTrainingDisplayEvidence()).toEqual([]);
  }
);
