/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { page, record } from '@/test/operator-fixtures';
import { RevisionDetails } from './RevisionDetails';
afterEach(cleanup);
it('makes superseded issue text and manual capability values inspectable in audit', () => {
  const issue = {
    ...record,
    record_type: 'issue' as const,
    payload: {
      ...record.payload,
      entry_type: 'issue' as const,
      status: 'resolved' as const,
      update_text: 'Synthetic superseded backup report',
    },
  };
  const view = render(<RevisionDetails {...page([issue]).items[0]} />);
  expect(screen.getByText(/Synthetic superseded backup report/)).toBeTruthy();
  const assessment = {
    ...record,
    payload: {
      ...record.payload,
      entry_type: 'capability_assessment' as const,
      functional_status: 'functional' as const,
      redundancy_status: 'unavailable' as const,
      functional_observed_at: null,
      redundancy_observed_at: null,
      functional_time_precision: 'unknown' as const,
      redundancy_time_precision: 'unknown' as const,
    },
  };
  view.rerender(<RevisionDetails {...page([assessment]).items[0]} />);
  expect(screen.getByText(/Functional: functional/)).toBeTruthy();
  expect(screen.getByText(/Redundancy: unavailable/)).toBeTruthy();
});
