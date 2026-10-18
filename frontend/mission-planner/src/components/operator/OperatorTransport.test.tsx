/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { health, page, record } from '@/test/operator-fixtures';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
import { OperatorTransport } from './OperatorTransport';
import { newTransportDraft } from './transportForms';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it('freezes an uncertain applied-only request across reload and retries its original command', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const saved = {
    ...record,
    record_type: 'transport_decision' as const,
    payload: newTransportDraft('mission-a').input.payload,
  };
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue({
    ...page().items[0],
    record: saved,
  });
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('lost response'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'synthetic-receipt',
      saved_records: [saved],
    });
  const feed = {
    failed: true,
    receivedAt: -Infinity,
    refresh: vi.fn(),
  } as unknown as OperatorEventsState;
  function mount() {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    clients.push(client);
    return render(
      <QueryClientProvider client={client}>
        <OperatorTransport missionId="mission-a" eventFeed={feed} />
      </QueryClientProvider>
    );
  }
  const first = mount();
  fireEvent.change(await screen.findByLabelText('Service 1'), {
    target: { value: 'VTC' },
  });
  fireEvent.click(screen.getByLabelText('Reported Applied 1'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Save transport decision' })
  );
  await screen.findByRole('button', { name: 'Retry transport save' });
  const original = structuredClone(save.mock.calls[0]);
  expect(screen.queryByText('Transport save acknowledged.')).toBeNull();
  first.unmount();
  mount();
  await screen.findByRole('button', { name: 'Retry transport save' });
  await act(async () =>
    fireEvent.click(
      screen.getByRole('button', { name: 'Retry transport save' })
    )
  );
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1]).toEqual(original);
  await screen.findByText('Transport save acknowledged.');
});

it('can explicitly keep a corrected draft as new when its old-store record is absent', async () => {
  const { failure } = await import('@/test/operator-fixtures');
  const healthRead = vi
    .spyOn(api, 'getOperatorHealth')
    .mockResolvedValue(health);
  const draft = newTransportDraft('mission-a');
  draft.input.payload.services[0].service = 'Original service';
  const saved = {
    ...record,
    record_type: 'transport_decision' as const,
    payload: draft.input.payload,
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([saved]));
  const read = vi
    .spyOn(api, 'readOperatorRecord')
    .mockResolvedValue({ ...page().items[0], record: saved });
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(failure(503, 'commit_outcome_unknown'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'new-decision',
      saved_records: [saved],
    });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <OperatorTransport
        missionId="mission-a"
        eventFeed={
          {
            failed: true,
            receivedAt: -Infinity,
            refresh: vi.fn(),
          } as unknown as OperatorEventsState
        }
      />
    </QueryClientProvider>
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Correct this decision' })
  );
  fireEvent.change(screen.getByLabelText('Service 1'), {
    target: { value: 'Retained correction' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save transport decision' })
  );
  await screen.findByRole('button', { name: 'Retry transport save' });
  healthRead.mockResolvedValue({ ...health, api_epoch: 'restored-epoch' });
  read.mockRejectedValue(failure(404, 'record_not_found'));
  fireEvent.click(screen.getByRole('button', { name: 'Retry transport save' }));
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Reread transport for reconciliation',
    })
  );
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Keep draft as new transport decision',
    })
  );
  expect((screen.getByLabelText('Service 1') as HTMLInputElement).value).toBe(
    'Retained correction'
  );
  read.mockResolvedValue({ ...page().items[0], record: saved });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save transport decision' })
  );
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1][0]).toMatchObject({
    operation: 'create',
    body: { payload: { services: [{ service: 'Retained correction' }] } },
  });
  expect(save.mock.calls[1][2]).toBe('restored-epoch');
});
