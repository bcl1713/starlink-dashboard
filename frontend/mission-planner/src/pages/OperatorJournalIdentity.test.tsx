/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { OperatorJournalPage } from './OperatorJournalPage';
import { health, page, record } from '@/test/operator-fixtures';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?mission_id=mission-a']}>
        <OperatorJournalPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return client;
}
const title = () => screen.getByLabelText('Title') as HTMLInputElement;
const click = (name: string) =>
  fireEvent.click(screen.getByRole('button', { name }));
it.each([
  ['existing', { api_epoch: 'restored-epoch' }],
  ['new', { api_epoch: 'restored-epoch' }],
  [
    'existing',
    { source_mode: 'simulation' as const, simulation_run_id: 'run-b' },
  ],
  ['new', { source_mode: 'simulation' as const, simulation_run_id: 'run-b' }],
  ['new', { store_id: 'replacement-store' }],
  ['new', { simulation_run_id: 'run-c' }],
] as const)(
  'pins an unsent %s draft through a ready-to-ready identity change %o',
  async (kind, change) => {
    const readHealth = vi
      .spyOn(api, 'getOperatorHealth')
      .mockResolvedValue(health);
    const rows = vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
    const history = vi
      .spyOn(api, 'readOperatorHistory')
      .mockResolvedValue(page());
    const target = vi
      .spyOn(api, 'readOperatorRecord')
      .mockResolvedValue(page().items[0]);
    const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
      schema_version: 1,
      command_id: 'saved',
      saved_records: [record],
    });
    const client = mount();
    await screen.findByRole('button', { name: 'Edit Original' });
    click('History for Original');
    await within(
      screen.getByRole('region', { name: 'Entry history' })
    ).findByRole('heading', { name: 'Original' });
    if (kind === 'existing') click('Edit Original');
    fireEvent.change(title(), { target: { value: 'Unsent local draft' } });
    let release!: (value: ReturnType<typeof page>) => void;
    rows.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = resolve;
        })
    );
    history.mockResolvedValue(page([]));
    readHealth.mockResolvedValue({ ...health, ...change });
    await act(async () => {
      await client.invalidateQueries({ queryKey: ['operator-health'] });
    });
    await screen.findByRole('button', { name: 'Reread and use saved state' });
    expect(title().value).toBe('Unsent local draft');
    expect(
      screen
        .getByRole('button', { name: 'Save entry' })
        .hasAttribute('disabled')
    ).toBe(true);
    expect(screen.queryByRole('button', { name: 'Edit Original' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Original' })).toBeNull();
    click('Save entry');
    expect(save).not.toHaveBeenCalled();
    rows.mockResolvedValue(page([]));
    await act(async () => {
      release(page([]));
    });
    click('Reread and use saved state');
    await waitFor(() =>
      expect(
        screen
          .getByRole('button', { name: 'Save entry' })
          .hasAttribute('disabled')
      ).toBe(false)
    );
    if (kind === 'existing') {
      expect(target).toHaveBeenCalledWith(record.record_id);
      expect(title().value).toBe('Original');
    } else
      fireEvent.change(title(), {
        target: { value: 'Explicit new-store entry' },
      });
    click('Save entry');
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][2]).toBe(
      'api_epoch' in change ? change.api_epoch : health.api_epoch
    );
  }
);
it('announces saving while acknowledgment is held, and saved only after receipt', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page().items[0]);
  let acknowledge!: (value: {
    schema_version: 1;
    command_id: string;
    saved_records: (typeof record)[];
  }) => void;
  vi.spyOn(api, 'saveOperatorCommand').mockImplementation(
    () =>
      new Promise((resolve) => {
        acknowledge = resolve;
      })
  );
  mount();
  await screen.findByRole('button', { name: 'Edit Original' });
  fireEvent.change(title(), { target: { value: 'New entry' } });
  click('Save entry');
  expect(screen.getByRole('status').textContent).toMatch(/Saving/);
  expect(screen.getByRole('status').textContent).not.toMatch(/Saved/);
  await act(async () =>
    acknowledge({
      schema_version: 1,
      command_id: 'saved',
      saved_records: [record],
    })
  );
  await waitFor(() =>
    expect(screen.getByRole('status').textContent).toMatch(/Saved/)
  );
});
