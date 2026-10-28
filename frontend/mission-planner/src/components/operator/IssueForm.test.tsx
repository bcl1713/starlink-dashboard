import { useState } from 'react';
import { enterZulu } from '@/test/utc-controls';
/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { IssueForm, type IssueEditorDraft } from './IssueEditor';
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
  fireEvent.change(screen.getByLabelText('Problem Description'), {
    target: { value: 'Synthetic retained issue' },
  });
  expect(changed.mock.calls[0][0].input.payload.title).toBe(
    'Synthetic retained issue'
  );
  expect(storage).not.toHaveBeenCalled();
  storage.mockRestore();
});
it('clears a partial follow-up date and its required controls before saving', () => {
  const save = vi.fn().mockResolvedValue(false);
  function Form() {
    const [draft, setDraft] = useState<IssueEditorDraft>({
      input: issueInput('mission-a'),
      baseVersion: null,
      occurredAt: null,
      useCurrentTime: true,
    });
    return (
      <IssueForm
        draft={draft}
        onDraftChange={setDraft}
        disabled={false}
        asOf={null}
        related={[]}
        onSave={save}
      />
    );
  }
  render(<Form />);
  fireEvent.change(screen.getByLabelText('Problem Description'), {
    target: { value: 'Voice degraded' },
  });
  fireEvent.change(screen.getByLabelText('Follow-Up date (Zulu)'), {
    target: { value: '2026-10-29' },
  });
  expect(
    (screen.getByLabelText('Follow-Up hour (Zulu)') as HTMLSelectElement)
      .required
  ).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Clear Follow-Up' }));
  expect(
    (screen.getByLabelText('Follow-Up date (Zulu)') as HTMLInputElement).value
  ).toBe('');
  expect(
    (screen.getByLabelText('Follow-Up hour (Zulu)') as HTMLSelectElement)
      .required
  ).toBe(false);
  enterZulu('Follow-Up', '2026-10-30T01:30:00Z');
  fireEvent.click(screen.getByRole('button', { name: 'Clear Follow-Up' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save Issue' }));
  expect(save.mock.calls[0][0].body.payload.follow_up_at).toBeNull();
});
