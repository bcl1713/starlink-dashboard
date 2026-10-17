/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from '@tanstack/react-query';
import * as api from '@/services/operator';
import { health, page, record, failure } from '@/test/operator-fixtures';
import type { CallInput, SavedRecord } from '@/types/operator';
import { OperatorCommunications } from './OperatorCommunications';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
const original: SavedRecord = {
  ...record,
  record_type: 'call',
  payload: {
    ...record.payload,
    title: 'Synthetic call',
    entry_type: 'call',
    status: 'completed',
    conference_id: null,
    prep_lead_minutes: null,
    party: 'Synthetic party',
  },
};
function mount() {
  let saved = structuredClone(original);
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockImplementation(async () =>
    page([saved])
  );
  vi.spyOn(api, 'readOperatorRecord').mockImplementation(
    async () => page([saved]).items[0]
  );
  const writes = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockImplementation(async (command) => {
      if (command.operation === 'create' || command.operation === 'update')
        saved = {
          ...saved,
          ...command.body,
          payload: (command.body as CallInput).payload,
          record_type: 'call',
          version: saved.version + 1,
        };
      else
        saved = {
          ...saved,
          version: saved.version + 1,
          deleted: command.operation === 'remove',
        };
      return {
        schema_version: 1,
        command_id: 'receipt',
        saved_records: [saved],
      };
    });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  function IndependentSummary() {
    const result = useQuery({
      queryKey: ['operator-brief', 'mission-a', 'separate'],
      queryFn: () => api.readOperatorRecords({ mission_id: 'mission-a' }),
    });
    return (
      <p data-testid="independent-summary">
        {result.data?.items[0].record.payload.note}
      </p>
    );
  }
  const view = render(
    <QueryClientProvider client={client}>
      <IndependentSummary />
      <OperatorCommunications missionId="mission-a" />
    </QueryClientProvider>
  );
  return { ...view, client, writes };
}
function completed() {
  fireEvent.click(screen.getByText('Completed, canceled and removed calls'));
}
function details() {
  fireEvent.click(screen.getByText('Timing, association and optional details'));
}
it('saves a correction, refreshes an independent summary, and preserves unknown prep', async () => {
  const { writes } = mount();
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Edit call' })).toBeTruthy()
  );
  completed();
  fireEvent.click(screen.getByRole('button', { name: 'Edit call' }));
  details();
  fireEvent.change(screen.getByLabelText('Notes (optional)'), {
    target: { value: 'Corrected synthetic note' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  await waitFor(() => expect(screen.getByText('Call saved.')).toBeTruthy());
  expect(screen.getByTestId('independent-summary').textContent).toBe(
    'Corrected synthetic note'
  );
  expect(writes.mock.calls[0][0]).toMatchObject({
    operation: 'update',
    body: { expected_version: 1, payload: { prep_lead_minutes: null } },
  });
});
it('retains dirty drafts through refresh and uncertain retry uses the same request', async () => {
  const { writes, client } = mount();
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Edit call' })).toBeTruthy()
  );
  completed();
  fireEvent.click(screen.getByRole('button', { name: 'Edit call' }));
  fireEvent.change(screen.getByLabelText('Party / participant (optional)'), {
    target: { value: 'Local unsaved participant' },
  });
  await act(async () => {
    await client.invalidateQueries({ queryKey: ['operator-records'] });
  });
  expect(
    (
      screen.getByLabelText(
        'Party / participant (optional)'
      ) as HTMLInputElement
    ).value
  ).toBe('Local unsaved participant');
  writes.mockRejectedValueOnce(failure(503, 'commit_outcome_unknown'));
  fireEvent.click(screen.getByRole('button', { name: 'Save call' }));
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Retry same call save' })
    ).toBeTruthy()
  );
  expect(screen.queryByText('Call saved.')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Retry same call save' }));
  await waitFor(() => expect(screen.getByText('Call saved.')).toBeTruthy());
  expect(writes.mock.calls[1]).toEqual(writes.mock.calls[0]);
});
it('remove/restore preserves completed timing and never invents preparation', async () => {
  mount();
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Remove call' })).toBeTruthy()
  );
  completed();
  fireEvent.click(screen.getByRole('button', { name: 'Remove call' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Restore call' })).toBeTruthy()
  );
  fireEvent.click(screen.getByRole('button', { name: 'Restore call' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Remove call' })).toBeTruthy()
  );
  expect(screen.queryByText(/^Prepare:/)).toBeNull();
});
