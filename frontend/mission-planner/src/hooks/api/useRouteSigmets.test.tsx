// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { expect, it, vi } from 'vitest';
import {
  useRouteSigmets,
  useSetSigmetAcknowledgement,
} from './useRouteSigmets';
import { aviationWeatherApi } from '@/services/aviation-weather';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import type { ReactNode } from 'react';
it('Configuration alone loads reports and two hook readers share one route request', async () => {
  const { snapshot, bytes } = routeSnapshot();
  const settings = vi
    .spyOn(aviationWeatherApi, 'getSettings')
    .mockResolvedValue({
      metar: false,
      taf: false,
      departure_weather: false,
      arrival_weather: false,
      sigmet: true,
      sigmet_intersecting_only: false,
      winds: false,
      temperature: false,
      gfs_selection: {
        vertical: { kind: 'pressure', pressure_pa: 50000 },
        horizon_hours: 0,
      },
      revision: 1,
    });
  const response = (data: unknown) => {
    const text = JSON.stringify(data);
    return new Response(text, {
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': String(text.length),
      },
    });
  };
  const fetcher = vi.fn(async (p: RequestInfo | URL) =>
    String(p).endsWith('.json')
      ? new Response(bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
      : String(p).endsWith('acknowledgement')
        ? response({
            context_key: hash('c'),
            notice_key: hash('d'),
            semantic_digest: hash('f'),
            acknowledged: true,
            state_revision: 2,
            attention_order: 1,
          })
        : response(snapshot)
  );
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(
    () => ({
      configuration: useRouteSigmets(),
      overview: useRouteSigmets(),
      mutation: useSetSigmetAcknowledgement(),
    }),
    { wrapper }
  );
  try {
    await waitFor(() =>
      expect(
        hook.result.current.configuration.collection?.features
      ).toHaveLength(1)
    );
    expect(hook.result.current.configuration).toBe(
      hook.result.current.overview
    );
    expect(
      fetcher.mock.calls.filter(([p]) => String(p).endsWith('route-sigmets'))
    ).toHaveLength(1);
    await act(() =>
      hook.result.current.mutation.mutateAsync({
        context_key: hash('c'),
        notice_key: hash('d'),
        semantic_digest: hash('f'),
        acknowledged: true,
      })
    );
    expect(
      hook.result.current.configuration.snapshot?.entries[0].acknowledged
    ).toBe(true);
  } finally {
    hook.unmount();
    client.clear();
    settings.mockRestore();
    vi.unstubAllGlobals();
  }
});
