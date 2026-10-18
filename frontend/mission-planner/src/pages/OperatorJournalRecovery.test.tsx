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
  clients.forEach((client) => client.clear());
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
}
const title = () => screen.getByLabelText('Title') as HTMLInputElement;
const click = (name: string) =>
  fireEvent.click(screen.getByRole('button', { name }));
it('deliberately releases an absent old-epoch update and keeps the correction as a new-entry draft', async () => {
  const healthRead = vi
    .spyOn(api, 'getOperatorHealth')
    .mockResolvedValue(health);
  const rows = vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  vi.spyOn(api, 'readOperatorRecord').mockRejectedValue(
    failure(404, 'record_not_found')
  );
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('lost acknowledgment'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'new',
      saved_records: [record],
    });
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Original' }));
  fireEvent.change(title(), { target: { value: 'Keep correction' } });
  click('Save entry');
  await screen.findByRole('button', { name: 'Retry exact save' });
  const original = structuredClone(save.mock.calls[0]);
  healthRead.mockResolvedValue({ ...health, api_epoch: 'epoch-b' });
  rows.mockResolvedValue(page([]));
  click('Retry exact save');
  await screen.findByRole('button', { name: 'Reread and use saved state' });
  click('Reread and use saved state');
  await screen.findByText(/Entry is absent from the current store/);
  expect(title().value).toBe('Keep correction');
  expect(title().closest('fieldset')?.disabled).toBe(true);
  expect(save).toHaveBeenCalledTimes(1);
  click('Keep draft as new entry');
  expect(title().value).toBe('Keep correction');
  expect(title().closest('fieldset')?.disabled).toBe(false);
  expect(
    screen.getByRole('heading', { name: 'New journal entry' })
  ).toBeTruthy();
  click('Save entry');
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1][0]).toMatchObject({
    operation: 'create',
    body: { payload: { title: 'Keep correction' }, time: record.time },
  });
  expect(save.mock.calls[1][0]).not.toHaveProperty('record_id');
  expect(save.mock.calls[1][1]).not.toBe(original[1]);
  expect(save.mock.calls[1][2]).toBe('epoch-b');
});
it('shows failed targeted rereads and keeps the dirty correction until the target recovers', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  const target = vi
    .spyOn(api, 'readOperatorRecord')
    .mockRejectedValue(failure(503, 'busy'));
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(409, 'version_conflict')
  );
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Original' }));
  fireEvent.change(title(), { target: { value: 'Unsaved correction' } });
  click('Save entry');
  await screen.findByText(/Latest saved entry could not be read/);
  expect(title().value).toBe('Unsaved correction');
  click('Reread and use saved state');
  await waitFor(() => expect(target).toHaveBeenCalledTimes(2));
  expect(title().value).toBe('Unsaved correction');
  expect(
    screen.getByRole('button', { name: 'Save entry' }).hasAttribute('disabled')
  ).toBe(true);
  const latest = {
    ...record,
    version: 3,
    payload: { ...record.payload, title: 'Recovered latest' },
  };
  target.mockResolvedValue(page([latest]).items[0]);
  click('Reread and use saved state');
  await waitFor(() => expect(title().value).toBe('Recovered latest'));
  expect(target.mock.calls).toEqual([
    [record.record_id],
    [record.record_id],
    [record.record_id],
  ]);
});
it('waits for conflict recovery reads before enabling explicit reconciliation', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  let release!: (value: ReturnType<typeof page>['items'][number]) => void;
  vi.spyOn(api, 'readOperatorRecord').mockReturnValue(
    new Promise((resolve) => {
      release = resolve;
    })
  );
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(409, 'version_conflict')
  );
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Original' }));
  click('Save entry');
  const reconcile = await screen.findByRole('button', {
    name: 'Reread and use saved state',
  });
  expect(reconcile.hasAttribute('disabled')).toBe(true);
  release(page().items[0]);
  await waitFor(() => expect(reconcile.hasAttribute('disabled')).toBe(false));
});
