/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/services/api-client';
import { ManualDestinationSettingsCard } from './ManualDestinationSettingsCard';

vi.mock('@/services/api-client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
const clients: QueryClient[] = [];
let saved: unknown = null;
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <ManualDestinationSettingsCard />
    </QueryClientProvider>
  );
}
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.clearAllMocks();
});
beforeEach(() => {
  saved = null;
  vi.mocked(apiClient.get).mockImplementation(async (url) => ({
    data: url.includes('/airports')
      ? {
          airports: [
            {
              ident: 'EGLL',
              icao_code: 'EGLL',
              iata_code: 'LHR',
              name: 'London Heathrow Airport',
              latitude: 51.47,
              longitude: -0.4543,
              municipality: 'London',
              country: 'GB',
            },
          ],
        }
      : { destination: saved },
  }));
  vi.mocked(apiClient.put).mockImplementation(async (_url, body) => {
    saved = (body as { destination: unknown }).destination;
    return { data: { destination: saved } };
  });
});
describe('manual destination settings', () => {
  it('selects an airport explicitly, fills coordinates, saves and clears the shared destination', async () => {
    mount();
    await screen.findByRole('button', { name: 'Save destination' });
    fireEvent.change(screen.getByLabelText('Airport search'), {
      target: { value: 'LHR' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search airports' }));
    fireEvent.click(
      await screen.findByRole('button', { name: /London Heathrow Airport/ })
    );
    expect(
      (screen.getByLabelText('Destination name') as HTMLInputElement).value
    ).toBe('London Heathrow Airport');
    expect((screen.getByLabelText('Latitude') as HTMLInputElement).value).toBe(
      '51.47'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    await screen.findByText('Destination saved');
    expect(saved).toEqual({
      name: 'London Heathrow Airport',
      latitude: 51.47,
      longitude: -0.4543,
      airport_code: 'EGLL',
    });
    fireEvent.click(screen.getByRole('button', { name: 'Clear destination' }));
    await screen.findByText('Destination cleared');
    expect(saved).toBeNull();
  });
  it('saves coordinate fallback including zero and rejects missing or out of range input', async () => {
    mount();
    await screen.findByRole('button', { name: 'Save destination' });
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(
      /name|coordinates/i
    );
    fireEvent.change(screen.getByLabelText('Destination name'), {
      target: { value: 'Remote stop' },
    });
    fireEvent.change(screen.getByLabelText('Latitude'), {
      target: { value: '91' },
    });
    fireEvent.change(screen.getByLabelText('Longitude'), {
      target: { value: '0' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(
      /latitude|coordinates/i
    );
    fireEvent.change(screen.getByLabelText('Latitude'), {
      target: { value: '0' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    await screen.findByText('Destination saved');
    expect(saved).toEqual({
      name: 'Remote stop',
      latitude: 0,
      longitude: 0,
      airport_code: null,
    });
  });
  it('preserves draft on save error and reports search failure without blocking coordinate fallback', async () => {
    mount();
    await screen.findByRole('button', { name: 'Save destination' });
    vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'));
    fireEvent.change(screen.getByLabelText('Airport search'), {
      target: { value: 'LHR' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search airports' }));
    await screen.findByText(/Airport search unavailable/);
    fireEvent.change(screen.getByLabelText('Destination name'), {
      target: { value: 'Remote stop' },
    });
    fireEvent.change(screen.getByLabelText('Latitude'), {
      target: { value: '0' },
    });
    fireEvent.change(screen.getByLabelText('Longitude'), {
      target: { value: '1' },
    });
    vi.mocked(apiClient.put).mockRejectedValueOnce(new Error('offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    await screen.findByText(/Unable to save destination/);
    expect(
      (screen.getByLabelText('Destination name') as HTMLInputElement).value
    ).toBe('Remote stop');
    fireEvent.click(screen.getByRole('button', { name: 'Save destination' }));
    await screen.findByText('Destination saved');
  });
  it('reports empty search results and loading errors', async () => {
    vi.mocked(apiClient.get).mockImplementation(async (url) => ({
      data: url.includes('/airports')
        ? { airports: [] }
        : { destination: null },
    }));
    mount();
    await screen.findByRole('button', { name: 'Save destination' });
    fireEvent.change(screen.getByLabelText('Airport search'), {
      target: { value: 'unknown' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search airports' }));
    await screen.findByText(/No airports found/);
    cleanup();
    vi.mocked(apiClient.get).mockRejectedValue(new Error('offline'));
    mount();
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain(
        'Destination settings unavailable'
      )
    );
  });
});
