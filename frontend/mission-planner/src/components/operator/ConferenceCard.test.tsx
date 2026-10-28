/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { record } from '@/test/operator-fixtures';
import { ConferenceCard } from './ConferenceCard';
import { ParticipationRow } from './ParticipationRow';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
const conference: SavedRecord = {
  ...record,
  record_type: 'conference',
  payload: { ...record.payload, entry_type: 'conference', status: 'closed' },
};
const customer: SavedRecord = {
  ...record,
  record_id: 'customer',
  record_type: 'participation',
  payload: {
    ...record.payload,
    entry_type: 'participation',
    conference_id: 'record-a',
    call_id: null,
    state: 'connected',
  },
};
it('conference close keeps customer connected with conspicuous discrepancy', () => {
  render(
    <ConferenceCard
      record={conference}
      participations={[customer]}
      disabled={false}
      onAction={vi.fn()}
      onEdit={vi.fn()}
      onJoin={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  expect(screen.getByRole('alert').textContent).toMatch(/continuity unknown/i);
  expect(screen.getByText(/Customer reported connected: 1/)).toBeTruthy();
});
it('one-tap customer actions need no note or confirmation', () => {
  const action = vi.fn();
  render(
    <ParticipationRow
      record={customer}
      conference={conference}
      disabled={false}
      onAction={action}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Customer Left' }));
  expect(action).toHaveBeenCalledWith('left');
  expect(screen.queryByRole('dialog')).toBeNull();
});
it('Restore connection and Restore Record are distinct', () => {
  const interrupted = {
    ...customer,
    payload: { ...customer.payload, state: 'interrupted' },
  } as SavedRecord;
  const view = render(
    <ParticipationRow
      record={interrupted}
      disabled={false}
      onAction={vi.fn()}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  expect(
    screen.getByRole('button', { name: 'Restore connection' })
  ).toBeTruthy();
  view.rerender(
    <ParticipationRow
      record={{ ...interrupted, deleted: true }}
      disabled={false}
      onAction={vi.fn()}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  expect(screen.getByRole('button', { name: /Restore record/i })).toBeTruthy();
  expect(
    screen.queryByRole('button', { name: 'Restore connection' })
  ).toBeNull();
});
it('offers explicit reestablishment of a historical session without claiming readiness', () => {
  const current = {
    scope: 'leg' as const,
    leg_id: 'return',
    previous_leg_id: null,
    next_leg_id: null,
    label: 'Return',
  };
  const action = vi.fn();
  render(
    <ConferenceCard
      record={{
        ...conference,
        scope: 'leg',
        leg_id: 'outbound',
        payload: {
          ...conference.payload,
          entry_type: 'conference',
          status: 'established',
        },
      }}
      currentAssociation={current}
      compactActions
      participations={[]}
      disabled={false}
      onAction={action}
      onEdit={vi.fn()}
      onJoin={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  expect(screen.getByText(/not assumed available/i)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Verify' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /establish/i }));
  expect(action).toHaveBeenCalledWith('establish');
});

it('keeps Establish and eligible Close in the same primary slot and moves rare actions to details', () => {
  const action = vi.fn();
  const props = {
    participations: [],
    calls: [],
    disabled: false,
    onAction: action,
    onEdit: vi.fn(),
    onJoin: vi.fn(),
    onHistory: vi.fn(),
    onRemove: vi.fn(),
  };
  const view = render(<ConferenceCard {...props} record={conference} />);
  const establish = screen.getByRole('button', { name: /^Establish$/ });
  const slot = establish.parentElement;
  const style = establish.className;
  fireEvent.click(establish);
  expect(action).toHaveBeenCalledWith('establish');
  view.rerender(
    <ConferenceCard
      {...props}
      record={{
        ...conference,
        payload: {
          ...conference.payload,
          entry_type: 'conference',
          status: 'established',
          verified_at: '2026-10-17T16:00:00Z',
        },
      }}
    />
  );
  const close = screen.getByRole('button', { name: 'Close Conference' });
  expect(close.parentElement).toBe(slot);
  expect(close.className).toBe(style);
  expect(close.hasAttribute('disabled')).toBe(false);
  expect(screen.queryByRole('button', { name: /^Verify$/ })).toBeNull();
  fireEvent.click(close);
  expect(action).toHaveBeenCalledWith('close');
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(
    screen
      .getByRole('button', { name: 'Correct Conference' })
      .closest('details')
  ).toBeTruthy();
});
it('guards close for connected or unresolved customers and actual calls but ignores future-only calls', () => {
  const established = {
    ...conference,
    payload: {
      ...conference.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
      verified_at: '2026-10-17T16:00:00Z',
    },
  };
  const future = {
    ...record,
    record_type: 'call' as const,
    time: {
      ...record.time,
      occurred_at: null,
      ended_at: null,
      planned_start_at: '2026-10-18T16:00:00Z',
    },
    payload: {
      ...record.payload,
      entry_type: 'call' as const,
      status: 'scheduled' as const,
      conference_id: conference.record_id,
    },
  };
  const props = {
    record: established,
    participations: [],
    calls: [future],
    disabled: false,
    onAction: vi.fn(),
    onEdit: vi.fn(),
    onJoin: vi.fn(),
    onHistory: vi.fn(),
    onRemove: vi.fn(),
  };
  const view = render(<ConferenceCard {...props} />);
  expect(
    screen
      .getByRole('button', { name: 'Close Conference' })
      .hasAttribute('disabled')
  ).toBe(false);
  view.rerender(<ConferenceCard {...props} participations={[customer]} />);
  expect(
    screen
      .getByRole('button', { name: 'Close Conference' })
      .hasAttribute('disabled')
  ).toBe(true);
  view.rerender(
    <ConferenceCard
      {...props}
      calls={[
        {
          ...future,
          time: {
            ...future.time,
            occurred_at: '2026-10-17T15:00:00Z',
            end_state: 'ongoing',
          },
        },
      ]}
    />
  );
  expect(
    screen
      .getByRole('button', { name: 'Close Conference' })
      .hasAttribute('disabled')
  ).toBe(true);
  view.rerender(<ConferenceCard {...props} incomplete />);
  expect(
    screen
      .getByRole('button', { name: 'Close Conference' })
      .hasAttribute('disabled')
  ).toBe(true);
});
it('allows an explicit two-way check report for a legacy session with existing customer activity', () => {
  const action = vi.fn();
  render(
    <ConferenceCard
      record={{
        ...conference,
        payload: {
          ...conference.payload,
          entry_type: 'conference',
          status: 'established',
          verified_at: null,
        },
      }}
      participations={[customer]}
      disabled={false}
      onAction={action}
      onEdit={vi.fn()}
      onJoin={vi.fn()}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  const establish = screen.getByRole('button', { name: 'Establish' });
  expect(establish.hasAttribute('disabled')).toBe(false);
  fireEvent.click(establish);
  expect(action).toHaveBeenCalledWith('establish');
});
