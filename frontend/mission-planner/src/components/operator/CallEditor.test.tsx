/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import type { CallInput, SavedRecord } from '@/types/operator';
import { record } from '@/test/operator-fixtures';
import { conferenceDraft } from './conferenceCommands';
import { CallEditor } from './CallEditor';
import { callDraft } from './callDraft';
afterEach(cleanup);
function mount(
  mode: 'planned' | 'retrospective' = 'planned',
  lead?: number | null,
  records?: SavedRecord[]
) {
  const submitted = vi.fn();
  const initial = callDraft(undefined, mode, 'demo');
  if (lead !== undefined) initial.payload.prep_lead_minutes = lead;
  function Wrapper() {
    const [draft, setDraft] = useState<CallInput>(initial);
    return (
      <CallEditor
        draft={draft}
        disabled={false}
        onChange={setDraft}
        onSubmit={submitted}
        records={records}
      />
    );
  }
  render(<Wrapper />);
  return submitted;
}
function field(name: string, value: string) {
  const labels: Record<string, string> = {
    'Planned start (UTC)': 'Planned start',
    'Actual start (UTC, optional)': 'Actual start',
    'Actual end (UTC, optional)': 'Actual end',
  };
  if (labels[name]) {
    fireEvent.change(screen.getByLabelText(`${labels[name]} date (UTC)`), {
      target: { value: value.slice(0, 10) },
    });
    fireEvent.change(screen.getByLabelText(`${labels[name]} time (UTC)`), {
      target: { value: value.slice(11, 16) },
    });
  } else fireEvent.change(screen.getByLabelText(name), { target: { value } });
}
it.each(['tentative', 'delayed'] as const)(
  'retains %s status and optional named conference, type and coordinator fields',
  (status) => {
    const conference = {
      ...record,
      ...conferenceDraft('demo'),
      record_id: 'conference-a',
    };
    const submit = mount('planned', undefined, [conference]);
    field('Planned start (UTC)', '2026-10-17T17:00:00Z');
    field('Status', status);
    field('Communications type', 'vtc');
    field('Ground coordinator (optional)', 'Fictional ground coordinator');
    field('Conference (optional)', conference.record_id);
    fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
    expect(submit.mock.calls[0][0]).toMatchObject({
      payload: {
        status,
        communications_kind: 'vtc',
        coordinator: 'Fictional ground coordinator',
        conference_id: 'conference-a',
        prep_lead_minutes: 10,
      },
      time: {
        planned_start_at: '2026-10-17T17:00:00Z',
        occurred_at: null,
        ended_at: null,
      },
    });
  }
);
it('creates from party/time alone with unknown duration', () => {
  const submit = mount();
  field('Party / participant (optional)', 'Synthetic party');
  field('Planned start (UTC)', '2026-10-17T23:45:00Z');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0]).toMatchObject({
    time: {
      planned_start_at: '2026-10-17T23:45:00Z',
      planned_end_at: null,
      occurred_at: null,
    },
    payload: {
      party: 'Synthetic party',
      title: 'Synthetic party',
      prep_lead_minutes: 10,
    },
  });
});
it.each([null, 0, 25])('unrelated edits retain lead %s', (lead) => {
  const submit = mount('retrospective', lead);
  field('Notes (optional)', 'Corrected');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0].payload.prep_lead_minutes).toBe(lead);
  expect(submit.mock.calls[0][0].time.planned_start_at).toBeNull();
});
it('shifts across midnight without inventing an end', () => {
  const submit = mount();
  field('Planned start (UTC)', '2026-10-17T23:45:00Z');
  field('Shift amount', '2');
  fireEvent.change(screen.getByLabelText('Shift unit'), {
    target: { value: 'hours' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Apply shift' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0].time).toMatchObject({
    planned_start_at: '2026-10-18T01:45:00.000Z',
    planned_end_at: null,
  });
});
it('logs actual timing independently and validates end-only input', () => {
  const submit = mount('retrospective');
  field('Actual end (UTC, optional)', '2026-10-17T14:42:00Z');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toBeTruthy();
  field('Actual start (UTC, optional)', '2026-10-17T14:30:00Z');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0]).toMatchObject({
    time: {
      occurred_at: '2026-10-17T14:30:00Z',
      ended_at: '2026-10-17T14:42:00Z',
      precision: 'exact',
      end_state: 'known',
      planned_start_at: null,
    },
    payload: { status: 'completed', prep_lead_minutes: null },
  });
});
it('keeps invalid numeric input visible without submitting', () => {
  const submit = mount('retrospective');
  field('Preparation lead minutes (blank = unknown)', '1.5');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit).not.toHaveBeenCalled();
  expect(
    (
      screen.getByLabelText(
        'Preparation lead minutes (blank = unknown)'
      ) as HTMLInputElement
    ).value
  ).toBe('1.5');
});
it('preserves precise known planned duration on an unrelated edit', () => {
  const submit = vi.fn();
  const initial = callDraft(undefined, 'planned', 'demo');
  initial.time.planned_start_at = '2026-10-17T17:00:00.123456Z';
  initial.time.planned_end_at = '2026-10-17T17:12:30.123456Z';
  function Wrapper() {
    const [draft, setDraft] = useState(initial);
    return (
      <CallEditor
        draft={draft}
        disabled={false}
        onChange={setDraft}
        onSubmit={submit}
      />
    );
  }
  render(<Wrapper />);
  field('Notes (optional)', 'Only note changed');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0].time.planned_end_at).toBe(
    '2026-10-17T17:12:30.123456Z'
  );
});
it('corrects legacy scheduled unknown timing without requiring an invented start', () => {
  const submit = vi.fn();
  const initial = callDraft(undefined, 'planned', 'demo');
  initial.payload.prep_lead_minutes = null;
  function Wrapper() {
    const [draft, setDraft] = useState(initial);
    return (
      <CallEditor
        draft={draft}
        creating={false}
        disabled={false}
        onChange={setDraft}
        onSubmit={submit}
      />
    );
  }
  render(<Wrapper />);
  field('Notes (optional)', 'Legacy correction');
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  expect(submit.mock.calls[0][0].time.planned_start_at).toBeNull();
  expect(submit.mock.calls[0][0].payload.prep_lead_minutes).toBeNull();
});
it('restores unsent duration, prep and shift controls after the editor is parked', () => {
  const initial = callDraft(undefined, 'planned', 'demo');
  const changed = vi.fn();
  const first = render(
    <CallEditor
      draft={initial}
      disabled={false}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      onEditorStateChange={changed}
    />
  );
  field('Preparation lead minutes (blank = unknown)', '0');
  expect(changed).toHaveBeenCalled();
  const saved = changed.mock.calls.at(-1)![0];
  first.unmount();
  render(
    <CallEditor
      draft={initial}
      disabled={false}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      editorState={saved}
    />
  );
  expect(
    (
      screen.getByLabelText(
        'Preparation lead minutes (blank = unknown)'
      ) as HTMLInputElement
    ).value
  ).toBe('0');
});
