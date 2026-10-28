/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { JournalEditor } from './JournalEditor';
import type { JournalInput } from '@/types/operator';
import { input, record } from '@/test/operator-fixtures';
vi.mock('@/services/operator', () => ({
  readOperatorRecords: vi.fn(async () => ({ as_of: new Date().toISOString() })),
}));
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
    (screen.getByLabelText('Occurred At date (Zulu)') as HTMLInputElement).value
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
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0]).toMatchObject({
    operation: 'update',
    body: {
      expected_version: 1,
      time: input.time,
      payload: { title: 'Typo corrected' },
    },
  });
  expect(screen.getByLabelText('Audit Note (Optional)')).toBeTruthy();
  expect(screen.queryByText(/acknowledge/i)).toBeNull();
});
it('creates a frozen Now note and explicit between-leg scope without an active route', async () => {
  const save = vi.fn();
  render(
    <JournalEditor missionId="mission-a" onSave={save} disabled={false} />
  );
  await act(async () => {});
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: 'Between Legs' },
  });
  fireEvent.change(screen.getByLabelText('Scope'), {
    target: { value: 'between_legs' },
  });
  fireEvent.change(screen.getByLabelText('Previous Leg ID (Optional)'), {
    target: { value: 'leg-a' },
  });
  fireEvent.change(screen.getByLabelText('Next Leg ID (Optional)'), {
    target: { value: 'leg-b' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
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
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toMatchObject({
    occurred_at: input.time.occurred_at,
    ended_at: '2026-10-17T10:12:13.987654Z',
    planned_start_at: '2026-10-17T09:00:00.123456Z',
    planned_end_at: '2026-10-17T09:30:00.123456Z',
  });
});

it('submits a call observation with an explicit leg and known actual end without inventing planning times', async () => {
  const save = vi.fn();
  render(
    <JournalEditor missionId="mission-a" onSave={save} disabled={false} />
  );
  await act(async () => {});
  const change = (name: string, value: string) =>
    fireEvent.change(screen.getByLabelText(name), { target: { value } });
  change('Entry Type', 'call_observation');
  change('Title', 'Fictional retrospective observation');
  change('Scope', 'leg');
  change('Leg ID', 'leg-a');
  change('Time Precision', 'exact');
  change('Occurred At date (Zulu)', '2026-10-17');
  change('Occurred At hour (Zulu)', '14');
  change('Occurred At minute (Zulu)', '00');
  change('End State', 'known');
  change('Ended At date (Zulu)', '2026-10-17');
  change('Ended At hour (Zulu)', '14');
  change('Ended At minute (Zulu)', '10');
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
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

it('requires only note text and freezes Now through a failed save and later retry', async () => {
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
  await act(async () => {});
  expect((screen.getByLabelText('Title') as HTMLInputElement).required).toBe(
    false
  );
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: '  Customer restored.\nMonitoring voice.  ' },
  });
  vi.setSystemTime(new Date('2026-10-29T01:01:00Z'));
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
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
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
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
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toEqual(unknown.time);
});
it('updates retained backdate controls when Now is explicitly chosen', async () => {
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
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Now' }));
  });
  expect(parts).toHaveBeenCalledWith({ date: '2026-10-29', time: '01:02' });
  expect(changed.mock.calls[0][0].time.occurred_at).toBe(
    '2026-10-29T01:02:03.000Z'
  );
});
it('makes an explicitly backdated unknown correction precise without changing unrelated evidence', () => {
  const save = vi.fn();
  const saved = {
    ...record,
    time: {
      ...record.time,
      occurred_at: null,
      precision: 'unknown' as const,
      end_state: 'unknown' as const,
    },
  };
  render(
    <JournalEditor
      missionId="mission-a"
      record={saved}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.change(screen.getByLabelText('Occurred At date (Zulu)'), {
    target: { value: '2026-10-16' },
  });
  fireEvent.change(screen.getByLabelText('Occurred At hour (Zulu)'), {
    target: { value: '23' },
  });
  fireEvent.change(screen.getByLabelText('Occurred At minute (Zulu)'), {
    target: { value: '59' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toMatchObject({
    occurred_at: '2026-10-16T23:59:00Z',
    precision: 'exact',
    end_state: 'unknown',
  });
});
it('keeps interval and planning evidence when explicitly changing a historical occurrence to Now', async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-17T10:00:00Z'));
  const save = vi.fn();
  const time = {
    ...record.time,
    ended_at: '2026-10-17T11:00:00.123456Z',
    end_state: 'known' as const,
    planned_start_at: '2026-10-17T09:00:00.123456Z',
  };
  render(
    <JournalEditor
      missionId="mission-a"
      record={{ ...record, time }}
      onSave={save}
      disabled={false}
    />
  );
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Now' }));
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toEqual({
    ...time,
    occurred_at: '2026-10-17T10:00:00.000Z',
  });
});
it('uses the source clock for Now and preserves text edited while capturing it', async () => {
  let resolve!: (value: string) => void;
  const captureNow = () =>
    new Promise<string>((done) => {
      resolve = done;
    });
  const save = vi.fn();
  render(
    <JournalEditor
      missionId="mission-a"
      record={record}
      captureNow={captureNow}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Now' }));
  fireEvent.change(screen.getByLabelText('Note'), {
    target: { value: 'Retained during source-clock lookup' },
  });
  await act(async () => resolve('2035-01-02T00:05:00Z'));
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body).toMatchObject({
    time: { occurred_at: '2035-01-02T00:05:00Z' },
    payload: { note: 'Retained during source-clock lookup' },
  });
});
it('keeps a historical occurrence and text if the source clock is unavailable', async () => {
  const save = vi.fn();
  render(
    <JournalEditor
      missionId="mission-a"
      record={record}
      captureNow={async () => {
        throw new Error('offline');
      }}
      onSave={save}
      disabled={false}
    />
  );
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Now' }));
  });
  expect(screen.getByRole('alert').textContent).toMatch(/source clock/i);
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toEqual(record.time);
  expect(save.mock.calls[0][0].body.payload.note).toBe(record.payload.note);
});
it('retains historical precision and end evidence through a partial occurrence edit', () => {
  const save = vi.fn();
  const time = {
    ...record.time,
    ended_at: '2026-10-17T15:00:00.123456Z',
    end_state: 'known' as const,
  };
  render(
    <JournalEditor
      missionId="mission-a"
      record={{ ...record, time }}
      onSave={save}
      disabled={false}
    />
  );
  fireEvent.change(screen.getByLabelText('Occurred At hour (Zulu)'), {
    target: { value: '' },
  });
  fireEvent.change(screen.getByLabelText('Occurred At hour (Zulu)'), {
    target: { value: '12' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Entry' }));
  expect(save.mock.calls[0][0].body.time).toEqual({
    ...time,
    occurred_at: '2026-10-17T12:11:00Z',
  });
});
