// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { useGfsWeather } from './useGfsWeather';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { gridFixture, GRID_RUN } from '@/test/gfs-grid';
import { optionalWeatherBudget } from '@/pages/aviation-weather/weather-budget';

vi.mock('./api/useAviationSettings', () => ({
  useAviationSettings: () => ({
    data: {
      metar: false,
      taf: false,
      sigmet: false,
      winds: true,
      temperature: false,
      revision: 1,
      gfs_selection: {
        vertical: { kind: 'pressure', pressure_pa: 50000 },
        horizon_hours: 0,
      },
    },
  }),
}));
vi.mock('@/services/aviation-weather', async (original) => {
  const actual = await original<typeof import('@/services/aviation-weather')>();
  return {
    ...actual,
    aviationWeatherApi: { ...actual.aviationWeatherApi, getCatalog: vi.fn() },
  };
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function prepare(reduced: boolean) {
  const f = gridFixture();
  vi.mocked(aviationWeatherApi.getCatalog).mockResolvedValue({
    schema: 'aviation-weather-v1',
    generated_at_ms: GRID_RUN,
    settings_revision: 1,
    products: [f.product],
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => f.response(String(input)))
  );
  const media = Object.assign(new EventTarget(), {
    matches: reduced,
    media: '(prefers-reduced-motion: reduce)',
  });
  vi.stubGlobal('matchMedia', () => media as unknown as MediaQueryList);
  let hidden = false,
    online = true;
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
  vi.spyOn(navigator, 'onLine', 'get').mockImplementation(() => online);
  return {
    media,
    setHidden(value: boolean) {
      hidden = value;
      document.dispatchEvent(new Event('visibilitychange'));
    },
    setOnline(value: boolean) {
      online = value;
      window.dispatchEvent(new Event(value ? 'online' : 'offline'));
    },
  };
}
it('honors reduced motion before admission and changes it without fetching another grid', async () => {
  const p = prepare(true),
    remove = vi.spyOn(p.media, 'removeEventListener');
  const r = renderHook(() => useGfsWeather());
  await waitFor(() => expect(r.result.current.drawing).toBeDefined());
  const drawing = r.result.current.drawing!;
  expect(drawing.object.getObjectByName('GFS wind particles')).toBeUndefined();
  const fetches = vi.mocked(fetch).mock.calls.length;
  act(() => {
    p.media.matches = false;
    p.media.dispatchEvent(new Event('change'));
  });
  await waitFor(() =>
    expect(drawing.object.getObjectByName('GFS wind particles')).toBeTruthy()
  );
  expect(vi.mocked(fetch).mock.calls.length).toBe(fetches);
  act(() => {
    p.media.matches = true;
    p.media.dispatchEvent(new Event('change'));
  });
  await waitFor(() =>
    expect(drawing.object.getObjectByName('GFS wind particles')).toBeUndefined()
  );
  r.unmount();
  expect(remove).toHaveBeenCalled();
  expect(optionalWeatherBudget.snapshot()).toMatchObject({
    decoded: 0,
    gpu: 0,
    encoded: 0,
    slots: 0,
  });
});
it('disposes on hide/offline and reacquires only eligible visible work', async () => {
  const p = prepare(false),
    r = renderHook(() => useGfsWeather());
  await waitFor(() => expect(r.result.current.drawing).toBeDefined());
  act(() => p.setHidden(true));
  await waitFor(() => expect(r.result.current.drawing).toBeUndefined());
  expect(optionalWeatherBudget.snapshot()).toMatchObject({
    decoded: 0,
    gpu: 0,
  });
  act(() => p.setHidden(false));
  await waitFor(() => expect(r.result.current.drawing).toBeDefined());
  act(() => p.setOnline(false));
  await waitFor(() => expect(r.result.current.drawing).toBeUndefined());
  r.unmount();
  expect(optionalWeatherBudget.snapshot()).toMatchObject({
    decoded: 0,
    gpu: 0,
    encoded: 0,
    slots: 0,
  });
});
