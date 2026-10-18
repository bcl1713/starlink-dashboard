/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { missionsApi } from '@/services/missions';
import type { Mission } from '@/types/mission';
import { MissionContextChooser } from './MissionContextChooser';

const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
});
it('selects readable mission names without activating an aircraft leg', async () => {
  const mission: Mission = {
    id: 'mission-a',
    name: 'Synthetic mission with a long readable operational name',
    legs: [],
    created_at: '',
    updated_at: '',
    metadata: {},
  };
  vi.spyOn(missionsApi, 'listPage').mockResolvedValue({
    missions: [mission],
    total: 1,
  });
  const activate = vi.spyOn(missionsApi, 'activateLeg');
  const change = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MissionContextChooser missionId="" onChange={change} />
    </QueryClientProvider>
  );
  expect(
    await screen.findByRole('option', { name: mission.name })
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Mission'), {
    target: { value: mission.id },
  });
  expect(change).toHaveBeenCalledWith(mission.id);
  expect(activate).not.toHaveBeenCalled();
});
