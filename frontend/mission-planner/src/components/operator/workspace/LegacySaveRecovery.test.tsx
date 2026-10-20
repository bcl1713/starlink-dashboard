/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { health, record, page } from '@/test/operator-fixtures';
import { operatorIdentity } from '@/hooks/api/operatorReadSession';
import { LegacySaveRecovery } from './LegacySaveRecovery';
let client: QueryClient;
afterEach(() => {
  cleanup();
  client?.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it('recovers a legacy uncertain save without automatic submission and retries its original request', async () => {
  const command = {
    operation: 'remove' as const,
    record_id: record.record_id,
    body: { schema_version: 1 as const, expected_version: record.version },
  };
  const pending = {
    command,
    key: 'original-key',
    epoch: health.api_epoch!,
    identity: operatorIdentity(health)!,
  };
  const key = 'operator-367-pending:mission-a:journal_entry';
  sessionStorage.setItem(key, JSON.stringify(pending));
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [record],
  });
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['operator-health'], health);
  render(
    <QueryClientProvider client={client}>
      <LegacySaveRecovery />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'Retry original save',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  expect(save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Retry original save' }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(save).toHaveBeenCalledWith(command, pending.key, pending.epoch);
});
it('blocks an older-store retry and releases an absent record only after an explicit reread', async () => {
  const key = 'operator-367-pending:mission-a:journal_entry';
  sessionStorage.setItem(
    key,
    JSON.stringify({
      command: {
        operation: 'remove',
        record_id: record.record_id,
        body: { schema_version: 1, expected_version: record.version },
      },
      key: 'old-key',
      epoch: 'old-epoch',
      identity: operatorIdentity({ ...health, api_epoch: 'old-epoch' }),
    })
  );
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  vi.spyOn(api, 'readOperatorRecord').mockRejectedValue({
    response: {
      status: 404,
      data: {
        detail: {
          code: 'record_not_found',
          message: 'Missing',
          retryable: false,
        },
      },
    },
  });
  const save = vi.spyOn(api, 'saveOperatorCommand');
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['operator-health'], health);
  render(
    <QueryClientProvider client={client}>
      <LegacySaveRecovery />
    </QueryClientProvider>
  );
  await screen.findByText(/Store changed. Reread and reconcile/);
  expect(
    (
      screen.getByRole('button', {
        name: 'Retry original save',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  expect(sessionStorage.getItem(key)).not.toBeNull();
  fireEvent.click(
    screen.getByRole('button', { name: 'Reread and reconcile older save' })
  );
  const release = await screen.findByRole('button', {
    name: 'Release older save absent from current store',
  });
  expect(sessionStorage.getItem(key)).not.toBeNull();
  fireEvent.click(release);
  expect(sessionStorage.getItem(key)).toBeNull();
  expect(save).not.toHaveBeenCalled();
});
