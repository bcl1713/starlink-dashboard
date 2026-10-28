/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { IssuesView } from './IssuesView';
import { issueInput } from '../issueForms';
import { record, page } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
it('exposes issue lifecycle without changing mitigation or hiding removed history', () => {
  const issue = {
    ...record,
    ...issueInput('mission-a'),
    record_id: 'issue-a',
  } as SavedRecord;
  const action = vi.fn();
  render(
    <IssuesView
      pages={[page([issue])]}
      incomplete={false}
      unavailable={false}
      disabled={false}
      onCreate={vi.fn()}
      onEdit={vi.fn()}
      onAction={action}
      onHistory={vi.fn()}
      onActivity={vi.fn()}
      onTransition={vi.fn()}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Monitor' }));
  expect(action).toHaveBeenCalledWith(issue, 'monitoring');
  expect(screen.getByText(/Mitigation unknown/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Audit History' })).toBeTruthy();
});
