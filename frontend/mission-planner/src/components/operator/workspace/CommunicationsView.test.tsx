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
import { callDraft } from '../callDraft';
import { conferenceDraft, participationDraft } from '../conferenceCommands';
import { CommunicationsView } from './CommunicationsView';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
const callbacks = () => ({
  onCreateCall: vi.fn(),
  onCreateActualCall: vi.fn(),
  onCreateConference: vi.fn(),
  onJoin: vi.fn(),
  onEdit: vi.fn(),
  onHistory: vi.fn(),
  onTransition: vi.fn(),
  onConferenceAction: vi.fn(),
  onCustomerAction: vi.fn(),
});
it('makes first-use call, conference and customer reporting discoverable', () => {
  const actions = callbacks();
  render(
    <CommunicationsView
      items={[]}
      disabled={false}
      incomplete={false}
      {...actions}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Create call' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create conference' }));
  fireEvent.click(
    screen.getByRole('button', { name: 'Report customer joined' })
  );
  expect(actions.onCreateCall).toHaveBeenCalledOnce();
  expect(actions.onCreateConference).toHaveBeenCalledOnce();
  expect(actions.onJoin).toHaveBeenCalledOnce();
});
it('exposes conference reuse and independent customer interruption with the actual selected record', () => {
  const conference = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'bridge',
  } as SavedRecord;
  const customer = {
    ...record,
    ...participationDraft('mission-a', 'bridge'),
    record_id: 'customer',
  } as SavedRecord;
  const actions = callbacks();
  render(
    <CommunicationsView
      items={page([conference, customer]).items}
      disabled={false}
      incomplete={false}
      {...actions}
    />
  );
  const bridge = screen.getByRole('article', { name: 'Conference Conference' });
  fireEvent.click(within(bridge).getByRole('button', { name: 'Establish' }));
  expect(actions.onConferenceAction).toHaveBeenCalledWith(
    conference,
    'establish'
  );
  expect(
    screen.queryByRole('button', {
      name: 'Use this session for another customer',
    })
  ).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Interrupt customer' }));
  expect(actions.onCustomerAction).toHaveBeenCalledWith(
    customer,
    'interrupted'
  );
});

it('offers reuse once a bridge is established', () => {
  const conference = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'bridge',
  } as SavedRecord;
  if (conference.payload.entry_type === 'conference')
    conference.payload.status = 'established';
  const actions = callbacks();
  render(
    <CommunicationsView
      items={page([conference]).items}
      disabled={false}
      incomplete={false}
      {...actions}
    />
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Use this session for another customer',
    })
  );
  expect(actions.onJoin).toHaveBeenCalledWith(conference);
});

it('keeps active bridge independent and closed definitions reusable', () => {
  const bridge = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'bridge',
  } as SavedRecord;
  const actions = callbacks();
  const props = {
    disabled: false,
    incomplete: false,
    activeOnly: true,
    ...actions,
  };
  const { rerender } = render(
    <CommunicationsView {...props} items={page([bridge]).items} />
  );
  expect(screen.getByRole('heading', { name: 'Active Calls' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Active Bridges' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Close conference' }));
  expect(actions.onConferenceAction).toHaveBeenCalledWith(bridge, 'close');
  const closed = {
    ...bridge,
    payload: { ...bridge.payload, status: 'closed' },
  } as SavedRecord;
  rerender(<CommunicationsView {...props} items={page([closed]).items} />);
  expect(screen.queryByRole('article')).toBeNull();
  rerender(
    <CommunicationsView
      {...props}
      activeOnly={false}
      items={page([closed]).items}
    />
  );
  expect(
    screen.getByRole('article', { name: 'Conference Conference' })
  ).toBeTruthy();
});
it('does not promote previous replay bridge definitions as active sessions', () => {
  const bridge = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'old',
  } as SavedRecord;
  render(
    <CommunicationsView
      activeOnly
      items={page([bridge]).items}
      disabled={false}
      incomplete={false}
      isSessionCurrent={() => false}
      {...callbacks()}
    />
  );
  expect(screen.queryByRole('article')).toBeNull();
});

it('retains multiple independent bridges and customer reports when a call finishes', () => {
  const bridge = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'bridge',
    scope: 'leg',
    leg_id: 'leg-a',
  } as SavedRecord;
  const other = {
    ...bridge,
    record_id: 'other',
    payload: {
      ...bridge.payload,
      title: 'Other bridge',
      status: 'interrupted',
    },
  } as SavedRecord;
  const call = {
    ...record,
    ...callDraft(undefined, 'planned', 'mission-a'),
    record_id: 'call',
  } as SavedRecord;
  const customer = {
    ...record,
    ...participationDraft('mission-a', 'bridge'),
    record_id: 'customer',
  } as SavedRecord;
  const actions = { ...callbacks(), onCallAction: vi.fn() };
  const props = {
    activeOnly: true,
    disabled: false,
    incomplete: false,
    ...actions,
  };
  const { rerender } = render(
    <CommunicationsView
      {...props}
      items={page([bridge, other, call, customer]).items}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Start call' }));
  expect(actions.onCallAction).toHaveBeenCalledWith(call, 'start');
  const finished = {
    ...call,
    payload: { ...call.payload, status: 'completed' },
  } as SavedRecord;
  rerender(
    <CommunicationsView
      {...props}
      items={page([bridge, other, finished, customer]).items}
    />
  );
  expect(screen.getAllByRole('article').length).toBeGreaterThanOrEqual(2);
  fireEvent.click(screen.getByRole('button', { name: 'Customer Left' }));
  expect(actions.onCustomerAction).toHaveBeenCalledWith(customer, 'left');
  expect(screen.queryByRole('button', { name: 'Start call' })).toBeNull();
  expect(actions.onConferenceAction).not.toHaveBeenCalled();
});
it('excludes a bridge session reported in another phase', () => {
  const bridge = {
    ...record,
    ...conferenceDraft('mission-a'),
    scope: 'leg',
    leg_id: 'old-leg',
  } as SavedRecord;
  render(
    <CommunicationsView
      activeOnly
      items={page([bridge]).items}
      disabled={false}
      incomplete={false}
      currentAssociation={{
        scope: 'leg',
        leg_id: 'current-leg',
        previous_leg_id: null,
        next_leg_id: null,
        label: 'Current',
      }}
      {...callbacks()}
    />
  );
  expect(screen.queryByRole('article')).toBeNull();
});
