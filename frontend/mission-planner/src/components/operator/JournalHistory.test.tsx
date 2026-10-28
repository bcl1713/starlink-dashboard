/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { page, record } from '@/test/operator-fixtures';
import { JournalHistory } from './JournalHistory';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('exposes corrected intervals, retained planning times, scope, legs and attribution for each revision', async () => {
  const original = {
    ...record,
    scope: 'leg' as const,
    leg_id: 'wrong-leg',
    time: {
      ...record.time,
      ended_at: '2026-10-17T15:45:00Z',
      end_state: 'known' as const,
      planned_start_at: '2026-10-17T15:00:00Z',
      planned_end_at: '2026-10-17T15:50:00Z',
    },
    author: { backend: 'restricted-access operator', operator_label: 'Alex' },
  };
  const corrected = {
    ...original,
    version: 2,
    leg_id: 'correct-leg',
    time: { ...original.time, ended_at: '2026-10-17T15:35:00Z' },
  };
  const unknown = {
    ...record,
    version: 3,
    scope: 'between_legs' as const,
    time: {
      ...record.time,
      occurred_at: null,
      precision: 'unknown' as const,
      end_state: 'unknown' as const,
    },
    payload: {
      ...record.payload,
      previous_leg_id: 'before',
      next_leg_id: 'after',
    },
  };
  const revisions = page([original, corrected, unknown]);
  revisions.items[2].association = {
    status: 'missing',
    unresolved_fields: ['payload.previous_leg_id'],
    error_code: 'missing_leg',
  };
  vi.spyOn(api, 'readOperatorHistory').mockResolvedValue(revisions);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <JournalHistory
        id={record.record_id}
        identity="store-a"
        onClose={() => {}}
      />
    </QueryClientProvider>
  );
  const items = await screen.findAllByRole('listitem');
  expect(items[0].textContent).toContain('2026-10-17 15:45:00 Zulu');
  expect(items[1].textContent).toContain('2026-10-17 15:35:00 Zulu');
  expect(items[0].textContent).toContain('wrong-leg');
  expect(items[1].textContent).toContain('correct-leg');
  for (const item of items.slice(0, 2)) {
    expect(item.textContent).toContain('2026-10-17 10:11:12.123456 Zulu');
    expect(item.textContent).toContain('2026-10-17 15:00:00 Zulu');
    expect(item.textContent).toContain('2026-10-17 15:50:00 Zulu');
    expect(item.textContent).toContain('approximate');
    expect(item.textContent).toContain('known');
    expect(item.textContent).toContain('Alex');
    expect(item.textContent).toContain('restricted-access operator');
    expect(item.textContent).toContain('mission-a');
    expect(item.textContent).toContain('operator_reported');
    expect(item.textContent).toContain('live');
  }
  expect(within(items[2]).getByText(/Actual start: Unknown/)).toBeTruthy();
  expect(items[2].textContent).toContain('between_legs');
  expect(items[2].textContent).toContain('before');
  expect(items[2].textContent).toContain('after');
  expect(items[2].textContent).toContain('missing');
  client.clear();
});
it('withholds cached history when the same record ID is opened in another store identity', async () => {
  const history = vi
    .spyOn(api, 'readOperatorHistory')
    .mockResolvedValue(page());
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = (identity: string) => (
    <QueryClientProvider client={client}>
      <JournalHistory
        id={record.record_id}
        identity={identity}
        onClose={() => {}}
      />
    </QueryClientProvider>
  );
  const mounted = render(view('old-store'));
  await screen.findByRole('heading', { name: 'Original' });
  history.mockImplementation(() => new Promise(() => {}));
  mounted.rerender(view('new-store'));
  expect(screen.queryByRole('heading', { name: 'Original' })).toBeNull();
  expect(screen.getByText('Loading history…')).toBeTruthy();
  client.clear();
});

it('retains original revisions after a next-page failure and exposes explicit retry and remaining history', async () => {
  const original = { ...record, recorded_at: '2026-10-17T10:00:00Z' };
  const replacement = {
    ...original,
    version: 2,
    previous_version: 1,
    operation: 'update' as const,
    recorded_at: '2026-10-17T10:01:00Z',
    payload: { ...original.payload, title: 'Replacement' },
  };
  const removed = {
    ...replacement,
    version: 3,
    previous_version: 2,
    operation: 'remove' as const,
    deleted: true,
  };
  const restored = {
    ...replacement,
    version: 4,
    previous_version: 3,
    operation: 'restore' as const,
    deleted: false,
    payload: { ...replacement.payload, title: 'Restored' },
  };
  let failed = false;
  const read = vi
    .spyOn(api, 'readOperatorHistory')
    .mockImplementation(async (_id, cursor) => {
      if (cursor && !failed) {
        failed = true;
        throw new Error('next page unavailable');
      }
      return cursor
        ? { ...page([removed, restored]), cursor: null, H: 4 }
        : { ...page([original, replacement]), cursor: 'history-next', H: 4 };
    });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <JournalHistory
        id={record.record_id}
        identity="store-a"
        onClose={() => {}}
      />
    </QueryClientProvider>
  );
  await screen.findByRole('heading', { name: 'Original' });
  fireEvent.click(screen.getByRole('button', { name: 'More history' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('heading', { name: 'Original' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Replacement' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Retry history' }));
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'More history' }));
  await screen.findByRole('heading', { name: 'Restored' });
  expect(screen.getAllByRole('listitem')).toHaveLength(4);
  expect(
    screen.getByText(/Version 1 · create · 2026-10-17 10:00:00 Zulu/)
  ).toBeTruthy();
  expect(screen.getByText(/Version 4 · restore/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'More history' })).toBeNull();
  expect(
    read.mock.calls.filter(([, cursor]) => cursor === 'history-next')
  ).toHaveLength(2);
  client.clear();
});
