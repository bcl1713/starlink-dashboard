/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { useOverviewBoundaries } from './useOverviewBoundaries';
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: 0 } },
  });
  return {
    client,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}
it('does no boundary work when off, aborts its own load on disable, and remains usable after a failure', async () => {
  let signal: AbortSignal | undefined;
  const fetcher = vi.fn((_url, options) => {
    signal = options.signal;
    return new Promise(() => {});
  });
  vi.stubGlobal('fetch', fetcher);
  const { wrapper, client } = setup();
  const { result, rerender } = renderHook(
    ({ enabled }) => useOverviewBoundaries('countries', enabled),
    { wrapper, initialProps: { enabled: false } }
  );
  expect(fetcher).not.toHaveBeenCalled();
  rerender({ enabled: true });
  await waitFor(() => expect(signal).toBeDefined());
  expect(result.current.loading).toBe(true);
  rerender({ enabled: false });
  await waitFor(() => expect(signal?.aborted).toBe(true));
  expect(result.current.data).toBeUndefined();
  fetcher.mockImplementation(() => Promise.reject(new Error('unavailable')));
  rerender({ enabled: true });
  await waitFor(() => expect(result.current.unavailable).toBe(true));
  expect(result.current.data).toBeUndefined();
  client.clear();
});
it('caches immutable boundary data and hides it immediately when disabled', async () => {
  const fetcher = vi.fn(
    async () =>
      new Response(
        JSON.stringify({
          version: 1,
          lines: [
            {
              points: [
                [0, 0],
                [1, 0],
              ],
              disputed: false,
            },
          ],
        })
      )
  );
  vi.stubGlobal('fetch', fetcher);
  const { wrapper, client } = setup();
  const { result, rerender } = renderHook(
    ({ enabled }) => useOverviewBoundaries('countries', enabled),
    { wrapper, initialProps: { enabled: true } }
  );
  await waitFor(() => expect(result.current.data?.lines).toHaveLength(1));
  rerender({ enabled: false });
  expect(result.current.data).toBeUndefined();
  await act(async () => {
    rerender({ enabled: true });
  });
  expect(result.current.data?.lines).toHaveLength(1);
  expect(fetcher).toHaveBeenCalledTimes(1);
  client.clear();
});

it('stops an oversized stream without waiting for its end or Content-Length', async () => {
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array(2_000_001));
      controller.enqueue(new Uint8Array(2_000_001));
      // The server never finishes this body. A post-buffer check cannot protect it.
    },
    cancel() {
      cancelled = true;
    },
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(stream))
  );
  const { wrapper, client } = setup();
  const { result } = renderHook(
    () => useOverviewBoundaries('countries', true),
    { wrapper }
  );
  await waitFor(() => expect(result.current.unavailable).toBe(true));
  expect(cancelled).toBe(true);
  expect(result.current.data).toBeUndefined();
  client.clear();
});
