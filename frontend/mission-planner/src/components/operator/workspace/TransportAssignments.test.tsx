// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TransportAssignments } from './TransportAssignments';
import { record } from '@/test/operator-fixtures';
import { assignmentInput } from './transportAssignments';
vi.mock('@/services/transportCatalog', () => ({
  readTransportCatalog: async () => ({
    schema_version: 1,
    version: 0,
    services: [{ id: 'svc', name: 'Data', enabled: true, archived: false }],
    transports: [
      { id: 'custom', name: 'Terrestrial', enabled: true, archived: false },
      { id: 'X', name: 'Renamed RF', enabled: true, archived: false },
      { id: 'Starshield', name: 'LEO', enabled: true, archived: false },
    ],
  }),
  saveTransportCatalog: vi.fn(async (data) => ({
    ...data,
    version: data.version + 1,
  })),
}));
afterEach(cleanup);
it('changes dropdown only on Apply and renders accepted assignment immediately', async () => {
  const apply = vi.fn(async () => {});
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = (records = [] as (typeof record)[]) => (
    <QueryClientProvider client={client}>
      <TransportAssignments
        records={records}
        legId={null}
        disabled={false}
        onApply={apply}
      />
    </QueryClientProvider>
  );
  const rendered = render(view());
  const card = await screen.findByRole('article', { name: 'Data' });
  fireEvent.change(within(card).getByRole('combobox'), {
    target: { value: 'custom' },
  });
  expect(apply).not.toHaveBeenCalled();
  fireEvent.click(within(card).getByRole('button', { name: 'Apply' }));
  await waitFor(() => expect(apply).toHaveBeenCalledTimes(1));
  const accepted = {
    ...record,
    ...assignmentInput(
      'mission-a',
      { id: 'svc', name: 'Data' },
      { id: 'custom', name: 'Terrestrial' },
      '2026-10-19T12:00:00Z',
      null
    ),
  };
  rendered.rerender(view([accepted]));
  expect(
    within(card).getByText('Terrestrial', { selector: 'strong' })
  ).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Manage transports' }));
  const manager = screen.getByRole('region', { name: 'Manage transports' });
  expect(
    within(manager).getAllByRole('button', { name: 'Archive' })[0]
  ).toBeTruthy();
});
it('does not show a rejected save as an assignment', async () => {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <TransportAssignments
        records={[]}
        legId={null}
        disabled={false}
        onApply={async () => {
          throw new Error('Unconfirmed');
        }}
      />
    </QueryClientProvider>
  );
  const card = await screen.findByRole('article', { name: 'Data' });
  fireEvent.change(within(card).getByRole('combobox'), {
    target: { value: 'custom' },
  });
  fireEvent.click(within(card).getByRole('button', { name: 'Apply' }));
  expect(await screen.findByRole('alert')).toHaveProperty(
    'textContent',
    'Unconfirmed'
  );
  expect(within(card).getByText('Not reported')).toBeTruthy();
});

it('unavailable_transport_not_offered_for_assignment_but_report_is_retained', async () => {
  const accepted = {
    ...record,
    ...assignmentInput(
      'mission-a',
      { id: 'svc', name: 'Data' },
      { id: 'X', name: 'Renamed RF' },
      '2026-10-19T12:00:00Z',
      null
    ),
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TransportAssignments
        records={[accepted]}
        legId={null}
        disabled={false}
        onApply={async () => {}}
        availability={{ X: false, Ka: true, Ku: false }}
      />
    </QueryClientProvider>
  );
  const card = await screen.findByRole('article', { name: 'Data' });
  expect(
    within(card).getByText('Renamed RF', { selector: 'strong' })
  ).toBeTruthy();
  expect(within(card).getByText(/unavailable for this mission/)).toBeTruthy();
  expect(
    within(card).getByRole('option', { name: 'Renamed RF (unavailable)' })
  ).toHaveProperty('disabled', true);
  expect(within(card).queryByRole('option', { name: 'LEO' })).toBeNull();
  expect(
    within(card).getByRole('option', { name: 'Terrestrial' })
  ).toBeTruthy();
});
