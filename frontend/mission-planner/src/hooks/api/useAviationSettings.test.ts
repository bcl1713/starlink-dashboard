/** @vitest-environment jsdom */
import { createElement, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import {
  focusManager,
  onlineManager,
  QueryClientProvider,
} from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createQueryClient } from '@/lib/query-client';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { useAviationSettings } from './useAviationSettings';

vi.mock('@/services/aviation-weather', () => ({
  aviationWeatherApi: { getSettings: vi.fn() },
}));
let client: ReturnType<typeof createQueryClient>;
let hidden: boolean;
beforeEach(() => {
  vi.useFakeTimers();
  focusManager.setFocused(true);
  onlineManager.setOnline(false);
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
  hidden = false;
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
  vi.mocked(aviationWeatherApi.getSettings).mockResolvedValue({
    metar: false,
    taf: false,
    departure_weather: false,
    arrival_weather: false,
    sigmet: false,
    sigmet_intersecting_only: false,
    winds: false,
    temperature: false,
    gfs_selection: {
      vertical: { kind: 'pressure', pressure_pa: 50000 },
      horizon_hours: 0,
    },
    revision: 0,
  });
  client = createQueryClient();
});
afterEach(() => {
  cleanup();
  client.clear();
  onlineManager.setOnline(true);
  focusManager.setFocused(undefined);
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.useRealTimers();
});
it('loads and polls local settings offline while still pausing in hidden documents', async () => {
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  const hook = renderHook(
    () => {
      const query = useAviationSettings();
      return { data: query.data };
    },
    { wrapper }
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(hook.result.current.data).toMatchObject({ metar: false, revision: 0 });
  expect(aviationWeatherApi.getSettings).toHaveBeenCalledTimes(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(aviationWeatherApi.getSettings).toHaveBeenCalledTimes(2);
  await act(async () => {
    hidden = true;
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(aviationWeatherApi.getSettings).toHaveBeenCalledTimes(2);
  await act(async () => {
    hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10);
  });
  expect(
    vi.mocked(aviationWeatherApi.getSettings).mock.calls.length
  ).toBeGreaterThan(2);
});
