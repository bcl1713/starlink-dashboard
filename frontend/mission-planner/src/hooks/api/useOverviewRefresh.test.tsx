/** @vitest-environment jsdom */
import { createElement, StrictMode, type PropsWithChildren } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useOverviewClockSettings } from './useOverviewClockSettings';
import { useOverviewHistorySettings } from './useOverviewHistorySettings';
import { useOverviewHistory } from './useOverviewHistory';
import { useOverviewLinkSettings } from './useOverviewLinkSettings';
import { useRoutes, useRoute } from './useRoutes';
import { useSatellites } from './useSatellites';

vi.mock('@/services/api-client', () => {
  const client = { get: vi.fn() };
  return { default: client, apiClient: client };
});
const cases: Array<{
  name: string;
  endpoint: string;
  interval?: number;
  use: () => { data: unknown };
}> = [
  {
    name: 'clocks',
    endpoint: '/api/overview-clocks/settings',
    use: () => useOverviewClockSettings(true),
  },
  {
    name: 'history settings',
    endpoint: '/api/overview-history/settings',
    use: () => useOverviewHistorySettings(true),
  },
  {
    name: 'history bundle',
    interval: 1000,
    endpoint: '/api/overview-history',
    use: useOverviewHistory,
  },
  {
    name: 'link settings',
    endpoint: '/api/overview-links/settings',
    use: () => useOverviewLinkSettings(true),
  },
  { name: 'route list', endpoint: '/api/routes', use: () => useRoutes(true) },
  {
    name: 'route detail',
    endpoint: '/api/routes/active',
    use: () => useRoute('active', true),
  },
  {
    name: 'satellites',
    endpoint: '/api/satellites',
    use: () => useSatellites(true),
  },
];
let client: QueryClient;
let wrapper: (props: PropsWithChildren) => ReturnType<typeof createElement>;
let revision: number;
function payload(endpoint: string) {
  if (endpoint === '/api/overview-clocks/settings')
    return { clocks: [{ label: `Clock ${revision}`, time_zone: 'UTC' }] };
  if (endpoint === '/api/overview-history/settings')
    return { window_seconds: revision === 1 ? 300 : 600 };
  if (endpoint === '/api/overview-history')
    return {
      window_seconds: 300,
      start_timestamp_seconds: 0,
      end_timestamp_seconds: revision * 5,
      step_seconds: 5,
      series: { latency: [[revision * 5, 54]] },
    };
  if (endpoint === '/api/routes')
    return {
      routes: [
        { id: `route-${revision}`, name: 'Confirmed route', is_active: true },
      ],
      total: 1,
    };
  if (endpoint === '/api/routes/active')
    return {
      id: 'active',
      name: 'Confirmed route',
      points: [
        { latitude: 35, longitude: -100 },
        { latitude: 40 + revision, longitude: -80 },
      ],
    };
  if (endpoint === '/api/overview-links/settings')
    return {
      starshield_link_enabled: revision === 1,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
      aircraft_history_enabled: true,
      country_borders_enabled: false,
      state_borders_enabled: false,
    };
  if (endpoint === '/api/satellites')
    return [
      {
        satellite_id: `X-${revision}`,
        transport: 'X',
        longitude: -70,
        slot: null,
        color: '#a855f7',
      },
    ];
  throw new Error(`Unexpected GET ${endpoint}`);
}
async function tick(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  revision = 1;
  focusManager.setFocused(false);
  onlineManager.setOnline(true);
  client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity, retry: false } },
  });
  wrapper = ({ children }) =>
    createElement(QueryClientProvider, { client }, children);
  vi.mocked(apiClient.get).mockImplementation(async (endpoint) => ({
    data: payload(endpoint),
  }));
});
afterEach(() => {
  cleanup();
  client.clear();
  focusManager.setFocused(undefined);
  onlineManager.setOnline(true);
  vi.useRealTimers();
});

