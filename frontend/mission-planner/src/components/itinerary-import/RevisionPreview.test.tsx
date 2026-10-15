/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { RevisionPreview } from './RevisionPreview';
import type { ImportOperation } from '../../types/itinerary-import';
afterEach(cleanup);
it('shows affected legs and values for changes and conflicting edits', () => {
  const operation = {
    details: {
      revision: {
        changes: ['legs.leg1.route_id'],
        change_details: [
          {
            field: 'legs.leg1.route_id',
            leg: 'AAAA–BBBB',
            current: 'old-route',
            incoming: 'new-route',
          },
        ],
        leg_names: { leg2: 'BBBB–CCCC' },
        conflicts: [
          {
            field: 'legs.leg2.adjusted_departure_time',
            current: '2035-01-01T12:00:00Z',
            incoming: '2035-01-01T13:00:00Z',
            baseline: null,
          },
        ],
      },
    },
  } as unknown as ImportOperation;
  render(
    <RevisionPreview operation={operation} busy={false} onApply={vi.fn()} />
  );
  expect(screen.getByText('AAAA–BBBB: Route')).toBeInTheDocument();
  expect(screen.getByText('"old-route"')).toBeInTheDocument();
  expect(screen.getByText('"new-route"')).toBeInTheDocument();
  expect(screen.getByText('BBBB–CCCC: Takeoff time')).toBeInTheDocument();
  expect(screen.getByText('"2035-01-01T12:00:00Z"')).toBeInTheDocument();
  expect(screen.getByText('"2035-01-01T13:00:00Z"')).toBeInTheDocument();
});
