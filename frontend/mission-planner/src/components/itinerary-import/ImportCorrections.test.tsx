import { enterZulu } from '@/test/utc-controls';
/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { ImportCorrections } from './ImportCorrections';
import type { ImportOperation } from '../../types/itinerary-import';
afterEach(cleanup);
it('lets an operator explicitly confirm an unrecognized AR section has no AR', () => {
  const resolve = vi.fn();
  const operation = {
    issues: [
      {
        code: 'ar_section_unrecognized',
        message: 'Confirm AR section',
        leg_id: 'leg',
        candidates: [],
      },
    ],
    details: {
      itinerary: {
        name: 'Invented',
        expected_legs: [
          {
            id: 'leg',
            ordinal: 1,
            departure_airport: 'AAAA',
            arrival_airport: 'BBBB',
            departure_time: '2035-01-01T10:00:00Z',
            arrival_time: '2035-01-01T11:00:00Z',
            ar_section_status: 'unrecognized',
            ar_rows: [],
          },
        ],
      },
    },
  } as unknown as ImportOperation;
  render(
    <ImportCorrections operation={operation} busy={false} onResolve={resolve} />
  );
  fireEvent.change(screen.getByLabelText('AR section for leg 1'), {
    target: { value: 'empty' },
  });
  enterZulu('Arrival', '2035-01-02T00:15:00Z');
  fireEvent.click(screen.getByRole('button', { name: 'Continue import' }));
  expect(resolve).toHaveBeenCalledWith(
    expect.objectContaining({
      itinerary: expect.objectContaining({
        expected_legs: [
          expect.objectContaining({
            ar_section_status: 'empty',
            arrival_time: '2035-01-02T00:15:00Z',
            departure_time: '2035-01-01T10:00:00Z',
          }),
        ],
      }),
    })
  );
});
