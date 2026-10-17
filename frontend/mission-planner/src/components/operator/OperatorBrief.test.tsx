/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { OperatorBrief } from './OperatorBrief';
import { page, record } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
const at = '2026-10-17T16:00:00Z';
function row(
  type: SavedRecord['record_type'],
  title: string,
  start: string,
  status?: string
): SavedRecord {
  return {
    ...record,
    record_id: title,
    record_type: type,
    time: { ...record.time, planned_start_at: start },
    payload: {
      ...record.payload,
      entry_type: type,
      title,
      ...(status ? { status } : {}),
    },
  } as SavedRecord;
}
function mount(records: SavedRecord[], extra = {}) {
  return render(
    <MemoryRouter>
      <OperatorBrief
        missionId="synthetic-a"
        pages={[{ ...page(records), as_of: at }]}
        unavailable={false}
        loading={false}
        failed={false}
        incomplete={false}
        {...extra}
      />
    </MemoryRouter>
  );
}
it('selects the next scheduled requirement by backend UTC time, excluding completed, removed and other missions', () => {
  mount(
    [
      row('call', 'Later', '2026-10-17T18:00:00Z', 'scheduled'),
      row('call', 'Next call', '2026-10-17T16:30:00Z', 'scheduled'),
      row('call', 'Finished', '2026-10-17T16:10:00Z', 'completed'),
      {
        ...row('call', 'Removed', '2026-10-17T16:05:00Z', 'scheduled'),
        deleted: true,
      },
    ].map((r) => ({ ...r, mission_id: 'synthetic-a' }))
  );
  const section = screen.getByRole('region', { name: 'Next requirement' });
  expect(within(section).getByText('Next call')).toBeTruthy();
  expect(within(section).getByText(/16:30:00 UTC/)).toBeTruthy();
  expect(within(section).queryByText('Finished')).toBeNull();
  expect(screen.getByText(/Snapshot.*16:00:00 UTC/)).toBeTruthy();
});
it('keeps modeled risks separate from reported issues and discloses unresolved and stale data', () => {
  const rows = page([
    {
      ...row('risk', 'Transition advisory', '2026-10-17T16:20:00Z'),
      mission_id: 'synthetic-a',
      provenance: { ...record.provenance, kind: 'modeled' },
    },
    {
      ...row('issue', 'Reported audio issue', '2026-10-17T15:00:00Z', 'open'),
      mission_id: 'synthetic-a',
    },
    {
      ...row('issue', 'Resolved issue', '2026-10-17T15:00:00Z', 'resolved'),
      mission_id: 'synthetic-a',
    },
  ]);
  rows.items[0].association.status = 'missing';
  rows.items[0].freshness.status = 'stale';
  render(
    <MemoryRouter>
      <OperatorBrief
        missionId="synthetic-a"
        pages={[{ ...rows, as_of: at }]}
        unavailable={false}
        loading={false}
        failed={false}
        incomplete={false}
      />
    </MemoryRouter>
  );
  expect(
    within(screen.getByRole('region', { name: 'Next risk' })).getByText(
      'Transition advisory'
    )
  ).toBeTruthy();
  expect(screen.getByText(/Modeled.*stale.*association missing/)).toBeTruthy();
  expect(
    within(screen.getByRole('region', { name: 'Issues' })).getByText(
      'Reported audio issue'
    )
  ).toBeTruthy();
  expect(screen.queryByText('Resolved issue')).toBeNull();
});
it('does not claim an empty summary when loading, unavailable, or incomplete', () => {
  const view = mount([], { failed: true });
  expect(screen.getAllByText(/Summary unavailable/).length).toBeGreaterThan(0);
  expect(screen.queryByText('No recorded open issues.')).toBeNull();
  view.unmount();
  mount([], { incomplete: true });
  expect(screen.getByText(/More records available/)).toBeTruthy();
  expect(screen.queryByText('No recorded open issues.')).toBeNull();
});
it('offers a coherent no-mission entry without claiming system health', () => {
  mount([], { missionId: '' });
  expect(screen.getByText(/Choose a mission/)).toBeTruthy();
  expect(
    screen.getByRole('link', { name: 'Browse missions' }).getAttribute('href')
  ).toBe('/missions');
  expect(screen.queryByRole('region', { name: 'Next risk' })).toBeNull();
});
it('shows the imminent future requirement separately from overdue attention and unknown timing', () => {
  mount([
    {
      ...row(
        'call',
        'Overdue uncompleted call',
        '2026-10-17T15:00:00Z',
        'scheduled'
      ),
      mission_id: 'synthetic-a',
    },
    {
      ...row('call', 'Future call', '2026-10-17T16:05:00Z', 'scheduled'),
      mission_id: 'synthetic-a',
    },
    {
      ...row('call', 'Unknown timing', '', 'scheduled'),
      mission_id: 'synthetic-a',
    },
  ]);
  expect(
    within(screen.getByRole('region', { name: 'Next requirement' })).getByText(
      'Future call'
    )
  ).toBeTruthy();
  const attention = screen.getByRole('region', { name: 'Attention needed' });
  expect(within(attention).getByText('Overdue uncompleted call')).toBeTruthy();
  expect(
    within(attention).getByText(/Past planned start.*still scheduled/)
  ).toBeTruthy();
  expect(
    within(
      screen.getByRole('region', { name: 'Next requirement' })
    ).queryByText('Overdue uncompleted call')
  ).toBeNull();
  expect(screen.getByText(/1 requirement\/risk record/)).toBeTruthy();
});

it('keeps all overdue calls visible for attention when there are no future requirements', () => {
  mount([
    {
      ...row('call', 'First overdue call', '2026-10-17T14:00:00Z', 'scheduled'),
      mission_id: 'synthetic-a',
    },
    {
      ...row(
        'call',
        'Second overdue call',
        '2026-10-17T15:00:00Z',
        'scheduled'
      ),
      mission_id: 'synthetic-a',
    },
    {
      ...row(
        'call',
        'Completed past call',
        '2026-10-17T14:30:00Z',
        'completed'
      ),
      mission_id: 'synthetic-a',
    },
  ]);
  expect(
    within(screen.getByRole('region', { name: 'Next requirement' })).getByText(
      'No recorded upcoming requirements.'
    )
  ).toBeTruthy();
  const attention = screen.getByRole('region', { name: 'Attention needed' });
  expect(within(attention).getByText('First overdue call')).toBeTruthy();
  expect(within(attention).getByText('Second overdue call')).toBeTruthy();
  expect(screen.queryByText('Completed past call')).toBeNull();
});
it('treats a scheduled call at the snapshot instant as next rather than overdue', () => {
  mount([
    {
      ...row('call', 'Call starting now', '2026-10-17T16:00:00Z', 'scheduled'),
      mission_id: 'synthetic-a',
    },
  ]);
  expect(
    within(screen.getByRole('region', { name: 'Next requirement' })).getByText(
      'Call starting now'
    )
  ).toBeTruthy();
  expect(screen.queryByRole('region', { name: 'Attention needed' })).toBeNull();
});
