/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as api from '@/services/operator';
import { health, page } from '@/test/operator-fixtures';
import { OperatorCommunications } from './OperatorCommunications';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('retains conference draft when the disclosure is closed and reopened', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorCommunications missionId="mission-a" />
    </QueryClientProvider>
  );
  const disclosure = screen
    .getByText('Conferences and customers')
    .closest('details')!;
  disclosure.open = true;
  fireEvent(disclosure, new Event('toggle'));
  fireEvent.click(
    await screen.findByRole('button', { name: 'New conference' })
  );
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Retain synthetic draft' },
  });
  disclosure.open = false;
  fireEvent(disclosure, new Event('toggle'));
  disclosure.open = true;
  fireEvent(disclosure, new Event('toggle'));
  expect(
    (screen.getByLabelText('Conference name (optional)') as HTMLInputElement)
      .value
  ).toBe('Retain synthetic draft');
  view.unmount();
  client.clear();
});

it('retains an acknowledged draft when current-state reread fails', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  vi.spyOn(api, 'readOperatorRecord').mockRejectedValue(
    new Error('current unavailable')
  );
  const { record } = await import('@/test/operator-fixtures');
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [
      {
        ...record,
        record_type: 'conference',
        payload: {
          ...record.payload,
          entry_type: 'conference',
          status: 'preparing',
        },
      },
    ],
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { OperatorConferences } = await import('./OperatorConferences');
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorConferences missionId="mission-a" />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'New conference',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'New conference' }));
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Retain acknowledged draft' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save conference' }));
  await screen.findByText(/acknowledged.*current.*unavailable/i);
  expect(
    (screen.getByLabelText('Conference name (optional)') as HTMLInputElement)
      .value
  ).toBe('Retain acknowledged draft');
  expect(
    (
      screen.getByRole('button', {
        name: 'Save conference',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  view.unmount();
  client.clear();
});

it('releases all mutation guards after visible store-epoch reconciliation', async () => {
  const newer = { ...health, api_epoch: 'epoch-b' };
  const healthRead = vi
    .spyOn(api, 'getOperatorHealth')
    .mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page([]));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { OperatorConferences } = await import('./OperatorConferences');
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorConferences missionId="mission-a" />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'New conference',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  healthRead.mockResolvedValue(newer);
  await client.invalidateQueries({ queryKey: ['operator-health'] });
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Reread and use saved conference state',
    })
  );
  await waitFor(() =>
    expect(
      screen.queryByRole('button', {
        name: 'Reread and use saved conference state',
      })
    ).toBeNull()
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Reread and use saved customer state' })
  );
  await waitFor(() =>
    expect(
      screen.queryByRole('button', {
        name: 'Reread and use saved customer state',
      })
    ).toBeNull()
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'New conference',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  view.unmount();
  client.clear();
});

it('owns a lost quick-action command until receipt reconciliation', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  const { record } = await import('@/test/operator-fixtures');
  const conference = {
    ...record,
    record_type: 'conference' as const,
    payload: {
      ...record.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
    },
  };
  vi.spyOn(api, 'readOperatorRecords').mockImplementation(async (filters) =>
    page(filters.record_type === 'conference' ? [conference] : [])
  );
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    new Error('lost response')
  );
  const dirty = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { OperatorConferences } = await import('./OperatorConferences');
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorConferences missionId="mission-a" onDirty={dirty} />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'Customer Joined',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Customer Joined' }));
  await screen.findByRole('button', { name: 'Retry same customer save' });
  expect(dirty).toHaveBeenLastCalledWith(true);
  view.unmount();
  client.clear();
});

it('offers explicit recovery when the edited record is absent in a restored store', async () => {
  const { record, failure } = await import('@/test/operator-fixtures');
  const conference = {
    ...record,
    record_type: 'conference' as const,
    payload: {
      ...record.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
    },
  };
  const healthRead = vi
    .spyOn(api, 'getOperatorHealth')
    .mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockImplementation(async (filters) =>
    page(filters.record_type === 'conference' ? [conference] : [])
  );
  vi.spyOn(api, 'readOperatorRecord').mockRejectedValue(
    failure(404, 'record_not_found')
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { OperatorConferences } = await import('./OperatorConferences');
  const view = render(
    <QueryClientProvider client={client}>
      <OperatorConferences missionId="mission-a" />
    </QueryClientProvider>
  );
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'Correct conference',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Correct conference' }));
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Keep recovered draft' },
  });
  healthRead.mockResolvedValue({ ...health, api_epoch: 'epoch-b' });
  await client.invalidateQueries({ queryKey: ['operator-health'] });
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Reread and use saved conference state',
    })
  );
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Keep conference draft as new in current store',
    })
  );
  expect(
    (screen.getByLabelText('Conference name (optional)') as HTMLInputElement)
      .value
  ).toBe('Keep recovered draft');
  view.unmount();
  client.clear();
});
