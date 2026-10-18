/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import { record } from '@/test/operator-fixtures';
import { WorkspaceAwareness } from './WorkspaceAwareness';
import { nextRequirement } from './awarenessModel';
import type { SavedRecord } from '@/types/operator';

afterEach(cleanup);
it('keeps the named future requirement separate from overdue activity and three risks', () => {
  const future = eventFixture({
    event_id: 'future',
    title: 'Next customer',
    state: 'upcoming',
    due_at: '2026-10-17T16:20:00Z',
  });
  const snapshot = eventSnapshot({
    events: [
      eventFixture({
        title: 'Overdue customer',
        state: 'overdue',
        due_at: '2026-10-17T15:00:00Z',
      }),
      ...[1, 2, 3].map((i) =>
        eventFixture({
          event_id: `risk-${i}`,
          kind: 'restriction',
          title: `Risk ${i}`,
          time_basis: 'live_route_eta' as const,
        })
      ),
      future,
    ],
  });
  const customers = [1, 2, 3, 4, 5].map(
    (i) =>
      ({
        ...record,
        record_id: `customer-${i}`,
        record_type: 'participation',
        payload: {
          ...record.payload,
          entry_type: 'participation',
          participant: `Customer ${i}`,
          state: 'connected',
          call_id: null,
          conference_id: null,
        },
      }) as SavedRecord
  );
  render(
    <WorkspaceAwareness
      snapshot={snapshot}
      next={nextRequirement(snapshot)}
      records={customers}
      recordsIncomplete={false}
      failed={false}
    />
  );
  const next = screen.getByRole('region', { name: 'Next requirement' });
  expect(within(next).getByText('Next customer')).toBeTruthy();
  expect(within(next).queryByText('Overdue customer')).toBeNull();
  expect(screen.getByText('Overdue customer')).toBeTruthy();
  for (let i = 1; i <= 5; i++)
    expect(screen.getByText(`Customer ${i}`)).toBeTruthy();
  for (let i = 1; i <= 3; i++)
    expect(screen.getByText(`Risk ${i}`)).toBeTruthy();
});

it('shows incomplete coverage and unknown times without inventing live timing', () => {
  const snapshot = eventSnapshot({
    coverage: 'partial',
    truncated: true,
    events: [
      eventFixture({
        kind: 'restriction',
        title: 'Live unavailable advisory',
        time_basis: 'live_unavailable',
        due_at: null,
        planned_due_at: '2026-10-17T16:45:00Z',
        state: 'unknown',
      }),
    ],
  });
  render(
    <WorkspaceAwareness
      snapshot={snapshot}
      next={nextRequirement(snapshot)}
      records={[]}
      recordsIncomplete
      failed={false}
    />
  );
  expect(screen.getByText(/Coverage partial/)).toBeTruthy();
  expect(screen.getByText(/Loaded records only/)).toBeTruthy();
  expect(screen.getAllByText(/Live timing unavailable/).length).toBeGreaterThan(
    0
  );
  expect(screen.queryByText(/16:45/)).toBeNull();
});

it('does not infer a connected customer from an established conference', () => {
  render(
    <WorkspaceAwareness
      snapshot={eventSnapshot()}
      next={undefined}
      records={[
        {
          ...record,
          record_type: 'conference',
          payload: {
            ...record.payload,
            entry_type: 'conference',
            status: 'established',
          },
        } as SavedRecord,
      ]}
      recordsIncomplete={false}
      failed
    />
  );
  expect(screen.getByText('No reported connected customers.')).toBeTruthy();
  expect(screen.getByText(/Feed unavailable/)).toBeTruthy();
});

it('sorts future call requirements and excludes prep, inactive and unknown times', () => {
  const snapshot = eventSnapshot({
    events: [
      eventFixture({
        kind: 'call_prep',
        title: 'Prep',
        state: 'upcoming',
        due_at: '2026-10-17T16:01:00Z',
      }),
      eventFixture({
        title: 'Inactive',
        active: false,
        due_at: '2026-10-17T16:02:00Z',
      }),
      eventFixture({ title: 'Unknown', state: 'unknown', due_at: null }),
      eventFixture({
        title: 'Later',
        state: 'upcoming',
        due_at: '2026-10-17T17:00:00Z',
      }),
      eventFixture({
        title: 'Sooner',
        state: 'upcoming',
        due_at: '2026-10-17T16:30:00Z',
      }),
    ],
  });
  expect(nextRequirement(snapshot)?.title).toBe('Sooner');
});
it('does not claim there is no future requirement when event pages are incomplete', () => {
 render(<WorkspaceAwareness snapshot={eventSnapshot({events:[],truncated:true,coverage:'partial'})} next={undefined} records={[]} recordsIncomplete={false} failed={false}/>);
 expect(screen.queryByText('No timed future requirement recorded.')).toBeNull();
 expect(screen.getByText('Next requirement unavailable in loaded events.')).toBeTruthy();
});
