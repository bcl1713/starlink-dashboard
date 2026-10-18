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
import { health, page, record } from '@/test/operator-fixtures';
import { OperatorIssues } from './OperatorIssues';
import { CapabilityAssessments } from './CapabilityAssessments';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  sessionStorage.clear();
  vi.restoreAllMocks();
});
function mount(component: React.ReactNode, issue = false) {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  const saved = {
    ...record,
    record_type: 'issue' as const,
    payload: {
      ...record.payload,
      entry_type: 'issue' as const,
      status: 'monitoring' as const,
      mitigation: 'workaround' as const,
      update_text: '',
    },
  };
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(
    page(issue ? [saved] : [])
  );
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([saved]).items[0]);
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [saved],
    });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>{component}</QueryClientProvider>
  );
  return save;
}
it('logs a problem from its description only', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />);
  const description = await screen.findByLabelText('Problem description');
  fireEvent.change(description, {
    target: { value: 'Synthetic preflight problem' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save issue' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  expect(save.mock.calls[0][0]).toMatchObject({
    operation: 'create',
    body: {
      record_type: 'issue',
      payload: {
        title: 'Synthetic preflight problem',
        status: 'open',
        follow_up_at: null,
      },
    },
  });
});
it('resolves a monitoring workaround with one action and no audit note', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />, true);
  fireEvent.click(await screen.findByRole('button', { name: 'Resolve' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  expect(save.mock.calls[0][0]).toMatchObject({
    operation: 'update',
    body: {
      payload: {
        status: 'resolved',
        follow_up_at: null,
        mitigation: 'workaround',
      },
      expected_version: 1,
    },
  });
  expect(save.mock.calls[0][0].body).not.toHaveProperty('audit_note');
});
it('keeps functional service and redundancy separate and unknown by default', async () => {
  const save = mount(<CapabilityAssessments missionId="mission-a" />);
  fireEvent.change(await screen.findByLabelText('Capability name'), {
    target: { value: 'Synthetic secure voice' },
  });
  fireEvent.change(screen.getByLabelText('Functional capability'), {
    target: { value: 'functional' },
  });
  fireEvent.change(screen.getByLabelText('Redundancy'), {
    target: { value: 'unavailable' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save assessment' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save assessment' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  expect(save.mock.calls[0][0]).toMatchObject({
    body: {
      payload: {
        entry_type: 'capability_assessment',
        functional_status: 'functional',
        redundancy_status: 'unavailable',
      },
    },
  });
  expect(screen.queryByText('Aircraft ready')).toBeNull();
});
