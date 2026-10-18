/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TransportForm } from './TransportEditor';
import { newTransportDraft } from './transportForms';
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