describe('Overview saved-state refresh', () => {
  it.each(cases)(
    'refreshes $name at its default cadence without focus, then releases its timer',
    async ({ use, endpoint, interval = 5000 }) => {
      const { result, unmount } = renderHook(use, { wrapper });
      await tick(1);
      const initial = result.current.data;
      expect(initial).toBeDefined();
      expect(apiClient.get).toHaveBeenCalledTimes(1);
      revision = 2;
      await tick(interval - 2);
      expect(apiClient.get).toHaveBeenCalledTimes(1);
      await tick(2);
      expect(apiClient.get).toHaveBeenCalledTimes(2);
      expect(apiClient.get).toHaveBeenLastCalledWith(endpoint, {
        signal: expect.any(AbortSignal),
      });
      await tick(1);
      expect(result.current.data).not.toEqual(initial);
      unmount();
      await tick(15000);
      expect(apiClient.get).toHaveBeenCalledTimes(2);
    }
  );

  it.each([
    useOverviewClockSettings,
    useOverviewHistorySettings,
    useRoutes,
    useSatellites,
  ])('keeps non-live observers free of periodic refresh', async (use) => {
    renderHook(
      () => {
        use();
      },
      { wrapper }
    );
    await tick(1);
    await tick(15000);
    expect(apiClient.get).toHaveBeenCalledTimes(1);
  });

  it('never reads an empty route ID even with live refresh', async () => {
    renderHook(() => useRoute('', true), { wrapper });
    await tick(15000);
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it('deduplicates shared-key observers and does not overlap a pending read', async () => {
    let release!: (value: { data: unknown }) => void;
    vi.mocked(apiClient.get).mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      })
    );
    const first = renderHook(() => useOverviewClockSettings(true), { wrapper });
    const second = renderHook(() => useOverviewClockSettings(true), {
      wrapper,
    });
    await tick(15000);
    expect(apiClient.get).toHaveBeenCalledTimes(1);
    await act(async () => {
      release({ data: payload('/api/overview-clocks/settings') });
    });
    await tick(1);
    vi.mocked(apiClient.get).mockImplementation(async (endpoint) => ({
      data: payload(endpoint),
    }));
    revision = 2;
    await tick(5001);
    expect(apiClient.get).toHaveBeenCalledTimes(2);
    expect(first.result.current.data).toEqual({
      clocks: [{ label: 'Clock 2', time_zone: 'UTC' }],
    });
    expect(second.result.current.data).toEqual(first.result.current.data);
  });

  it.each(cases.filter(({ name }) => name !== 'history bundle'))(
    'catches up $name on focus and network recovery even with fresh cache',
    async ({ use }) => {
      client.setDefaultOptions({
        queries: { staleTime: Infinity, gcTime: Infinity, retry: false },
      });
      const { result } = renderHook(use, { wrapper });
      await tick(1);
      const initial = result.current.data;
      revision = 2;
      await act(async () => {
        focusManager.setFocused(true);
      });
      await tick(1);
      expect(apiClient.get).toHaveBeenCalledTimes(2);
      expect(result.current.data).not.toEqual(initial);
      revision = 3;
      await act(async () => {
        onlineManager.setOnline(false);
        onlineManager.setOnline(true);
      });
      await tick(1);
      expect(apiClient.get).toHaveBeenCalledTimes(3);
    }
  );

  it.each(cases)(
    'aborts an in-flight $name read when its final observer unmounts',
    async ({ use }) => {
      vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}));
      const { unmount } = renderHook(use, { wrapper });
      await tick(1);
      const signal = vi.mocked(apiClient.get).mock.calls[0][1]?.signal;
      expect(signal).toBeInstanceOf(AbortSignal);
      unmount();
      expect(signal?.aborted).toBe(true);
    }
  );

  it.each(
    cases.filter(({ name }) => name.includes('settings') || name === 'clocks')
  )(
    'retains confirmed $name during a failed refresh and catches up on the next background read',
    async ({ use, endpoint }) => {
      const { result } = renderHook(use, { wrapper });
      await tick(1);
      const confirmed = result.current.data;
      revision = 2;
      vi.mocked(apiClient.get).mockRejectedValueOnce(
        new Error('temporary outage')
      );
      await tick(5001);
      expect(
        client.getQueryState(
          endpoint.includes('clocks')
            ? ['overview-clock-settings']
            : endpoint.includes('history')
              ? ['overview-history-settings']
              : ['overview-link-settings']
        )?.status
      ).toBe('error');
      expect(result.current.data).toEqual(confirmed);
      await tick(5001);
      expect(result.current.data).toMatchObject(payload(endpoint) as object);
      expect(result.current.data).not.toEqual(confirmed);
      expect(focusManager.isFocused()).toBe(false);
    }
  );

  it('cannot reactivate the old route when its delayed detail arrives after a list switch', async () => {
    let releaseOld!: (value: { data: unknown }) => void;
    const oldRead = new Promise<{ data: unknown }>((resolve) => {
      releaseOld = resolve;
    });
    const routeA = {
      id: 'route-a',
      name: 'Old active route',
      points: [{ latitude: 35, longitude: -100 }],
    };
    const routeB = {
      id: 'route-b',
      name: 'New active route',
      points: [{ latitude: 42, longitude: -70 }],
    };
    let activeId = 'route-a';
    let oldSignal: AbortSignal | undefined;
    vi.mocked(apiClient.get).mockImplementation(async (endpoint, options) => {
      if (endpoint === '/api/routes')
        return {
          data: {
            routes: [
              {
                id: 'route-a',
                name: routeA.name,
                point_count: 1,
                is_active: activeId === 'route-a',
              },
              {
                id: 'route-b',
                name: routeB.name,
                point_count: 1,
                is_active: activeId === 'route-b',
              },
            ],
            total: 2,
          },
        };
      if (endpoint === '/api/routes/route-a') {
        oldSignal = options?.signal as AbortSignal;
        return oldRead;
      }
      if (endpoint === '/api/routes/route-b') return { data: routeB };
      throw new Error(`Unexpected route read ${endpoint}`);
    });
    const { result } = renderHook(
      () => {
        const list = useRoutes(true);
        const active = list.data?.find((route) => route.is_active)?.id ?? '';
        return { active, detail: useRoute(active, true) };
      },
      { wrapper }
    );
    await tick(5);
    expect(result.current.active).toBe('route-a');
    expect(oldSignal?.aborted).toBe(false);
    activeId = 'route-b';
    await tick(5005);
    expect(result.current.active).toBe('route-b');
    expect(result.current.detail.data).toEqual(routeB);
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      releaseOld({ data: routeA });
    });
    await tick(1);
    expect(result.current.active).toBe('route-b');
    expect(result.current.detail.data).toEqual(routeB);
  });

  it('StrictMode retains one live observer and no timer after cleanup', async () => {
    const strictWrapper = ({ children }: PropsWithChildren) =>
      createElement(
        StrictMode,
        null,
        createElement(QueryClientProvider, { client }, children)
      );
    const { unmount } = renderHook(() => useOverviewClockSettings(true), {
      wrapper: strictWrapper,
    });
    await tick(1);
    const reads = vi.mocked(apiClient.get).mock.calls.length;
    await tick(5001);
    expect(apiClient.get).toHaveBeenCalledTimes(reads + 1);
    unmount();
    await tick(15000);
    expect(apiClient.get).toHaveBeenCalledTimes(reads + 1);
  });
});
