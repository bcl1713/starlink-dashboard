/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { OrbitalTrafficDiagnostics } from './OrbitalTrafficDiagnostics';
import { orbitalCatalogApi } from '@/services/orbital-catalog';
vi.mock('@/services/orbital-catalog', () => ({
  orbitalCatalogApi: { status: vi.fn(), resume: vi.fn(), acquire: vi.fn() },
}));
afterEach(() => cleanup());
it('configuration_only_diagnostics explains provenance and operator resume creates no demand', async () => {
  const data = {
    status: 'provider-suspended',
    suspended: true,
    eligible_count: 8,
    rejected_count: 2,
    truncated_count: 1,
    acquired_at: '2026-10-04T12:00:00Z',
    last_attempt_at: '2026-10-04T12:00:00Z',
    retry_after_at: '2026-10-04T15:00:00Z',
  };
  vi.mocked(orbitalCatalogApi.status).mockResolvedValue(data as never);
  vi.mocked(orbitalCatalogApi.resume).mockResolvedValue(data as never);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <OrbitalTrafficDiagnostics />
    </QueryClientProvider>
  );
  expect(screen.getByText(/Public Starlink elements/i)).toBeInTheDocument();
  expect(screen.getByText(/inferred routing/i)).toBeInTheDocument();
  expect(screen.getByText(/abstract PoP/i)).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByText(/Eligible objects: 8/)).toBeInTheDocument()
  );
  expect(screen.getByText(/Truncated: 1/)).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Resume orbital provider' })
  );
  await waitFor(() =>
    expect(orbitalCatalogApi.resume).toHaveBeenCalledTimes(1)
  );
  expect(orbitalCatalogApi.acquire).not.toHaveBeenCalled();
  client.clear();
});

it('does not invent an arc fallback for the last successful inferred route', async () => {
  vi.mocked(orbitalCatalogApi.status).mockResolvedValue({
    status: 'ready',
    eligible_count: 1,
    suspended: false,
    fallback_reason: null,
  } as never);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(['orbital-runtime-status'], {
    kind: 'ready',
    diagnostics: null,
    reason: null,
  });
  render(
    <QueryClientProvider client={client}>
      <OrbitalTrafficDiagnostics />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      screen.getByText(/Arc fallback reason: None in last Overview observation/)
    ).toBeInTheDocument()
  );
  expect(screen.queryByText(/No usable inferred route/)).toBeNull();
  client.clear();
});
