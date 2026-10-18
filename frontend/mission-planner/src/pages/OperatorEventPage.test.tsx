/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import * as eventApi from '@/services/operatorEvents';
import { health, page } from '@/test/operator-fixtures';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import { OperatorJournalPage } from './OperatorJournalPage';
let client: QueryClient;
afterEach(() => {
  cleanup();
  client?.clear();
  sessionStorage.clear();
  localStorage.clear();
  vi.restoreAllMocks();
});
it('keeps one shared timeline accessible across work sections without losing the journal draft', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const read = vi
    .spyOn(eventApi, 'readEventSnapshot')
    .mockResolvedValue(eventSnapshot());
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?mission_id=mission-a']}>
        <OperatorJournalPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  await screen.findByRole('button', { name: 'Open events' });
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  const title = screen.getByLabelText('Title') as HTMLInputElement;
  fireEvent.change(title, { target: { value: 'Unsent synthetic draft' } });
  for (const section of [
    'Communications',
    'Issues',
    'Journal',
    'Display tools',
  ]) {
    fireEvent.click(screen.getByRole('link', { name: section }));
    fireEvent.click(screen.getByRole('button', { name: 'Open events' }));
    expect(
      screen.getByRole('dialog', { name: 'Operational timeline' })
    ).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(title.value).toBe('Unsent synthetic draft');
  }
  expect(read).toHaveBeenCalledTimes(1);
});
it('retains last-known event rows when health and feed requests fail offline', async () => {
  const readHealth = vi
    .spyOn(api, 'getOperatorHealth')
    .mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const readEvents = vi
    .spyOn(eventApi, 'readEventSnapshot')
    .mockResolvedValue(eventSnapshot());
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?mission_id=mission-a']}>
        <OperatorJournalPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  await screen.findByRole('button', { name: 'Open events' });
  await waitFor(() => expect(readEvents).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Open events' }));
  await screen.findByText('Synthetic requirement');
  readHealth.mockRejectedValue(new Error('Offline'));
  readEvents.mockRejectedValue(new Error('Offline'));
  await client.invalidateQueries({ queryKey: ['operator-health'] });
  await client.invalidateQueries({ queryKey: ['operator-events'] });
  await waitFor(() =>
    expect(screen.getAllByText(/Feed unavailable/).length).toBeGreaterThan(0)
  );
  expect(screen.getByText('Synthetic requirement')).toBeTruthy();
});
