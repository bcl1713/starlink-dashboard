/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import * as operator from '@/services/operator';
import * as events from '@/services/operatorEvents';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import { useOverviewAdvisories } from './useOverviewAdvisories';
const now = Date.parse('2026-10-17T16:00:00Z');
const clients: QueryClient[] = [];
const active = {
  state: 'available',
  mission_id: 'mission-a',
  mission_name: '',
  leg_id: 'leg-a',
  leg_name: '',
  phase: 'in_flight',
  source_mode: 'live' as const,
  replay_run_id: null,
  operating_context_id: 'ctx-a',
};
const health = {
  schema_version: 1 as const,
  enabled: true,
  ready: true,
  store_id: 'store',
  api_epoch: 'epoch-a',
  source_mode: 'live' as const,
  simulation_run_id: 'journal',
  clock_regression: false,
  error_code: null,
  mission_journal: true,
  operating_context_id: 'ctx-a',
  replay_run_id: null,
};
const data = () =>
  eventSnapshot({
    simulation_run_id: 'ctx-a',
    coverage: 'available',
    sources: [
      {
        source: 'model:leg-a',
        revision: '1',
        generation: '1',
        input_identity: 'route',
        captured_at: '2026-10-17T16:00:00Z',
        freshness: 'fresh',
        aligned: true,
        guardable: true,
        reason: null,
      },
    ],
    events: [
      eventFixture({
        leg_id: 'leg-a',
        operating_context_id: 'ctx-a',
        replay_run_id: null,
        kind: 'restriction',
        significance: 'unavailable',
        transport: 'Ka',
        title: 'KA Service Interruption Expected',
        provenance: 'modeled',
        source_ref: 'model:leg-a',
      }),
    ],
  });
function setup() {
  vi.spyOn(operator, 'readOperatingContext').mockResolvedValue(active);
  vi.spyOn(operator, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(events, 'readEventSnapshot').mockResolvedValue(data());
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  const hook = renderHook(() => useOverviewAdvisories(now), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  return { client, hook };
}
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
it('reads active context only and never mounts mutation/audio controllers; hides on 503 without raw fallback', async () => {
  const post = vi.spyOn(events, 'acknowledgeOperatorEvent');
  const { client, hook } = setup();
  await waitFor(() => expect(hook.result.current.items).toHaveLength(1));
  expect(events.readEventSnapshot).toHaveBeenCalledWith(
    'mission-a',
    expect.any(AbortSignal)
  );
  expect(post).not.toHaveBeenCalled();
  vi.mocked(events.readEventSnapshot).mockRejectedValue(
    new Error('503 unavailable')
  );
  await act(async () => {
    await client.refetchQueries({ queryKey: ['overview-advisories'] });
  });
  await waitFor(() =>
    expect(hook.result.current).toMatchObject({
      items: [],
      notice: 'Transport Advisories Unavailable',
    })
  );
});
it('removes a confirmed acknowledgment on refresh and survives a new reader', async () => {
  const { client, hook } = setup();
  await waitFor(() => expect(hook.result.current.items).toHaveLength(1));
  const acknowledged = data();
  acknowledged.events[0].notification.acknowledged = true;
  vi.mocked(events.readEventSnapshot).mockResolvedValue(acknowledged);
  await act(async () => {
    await client.refetchQueries({ queryKey: ['overview-advisories'] });
  });
  await waitFor(() => expect(hook.result.current.items).toHaveLength(0));
  expect(hook.result.current.notice).toBeNull();
});
it('quarantines old store results and does not leak a late response after active-leg switch', async () => {
  const { client, hook } = setup();
  await waitFor(() => expect(hook.result.current.items).toHaveLength(1));
  let resolve!: (value: ReturnType<typeof data>) => void;
  vi.mocked(events.readEventSnapshot).mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      })
  );
  let pending!: Promise<void>;
  await act(async () => {
    pending = client.refetchQueries({ queryKey: ['overview-advisories'] });
  });
  vi.mocked(operator.readOperatingContext).mockResolvedValue({
    ...active,
    leg_id: 'leg-b',
  });
  vi.mocked(events.readEventSnapshot).mockResolvedValue(
    eventSnapshot({ ...data(), store_id: 'wrong-store' })
  );
  await act(async () => {
    await client.refetchQueries({ queryKey: ['operator-operating-context'] });
  });
  await waitFor(() => expect(hook.result.current.items).toHaveLength(0));
  await act(async () => {
    resolve(data());
    await pending;
  });
  await waitFor(() =>
    expect(hook.result.current).toMatchObject({
      items: [],
      notice: 'Transport Advisories Unavailable',
    })
  );
});
