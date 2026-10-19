/** @vitest-environment jsdom */
import { useLayoutEffect } from 'react';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DraftRegistry } from './draftRegistry';
import {
  OperatorWorkspaceProvider,
  useOperatorWorkspace,
} from './OperatorWorkspaceProvider';
import { WorkspaceEditor } from './WorkspaceEditor';
import { health, input, page, record } from '@/test/operator-fixtures';
import * as api from '@/services/operator';
import type { DraftTarget } from './types';
import type { OperatorInput } from '@/types/operator';
import { participationDraft } from '../conferenceCommands';

const clients: QueryClient[] = [];
const target: DraftTarget = {
  storeId: health.store_id!,
  epoch: health.api_epoch!,
  sourceMode: health.source_mode,
  simulationRunId: health.simulation_run_id,
  missionId: input.mission_id,
  recordType: input.record_type,
  recordId: null,
  newDraftId: null,
  scope: input.scope,
  legId: input.leg_id,
  previousLegId: input.payload.previous_leg_id,
  nextLegId: input.payload.next_leg_id,
  correctionVersion: null,
};
function mount(initial: OperatorInput = input) {
  const registry = new DraftRegistry(sessionStorage);
  const draft = registry.createDraft(
    { ...target, recordType: initial.record_type },
    initial
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  client.setQueryData(['operator-health'], health);
  function Editor() {
    const workspace = useOperatorWorkspace();
    useLayoutEffect(() => {
      workspace.openDraft(draft.draftId);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps
    return (
      <WorkspaceEditor
        mission={{
          id: 'mission-a',
          name: 'Fictional mission',
          legs: [
            { id: 'leg-1', name: 'First flight' },
            { id: 'leg-2', name: 'Second flight' },
          ],
        }}
      />
    );
  }
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?workspace=1']}>
        <OperatorWorkspaceProvider registry={registry}>
          <Editor />
        </OperatorWorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { registry, draft, client };
}
beforeEach(() => {
  sessionStorage.clear();
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue({
    schema_version: 1,
    items: [],
    cursor: null,
    H: 0,
    as_of: '2026-10-18T10:00:00Z',
  });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.restoreAllMocks();
});

it('keeps registry-owned unsent text when the editor closes', async () => {
  const { registry, draft } = mount();
  fireEvent.change(await screen.findByLabelText('Title'), {
    target: { value: 'Parked note' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Keep draft and return' })
  );
  expect(registry.resumeDraft(draft.draftId)?.input.payload.title).toBe(
    'Parked note'
  );
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});

it('uses explicit named scope selectors without changing the pinned mission', async () => {
  const { registry, draft } = mount();
  fireEvent.change(await screen.findByLabelText('Draft scope'), {
    target: { value: 'between_legs' },
  });
  fireEvent.change(screen.getByLabelText('Previous leg'), {
    target: { value: 'leg-1' },
  });
  fireEvent.change(screen.getByLabelText('Next leg'), {
    target: { value: 'leg-2' },
  });
  expect(registry.resumeDraft(draft.draftId)?.target).toMatchObject({
    missionId: 'mission-a',
    scope: 'between_legs',
    previousLegId: 'leg-1',
    nextLegId: 'leg-2',
  });
  expect(screen.getByText(/Draft mission: Fictional mission/)).toBeTruthy();
  expect(screen.queryByLabelText('Entry mission ID')).toBeNull();
});
it.each(['preflight', 'postflight'] as const)(
  'keeps %s scope explicit without moving the draft mission or inventing a leg',
  async (scope) => {
    const { registry, draft } = mount();
    fireEvent.change(await screen.findByLabelText('Draft scope'), {
      target: { value: scope },
    });
    const retained = registry.resumeDraft(draft.draftId)!;
    expect(retained.target).toMatchObject({
      missionId: 'mission-a',
      scope,
      legId: null,
      previousLegId: null,
      nextLegId: null,
    });
    expect(retained.input.scope).toBe(scope);
    expect(retained.input.leg_id).toBeNull();
  }
);

it('keeps input editable while the store is unavailable and disables saving', async () => {
  const { client, registry, draft } = mount();
  vi.mocked(api.getOperatorHealth).mockResolvedValue({
    ...health,
    ready: false,
  });
  await act(async () => {
    await client.refetchQueries({ queryKey: ['operator-health'] });
  });
  await waitFor(() =>
    expect(
      (screen.getByRole('button', { name: 'Save entry' }) as HTMLButtonElement)
        .disabled
    ).toBe(true)
  );
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Still retained' },
  });
  expect(registry.resumeDraft(draft.draftId)?.input.payload.title).toBe(
    'Still retained'
  );
});

it('makes current join time explicit and retains intentional unknown join time', async () => {
  const { registry, draft } = mount(
    participationDraft('mission-a', 'conference-a')
  );
  const choice = await screen.findByRole('checkbox', {
    name: 'Report joined now using backend UTC',
  });
  expect((choice as HTMLInputElement).checked).toBe(false);
  fireEvent.click(choice);
  expect(registry.resumeDraft(draft.draftId)?.editorState?.joinNow).toBe(true);
  fireEvent.click(choice);
  expect(registry.resumeDraft(draft.draftId)?.editorState?.joinNow).toBe(false);
  expect(
    registry.resumeDraft(draft.draftId)?.input.time.occurred_at
  ).toBeNull();
  expect(registry.resumeDraft(draft.draftId)?.input.time.precision).toBe(
    'unknown'
  );
});

for (const captureNow of [false, true]) {
  it(`submits ${captureNow ? 'backend UTC' : 'unknown time'} only as explicitly chosen`, async () => {
    const save = vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue({
      code: 'test-stop',
      message: 'Retain command for assertion',
      retryable: false,
    });
    mount(participationDraft('mission-a', 'conference-a'));
    const choice = await screen.findByRole('checkbox', {
      name: 'Report joined now using backend UTC',
    });
    if (captureNow) fireEvent.click(choice);
    fireEvent.click(
      screen.getByRole('button', { name: 'Save customer interval' })
    );
    await waitFor(() => expect(save).toHaveBeenCalled());
    const command = save.mock.calls[0][0];
    expect(command.operation).toBe('create');
    if (command.operation === 'create') {
      expect(command.body.time.occurred_at).toBe(
        captureNow ? '2026-10-18T10:00:00Z' : null
      );
      expect(command.body.time.precision).toBe(
        captureNow ? 'exact' : 'unknown'
      );
    }
  });
}

it('loads later relationship pages without dropping the pinned draft', async () => {
  const customer = {
    ...record,
    record_type: 'call' as const,
    payload: {
      ...record.payload,
      entry_type: 'call' as const,
      title: 'Related customer 51',
      status: 'scheduled' as const,
      conference_id: null,
    },
  };
  vi.mocked(api.readOperatorRecords)
    .mockResolvedValueOnce({ ...page([]), cursor: 'page-2' })
    .mockResolvedValueOnce(page([customer]));
  const { registry, draft } = mount(
    participationDraft('mission-a', 'conference-a')
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Load more related records' })
  );
  expect(
    await screen.findByRole('option', { name: 'Related customer 51' })
  ).toBeTruthy();
  expect(api.readOperatorRecords).toHaveBeenCalledWith(
    { mission_id: 'mission-a' },
    'page-2'
  );
  expect(registry.resumeDraft(draft.draftId)?.target.missionId).toBe(
    'mission-a'
  );
});
