/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { ManualXBandSelectionCard } from './ManualXBandSelectionCard';
import { OverviewPlannedSatelliteCard } from './OverviewPlannedSatelliteCard';
import { derivePlannedSatelliteState } from './overview-planned-satellite';

vi.mock('@/services/api-client', () => {
  const client = { get: vi.fn(), put: vi.fn() };
  return { default: client, apiClient: client };
});
let selection: {
  satellite_id: string | null;
  manual_satellite_id: string | null;
  selection_source: 'none' | 'manual' | 'mission';
  manual_selection_invalid: boolean;
};
let satellites: {
  satellite_id: string;
  transport: string;
  longitude: number;
  color: string;
}[];
const clients: QueryClient[] = [];
beforeEach(() => {
  selection = {
    satellite_id: null,
    manual_satellite_id: null,
    selection_source: 'none',
    manual_selection_invalid: false,
  };
  satellites = [
    { satellite_id: 'X-A', transport: 'X', longitude: 30, color: '#FFFFFF' },
    { satellite_id: 'X-B', transport: 'X', longitude: -70, color: '#FFFFFF' },
    { satellite_id: 'Ka-A', transport: 'Ka', longitude: 60, color: '#FFFFFF' },
  ];
  vi.mocked(apiClient.get).mockImplementation(async (url) => ({
    data: url === '/api/satellites' ? satellites : selection,
  }));
  vi.mocked(apiClient.put).mockImplementation(async (_url, payload) => {
    const { satellite_id: satelliteId } = payload as {
      satellite_id: string | null;
    };
    selection = {
      ...selection,
      satellite_id: satelliteId,
      manual_satellite_id: satelliteId,
      selection_source: satelliteId ? 'manual' : 'none',
      manual_selection_invalid: false,
    };
    return { data: selection };
  });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.resetAllMocks();
});

function Consumer() {
  const query = useActiveXLink();
  return (
    <OverviewPlannedSatelliteCard
      state={derivePlannedSatelliteState(
        query.data,
        query.isLoading,
        query.isError
      )}
    />
  );
}
function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <ManualXBandSelectionCard />
      <Consumer />
    </QueryClientProvider>
  );
  return client;
}
async function selector() {
  const element = screen.getByRole('combobox', {
    name: 'Planned X-band satellite',
  });
  await waitFor(() =>
    expect((element as HTMLSelectElement).disabled).toBe(false)
  );
  return element as HTMLSelectElement;
}

it('switches and clears the confirmed selection consumed by the Overview card', async () => {
  setup();
  const select = await selector();
  expect(screen.queryByRole('option', { name: 'Ka-A' })).toBeNull();
  for (const name of ['X-A', 'X-B']) {
    fireEvent.change(select, { target: { value: name } });
    await waitFor(() => expect(select.value).toBe(name));
    expect(
      screen.getByText(name, { selector: '.overview-planned-satellite__id' })
    ).not.toBeNull();
    expect(apiClient.put).toHaveBeenLastCalledWith(
      '/api/active-x-link/selection',
      { satellite_id: name }
    );
  }
  fireEvent.change(select, { target: { value: '' } });
  await waitFor(() => expect(select.value).toBe(''));
  expect(screen.getByText('NO SATELLITE SELECTED')).not.toBeNull();
});

it('disables manual changes while a mission owns selection', async () => {
  selection = {
    ...selection,
    satellite_id: 'X-B',
    manual_satellite_id: 'X-A',
    selection_source: 'mission',
  };
  setup();
  await screen.findByText(/active mission controls/i);
  const select = screen.getByRole('combobox') as HTMLSelectElement;
  expect(select.disabled).toBe(true);
  expect(select.value).toBe('X-B');
});

it('keeps the confirmed selection visible when saving fails and permits retry', async () => {
  selection = {
    ...selection,
    satellite_id: 'X-A',
    manual_satellite_id: 'X-A',
    selection_source: 'manual',
  };
  vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('offline'));
  setup();
  const select = await selector();
  fireEvent.change(select, { target: { value: 'X-B' } });
  await screen.findByRole('alert');
  expect(select.value).toBe('X-A');
  fireEvent.change(select, { target: { value: 'X-B' } });
  await waitFor(() => expect(select.value).toBe('X-B'));
  expect(screen.queryByRole('alert')).toBeNull();
});

it('reports an empty configuration and disables the picker', async () => {
  satellites = [];
  setup();
  await screen.findByText(/No X-band satellites configured/i);
  expect((screen.getByRole('combobox') as HTMLSelectElement).disabled).toBe(
    true
  );
});

it('reports a removed selection and allows clearing it even with an empty catalog', async () => {
  satellites = [];
  selection = {
    ...selection,
    manual_satellite_id: 'removed',
    manual_selection_invalid: true,
  };
  setup();
  await screen.findByText(/saved satellite is no longer/i);
  fireEvent.click(
    screen.getByRole('button', { name: 'Clear saved selection' })
  );
  await waitFor(() =>
    expect(screen.queryByText(/saved satellite is no longer/i)).toBeNull()
  );
});

it('disables edits when selection refresh becomes unavailable', async () => {
  const client = setup();
  const select = await selector();
  vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'));
  await client.invalidateQueries({ queryKey: ['active-x-link'] });
  await screen.findByText('Satellite selection unavailable');
  expect(select.disabled).toBe(true);
});
