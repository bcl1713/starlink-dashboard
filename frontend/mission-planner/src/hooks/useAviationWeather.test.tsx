// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, renderHook } from '@testing-library/react';
import { useAviationWeather } from './useAviationWeather';
import type { AviationLayerView } from '@/pages/aviation-weather/aviation-controller';
vi.mock('./api/useAviationSettings', () => ({
  useAviationSettings: () => ({ data: undefined }),
}));
vi.mock('./api/useRouteSigmets', () => ({
  useRouteSigmets: () => ({
    snapshot: null,
    available: false,
    error: null,
    nowMs: 1791288000000,
  }),
}));
afterEach(cleanup);
it('returns the new borrowed SIGMET view during the route-change render before effects publish', () => {
  const seen: AviationLayerView[] = [];
  const first: AviationLayerView = { state: 'current' },
    next: AviationLayerView = { state: 'loading' };
  const hook = renderHook(
    ({ view }) => {
      const result = useAviationWeather(view);
      seen.push(result.layers.sigmet);
      return result;
    },
    { initialProps: { view: first } }
  );
  seen.length = 0;
  hook.rerender({ view: next });
  expect(seen[0]).toBe(next);
  hook.unmount();
});

it('uses anchored source UTC for external SIGMET eligibility when station catalogs are off', () => {
  const view: AviationLayerView = { state: 'current' };
  const hook = renderHook(() => useAviationWeather(view));
  expect(hook.result.current.now).toBe(1791288000000);
  hook.unmount();
});
