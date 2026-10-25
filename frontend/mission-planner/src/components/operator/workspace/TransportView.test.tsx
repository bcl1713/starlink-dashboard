// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OperatorTransportAvailability } from './OperatorTransportAvailability';
import {
  transportAvailabilityApi,
  type AvailabilityView,
} from '@/services/transportAvailability';
vi.mock('@/services/transportAvailability', async (load) => ({
  ...(await load<object>()),
  transportAvailabilityApi: { read: vi.fn(), update: vi.fn(), action: vi.fn() },
}));
const initial: AvailabilityView = {
  mission_id: 'm',
  revision: 0,
  defaults: { X: true, Ka: true, Ku: false },
  leg_overrides: {},
  history: [],
  simulation_run_id: null,
  as_of: '2026-10-25T12:00:00Z',
  active_leg_id: 'l',
  effective: { X: true, Ka: true, Ku: false },
  operator_actions_allowed: true,
  operator_actions_unavailable_reason: null,
  legs: [
    {
      leg_id: 'l',
      planned: { X: true, Ka: true, Ku: false },
      effective: { X: true, Ka: true, Ku: false },
      overrides: {},
    },
  ],
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(transportAvailabilityApi.read).mockResolvedValue(initial);
});
afterEach(cleanup);
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <OperatorTransportAvailability missionId="m" />
    </QueryClientProvider>
  );
}
it('operator_failure_and_restore_are_explicit_and_reason_optional', async () => {
  const failed = {
    ...initial,
    revision: 1,
    effective: { X: false, Ka: true, Ku: false },
    history: [
      {
        id: 'f',
        transport: 'X' as const,
        unavailable: true,
        effective_at: initial.as_of!,
        simulation_run_id: null,
      },
    ],
  };
  vi.mocked(transportAvailabilityApi.action)
    .mockImplementationOnce(async () => {
      vi.mocked(transportAvailabilityApi.read).mockResolvedValue(failed);
      return failed;
    })
    .mockImplementationOnce(async () => {
      const restored = { ...initial, revision: 2 };
      vi.mocked(transportAvailabilityApi.read).mockResolvedValue(restored);
      return restored;
    });
  mount();
  const row = await screen.findByRole('group', { name: 'X-band availability' });
  fireEvent.click(
    within(row).getByRole('button', { name: 'Unavailable for rest of mission' })
  );
  await within(row).findByRole('button', { name: 'Restore' });
  expect(transportAvailabilityApi.action).toHaveBeenCalledWith(
    'm',
    expect.objectContaining({ transport: 'X', action: 'unavailable' })
  );
  fireEvent.click(within(row).getByRole('button', { name: 'Restore' }));
  await within(row).findByText('Available');
  expect(transportAvailabilityApi.action).toHaveBeenLastCalledWith(
    'm',
    expect.objectContaining({
      transport: 'X',
      action: 'restore',
      expected_revision: 1,
    })
  );
});
it('planned_unavailable_remains_after_restore_and_other_run_failure_is_ignored', async () => {
  vi.mocked(transportAvailabilityApi.read).mockResolvedValue({
    ...initial,
    history: [
      {
        id: 'old',
        transport: 'X',
        unavailable: true,
        effective_at: initial.as_of!,
        simulation_run_id: 'other',
      },
      {
        id: 'f',
        transport: 'Ku',
        unavailable: true,
        effective_at: initial.as_of!,
        simulation_run_id: null,
      },
    ],
  });
  vi.mocked(transportAvailabilityApi.action).mockImplementation(async () => {
    const restored = { ...initial, revision: 1 };
    vi.mocked(transportAvailabilityApi.read).mockResolvedValue(restored);
    return restored;
  });
  mount();
  const row = await screen.findByRole('group', {
    name: 'Starshield availability',
  });
  expect(
    within(
      await screen.findByRole('group', { name: 'X-band availability' })
    ).queryByRole('button', { name: 'Restore' })
  ).toBeNull();
  fireEvent.click(within(row).getByRole('button', { name: 'Restore' }));
  await within(row).findByText('Planned unavailable');
  expect(within(row).queryByRole('button', { name: 'Restore' })).toBeNull();
});
