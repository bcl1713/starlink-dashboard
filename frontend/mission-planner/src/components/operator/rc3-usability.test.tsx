/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { CallEditor } from './CallEditor';
import { callDraft } from './callDraft';
afterEach(cleanup);
it('schedules and reschedules with UTC date and time controls and visible preparation fields', () => {
  const save = vi.fn();
  function Form() {
    const [draft, setDraft] = useState(callDraft(undefined, 'planned', 'demo'));
    return (
      <CallEditor
        draft={draft}
        disabled={false}
        onChange={setDraft}
        onSubmit={save}
      />
    );
  }
  render(<Form />);
  expect(screen.getByLabelText('Planned Start date (Zulu)')).toHaveAttribute(
    'type',
    'date'
  );
  expect(screen.getByLabelText('Planned Start hour (Zulu)')).toHaveProperty(
    'tagName',
    'SELECT'
  );
  expect(screen.getByLabelText('Planned Start minute (Zulu)')).toHaveProperty(
    'tagName',
    'SELECT'
  );
  expect(
    screen.getByLabelText('Communications Type').closest('details')
  ).toBeNull();
  expect(
    screen
      .getByLabelText('Preparation Lead Minutes (blank = unknown)')
      .closest('details')
  ).toBeNull();
  fireEvent.change(screen.getByLabelText('Planned Start date (Zulu)'), {
    target: { value: '2026-10-20' },
  });
  fireEvent.change(screen.getByLabelText('Planned Start hour (Zulu)'), {
    target: { value: '14' },
  });
  fireEvent.change(screen.getByLabelText('Planned Start minute (Zulu)'), {
    target: { value: '30' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
  expect(save.mock.calls[0][0].time.planned_start_at).toBe(
    '2026-10-20T14:30:00Z'
  );
  fireEvent.change(screen.getByLabelText('Planned Start hour (Zulu)'), {
    target: { value: '15' },
  });
  fireEvent.change(screen.getByLabelText('Planned Start minute (Zulu)'), {
    target: { value: '45' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
  expect(save.mock.calls[1][0].time.planned_start_at).toBe(
    '2026-10-20T15:45:00Z'
  );
});
it('retains a partially entered date when parked without inventing a timestamp', () => {
  const changed = vi.fn();
  const draft = callDraft(undefined, 'planned', 'demo');
  const first = render(
    <CallEditor
      draft={draft}
      disabled={false}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      onEditorStateChange={changed}
    />
  );
  fireEvent.change(screen.getByLabelText('Planned Start date (Zulu)'), {
    target: { value: '2026-10-20' },
  });
  const state = changed.mock.calls.at(-1)![0];
  first.unmount();
  render(
    <CallEditor
      draft={draft}
      disabled={false}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      editorState={state}
    />
  );
  expect(screen.getByLabelText('Planned Start date (Zulu)')).toHaveValue(
    '2026-10-20'
  );
  expect(screen.getByLabelText('Planned Start hour (Zulu)')).toHaveValue('');
});

import { CallList } from './CallList';
import { page, record } from '@/test/operator-fixtures';
import { conferenceDraft, participationDraft } from './conferenceCommands';
it('shows contextual actions and independent bridge and customer reports on a call card', () => {
  const call = {
    ...record,
    ...callDraft(undefined, 'planned', 'demo'),
    record_id: 'call-a',
  };
  call.payload.conference_id = 'bridge';
  const bridge = { ...record, ...conferenceDraft('demo'), record_id: 'bridge' };
  const action = vi.fn();
  const view = render(
    <CallList
      items={page([call, bridge]).items}
      disabled={false}
      incomplete={false}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onTransition={vi.fn()}
      onCallAction={action}
      onConferenceAction={action}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: /Establish Bridge/i }));
  expect(action).toHaveBeenCalledWith(bridge, 'establish');
  expect(screen.getByText(/Bridge: .*preparing/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Reschedule' })).toBeVisible();
  const running = {
    ...call,
    time: { ...call.time, occurred_at: '2026-10-20T11:00:00Z' },
  };
  const customer = {
    ...record,
    ...participationDraft('demo', 'bridge'),
    record_id: 'customer',
  };
  customer.payload.call_id = call.record_id;
  view.rerender(
    <CallList
      items={page([running, bridge, customer]).items}
      disabled={false}
      incomplete={false}
      onEdit={vi.fn()}
      onHistory={vi.fn()}
      onTransition={vi.fn()}
      onCallAction={action}
      onConferenceAction={action}
    />
  );
  expect(screen.queryByRole('button', { name: 'Start call' })).toBeNull();
  expect(screen.getByText(/In progress/)).toBeVisible();
  expect(screen.getByText(/Actual: 20 Oct 2026/)).toBeVisible();
  expect(
    screen.queryByRole('button', { name: /Report Call Tested/i })
  ).toBeNull();
  expect(
    screen.getByRole('button', { name: 'Report Customer Left' })
  ).toBeVisible();
  expect(screen.getByRole('button', { name: 'Finish Call' })).toBeDisabled();
});
it('names the retained draft as soon as the participant is entered', () => {
  const change = vi.fn();
  render(
    <CallEditor
      draft={callDraft(undefined, 'planned', 'demo')}
      disabled={false}
      onChange={change}
      onSubmit={vi.fn()}
    />
  );
  fireEvent.change(screen.getByLabelText('Party / Participant (Optional)'), {
    target: { value: 'Recognizable draft' },
  });
  expect(change.mock.calls[0][0].payload.title).toBe('Recognizable draft');
});
