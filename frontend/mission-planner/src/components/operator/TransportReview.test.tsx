/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type {
  TransportAssessment,
  TransportReviewData,
} from '@/types/operatorTransport';
import { TransportReview } from './TransportReview';
afterEach(cleanup);
it('groups identical context messages without showing null transport as a reported path', () => {
  const assessment: TransportAssessment = {
    decision_id: 'synthetic-decision',
    row_id: 'row',
    service: 'VTC',
    subject: 'change_vs_activity',
    report_stage: 'applied',
    transport: null,
    status: 'possible_impact',
    message: 'Customer communications may be affected; timing unknown',
    activity_id: 'one',
    event_ids: [],
    source_refs: [],
    dependent_versions: {},
    time_basis: null,
    freshness: 'fresh',
  };
  const review: TransportReviewData = {
    as_of: '2026-10-17T16:45:00Z',
    H: 1,
    actual_routing: 'unknown',
    coverage: 'partial',
    horizon_end_at: '2026-10-18T16:45:00Z',
    activities: [],
    assessments: [assessment, { ...assessment, activity_id: 'two' }],
  };
  render(<TransportReview review={review} stale={false} error={false} />);
  expect(
    screen.getAllByText(/Customer communications may be affected/)
  ).toHaveLength(1);
  expect(screen.queryByText(/applied null/i)).toBeNull();
  expect(screen.getByText(/2 communications contexts/)).toBeTruthy();
});
it('keeps distinct modeled restrictions separate', () => {
  const base: TransportAssessment = {
    decision_id: 'synthetic-decision',
    row_id: 'row',
    service: 'VTC',
    subject: 'communications_vs_restriction',
    report_stage: 'requested',
    transport: 'X',
    status: 'overlap',
    message: 'Customer window overlaps modeled restriction',
    activity_id: 'one',
    event_ids: ['x-window'],
    source_refs: ['model:leg'],
    dependent_versions: {},
    time_basis: 'live_route_eta',
    freshness: 'fresh',
  };
  const review: TransportReviewData = {
    as_of: '2026-10-17T16:45:00Z',
    H: 1,
    actual_routing: 'unknown',
    coverage: 'available',
    horizon_end_at: '2026-10-18T16:45:00Z',
    activities: [],
    assessments: [base, { ...base, event_ids: ['ka-window'] }],
  };
  render(<TransportReview review={review} stale={false} error={false} />);
  expect(
    screen.getAllByText(/Customer window overlaps modeled restriction/)
  ).toHaveLength(2);
});
