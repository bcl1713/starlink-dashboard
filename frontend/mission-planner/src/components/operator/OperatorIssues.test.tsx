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
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
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
it('clears an acknowledged update and uses the latest version for the next update', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />, true);
  const current = {
    ...record,
    record_type: 'issue' as const,
    version: 2,
    payload: {
      ...record.payload,
      entry_type: 'issue' as const,
      status: 'monitoring' as const,
      mitigation: 'workaround' as const,
      update_text: 'Synthetic first update',
    },
  };
  save.mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt2',
    saved_records: [current],
  });
  vi.mocked(api.readOperatorRecord).mockResolvedValue(page([current]).items[0]);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Add update / follow up' })
  );
  fireEvent.change(screen.getByLabelText('Add update'), {
    target: { value: 'Synthetic first update' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await waitFor(() =>
    expect(
      (screen.getByLabelText('Add update') as HTMLTextAreaElement).value
    ).toBe('')
  );
  fireEvent.change(screen.getByLabelText('Add update'), {
    target: { value: 'Synthetic second update' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1][0].body).toHaveProperty('expected_version', 2);
});
it('retires the accepted create draft after an uncertain save is retried across reload', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />);
  save.mockRejectedValueOnce(new Error('lost acknowledgment'));
  fireEvent.change(await screen.findByLabelText('Problem description'), {
    target: { value: 'Synthetic lost create' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save issue' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await screen.findByRole('button', { name: 'Retry issue save' });
  cleanup();
  mount(<OperatorIssues missionId="mission-a" />);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Retry issue save' })
  );
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: 'Retry issue save' })
    ).toBeNull()
  );
  fireEvent.click(screen.getByRole('button', { name: 'New issue' }));
  expect(
    (screen.getByLabelText('Problem description') as HTMLInputElement).value
  ).toBe('');
});
it('captures fresh backend UTC for a quick issue action rather than an old list snapshot', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />);
  fireEvent.change(await screen.findByLabelText('Problem description'), {
    target: { value: 'Synthetic current time' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save issue' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  vi.mocked(api.readOperatorRecords).mockResolvedValue({
    ...page([]),
    as_of: '2026-10-17T12:00:00Z',
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0].body).toHaveProperty(
    'time.occurred_at',
    '2026-10-17T12:00:00Z'
  );
});
it('captures fresh UTC for changed assessment dimensions without making unknown backup known', async () => {
  const save = mount(<CapabilityAssessments missionId="mission-a" />);
  fireEvent.change(await screen.findByLabelText('Capability name'), {
    target: { value: 'Synthetic current assessment' },
  });
  fireEvent.change(screen.getByLabelText('Functional capability'), {
    target: { value: 'functional' },
  });
  vi.mocked(api.readOperatorRecords).mockResolvedValue({
    ...page([]),
    as_of: '2026-10-17T12:00:00Z',
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save assessment' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save assessment' }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0].body).toMatchObject({
    payload: {
      functional_observed_at: '2026-10-17T12:00:00Z',
      redundancy_observed_at: null,
      redundancy_status: 'unknown',
    },
  });
});
it('retires an acknowledged draft even when current-state reread fails', async () => {
  mount(<OperatorIssues missionId="mission-a" />);
  vi.mocked(api.readOperatorRecord).mockRejectedValue(
    new Error('read unavailable')
  );
  fireEvent.change(await screen.findByLabelText('Problem description'), {
    target: { value: 'Synthetic acknowledged read failure' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save issue' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await screen.findByText(
    /Current state unavailable; the submitted draft is retired/
  );
  expect(
    [...Array(sessionStorage.length)]
      .map((_, i) => sessionStorage.getItem(sessionStorage.key(i)!))
      .join('')
  ).not.toContain('Synthetic acknowledged read failure');
  expect(
    screen.getByRole('button', { name: 'Save issue' }).hasAttribute('disabled')
  ).toBe(true);
});
it('preserves deliberate retrospective issue time instead of capturing current UTC', async () => {
  const save = mount(<OperatorIssues missionId="mission-a" />);
  fireEvent.change(await screen.findByLabelText('Problem description'), {
    target: { value: 'Synthetic retrospective problem' },
  });
  fireEvent.click(screen.getByText('Optional issue details'));
  fireEvent.click(screen.getByLabelText('Use current backend UTC when saved'));
  fireEvent.change(screen.getByLabelText('Action occurred UTC (optional)'), {
    target: { value: '2026-10-17T10:00:00' },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Save issue' })
        .hasAttribute('disabled')
    ).toBe(false)
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save issue' }));
  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0].body).toHaveProperty(
    'time.occurred_at',
    '2026-10-17T10:00:00.000Z'
  );
});
