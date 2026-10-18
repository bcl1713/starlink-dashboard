/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TransportForm } from './TransportEditor';
import { newTransportDraft } from './transportForms';
import { record } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
it('submits applied-only transport from a controlled draft without legacy storage', async () => {
  const save = vi.fn().mockResolvedValue(false);
  const storage = vi.spyOn(Storage.prototype, 'setItem');
  function Form() {
    const [draft, setDraft] = useState(newTransportDraft('mission-a'));
    return (
      <TransportForm
        draft={draft}
        onDraftChange={setDraft}
        disabled={false}
        onSave={save}
      />
    );
  }
  render(<Form />);
  fireEvent.change(screen.getByLabelText('Service 1'), {
    target: { value: 'Synthetic video' },
  });
  fireEvent.click(screen.getByLabelText('Reported Applied 1'));
  fireEvent.change(screen.getByLabelText('Applied transport 1'), {
    target: { value: 'Ka' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save transport decision' })
  );
  await vi.waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0].body.payload.services[0]).toMatchObject({
    requested: null,
    intended: null,
    applied: { transport: 'Ka' },
  });
  expect(storage).not.toHaveBeenCalled();
  storage.mockRestore();
});

it('offers readable mission-scoped call and conference choices', () => {
  const draft = newTransportDraft('mission-a');
  const changed = vi.fn();
  const call: SavedRecord = {
    ...record,
    record_type: 'call',
    payload: {
      ...record.payload,
      entry_type: 'call',
      title: 'Meridian customer briefing',
      status: 'scheduled',
      conference_id: null,
    },
  };
  const conference: SavedRecord = {
    ...record,
    record_id: 'bridge',
    record_type: 'conference',
    payload: {
      ...record.payload,
      entry_type: 'conference',
      status: 'established',
      title: 'Harbor coordination bridge',
    },
  };
  render(
    <TransportForm
      draft={draft}
      onDraftChange={changed}
      disabled={false}
      contextual
      records={[
        call,
        conference,
        {
          ...call,
          record_id: 'other',
          mission_id: 'other',
          payload: { ...call.payload, title: 'Other mission call' },
        },
      ]}
      onSave={vi.fn()}
    />
  );
  fireEvent.click(
    screen.getByText('Reason, timing and associations (optional)')
  );
  const calls = screen.getByRole('combobox', { name: 'Related call' });
  expect(
    screen.getByRole('option', { name: 'Meridian customer briefing' })
  ).toBeTruthy();
  expect(
    screen.queryByRole('option', { name: 'Other mission call' })
  ).toBeNull();
  fireEvent.change(calls, { target: { value: call.record_id } });
  expect(changed.mock.calls[0][0].input.payload.call_id).toBe(call.record_id);
  expect(
    screen.getByRole('option', { name: 'Harbor coordination bridge' })
  ).toBeTruthy();
});
it('retains an unresolved saved association instead of silently clearing it', () => {
  const draft = newTransportDraft('mission-a');
  draft.input.payload.call_id = 'not-in-loaded-page';
  render(
    <TransportForm
      draft={draft}
      onDraftChange={vi.fn()}
      disabled={false}
      contextual
      records={[]}
      onSave={vi.fn()}
    />
  );
  fireEvent.click(
    screen.getByText('Reason, timing and associations (optional)')
  );
  const select = screen.getByRole('combobox', {
    name: 'Related call',
  }) as HTMLSelectElement;
  expect(select.value).toBe('not-in-loaded-page');
  expect(
    screen.getByRole('option', { name: 'Saved call (not loaded)' })
  ).toBeTruthy();
  expect(screen.getByText(/Choices cover loaded records only/)).toBeTruthy();
});
