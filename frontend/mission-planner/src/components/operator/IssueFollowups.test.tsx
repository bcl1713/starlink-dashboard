/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { page, record } from '@/test/operator-fixtures';
import { IssueFollowups } from './IssueFollowups';
afterEach(cleanup);
it('does not show no-follow-ups when the snapshot is incomplete or stale', () => {
  const view = render(
    <IssueFollowups pages={[page([])]} incomplete unavailable={false} />
  );
  expect(screen.queryByText(/No due follow-ups/)).toBeNull();
  view.rerender(
    <IssueFollowups pages={[page([])]} incomplete={false} unavailable />
  );
  expect(screen.queryByText(/No due follow-ups/)).toBeNull();
});
it('includes reopened and monitoring issues with due snapshots', () => {
  const snapshot = page([
    {
      ...record,
      record_type: 'issue',
      payload: { ...record.payload, entry_type: 'issue', status: 'reopened' },
    },
  ]);
  snapshot.items[0].follow_up = {
    state: 'overdue',
    as_of: snapshot.as_of,
    record_id: record.record_id,
    version: 1,
    follow_up_at: '2026-10-17T10:00:00Z',
  };
  render(
    <IssueFollowups pages={[snapshot]} incomplete={false} unavailable={false} />
  );
  expect(screen.getByText(/1 follow-up due in this snapshot/)).toBeTruthy();
});
