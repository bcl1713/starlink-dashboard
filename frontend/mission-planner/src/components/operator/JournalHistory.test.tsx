/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
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
  expect(items[0].textContent).toContain('2026-10-17 15:45:00 UTC');
  expect(items[1].textContent).toContain('2026-10-17 15:35:00 UTC');
  expect(items[0].textContent).toContain('wrong-leg');
  expect(items[1].textContent).toContain('correct-leg');
  for (const item of items.slice(0, 2)) {
    expect(item.textContent).toContain('2026-10-17 10:11:12.123456 UTC');
    expect(item.textContent).toContain('2026-10-17 15:00:00 UTC');
    expect(item.textContent).toContain('2026-10-17 15:50:00 UTC');
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
