// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TransportAvailabilityControls } from './TransportAvailabilityControls';
import {
  transportAvailabilityApi,
  type AvailabilityView,
} from '@/services/transportAvailability';
vi.mock('@/services/transportAvailability', async (load) => ({
  ...(await load<object>()),
  transportAvailabilityApi: { read: vi.fn(), update: vi.fn(), action: vi.fn() },
}));
export const initial: AvailabilityView = {
  mission_id: 'm',
  revision: 0,
  defaults: { X: true, Ka: true, Ku: true },
  leg_overrides: { l: {} },
  history: [],
  simulation_run_id: null,
  as_of: '2026-10-25T12:00:00Z',
  active_leg_id: 'l',
  effective: { X: true, Ka: true, Ku: true },
  operator_actions_allowed: true,
  operator_actions_unavailable_reason: null,
  legs: [
    {
      leg_id: 'l',
      planned: { X: true, Ka: true, Ku: true },
      effective: { X: true, Ka: true, Ku: true },
      overrides: {},
    },
  ],
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(transportAvailabilityApi.read).mockResolvedValue(initial);
});
afterEach(cleanup);
function mount(legId?: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <TransportAvailabilityControls missionId="m" legId={legId} />
    </QueryClientProvider>
  );
  return client;
}
it('mission_defaults_and_leg_inheritance', async () => {
  vi.mocked(transportAvailabilityApi.update).mockResolvedValue({
    ...initial,
    revision: 1,
    defaults: { X: false, Ka: true, Ku: true },
  });
  const client = mount();
  fireEvent.change(await screen.findByLabelText('X-band'), {
    target: { value: 'unavailable' },
  });
  expect(screen.getByLabelText('Ka')).toBeTruthy();
  expect(screen.getByLabelText('Starshield')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByText('Availability saved. Profiles regenerated.');
  expect(transportAvailabilityApi.update).toHaveBeenCalledWith(
    'm',
    expect.objectContaining({ expected_revision: 0, defaults: { X: false } })
  );
  cleanup();
  client.clear();
  mount('l');
  expect(await screen.findByLabelText('X-band')).toHaveProperty(
    'value',
    'inherit'
  );
  fireEvent.change(screen.getByLabelText('Ka'), {
    target: { value: 'unavailable' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await waitFor(() =>
    expect(transportAvailabilityApi.update).toHaveBeenLastCalledWith(
      'm',
      expect.objectContaining({ leg_overrides: { l: { Ka: false } } })
    )
  );
});
it('save_failure_retains_confirmed_state_and_reuses_command_on_retry', async () => {
  vi.mocked(transportAvailabilityApi.update)
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({
      ...initial,
      revision: 1,
      defaults: { ...initial.defaults, X: false },
    });
  const client = mount();
  fireEvent.change(await screen.findByLabelText('X-band'), {
    target: { value: 'unavailable' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByRole('alert');
  expect(client.getQueryData(['transport-availability', 'm'])).toEqual(initial);
  expect(screen.getByLabelText('X-band')).toHaveProperty(
    'value',
    'unavailable'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByText('Availability saved. Profiles regenerated.');
  const calls = vi.mocked(transportAvailabilityApi.update).mock.calls;
  expect(calls[1][1].command_id).toBe(calls[0][1].command_id);
});

it('leg_inheritance_saves_an_empty_override_map', async () => {
  const saved = {
    ...initial,
    leg_overrides: { l: { X: false } },
    legs: [
      {
        ...initial.legs[0],
        overrides: { X: false },
        planned: { ...initial.legs[0].planned, X: false },
      },
    ],
  };
  vi.mocked(transportAvailabilityApi.read).mockResolvedValue(saved);
  vi.mocked(transportAvailabilityApi.update).mockResolvedValue({
    ...initial,
    revision: 1,
  });
  mount('l');
  fireEvent.change(await screen.findByLabelText('X-band'), {
    target: { value: 'inherit' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByText('Availability saved. Profiles regenerated.');
  expect(transportAvailabilityApi.update).toHaveBeenCalledWith(
    'm',
    expect.objectContaining({ leg_overrides: { l: {} } })
  );
});
it('stale_revision_keeps_edits_and_retries_against_refreshed_confirmed_revision', async () => {
  const latest = {
    ...initial,
    revision: 3,
    defaults: { ...initial.defaults, Ku: false },
  };
  vi.mocked(transportAvailabilityApi.update)
    .mockRejectedValueOnce({ response: { status: 409 } })
    .mockResolvedValueOnce({
      ...latest,
      revision: 4,
      defaults: { ...latest.defaults, X: false },
    });
  const client = mount();
  fireEvent.change(await screen.findByLabelText('X-band'), {
    target: { value: 'unavailable' },
  });
  vi.mocked(transportAvailabilityApi.read).mockResolvedValue(latest);
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByRole('alert');
  expect(client.getQueryData(['transport-availability', 'm'])).toEqual(latest);
  expect(screen.getByLabelText('X-band')).toHaveProperty(
    'value',
    'unavailable'
  );
  expect(screen.getByLabelText('Starshield')).toHaveProperty(
    'value',
    'unavailable'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save availability' }));
  await screen.findByText('Availability saved. Profiles regenerated.');
  const calls = vi.mocked(transportAvailabilityApi.update).mock.calls;
  expect(calls[1][1].expected_revision).toBe(3);
  expect(calls[1][1].command_id).not.toBe(calls[0][1].command_id);
});
