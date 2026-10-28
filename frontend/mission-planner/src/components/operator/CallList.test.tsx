/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
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
    screen.getByRole('button', { name: 'Connect Customer' }).closest('details')
      ?.open
  ).toBe(false);
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

const controls = () => ({
  disabled: false,
  incomplete: false,
  onEdit: vi.fn(),
  onHistory: vi.fn(),
  onTransition: vi.fn(),
  onCallAction: vi.fn(),
  onConferenceAction: vi.fn(),
  onCustomerAction: vi.fn(),
});
const scheduled = (): SavedRecord => ({
  ...record,
  record_id: 'call',
  record_type: 'call',
  time: { ...record.time, occurred_at: null, ended_at: null },
  payload: {
    ...record.payload,
    entry_type: 'call',
    status: 'scheduled',
    conference_id: 'bridge',
  },
});
const bridge = (ready: boolean): SavedRecord =>
  ({
    ...record,
    record_id: 'bridge',
    record_type: 'conference',
    payload: {
      schema_version: 1,
      entry_type: 'conference',
      title: 'Reusable Bridge',
      status: ready ? 'established' : 'preparing',
      verified_at: ready ? '2026-10-17T15:00:00Z' : null,
      configured_transport: 'Ka',
    },
  }) as SavedRecord;
it('shows one next action and keeps secondary controls and audit evidence in closed Call Details', () => {
  const props = controls();
  render(
    <CallList {...props} items={page([scheduled(), bridge(false)]).items} />
  );
  const primary = screen.getByRole('button', { name: 'Establish Bridge' });
  expect(primary.dataset.primaryAction).toBeDefined();
  expect(
    screen.getAllByRole('button').filter((button) => !button.closest('details'))
  ).toEqual([primary]);
  expect(screen.getByText('Call Details').closest('details')?.open).toBe(false);
  expect(
    screen.queryByText(/not verified|Two-way check|Actual: Unknown/i)
  ).toBeNull();
  fireEvent.click(screen.getByText('Call Details'));
  fireEvent.click(screen.getByRole('button', { name: 'Reschedule' }));
  fireEvent.click(screen.getByRole('button', { name: 'Call History' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel Call' }));
  fireEvent.click(screen.getByRole('button', { name: 'Remove Call' }));
  expect(props.onEdit).toHaveBeenCalledWith(scheduled());
  expect(props.onHistory).toHaveBeenCalledWith('call');
  expect(props.onCallAction).toHaveBeenCalledWith(scheduled(), 'cancel');
  expect(props.onTransition).toHaveBeenCalledWith(scheduled());
});
it('advances the single primary from connection to customer left to finish without losing recovery actions', () => {
  const props = controls();
  const call = scheduled();
  const established = bridge(true);
  const view = render(
    <CallList {...props} items={page([call, established]).items} />
  );
  expect(
    screen
      .getAllByRole('button')
      .filter((button) => !button.closest('details'))
      .map((b) => b.textContent)
  ).toEqual(['Connect Customer']);
  const running = {
    ...call,
    time: { ...call.time, occurred_at: '2026-10-17T15:01:00Z' },
  };
  const customer = {
    ...record,
    record_id: 'customer',
    record_type: 'participation',
    payload: {
      schema_version: 1,
      entry_type: 'participation',
      title: 'Customer',
      call_id: 'call',
      conference_id: 'bridge',
      state: 'connected',
    },
  } as SavedRecord;
  view.rerender(
    <CallList {...props} items={page([running, established, customer]).items} />
  );
  expect(
    screen
      .getAllByRole('button')
      .filter((button) => !button.closest('details'))
      .map((b) => b.textContent)
  ).toEqual(['Report Customer Left']);
  fireEvent.click(screen.getByText('Call Details'));
  expect(
    within(screen.getByText('Call Details').parentElement!)
      .getByRole('button', { name: 'Finish Call' })
      .hasAttribute('disabled')
  ).toBe(true);
  const left = {
    ...customer,
    payload: { ...customer.payload, state: 'left' },
  } as SavedRecord;
  view.rerender(
    <CallList {...props} items={page([running, established, left]).items} />
  );
  const primary = screen.getByRole('button', { name: 'Finish Call' });
  expect(primary.dataset.primaryAction).toBeDefined();
  fireEvent.click(primary);
  expect(props.onCallAction).toHaveBeenCalledWith(running, 'finish');
});
it('keeps an unresolved conference actionable rather than implying a direct connection', () => {
  render(<CallList {...controls()} items={page([scheduled()]).items} />);
  expect(screen.getByRole('status').textContent).toContain(
    'Conference unavailable'
  );
  expect(
    screen.getByRole('button', { name: 'Choose Conference' })
  ).toBeTruthy();
  expect(screen.queryByText('Direct Connection')).toBeNull();
});

it('finishes after a restored customer leaves instead of restoring the superseded interruption again', () => {
  const props = controls();
  const call = {
    ...scheduled(),
    time: { ...scheduled().time, occurred_at: '2026-10-17T15:00:00Z' },
  };
  const old = {
    ...record,
    record_id: 'interrupted',
    record_type: 'participation',
    payload: {
      schema_version: 1,
      entry_type: 'participation',
      title: 'Old interval',
      call_id: 'call',
      conference_id: 'bridge',
      state: 'interrupted',
    },
  } as SavedRecord;
  const resumed = {
    ...old,
    record_id: 'successor',
    payload: {
      ...old.payload,
      state: 'left',
      resumes_participation_id: 'interrupted',
    },
  } as SavedRecord;
  render(
    <CallList
      {...props}
      items={page([call, bridge(true), old, resumed]).items}
    />
  );
  expect(
    screen
      .getByRole('button', { name: 'Finish Call' })
      .hasAttribute('data-primary-action')
  ).toBe(true);
  expect(screen.queryByRole('button', { name: 'Restore Customer' })).toBeNull();
});
it.each(['direct', 'bridge'] as const)(
  'retains %s establishment recovery in Details when a connected customer is the primary work',
  (kind) => {
    const props = controls();
    const call = {
      ...scheduled(),
      payload: {
        ...scheduled().payload,
        conference_id: kind === 'direct' ? null : 'bridge',
      },
      time: { ...scheduled().time, occurred_at: '2026-10-17T15:00:00Z' },
    } as SavedRecord;
    const customer = {
      ...record,
      record_id: 'connected',
      record_type: 'participation',
      payload: {
        schema_version: 1,
        entry_type: 'participation',
        title: 'Customer',
        call_id: 'call',
        conference_id: kind === 'direct' ? null : 'bridge',
        state: 'connected',
      },
    } as SavedRecord;
    render(
      <CallList
        {...props}
        items={page([call, bridge(false), customer]).items}
      />
    );
    expect(
      screen
        .getByRole('button', { name: 'Report Customer Left' })
        .hasAttribute('data-primary-action')
    ).toBe(true);
    fireEvent.click(screen.getByText('Call Details'));
    fireEvent.click(
      screen.getByRole('button', {
        name: kind === 'direct' ? 'Establish' : 'Establish Bridge',
      })
    );
    if (kind === 'direct')
      expect(props.onCallAction).toHaveBeenCalledWith(call, 'establish');
    else
      expect(props.onConferenceAction).toHaveBeenCalledWith(
        bridge(false),
        'establish'
      );
  }
);
