/** @vitest-environment jsdom */
import { createElement, StrictMode, type PropsWithChildren } from 'react';
import { cleanup, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { useOrbitalTraffic } from './useOrbitalTraffic';
import { orbitalCatalogApi } from '@/services/orbital-catalog';
vi.mock('@/services/orbital-catalog', () => ({
  orbitalCatalogApi: { acquire: vi.fn(), catalog: vi.fn(), release: vi.fn() },
}));
afterEach(() => cleanup());
it('off/unconfirmed hook mounts allocate no worker, lease or timer under StrictMode', () => {
  const worker = vi.fn();
  vi.stubGlobal('Worker', worker);
  const client = new QueryClient();
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(
      StrictMode,
      null,
      createElement(QueryClientProvider, { client }, children)
    );
  const f = renderHook(
    () =>
      useOrbitalTraffic({
        settings: undefined,
        endpoints: { aircraft: null, pop: null },
      }),
    { wrapper }
  );
  expect(f.result.current.spritesReady).toBe(false);
  expect(f.result.current.status.kind).toBe('off');
  expect(worker).not.toHaveBeenCalled();
  expect(orbitalCatalogApi.acquire).not.toHaveBeenCalled();
  f.unmount();
  client.clear();
  vi.unstubAllGlobals();
});
