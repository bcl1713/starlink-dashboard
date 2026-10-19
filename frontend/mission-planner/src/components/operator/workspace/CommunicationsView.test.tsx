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
  expect(screen.queryByRole('button', { name: 'Reuse conference' })).toBeNull();
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
  fireEvent.click(screen.getByRole('button', { name: 'Reuse conference' }));
  expect(actions.onJoin).toHaveBeenCalledWith(conference);
});
