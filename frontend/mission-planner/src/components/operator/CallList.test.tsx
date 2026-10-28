/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { page, record } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
import { CallList } from './CallList';
afterEach(cleanup);
it('orders equal starts stably and warns of missing pages and unknown times', () => {
  const call = (id: string, start: string | null): SavedRecord => ({
    ...record,
    record_id: id,
    record_type: 'call',
    time: { ...record.time, planned_start_at: start },
    payload: {
      ...record.payload,
      title: id,
      entry_type: 'call',
      status: 'tentative',
      conference_id: null,
    },
  });
  render(
    <CallList
      items={
        page([
          call('b', '2026-10-17T18:00:00Z'),
          call('c', null),
          call('a', '2026-10-17T18:00:00Z'),
        ]).items
      }
      incomplete
      disabled={false}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onTransition={vi.fn()}
    />
  );
  expect(
    screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)
  ).toEqual(['a', 'b', 'Unknown planned timing', 'c']);
  expect(screen.getByRole('status').textContent).toContain('incomplete');
});

it('treats direct calls as first-class and offers Establish then Connect Customer without separate Test', () => {
  const direct: SavedRecord = {
    ...record,
    record_type: 'call',
    time: { ...record.time, occurred_at: null, ended_at: null },
    payload: {
      ...record.payload,
      entry_type: 'call',
      status: 'scheduled',
      conference_id: null,
      direct_transport: 'Ka',
    },
  };
  const props = {
    incomplete: false,
    disabled: false,
    onEdit: vi.fn(),
    onHistory: vi.fn(),
    onTransition: vi.fn(),
    onCallAction: vi.fn(),
  };
  const view = render(<CallList {...props} items={page([direct]).items} />);
  expect(screen.getByRole('button', { name: 'Establish' })).toBeTruthy();
  expect(screen.queryByRole('button', { name: /choose bridge/i })).toBeNull();
  expect(
    screen
      .getByRole('button', { name: 'Connect Customer' })
      .hasAttribute('disabled')
  ).toBe(true);
  view.rerender(
    <CallList
      {...props}
      items={
        page([
          {
            ...direct,
            payload: {
              ...direct.payload,
              entry_type: 'call',
              status: 'scheduled',
              conference_id: null,
              established_at: '2026-10-17T15:00:00Z',
            },
          },
        ]).items
      }
    />
  );
  expect(
    screen
      .getByRole('button', { name: 'Connect Customer' })
      .hasAttribute('disabled')
  ).toBe(false);
  expect(screen.queryByRole('button', { name: /call tested/i })).toBeNull();
});
