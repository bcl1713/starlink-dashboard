/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorEventStrip } from './OperatorEventStrip';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.restoreAllMocks();
});
function state(): OperatorEventsState {
  return {
    snapshot: eventSnapshot(),
    receivedAt: performance.now(),
    failed: false,
    loading: false,
    refreshing: false,
    visible: true,
    refresh: vi.fn(),
    acknowledge: vi.fn(async () => {}),
    acknowledging: false,
    pendingAcknowledgment: null,
    retryAcknowledgment: async () => {},
    discardPending: vi.fn(),
    acknowledgmentError: null,
    blocked: false,
    storageWarning: null,
  };
}
it('opens a compact timeline without removing acknowledged events or unknown protection', async () => {
  const events = state();
  const protectedEvent = eventFixture({
    kind: 'restriction',
    title: 'Synthetic modeled restriction',
    provenance: 'modeled',
    significance: 'unavailable',
    protected_participation_ids: ['customer'],
    discrepancies: ['Connected customer; conference continuity unknown'],
  });
  protectedEvent.notification = {
    ...protectedEvent.notification,
    acknowledged: true,
    acknowledgment_available: false,
  };
  events.snapshot = eventSnapshot({ events: [protectedEvent] });
  render(
    <MemoryRouter>
      <OperatorEventStrip events={events} />
    </MemoryRouter>
  );
  expect(screen.queryByRole('dialog')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Open events' }));
  const dialog = screen.getByRole('dialog', { name: 'Operational timeline' });
  expect(
    within(dialog).getByText('Synthetic modeled restriction')
  ).toBeTruthy();
  expect(
    within(dialog).getByText(
      /Connected customer; conference continuity unknown/
    )
  ).toBeTruthy();
  expect(
    within(dialog).getByRole('button', { name: 'Acknowledged' })
  ).toBeDisabled();
  expect(within(dialog).getAllByText(/Modeled/).length).toBeGreaterThan(0);
  expect(
    within(dialog)
      .getByRole('link', { name: 'Open Communications' })
      .getAttribute('href')
  ).toBe('#operator-communications');
});
it('acknowledges a notification separately from opening its source and preserves drafts', async () => {
  const events = state();
  render(
    <MemoryRouter>
      <label>
        Unsent draft
        <input defaultValue="Keep this draft" />
      </label>
      <OperatorEventStrip events={events} />
    </MemoryRouter>
  );
  const trigger = screen.getByRole('button', { name: 'Open events' });
  fireEvent.click(trigger);
  const dialog = screen.getByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Acknowledge' }));
  expect(events.acknowledge).toHaveBeenCalledWith(events.snapshot!.events[0]);
  fireEvent.click(
    within(dialog).getByRole('link', { name: 'Open Communications' })
  );
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(
    (screen.getByLabelText('Unsent draft') as HTMLInputElement).value
  ).toBe('Keep this draft');
});
it('does not report an all-clear on failure and explains local delivery limits', () => {
  const events = state();
  events.failed = true;
  render(
    <MemoryRouter>
      <OperatorEventStrip events={events} />
    </MemoryRouter>
  );
  expect(screen.getByText(/Feed unavailable/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Local alerts' }));
  expect(
    screen.getByText(/Closed or background browser delivery is not guaranteed/)
  ).toBeTruthy();
  expect(
    screen.getByRole('button', { name: 'Enable sound and vibration' })
  ).toBeTruthy();
});
