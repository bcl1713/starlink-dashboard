/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { UnresolvedARWindows } from './UnresolvedARWindows';
afterEach(cleanup);
it('requires two explicit accepted occurrences before replacing a pending AR window', () => {
  const change = vi.fn();
  render(
    <UnresolvedARWindows
      leg={{
        id: 'l',
        ordinal: 1,
        departure_airport: 'A',
        arrival_airport: 'B',
        departure_time: '2026-10-25T12:00:00Z',
        arrival_time: '2026-10-25T13:00:00Z',
        route: {
          route_id: 'r',
          source_id: 's',
          content_hash: 'h',
          filename: 'r.kml',
        },
      }}
      draft={{
        unresolved_aar_windows: [
          { id: 'ar', start_waypoint_name: 'ENTRY', end_waypoint_name: 'EXIT' },
        ],
      }}
      routePoints={[
        {
          latitude: 1,
          longitude: 2,
          occurrence_id: 'one',
          expected_arrival_time: '2026-10-25T12:00:00Z',
        },
        {
          latitude: 2,
          longitude: 3,
          occurrence_id: 'two',
          expected_arrival_time: '2026-10-25T13:00:00Z',
        },
      ]}
      onChange={change}
    />
  );
  expect(screen.getByRole('button', { name: 'Resolve AR ar' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('AR ar start occurrence'), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText('AR ar end occurrence'), {
    target: { value: '1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Resolve AR ar' }));
  expect(change).toHaveBeenCalledWith(
    expect.objectContaining({
      unresolved_aar_windows: [],
      ar_corrections: [
        expect.objectContaining({
          id: 'ar',
          confirmed: false,
          entry_time: '2026-10-25T12:00:00Z',
          start_anchor: expect.objectContaining({ occurrence_id: 'one' }),
        }),
      ],
    })
  );
});
