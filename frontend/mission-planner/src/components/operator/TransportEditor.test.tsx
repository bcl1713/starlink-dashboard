// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { TransportEditor } from './TransportEditor';
import { TransportReview } from './TransportReview';
import type { OperatorCommand } from '@/types/operator';
import type { TransportReviewData } from '@/types/operatorTransport';

beforeEach(() => sessionStorage.clear());
it('keeps applied-only entry direct and does not require a reason or request', async () => {
  const save = vi
    .fn<(...args: [OperatorCommand, string]) => Promise<boolean>>()
    .mockResolvedValue(true);
  render(
    <TransportEditor
      missionId="synthetic-a"
      identity="identity"
      disabled={false}
      onSave={save}
    />
  );
  fireEvent.change(screen.getByLabelText('Service 1'), {
    target: { value: 'IPTV' },
  });
  fireEvent.click(screen.getByLabelText('Reported Applied 1'));
  fireEvent.change(screen.getByLabelText('Applied transport 1'), {
    target: { value: 'Ka' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save transport decision' })
  );
  await vi.waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0].body).toMatchObject({
    payload: {
      reason: '',
      services: [
        {
          requested: null,
          intended: null,
          checked: null,
          applied: { transport: 'Ka' },
        },
      ],
    },
  });
});
it('renders stale review as unknown and keeps call warning advisory', () => {
  const review = {
    actual_routing: 'unknown',
    coverage: 'available',
    activities: [],
    assessments: [
      {
        decision_id: 'a',
        row_id: 'b',
        service: 'VTC',
        subject: 'change_vs_activity',
        status: 'overlap',
        message: 'Change overlaps customer communications',
        event_ids: [],
        dependent_versions: {},
      },
    ],
  } as unknown as TransportReviewData;
  render(<TransportReview review={review} stale={true} error={false} />);
  expect(screen.getByText(/review unavailable or stale/i)).toBeTruthy();
  expect(screen.getByText(/actual routing unknown/i)).toBeTruthy();
  expect(screen.queryByText('No overlap found')).toBeNull();
});
