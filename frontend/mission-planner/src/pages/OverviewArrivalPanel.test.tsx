/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { OverviewArrivalPanel } from './OverviewArrivalPanel';
import { deriveArrivalPanel } from './overview-arrival';
import type { OverviewUpcomingPoisResponse } from '@/services/overview-upcoming-pois';

afterEach(cleanup);
const now = Date.parse('2026-10-01T12:00:00Z');
const response: OverviewUpcomingPoisResponse = {
  state: 'available',
  calculated_at: new Date(now).toISOString(),
  flight_phase: 'pre_departure',
  current_route_progress: null,
  position_state: 'unavailable',
  position_observed_at: null,
  scheduled_departure_time: '2026-10-01T11:48:00Z',
  pois: [],
};
it('renders accessible UTC provenance and late departure independently of GPS', () => {
  render(<OverviewArrivalPanel state={deriveArrivalPanel(response, now)} />);
  expect(
    screen.getByRole('heading', { name: 'SCHEDULED DEPARTURE' })
  ).toBeTruthy();
  expect(screen.getByText('12 MIN AGO').className).toContain('countdown--late');
  expect(
    screen.getByLabelText('2026-10-01T11:48:00.000Z').getAttribute('datetime')
  ).toBe('2026-10-01T11:48:00.000Z');
  expect(screen.queryByRole('table')).toBeNull();
});
it('removes timing when refresh fails and communicates the exception in text', () => {
  render(
    <OverviewArrivalPanel state={deriveArrivalPanel(response, now, true)} />
  );
  expect(screen.queryByText('12 MIN AGO')).toBeNull();
  expect(screen.getByRole('status').textContent).toBe(
    'Arrival refresh unavailable'
  );
  expect(screen.getByText('Departure schedule unavailable')).toBeTruthy();
});
it('renders explicit context states', () => {
  render(
    <OverviewArrivalPanel
      state={deriveArrivalPanel(
        { ...response, state: 'route_unavailable' },
        now
      )}
    />
  );
  expect(
    screen.getByText('Active mission leg is not bound to the active route.')
  ).toBeTruthy();
});
