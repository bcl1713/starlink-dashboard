/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { JournalEditor } from './JournalEditor';
import { input, record } from '@/test/operator-fixtures';
afterEach(cleanup);
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
    (screen.getByLabelText('Occurred at (UTC)') as HTMLInputElement).value
  ).toBe('2026-10-17T10:11:12.123456Z');
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
it('creates unknown time and explicit between-leg scope without an active route', () => {
  const save = vi.fn();
  render(
    <JournalEditor missionId="mission-a" onSave={save} disabled={false} />
  );
  fireEvent.change(screen.getByLabelText('Title'), {
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
      time: { precision: 'unknown', occurred_at: null },
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
  });
});
