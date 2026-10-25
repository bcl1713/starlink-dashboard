// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTransportAvailability } from './useTransportAvailability';
import {
  transportAvailabilityApi,
  type AvailabilityView,
} from '@/services/transportAvailability';
vi.mock('@/services/transportAvailability', async (load) => ({
  ...(await load<object>()),
  transportAvailabilityApi: { read: vi.fn(), update: vi.fn(), action: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const initial: AvailabilityView = {
  mission_id: 'm',
  revision: 0,
  defaults: {},
  leg_overrides: {},
  history: [],
  simulation_run_id: 'run-a',
  as_of: '2026-10-25T12:00:00Z',
  active_leg_id: 'l',
  effective: { X: true, Ka: true, Ku: true },
  operator_actions_allowed: true,
  operator_actions_unavailable_reason: null,
  legs: [],
};
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const hook = renderHook(() => useTransportAvailability('m'), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  return { ...hook, client };
}
it('partitions_ambiguous_action_retries_by_current_simulation_run', async () => {
  let current = initial;
  vi.mocked(transportAvailabilityApi.read).mockImplementation(
    async () => current
  );
  vi.mocked(transportAvailabilityApi.action)
    .mockRejectedValueOnce(new Error('offline'))
    .mockImplementationOnce(async () => ({ ...current, revision: 1 }));
  const { result } = mount();
  await waitFor(() => expect(result.current.data).toBeTruthy());
  await act(async () => {
    await expect(
      result.current.act({ transport: 'X', action: 'unavailable' })
    ).rejects.toThrow('offline');
  });
  current = { ...initial, simulation_run_id: 'run-b' };
  await act(async () => {
    await result.current.refetch();
  });
  await act(async () => {
    await result.current.act({ transport: 'X', action: 'unavailable' });
  });
  const calls = vi.mocked(transportAvailabilityApi.action).mock.calls;
  expect(calls[0][1]).toMatchObject({ expected_simulation_run_id: 'run-a' });
  expect(calls[1][1]).toMatchObject({ expected_simulation_run_id: 'run-b' });
  expect(calls[1][1].command_id).not.toBe(calls[0][1].command_id);
});
it('does_not_report_success_for_a_response_from_a_replaced_run', async () => {
  let current = initial;
  vi.mocked(transportAvailabilityApi.read).mockImplementation(
    async () => current
  );
  vi.mocked(transportAvailabilityApi.action).mockImplementation(async () => {
    current = { ...initial, revision: 1, simulation_run_id: 'run-b' };
    return { ...initial, revision: 1 };
  });
  const { result } = mount();
  await waitFor(() => expect(result.current.data).toBeTruthy());
  await act(async () => {
    await expect(
      result.current.act({ transport: 'Ka', action: 'unavailable' })
    ).rejects.toThrow('Mission run changed');
  });
  await waitFor(() =>
    expect(result.current.data?.simulation_run_id).toBe('run-b')
  );
  expect(result.current.data?.effective?.Ka).toBe(true);
});
it('refreshes_guarded_receipt_after_wrapped_http_conflict_but_keeps_network_retries', async () => {
  let current = initial;
  vi.mocked(transportAvailabilityApi.read).mockImplementation(
    async () => current
  );
  const wrapped = new Error('stale revision');
  wrapped.cause = { response: { status: 409 } };
  vi.mocked(transportAvailabilityApi.update)
    .mockImplementationOnce(async () => {
      current = { ...initial, revision: 1 };
      throw wrapped;
    })
    .mockRejectedValueOnce(new Error('connection lost'))
    .mockImplementationOnce(async () => ({ ...current, revision: 2 }));
  const { result } = mount();
  await waitFor(() => expect(result.current.data).toBeTruthy());
  for (const message of ['stale revision', 'connection lost'])
    await act(async () => {
      await expect(
        result.current.savePlanned({ defaults: { X: false } })
      ).rejects.toThrow(message);
    });
  await act(async () => {
    await result.current.savePlanned({ defaults: { X: false } });
  });
  const calls = vi.mocked(transportAvailabilityApi.update).mock.calls;
  expect(calls[1][1].command_id).not.toBe(calls[0][1].command_id);
  expect(calls[1][1].expected_revision).toBe(1);
  expect(calls[2][1]).toEqual(calls[1][1]);
});
