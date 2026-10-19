import { afterEach, expect, it, vi } from 'vitest';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { readTrainingProviderEvidence } from './trainingProviderEvidence';
vi.mock('@/services/aviation-weather', () => ({
  aviationWeatherApi: { getCatalog: vi.fn() },
}));
afterEach(() => {
  vi.resetAllMocks();
  vi.useRealTimers();
});
it('preserves actual off, unavailable, stale and ready catalog branches without fetching products or claiming measured service', async () => {
  vi.mocked(aviationWeatherApi.getCatalog).mockResolvedValue({
    products: ['off', 'unavailable', 'stale', 'ready'].map((state, index) => ({
      state,
      layer_id: 'layer-' + index,
      product_type: index === 0 ? 'observed-precipitation' : 'winds',
      provenance: 'Provider observation ' + index,
    })),
  } as never);
  const value = await readTrainingProviderEvidence();
  expect(value.outcomes).toEqual(['optional-provider-branches']);
  expect(value.providerStates.map((row) => row.state)).toEqual([
    'off',
    'unavailable',
    'stale',
    'ready',
  ]);
  expect(value.providerStates[0].name).toBe('Radar');
});
it('keeps a failed read distinct from an authoritative unavailable product and gives no completion credit', async () => {
  vi.mocked(aviationWeatherApi.getCatalog).mockRejectedValue(
    new Error('Network unavailable')
  );
  const value = await readTrainingProviderEvidence();
  expect(value.outcomes).toEqual([]);
  expect(value.providerStates).toContainEqual({
    name: 'Weather catalog',
    state: 'read failed',
    detail: 'No confirmed provider response; retry the evidence check.',
  });
});
it('releases an unresponsive optional catalog within three seconds', async () => {
  vi.useFakeTimers();
  let observed: AbortSignal | undefined;
  vi.mocked(aviationWeatherApi.getCatalog).mockImplementation(
    (signal) => {
      observed = signal;
      return new Promise((_, reject) =>
        signal?.addEventListener('abort', () => reject(new Error('aborted')))
      );
    }
  );
  const pending = readTrainingProviderEvidence();
  await vi.advanceTimersByTimeAsync(3000);
  expect(observed?.aborted).toBe(true);
  expect((await pending).outcomes).toEqual([]);
});
