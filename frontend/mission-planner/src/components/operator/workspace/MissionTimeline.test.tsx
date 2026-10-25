/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import { MissionTimeline } from './MissionTimeline';

const snapshot = (events = [eventFixture()]) => ({
  ...eventSnapshot({ events }),
  legs: [
    {
      leg_id: 'leg-a',
      name: 'Atlantic leg',
      coverage: 'available' as const,
      reason: null,
    },
  ],
});
const state = (events = [eventFixture()]) => ({
  snapshot: snapshot(events),
  receivedAt: performance.now(),
  loading: false,
  failed: false,
  refreshing: false,
  refresh: vi.fn(),
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
it('sorts by current times, groups passed windows and shows start and recovery together', () => {
  const events = [
    eventFixture({
      event_id: 'later',
      title: 'Ka restriction',
      kind: 'restriction',
      due_at: '2026-10-18T00:05:00Z',
      end_at: '2026-10-18T00:10:00Z',
      state: 'upcoming',
      leg_id: 'leg-a',
    }),
    eventFixture({
      event_id: 'past',
      title: 'Earlier window',
      kind: 'restriction',
      due_at: '2026-10-17T14:00:00Z',
      end_at: '2026-10-17T15:00:00Z',
      state: 'inactive',
      active: false,
    }),
    eventFixture({
      event_id: 'active',
      title: 'X restriction',
      kind: 'restriction',
      due_at: '2026-10-17T15:55:00Z',
      end_at: '2026-10-17T16:12:00Z',
      time_basis: 'live_route_eta',
    }),
    eventFixture({
      event_id: 'soon',
      title: 'Prepare call',
      kind: 'call_prep',
      due_at: '2026-10-17T16:05:00Z',
      end_at: null,
      state: 'upcoming',
    }),
  ];
  render(<MissionTimeline timeline={state(events)} />);
  const rows = within(
    screen.getByRole('list', { name: 'Current and upcoming events' })
  ).getAllByRole('listitem');
  expect(
    rows.map((row) => within(row).getByRole('heading').textContent)
  ).toEqual(['X restriction', 'Prepare call', 'Ka restriction']);
  expect(within(rows[0]).getByText('Recovery in 12 min')).toBeTruthy();
  expect(within(rows[0]).getByText(/Live route ETA/)).toBeTruthy();
  expect(within(rows[2]).getByText(/2026-10-18 00:05:00 UTC/)).toBeTruthy();
  expect(within(rows[2]).getByText(/2026-10-18 00:10:00 UTC/)).toBeTruthy();
  expect(within(rows[2]).getByText('Atlantic leg')).toBeTruthy();
  const past = screen.getByText(/Past · 1/).closest('details');
  expect(past?.open).toBe(false);
  expect(screen.getByText('Now')).toBeTruthy();
});
it('shows every family and source navigation without offering timeline-only acknowledgments', () => {
  const open = vi.fn();
  render(
    <MissionTimeline
      timeline={state(
        [
          'call_start',
          'call_prep',
          'issue_followup',
          'pop_advisory',
          'restriction',
        ].map((kind, i) =>
          eventFixture({
            kind: kind as ReturnType<typeof eventFixture>['kind'],
            event_id: String(i),
            title: `Family ${i}`,
          })
        )
      )}
      onOpenSource={open}
    />
  );
  for (let i = 0; i < 5; i++)
    expect(screen.getByText(`Family ${i}`)).toBeTruthy();
  fireEvent.click(screen.getAllByRole('button', { name: 'Open source' })[0]);
  expect(open.mock.calls[0][0].kind).toBe('call_start');
  expect(screen.queryByRole('button', { name: /acknowledge/i })).toBeNull();
});
it('keeps unavailable live timing unknown and labels planned UTC as reference', () => {
  const query = state([
    eventFixture({
      title: 'Unknown X',
      time_basis: 'live_unavailable',
      due_at: null,
      end_at: null,
      planned_due_at: '2026-10-17T16:45:00Z',
    }),
  ]);
  render(<MissionTimeline timeline={query} />);
  expect(screen.getByText('Timing unavailable')).toBeTruthy();
  expect(screen.queryByText(/^In /)).toBeNull();
  expect(
    screen.getByText(/Schedule reference: 2026-10-17 16:45:00 UTC/)
  ).toBeTruthy();
});
it.each(['failed', 'aged', 'source'] as const)(
  'retains last-known rows but suppresses countdowns when %s',
  (reason) => {
    const query = state([
      eventFixture({
        title: 'Last known X',
        kind: 'restriction',
        freshness: reason === 'source' ? 'stale' : 'fresh',
      }),
    ]);
    query.failed = reason === 'failed';
    if (reason === 'aged') query.receivedAt = performance.now() - 31000;
    render(<MissionTimeline timeline={query} />);
    expect(screen.getByText('Last known X')).toBeTruthy();
    expect(screen.getAllByText(/Last known/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Recovery in/)).toBeNull();
  }
);
it('expands on a narrow screen without replacing an open editor draft', () => {
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  render(
    <>
      <input aria-label="Draft title" defaultValue="Unsaved call" />
      <MissionTimeline timeline={state()} />
    </>
  );
  const input = screen.getByRole('textbox');
  fireEvent.change(input, { target: { value: 'Keep this draft' } });
  const toggle = screen.getByRole('button', {
    name: 'Expand mission timeline',
  });
  expect(toggle.getAttribute('aria-expanded')).toBe('false');
  fireEvent.click(toggle);
  expect(toggle.getAttribute('aria-expanded')).toBe('true');
  expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe(
    'Keep this draft'
  );
});

it.each([
  ['call_start', 'Planned end', 'Ends in 30 min'],
  ['call_prep', 'Planned end', 'Ends in 30 min'],
  ['pop_advisory', 'Expected window end', 'Window ends in 30 min'],
] as const)(
  'uses event-specific end language for %s',
  (kind, label, countdown) => {
    render(<MissionTimeline timeline={state([eventFixture({ kind })])} />);
    expect(screen.getByText(new RegExp(`^${label}`))).toBeTruthy();
    expect(screen.getByText(countdown)).toBeTruthy();
    expect(screen.queryByText(/Recovery in/)).toBeNull();
  }
);

it.each(['age', 'failure'])(
  'never rewinds an elapsed window back out of Past on %s',
  (reason) => {
    vi.useFakeTimers();
    let monotonic = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => monotonic);
    const query = state([
      eventFixture({
        title: 'Elapsed X',
        kind: 'restriction',
        due_at: '2026-10-17T16:00:05Z',
        end_at: '2026-10-17T16:00:20Z',
        state: 'upcoming',
      }),
    ]);
    const view = render(<MissionTimeline timeline={query} />);
    monotonic = 29000;
    act(() => vi.advanceTimersByTime(29000));
    expect(screen.getByText('Past · 1')).toBeTruthy();
    if (reason === 'failure')
      view.rerender(<MissionTimeline timeline={{ ...query, failed: true }} />);
    monotonic = 31000;
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText('Past · 1')).toBeTruthy();
    expect(screen.queryByText(/Recovery in/)).toBeNull();
    view.unmount();
    vi.useRealTimers();
  }
);
