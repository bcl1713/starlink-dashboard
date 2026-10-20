/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { IssueForm } from './IssueEditor';
import { issueInput } from './issueForms';
afterEach(cleanup);
it('keeps issue text in the supplied workspace draft and never writes a legacy draft', () => {
  const changed = vi.fn();
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  const draft = {
    input: issueInput('mission-a'),
    baseVersion: null,
    occurredAt: null,
    useCurrentTime: true,
  };
  render(
    <IssueForm
      draft={draft}
      onDraftChange={changed}
      disabled={false}
      asOf={null}
      related={[]}
      onSave={vi.fn()}
    />
  );
  fireEvent.change(screen.getByLabelText('Problem description'), {
    target: { value: 'Synthetic retained issue' },
  });
  expect(changed.mock.calls[0][0].input.payload.title).toBe(
    'Synthetic retained issue'
  );
  expect(storage).not.toHaveBeenCalled();
  storage.mockRestore();
});
