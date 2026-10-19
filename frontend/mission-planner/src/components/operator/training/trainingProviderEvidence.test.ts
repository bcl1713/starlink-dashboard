import { afterEach, expect, it, vi } from 'vitest';
import { overviewWeatherApi } from '@/services/overview-weather';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { readTrainingProviderEvidence } from './trainingProviderEvidence';
vi.mock('@/services/overview-weather', () => ({
  overviewWeatherApi: { getFrame: vi.fn() },
}));
vi.mock('@/services/aviation-weather', () => ({
  aviationWeatherApi: { getCatalog: vi.fn() },
}));
afterEach(() => vi.resetAllMocks());
it('preserves actual off, unavailable, stale and ready catalog branches without claiming measured service', async () => {
  vi.mocked(overviewWeatherApi.getFrame).mockResolvedValue({
    state: 'off',
    source: 'radar',
    provenance: 'Observed precipitation disabled',
  } as never);
  vi.mocked(aviationWeatherApi.getCatalog).mockResolvedValue({
    products: ['off', 'unavailable', 'stale', 'ready'].map((state, index) => ({
      state,
      layer_id: 'layer-' + index,
      provenance: 'Provider observation ' + index,
    })),
  } as never);
  const value = await readTrainingProviderEvidence();
  expect(value.outcomes).toEqual(['optional-provider-branches']);
  expect(value.providerStates.map((row) => row.state)).toEqual([
    'off',
    'off',
    'unavailable',
    'stale',
    'ready',
  ]);
});
it('keeps a failed read distinct from an authoritative unavailable product and gives no completion credit', async () => {
  vi.mocked(overviewWeatherApi.getFrame).mockRejectedValue(
    new Error('Network unavailable')
  );
  vi.mocked(aviationWeatherApi.getCatalog).mockResolvedValue({
    products: [],
  } as never);
  const value = await readTrainingProviderEvidence();
  expect(value.outcomes).toEqual([]);
  expect(value.providerStates).toContainEqual({
    name: 'Radar',
    state: 'read failed',
    detail: 'No confirmed provider response; retry the evidence check.',
  });
});
