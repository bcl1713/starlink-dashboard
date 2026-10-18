import { expect, it } from 'vitest';
import fixture from '../../../../../backend/starlink-location/tests/fixtures/operator/issue-corrections.json';
import { record } from '@/test/operator-fixtures';
import type { SavedRecord, IssuePayload } from '@/types/operator';
import { projectIssueActivity } from './issueActivity';
const revisions: SavedRecord[] = fixture.actions.map((action, index) => ({
  ...record,
  record_type: 'issue',
  version: index + 1,
  journal_seq: index + 1,
  operation: index ? 'update' : 'create',
  recorded_at: action.recorded_at,
  time: { ...record.time, occurred_at: action.occurred_at },
  payload: {
    ...record.payload,
    entry_type: 'issue',
    status: action.status,
    update_text: action.update_text,
    corrects_version: action.corrects_version ?? null,
    corrected_update_at: action.corrected_update_at ?? null,
  } as IssuePayload,
}));
it('shows one corrected historical message while resolution remains one action', () => {
  const activity = projectIssueActivity(revisions);
  expect(activity.updates).toHaveLength(1);
  expect(activity.updates[0]).toMatchObject({
    text: 'Backup intermittent',
    effectiveAt: '2026-01-02T10:04:00Z',
    corrected: true,
    recordedAt: '2026-01-02T10:30:00Z',
    rootVersion: 2,
  });
  expect(
    activity.lifecycle.filter((item) => item.status === 'resolved')
  ).toHaveLength(1);
  expect(projectIssueActivity(revisions.slice(0, 3)).updates[0].text).toBe(
    'Backup unavailable'
  );
});
