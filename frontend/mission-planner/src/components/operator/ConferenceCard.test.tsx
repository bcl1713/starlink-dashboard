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
it('Restore connection and Restore record are distinct', () => {
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
  expect(screen.getByRole('button', { name: 'Restore record' })).toBeTruthy();
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

it('keeps active bridge actions visible without expanding a disclosure', () => {
  const action = vi.fn();
  const join = vi.fn();
  render(
    <ConferenceCard
      record={{
        ...conference,
        payload: {
          ...conference.payload,
          entry_type: 'conference',
          status: 'established',
        },
      }}
      participations={[]}
      disabled={false}
      compactActions
      prominentActions
      onAction={action}
      onEdit={vi.fn()}
      onJoin={join}
      onHistory={vi.fn()}
      onRemove={vi.fn()}
    />
  );
  for (const name of [
    'Verify',
    'Interrupt conference',
    'Close conference',
    'Correct conference',
    'Customer Joined',
  ]) {
    const button = screen.getByRole('button', { name });
    expect(button.closest('details')).toBeNull();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Verify' }));
  fireEvent.click(screen.getByRole('button', { name: 'Customer Joined' }));
  expect(action).toHaveBeenCalledWith('verify');
  expect(join).toHaveBeenCalledTimes(1);
});
