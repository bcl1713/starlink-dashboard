import { enterZulu } from '@/test/utc-controls';
/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ConferenceEditor } from './ConferenceEditor';
import { ParticipationEditor } from './ParticipationEditor';
import { conferenceDraft, participationDraft } from './conferenceCommands';
import { IssueForm, type IssueEditorDraft } from './IssueEditor';
import { issueInput } from './issueForms';
import { record } from '@/test/operator-fixtures';
import type { SavedRecord } from '@/types/operator';
afterEach(cleanup);
const change = (label: string, value: string) =>
  fireEvent.change(
    screen.getByLabelText((text) => text.toLowerCase() === label.toLowerCase()),
    { target: { value } }
  );
it('submits independent conference intent, configuration, coordinator and retrospective UTC fields', () => {
  const submit = vi.fn();
  function Form() {
    const [draft, setDraft] = useState(conferenceDraft('mission-a'));
    return (
      <ConferenceEditor
        draft={draft}
        onChange={setDraft}
        onSubmit={submit}
        disabled={false}
      />
    );
  }
  render(<Form />);
  change('Conference name (optional)', 'Fictional coordination bridge');
  change('Conference state', 'established');
  change('Coordinator (optional)', 'Fictional coordinator');
  change('Intended Transport', 'X');
  change('Operator-reported configuration', 'Ka');
  enterZulu('Configuration report', '2026-10-17T15:30:00Z');
  enterZulu('Two-way check', '2026-10-17T15:31:00Z');
  enterZulu('Action occurrence', '2026-10-17T15:00:00Z');
  change('Conference note (optional)', 'Retrospective operator report');
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  expect(submit.mock.calls[0][0]).toMatchObject({
    mission_id: 'mission-a',
    payload: {
      status: 'established',
      coordinator: 'Fictional coordinator',
      intended_transport: 'X',
      configured_transport: 'Ka',
      configuration_reported_at: '2026-10-17T15:30:00Z',
      verified_at: '2026-10-17T15:31:00Z',
      note: 'Retrospective operator report',
    },
    time: {
      occurred_at: '2026-10-17T15:00:00Z',
      precision: 'approximate',
      ended_at: null,
      end_state: 'instant',
    },
  });
  change('Operator-reported configuration', 'Starshield');
  expect(
    (screen.getByLabelText('Two-way check date (Zulu)') as HTMLInputElement)
      .value
  ).toBe('');
  enterZulu('Configuration report', '');
  enterZulu('Action occurrence', '');
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  expect(submit.mock.calls[1][0]).toMatchObject({
    payload: {
      configured_transport: 'Starshield',
      verified_at: null,
      configuration_reported_at: null,
    },
    time: { occurred_at: null, precision: 'unknown', end_state: 'unknown' },
  });
});
it('submits named participant and both associations while correcting an independent interval', () => {
  const submit = vi.fn();
  const conference = {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'conference-a',
  };
  const call = {
    ...record,
    record_id: 'call-a',
    record_type: 'call',
    payload: {
      ...record.payload,
      entry_type: 'call',
      status: 'scheduled',
      conference_id: null,
    },
  } as SavedRecord;
  function Form() {
    const [draft, setDraft] = useState(participationDraft('mission-a', null));
    return (
      <ParticipationEditor
        draft={draft}
        onChange={setDraft}
        onSubmit={submit}
        records={[conference, call]}
        disabled={false}
      />
    );
  }
  render(<Form />);
  change('Participant (optional)', 'Fictional customer');
  change('Customer call', 'call-a');
  change('Customer conference', 'conference-a');
  change('Customer state', 'left');
  enterZulu('Reported join', '2026-10-17T15:00:00Z');
  enterZulu('Reported leave / interruption', '2026-10-17T15:10:00Z');
  fireEvent.click(
    screen.getByRole('button', { name: 'Save Customer Interval' })
  );
  expect(submit.mock.calls[0][0]).toMatchObject({
    payload: {
      participant: 'Fictional customer',
      call_id: 'call-a',
      conference_id: 'conference-a',
      state: 'left',
    },
    time: {
      occurred_at: '2026-10-17T15:00:00Z',
      ended_at: '2026-10-17T15:10:00Z',
      precision: 'approximate',
      end_state: 'known',
    },
  });
  enterZulu('Reported join', '');
  fireEvent.click(
    screen.getByRole('button', { name: 'Save Customer Interval' })
  );
  expect(submit.mock.calls[1][0].time).toMatchObject({
    occurred_at: null,
    ended_at: null,
    precision: 'unknown',
    end_state: 'unknown',
  });
});
it('submits optional issue priority, ownership and named links and explicitly reschedules follow-up', () => {
  const save = vi.fn().mockResolvedValue(false);
  const related = [
    {
      ...record,
      record_id: 'capability-a',
      payload: {
        ...record.payload,
        entry_type: 'capability_assessment',
        functional_status: 'unknown',
        redundancy_status: 'unknown',
      },
    },
    {
      ...record,
      record_id: 'call-a',
      record_type: 'call',
      payload: {
        ...record.payload,
        entry_type: 'call',
        status: 'scheduled',
        conference_id: null,
      },
    },
    { ...record, ...conferenceDraft('mission-a'), record_id: 'conference-a' },
  ] as SavedRecord[];
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
        asOf="2026-10-17T16:00:00Z"
        related={related}
        onSave={save}
        contextual
      />
    );
  }
  render(<Form />);
  change('Problem Description', 'Fictional audio issue');
  change('Priority', 'high');
  change('Functional Area', 'Audio');
  change('Responsible Party (Optional)', 'Fictional ground team');
  change('Affected Capability', 'capability-a');
  change('Related Call', 'call-a');
  change('Related Conference', 'conference-a');
  change('Relevant Transport', 'X');
  enterZulu('Follow-Up', '2026-10-17T16:30:00');
  fireEvent.click(
    screen.getByRole('button', { name: /In 15 Minutes from Snapshot/i })
  );
  fireEvent.submit(screen.getByRole('form', { name: /Issue Editor/i }));
  expect(save.mock.calls[0][0].body.payload).toMatchObject({
    title: 'Fictional audio issue',
    priority: 'high',
    functional_area: 'Audio',
    responsible_party: 'Fictional ground team',
    capability_id: 'capability-a',
    call_id: 'call-a',
    conference_id: 'conference-a',
    transport: 'X',
    follow_up_at: '2026-10-17T16:15:00.000Z',
  });
  change('Status', 'resolved');
  expect(
    (
      screen
        .getByLabelText('Follow-Up date (Zulu)')
        .closest('fieldset') as HTMLFieldSetElement
    ).disabled
  ).toBe(true);
  fireEvent.submit(screen.getByRole('form', { name: /Issue Editor/i }));
  expect(save.mock.calls[1][0].body.payload).toMatchObject({
    status: 'resolved',
    follow_up_at: null,
  });
});
it('retains canonical standard labels while allowing ad hoc conference transport', () => {
  render(
    <ConferenceEditor
      draft={conferenceDraft('mission-a')}
      disabled={false}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
      transportOptions={[
        { id: 'Ka', name: 'Ka-band' },
        { id: 'backup', name: 'Satellite Backup' },
      ]}
    />
  );
  expect(screen.getAllByRole('option', { name: 'Ka Commercial' })).toHaveLength(
    2
  );
  expect(
    screen.getAllByRole('option', { name: 'Satellite Backup' })
  ).toHaveLength(2);
});
