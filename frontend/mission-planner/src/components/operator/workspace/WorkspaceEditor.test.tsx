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
import { callDraft } from '../callDraft';
import { routesApi } from '@/services/routes';
import { conferenceDraft, participationDraft } from '../conferenceCommands';

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
function mount(
  initial: OperatorInput = input,
  timed = false,
  active = false,
  saved?: typeof record,
  pinned: Partial<DraftTarget> = {},
  source = health
) {
  const registry = new DraftRegistry(sessionStorage);
  const draft = registry.createDraft(
    {
      ...target,
      recordType: initial.record_type,
      recordId: saved?.record_id ?? null,
      scope: initial.scope,
      legId: initial.leg_id,
      ...pinned,
    },
    initial,
    saved
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  client.setQueryData(['operator-health'], source);
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
            {
              id: 'leg-1',
              name: 'First flight',
              is_active: active,
              ...(timed ? { route_id: 'outbound' } : {}),
            },
            {
              id: 'leg-2',
              name: 'Second flight',
              ...(timed ? { route_id: 'return' } : {}),
            },
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

it('keeps native form submission outside the scrolling editor body', async () => {
  mount();
  const save = (await screen.findByRole('button', {
    name: 'Save entry',
  })) as HTMLButtonElement;
  expect(save.closest('.ws-editor-body')).toBeNull();
  expect(save.closest('.ws-editor-footer')).not.toBeNull();
  expect(save.form).toBeInstanceOf(HTMLFormElement);
  expect(save.form?.closest('.ws-editor-body')).not.toBeNull();
  expect(
    screen
      .getByRole('button', { name: 'Discard draft' })
      .closest('.ws-editor-body')
  ).toBeNull();
});

it('associates a picked UTC call time and preserves an explicit override across later changes', async () => {
  vi.spyOn(routesApi, 'get').mockImplementation(async (id) => ({
    id,
    name: id,
    timing_profile: {
      departure_time: `2026-10-20T${id === 'outbound' ? '10' : '14'}:00:00Z`,
      arrival_time: `2026-10-20T${id === 'outbound' ? '12' : '16'}:00:00Z`,
    },
  }));
  const initial = callDraft(undefined, 'planned', 'mission-a');
  initial.time.planned_start_at = '2026-10-20T11:00:00Z';
  const { registry, draft } = mount(initial, true);
  await screen.findByText('Mission association: First flight');
  fireEvent.change(screen.getByLabelText('Planned start time (UTC)'), {
    target: { value: '13:00' },
  });
  expect(registry.resumeDraft(draft.draftId)?.input).toMatchObject({
    scope: 'between_legs',
    leg_id: null,
    payload: { previous_leg_id: 'leg-1', next_leg_id: 'leg-2' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Change association' }));
  fireEvent.change(screen.getByLabelText('Association'), {
    target: { value: 'preflight' },
  });
  fireEvent.change(screen.getByLabelText('Planned start time (UTC)'), {
    target: { value: '15:00' },
  });
  expect(registry.resumeDraft(draft.draftId)?.input.scope).toBe('preflight');
  expect(registry.resumeDraft(draft.draftId)?.target.missionId).toBe(
    'mission-a'
  );
});

it('shows a readable current-leg association for new conferences without scope controls', async () => {
  mount(conferenceDraft('mission-a'), false, true);
  await screen.findByText('Mission association: First flight');
  expect(screen.queryByRole('combobox', { name: 'Association' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Change association' }));
  fireEvent.change(screen.getByRole('combobox', { name: 'Association' }), {
    target: { value: 'mission' },
  });
  expect(
    screen.getByRole('option', { name: 'Unassigned activity' })
  ).toBeTruthy();
});

it('keeps an explicitly saved conference association until the operator changes it', async () => {
  const initial = {
    ...conferenceDraft('mission-a'),
    scope: 'preflight' as const,
  };
  const saved = { ...record, ...initial };
  const { registry, draft } = mount(initial, false, true, saved);
  await screen.findByText('Mission association: preflight');
  expect(screen.queryByRole('combobox', { name: 'Association' })).toBeNull();
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Saved definition' },
  });
  expect(registry.resumeDraft(draft.draftId)?.input.scope).toBe('preflight');
});

it('explicitly copies an old replay draft without retargeting or discarding its original input', async () => {
  const source = {
    ...health,
    source_mode: 'simulation' as const,
    mission_journal: true,
    simulation_run_id: 'default',
    replay_run_id: 'new-run',
  };
  vi.mocked(api.getOperatorHealth).mockResolvedValue(source);
  const { registry, draft } = mount(
    input,
    false,
    false,
    undefined,
    { sourceMode: 'simulation', simulationRunId: 'old-run' },
    source
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Copy input to current replay' })
  );
  await waitFor(() => expect(registry.listDrafts()).toHaveLength(2));
  const retained = registry.resumeDraft(draft.draftId)!;
  expect(retained.target.simulationRunId).toBe('old-run');
  expect(retained.input).toEqual(input);
  const copy = registry
    .listDrafts()
    .find((item) => item.draftId !== draft.draftId)!;
  expect(copy.target.simulationRunId).toBe('new-run');
  expect(copy.input).toEqual(input);
});
