/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter } from 'react-router-dom';
import { ExpectedLegCards } from './ExpectedLegCards';
import type { PlanningView } from '../../types/planning';
afterEach(cleanup);
it('routes stable expected IDs with sparse expected ordinals and separate computation status', () => {
  const card = (ordinal: number) => ({
    input_identity: 'hash',
    computation_status: 'failed' as const,
    review_status: 'awaiting_kml' as const,
    leg: {
      id: `stable-${ordinal}`,
      ordinal,
      departure_airport: 'AAA',
      arrival_airport: 'BBB',
      departure_time: '2026-10-25T12:00:00Z',
      arrival_time: '2026-10-25T13:00:00Z',
      ar_rows: [],
    },
  });
  const view: PlanningView = {
    mission: {
      id: 'm',
      name: 'Synthetic',
      legs: [],
      metadata: {},
      created_at: '',
      updated_at: '',
    },
    revision: 1,
    expected_legs: [
      card(1),
      card(2),
      card(3),
      { ...card(4), leg: { ...card(4).leg, retired: true } },
    ],
  };
  render(
    <MemoryRouter>
      <ExpectedLegCards view={view} />
    </MemoryRouter>
  );
  expect(
    screen.getAllByRole('link', { name: /Upload KML/ })[2]
  ).toHaveAttribute('href', '/missions/m/legs/stable-3');
  expect(screen.getByText('Leg 3 of 3')).toBeVisible();
  expect(screen.getAllByText('Awaiting KML')).toHaveLength(3);
  expect(screen.getAllByText('Computation: failed')).toHaveLength(3);
  expect(screen.queryByText(/Leg 4/)).toBeNull();
});
