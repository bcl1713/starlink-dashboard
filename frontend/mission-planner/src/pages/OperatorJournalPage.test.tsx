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
import { OperatorJournalPage } from './OperatorJournalPage';
import { failure, health, page, record } from '@/test/operator-fixtures';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
function mount() {
  if (!vi.isMockFunction(api.readOperatorRecord))
    vi.spyOn(api, 'readOperatorRecord').mockImplementation(
      async () => page().items[0]
    );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?mission_id=mission-a']}>
        <OperatorJournalPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}
it('keeps one corrected row, separate history, removes/restores without a reason prompt and survives remount', async () => {
  let current = {
    ...record,
    version: 2,
    payload: { ...record.payload, title: 'Corrected row' },
  };
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockImplementation(async () =>
    page([current])
  );
  vi.spyOn(api, 'readOperatorHistory').mockResolvedValue(
    page([record, current])
  );
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockImplementation(async (command) => {
      current = {
        ...current,
        version: current.version + 1,
        deleted: command.operation === 'remove',
      };
      return {
        schema_version: 1,
        command_id: 'receipt',
        saved_records: [current],
      };
    });
  vi.spyOn(api, 'readOperatorRecord').mockImplementation(
    async () => page([current]).items[0]
  );
  const view = mount();
  await screen.findByRole('button', { name: 'Edit Corrected row' });
  expect(screen.getAllByText('Corrected row')).toHaveLength(1);
  fireEvent.click(
    screen.getByRole('button', { name: 'History for Corrected row' })
  );
  await screen.findByRole('heading', { name: 'Entry history' });
  expect(await screen.findByText('Original')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Remove Corrected row' }));
  await screen.findByRole('button', { name: 'Restore Corrected row' });
  expect(save.mock.calls[0][0]).toMatchObject({
    operation: 'remove',
    body: { expected_version: 2 },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Restore Corrected row' })
  );
  await screen.findByRole('button', { name: 'Remove Corrected row' });
  view.unmount();
  mount();
  await screen.findByRole('button', { name: 'Edit Corrected row' });
});
it('shows enabled unavailable store and preserves draft after 503 and exact retry', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(failure(503, 'busy'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  mount();
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save entry' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Keep this draft' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  await screen.findByRole('button', { name: 'Retry exact save' });
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Keep this draft'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Retry exact save' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1]).toEqual(save.mock.calls[0]);
});
it('does not show a false empty list when enabled store is unavailable', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    ready: false,
    error_code: 'store_unavailable',
  });
  const read = vi.spyOn(api, 'readOperatorRecords');
  mount();
  await screen.findByText(/Operator store unavailable/);
  expect(screen.queryByText('No journal entries.')).toBeNull();
  expect(read).not.toHaveBeenCalled();
  expect(
    screen.getByRole('button', { name: 'Save entry' }).hasAttribute('disabled')
  ).toBe(true);
});
it('hides disabled editor on health 404', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockRejectedValue(
    failure(404, 'operator_disabled')
  );
  mount();
  await screen.findByText('Operator journal is disabled.');
  expect(screen.queryByLabelText('Title')).toBeNull();
});
it('keeps dirty draft and original version on refetch and exposes latest separately after conflict', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  const read = vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  const latest = {
    ...record,
    version: 2,
    payload: { ...record.payload, title: 'Remote title' },
  };
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(
    page([latest]).items[0]
  );
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(409, 'version_conflict')
  );
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Original' }));
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Local correction' },
  });
  read.mockResolvedValue(page([latest]));
  await clients.at(-1)!.invalidateQueries({ queryKey: ['operator-records'] });
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Local correction'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  await screen.findByText(/Latest saved version 2: Remote title/);
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Local correction'
  );
  expect(
    screen.getByRole('button', { name: 'Save entry' }).hasAttribute('disabled')
  ).toBe(true);
  vi.mocked(api.readOperatorRecord).mockResolvedValue(
    page([
      {
        ...latest,
        version: 3,
        payload: { ...latest.payload, title: 'Newest remote' },
      },
    ]).items[0]
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Reread and use saved state' })
  );
  await waitFor(() =>
    expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
      'Newest remote'
    )
  );
});
it('retains an invalid draft for correction after a definite 422', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(422, 'validation_error')
  );
  mount();
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save entry' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Keep invalid draft' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  await screen.findByText('validation_error');
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Keep invalid draft'
  );
  expect(screen.queryByRole('button', { name: 'Retry exact save' })).toBeNull();
  expect(
    screen.getByRole('button', { name: 'Save entry' }).hasAttribute('disabled')
  ).toBe(false);
});
it('retains missing between-leg references and allows explicit reassociation', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  const missing = {
    ...record,
    scope: 'between_legs' as const,
    payload: {
      ...record.payload,
      previous_leg_id: 'leg-before',
      next_leg_id: 'leg-after',
    },
  };
  const rows = page([missing]);
  rows.items[0].association = {
    status: 'missing',
    unresolved_fields: ['payload.previous_leg_id'],
    error_code: null,
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(rows);
  mount();
  await screen.findByText(/Association missing: retained mission mission-a/);
  expect(screen.getByText(/Previous leg: leg-before/)).toBeTruthy();
  expect(screen.getByText(/Next leg: leg-after/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Edit Original' }));
  expect(
    (screen.getByLabelText('Previous leg ID (optional)') as HTMLInputElement)
      .value
  ).toBe('leg-before');
  expect(
    (screen.getByLabelText('Entry mission ID') as HTMLInputElement).value
  ).toBe('mission-a');
});
it('offers summary and display navigation while quick observation focuses a clean editor and protects a dirty draft', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  mount();
  const quick = await screen.findByRole('button', {
    name: 'Record observation',
  });
  await waitFor(() => expect(quick.hasAttribute('disabled')).toBe(false));
  Element.prototype.scrollIntoView = vi.fn();
  fireEvent.click(quick);
  await waitFor(() =>
    expect(document.activeElement).toBe(screen.getByLabelText('Title'))
  );
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Keep observation draft' },
  });
  expect(quick.hasAttribute('disabled')).toBe(true);
  expect(
    screen.getByRole('link', { name: 'Display settings' }).getAttribute('href')
  ).toBe('/configuration');
  expect(
    screen.getByRole('link', { name: 'Open Overview' }).getAttribute('href')
  ).toBe('/overview');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh summary' }));
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Keep observation draft'
  );
});
