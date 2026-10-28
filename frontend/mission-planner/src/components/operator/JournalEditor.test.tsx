/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { JournalEditor } from './JournalEditor';
import type { JournalInput } from '@/types/operator';
import { input, record } from '@/test/operator-fixtures';
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
it('preserves untouched UTC microseconds and a dirty draft across refetch; no reason prompt', () => {
  const save = vi.fn();
  const props = {
    missionId: 'mission-a',
    record,
    onSave: save,
    disabled: false,
  };
  const view = render(<JournalEditor {...props} />);
  expect(
    (screen.getByLabelText('Occurred at date (Zulu)') as HTMLInputElement).value
  ).toBe('2026-10-17');
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Typo corrected' },
  });
  view.rerender(
    <JournalEditor
      {...props}
      record={{
        ...record,
        version: 2,
        payload: { ...record.payload, title: 'Remote change' },
      }}
    />
  );
  expect((screen.getByLabelText('Title') as HTMLInputElement).value).toBe(
    'Typo corrected'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0]).toMatchObject({
    operation: 'update',
    body: {
      expected_version: 1,
      time: input.time,
      payload: { title: 'Typo corrected' },
    },
  });
  expect(screen.getByLabelText('Audit note (optional)')).toBeTruthy();
  expect(screen.queryByText(/acknowledge/i)).toBeNull();
});
it('creates a frozen Now note and explicit between-leg scope without an active route', () => {
  const save = vi.fn();
  render(
    <JournalEditor missionId="mission-a" onSave={save} disabled={false} />
  );
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: 'Between legs' },
  });
  fireEvent.change(screen.getByLabelText('Scope'), {
    target: { value: 'between_legs' },
  });
  fireEvent.change(screen.getByLabelText('Previous leg ID (optional)'), {
    target: { value: 'leg-a' },
  });
  fireEvent.change(screen.getByLabelText('Next leg ID (optional)'), {
    target: { value: 'leg-b' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0]).toMatchObject({
    body: {
      scope: 'between_legs',
      leg_id: null,
      time: { precision: 'exact', end_state: 'instant' },
      payload: { previous_leg_id: 'leg-a', next_leg_id: 'leg-b' },
    },
  });
});
it('uses UTC strings even in a non-UTC environment and preserves other saved time fields', () => {
  const save = vi.fn();
  render(
    <JournalEditor
      missionId="mission-a"
      record={{
        ...record,
        time: {
          ...record.time,
          ended_at: '2026-10-17T10:12:13.987654Z',
          end_state: 'known',
          planned_start_at: '2026-10-17T09:00:00.123456Z',
          planned_end_at: '2026-10-17T09:30:00.123456Z',
        },
      }}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Correction' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0].body.time).toMatchObject({
    occurred_at: input.time.occurred_at,
    ended_at: '2026-10-17T10:12:13.987654Z',
    planned_start_at: '2026-10-17T09:00:00.123456Z',
    planned_end_at: '2026-10-17T09:30:00.123456Z',
  });
});

it('submits a call observation with an explicit leg and known actual end without inventing planning times', () => {
  const save = vi.fn();
  render(
    <JournalEditor missionId="mission-a" onSave={save} disabled={false} />
  );
  const change = (name: string, value: string) =>
    fireEvent.change(screen.getByLabelText(name), { target: { value } });
  change('Entry type', 'call_observation');
  change('Title', 'Fictional retrospective observation');
  change('Scope', 'leg');
  change('Leg ID', 'leg-a');
  change('Time precision', 'exact');
  change('Occurred at date (Zulu)', '2026-10-17');
  change('Occurred at hour (Zulu)', '14');
  change('Occurred at minute (Zulu)', '00');
  change('End state', 'known');
  change('Ended at date (Zulu)', '2026-10-17');
  change('Ended at hour (Zulu)', '14');
  change('Ended at minute (Zulu)', '10');
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0].body).toMatchObject({
    scope: 'leg',
    leg_id: 'leg-a',
    payload: { entry_type: 'call_observation' },
    time: {
      occurred_at: '2026-10-17T14:00:00Z',
      ended_at: '2026-10-17T14:10:00Z',
      precision: 'exact',
      end_state: 'known',
      planned_start_at: null,
      planned_end_at: null,
    },
  });
});

it('requires only note text and freezes Now through a failed save and later retry', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-28T23:59:12Z'));
  const save = vi.fn();
  render(
    <JournalEditor
      missionId="mission-a"
      onSave={save}
      disabled={false}
      contextual
    />
  );
  expect((screen.getByLabelText('Title') as HTMLInputElement).required).toBe(
    false
  );
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: '  Customer restored.\nMonitoring voice.  ' },
  });
  vi.setSystemTime(new Date('2026-10-29T01:01:00Z'));
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save).toHaveBeenCalledTimes(2);
  expect(save.mock.calls[0][0]).toMatchObject({
    body: {
      payload: { title: 'Customer restored.' },
      time: {
        occurred_at: '2026-10-28T23:59:12.000Z',
        precision: 'exact',
        end_state: 'instant',
      },
    },
  });
  expect(save.mock.calls[1][0]).toEqual(save.mock.calls[0][0]);
  expect(save.mock.calls[0][0].body.recorded_at).toBeUndefined();
});
it('retains a backdated note occurrence across controlled draft park and reopen', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-29T01:00:00Z'));
  let retained: JournalInput = {
    ...input,
    time: {
      ...input.time,
      occurred_at: '2026-10-28T23:55:00Z',
      precision: 'exact' as const,
    },
    payload: { ...input.payload, title: '', note: 'Overnight handover' },
  };
  const save = vi.fn();
  const view = render(
    <JournalEditor
      missionId="mission-a"
      draft={retained}
      onChange={(d) => {
        retained = d;
      }}
      onSave={save}
      disabled={false}
    />
  );
  view.unmount();
  vi.setSystemTime(new Date('2026-10-30T12:00:00Z'));
  render(
    <JournalEditor
      missionId="mission-a"
      draft={retained}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0].body.time.occurred_at).toBe(
    '2026-10-28T23:55:00Z'
  );
});
it('does not convert an unknown historical occurrence into Now when correcting text', () => {
  const save = vi.fn();
  const unknown = {
    ...record,
    time: {
      ...record.time,
      precision: 'unknown' as const,
      occurred_at: null,
      end_state: 'unknown' as const,
    },
  };
  render(
    <JournalEditor
      missionId="mission-a"
      record={unknown}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: 'Corrected wording' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }));
  expect(save.mock.calls[0][0].body.time).toEqual(unknown.time);
});
it('updates retained backdate controls when Now is explicitly chosen', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-29T01:02:03Z'));
  const parts = vi.fn();
  const changed = vi.fn();
  render(
    <JournalEditor
      missionId="mission-a"
      draft={input}
      occurrenceParts={{ date: '2026-10-17', time: '10:11' }}
      onOccurrencePartsChange={parts}
      onChange={changed}
      onSave={vi.fn()}
      disabled={false}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Now' }));
  expect(parts).toHaveBeenCalledWith({ date: '2026-10-29', time: '01:02' });
  expect(changed.mock.calls[0][0].time.occurred_at).toBe(
    '2026-10-29T01:02:03.000Z'
  );
});
