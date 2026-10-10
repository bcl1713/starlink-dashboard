/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { RevisionReview } from './RevisionReview';
import type { PlanningView, RevisionPreview } from '../../types/planning';
afterEach(cleanup);
const view = {
  mission: { id: 'm' },
  revision: 7,
  expected_legs: [
    {
      leg: {
        id: 'old',
        ordinal: 1,
        departure_airport: 'AAA',
        arrival_airport: 'BBB',
      },
    },
  ],
} as PlanningView;
const preview: RevisionPreview = {
  preview_id: 'p',
  expected_revision: 7,
  input_identity: 'captured',
  expires_at: '2099-01-01T00:00:00Z',
  confirmable: true,
  parsed_values: {
    name: 'Revision',
    expected_legs: [
      {
        id: 'incoming',
        ordinal: 1,
        departure_airport: 'AAA',
        arrival_airport: 'BBB',
        departure_time: '2026-10-25T12:00:00Z',
        arrival_time: '2026-10-25T13:00:00Z',
      },
    ],
  },
  leg_mappings: [
    { incoming_leg_id: 'incoming', expected_leg_id: 'old', action: 'retain' },
  ],
  changes: [{ field: 'departure_time', before: '12:00', after: '13:00' }],
};
it('previews the source and confirms mappings with captured CAS, retaining errors on stale apply', async () => {
  const stage = vi.fn().mockResolvedValue(preview);
  const apply = vi.fn().mockRejectedValue({ response: { status: 409 } });
  render(
    <RevisionReview view={view} previewRevision={stage} applyRevision={apply} />
  );
  fireEvent.change(screen.getByLabelText('Revised itinerary PDF'), {
    target: { files: [new File(['synthetic'], 'revision.pdf')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview itinerary revision' })
  );
  await screen.findByText('departure_time: 12:00 → 13:00');
  expect(apply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('I confirm the complete leg mapping'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Apply itinerary revision' })
  );
  await waitFor(() =>
    expect(apply).toHaveBeenCalledWith(
      expect.objectContaining({
        expected_revision: 7,
        input_identity: 'captured',
        preview_id: 'p',
      })
    )
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Planning state changed'
  );
  expect(
    screen.getByLabelText('I confirm the complete leg mapping')
  ).toBeChecked();
});
it('cancel discards the preview without accepting source or changing installed work', async () => {
  const stage = vi.fn().mockResolvedValue(preview),
    apply = vi.fn();
  render(
    <RevisionReview view={view} previewRevision={stage} applyRevision={apply} />
  );
  fireEvent.change(screen.getByLabelText('Revised itinerary PDF'), {
    target: { files: [new File(['synthetic'], 'revision.pdf')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview itinerary revision' })
  );
  await screen.findByText('departure_time: 12:00 → 13:00');
  fireEvent.click(screen.getByRole('button', { name: 'Cancel revision' }));
  expect(apply).not.toHaveBeenCalled();
  expect(
    screen.queryByRole('button', { name: 'Apply itinerary revision' })
  ).toBeNull();
});

it('shows individual AR source changes and supports mixed conflict resolutions', async () => {
  const detailed = {
    ...preview,
    changes: [
      { field: 'AR SYNTH entry_time', before: '12:10Z', after: '12:15Z' },
    ],
    conflicts: [
      {
        id: 'old:incoming:ar:one',
        expected_leg_id: 'old',
        row_id: 'one',
        field: 'ar_rows',
        message: 'AR one changed',
        allowed_actions: ['retain', 'use_source'],
      },
      {
        id: 'old:incoming:ar:two',
        expected_leg_id: 'old',
        row_id: 'two',
        field: 'ar_rows',
        message: 'AR two removed',
        allowed_actions: ['retain', 'remove'],
      },
    ],
  } as RevisionPreview;
  const apply = vi.fn().mockResolvedValue(view);
  render(
    <RevisionReview
      view={view}
      previewRevision={vi.fn().mockResolvedValue(detailed)}
      applyRevision={apply}
    />
  );
  fireEvent.change(screen.getByLabelText('Revised itinerary PDF'), {
    target: { files: [new File(['synthetic'], 'revision.pdf')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview itinerary revision' })
  );
  await screen.findByText('AR SYNTH entry_time: 12:10Z → 12:15Z');
  const removed = screen.getByLabelText('AR two removed');
  expect(
    [...removed.querySelectorAll('option')].some(
      (o) => o.value === 'use_source'
    )
  ).toBe(false);
  fireEvent.change(screen.getByLabelText('AR one changed'), {
    target: { value: 'use_source' },
  });
  fireEvent.change(removed, { target: { value: 'retain' } });
  fireEvent.click(screen.getByLabelText('I confirm the complete leg mapping'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Apply itinerary revision' })
  );
  await waitFor(() =>
    expect(apply).toHaveBeenCalledWith(
      expect.objectContaining({
        correction_resolutions: [
          { conflict_id: 'old:incoming:ar:one', action: 'use_source' },
          { conflict_id: 'old:incoming:ar:two', action: 'retain' },
        ],
      })
    )
  );
});
