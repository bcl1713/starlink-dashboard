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
import * as transportCatalog from '@/services/transportCatalog';
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
  source = health,
  editorState?: Record<string, unknown>,
  restored?: { registry: DraftRegistry; draftId: string }
) {
  const registry = restored?.registry ?? new DraftRegistry(sessionStorage);
  const draft = restored
    ? registry.resumeDraft(restored.draftId)!
    : registry.createDraft(
        {
          ...target,
          recordType: initial.record_type,
          recordId: saved?.record_id ?? null,
          scope: initial.scope,
          legId: initial.leg_id,
          previousLegId: initial.payload.previous_leg_id,
          nextLegId: initial.payload.next_leg_id,
          ...pinned,
        },
        initial,
        saved
      );
  if (editorState) registry.parkDraft({ ...draft, editorState });
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
  vi.spyOn(transportCatalog, 'readTransportCatalog').mockResolvedValue({
    schema_version: 1,
    version: 1,
    services: [],
    transports: [],
  });
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
    screen.getByRole('button', { name: 'Keep Draft And Return' })
  );
  expect(registry.resumeDraft(draft.draftId)?.input.payload.title).toBe(
    'Parked note'
  );
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});

it('uses explicit named scope selectors without changing the pinned mission', async () => {
  const { registry, draft } = mount();
  fireEvent.change(await screen.findByLabelText('Draft Scope'), {
    target: { value: 'between_legs' },
  });
  fireEvent.change(screen.getByLabelText('Previous Leg'), {
    target: { value: 'leg-1' },
  });
  fireEvent.change(screen.getByLabelText('Next Leg'), {
    target: { value: 'leg-2' },
  });
  expect(registry.resumeDraft(draft.draftId)?.target).toMatchObject({
    missionId: 'mission-a',
    scope: 'between_legs',
    previousLegId: 'leg-1',
    nextLegId: 'leg-2',
  });
  expect(screen.getByText(/Draft Mission: Fictional mission/)).toBeTruthy();
  expect(screen.queryByLabelText('Entry Mission ID')).toBeNull();
});
it.each(['preflight', 'postflight'] as const)(
  'keeps %s scope explicit without moving the draft mission or inventing a leg',
  async (scope) => {
    const { registry, draft } = mount();
    fireEvent.change(await screen.findByLabelText('Draft Scope'), {
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
      (screen.getByRole('button', { name: 'Save Entry' }) as HTMLButtonElement)
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
    name: 'Report Joined Now Using Backend Zulu',
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
      name: 'Report Joined Now Using Backend Zulu',
    });
    if (captureNow) fireEvent.click(choice);
    fireEvent.click(
      screen.getByRole('button', { name: 'Save Customer Interval' })
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
      expect(
        command.body.record_type === 'participation' &&
          command.body.connect_customer === true
      ).toBe(captureNow);
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
    { mission_id: 'mission-a', include_removed: true },
    'page-2'
  );
  expect(registry.resumeDraft(draft.draftId)?.target.missionId).toBe(
    'mission-a'
  );
});

it('keeps native form submission outside the scrolling editor body', async () => {
  mount();
  const save = (await screen.findByRole('button', {
    name: 'Save Entry',
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
  fireEvent.change(screen.getByLabelText('Planned Start hour (Zulu)'), {
    target: { value: '13' },
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
  fireEvent.change(screen.getByLabelText('Planned Start hour (Zulu)'), {
    target: { value: '15' },
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

it('offers an already accepted ordinary-activation conference in the call chooser without migration', async () => {
  const source = {
    ...health,
    source_mode: 'simulation' as const,
    mission_journal: true,
    simulation_run_id: 'default',
    replay_run_id: null,
    operating_context_id: 'ordinary:runtime:1:route',
  };
  const accepted = {
    ...record,
    ...conferenceDraft('mission-a'),
    payload: { ...conferenceDraft('mission-a').payload, title: 'CABLES' },
    provenance: {
      ...record.provenance,
      source_mode: 'simulation' as const,
      replay_run_id: null,
    },
  };
  vi.mocked(api.getOperatorHealth).mockResolvedValue(source);
  vi.mocked(api.readOperatorRecords).mockResolvedValue(page([accepted]));
  const { registry, draft } = mount(
    callDraft(undefined, 'planned', 'mission-a'),
    false,
    true,
    undefined,
    { sourceMode: 'simulation', simulationRunId: source.operating_context_id },
    source
  );
  const option = await screen.findByRole('option', { name: /CABLES/ });
  fireEvent.change(option.parentElement!, {
    target: { value: accepted.record_id },
  });
  expect(registry.resumeDraft(draft.draftId)?.input.payload).toHaveProperty(
    'conference_id',
    accepted.record_id
  );
});

it('uses mission records already visible in Now while the list refresh is pending', async () => {
  const accepted = {
    ...record,
    ...conferenceDraft('mission-a'),
    payload: {
      ...conferenceDraft('mission-a').payload,
      title: 'Visible bridge',
    },
  };
  vi.mocked(api.readOperatorRecords).mockImplementation(
    () => new Promise(() => {})
  );
  const { client } = mount(callDraft(undefined, 'planned', 'mission-a'));
  act(() => {
    client.setQueryData(
      [
        'operator-records',
        'mission-a',
        JSON.stringify(['store', 'epoch-a', 'live', null]),
        'workspace-all',
      ],
      { pages: [page([accepted])], pageParams: [undefined] }
    );
  });
  expect(
    await screen.findByRole('option', { name: 'Visible bridge' })
  ).toBeTruthy();
});

it('closes the conference dialog after its exact draft is accepted', async () => {
  const saved = { ...record, ...conferenceDraft('mission-a') };
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([saved]).items[0]);
  const { registry, draft } = mount(conferenceDraft('mission-a'));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Save Conference' })
  );
  await waitFor(() => expect(registry.resumeDraft(draft.draftId)).toBeNull());
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});

function retainedCall() {
  const call = callDraft(undefined, 'planned', 'mission-a');
  call.scope = 'between_legs';
  call.payload = {
    ...call.payload,
    title: 'Customer Charlie',
    party: 'Customer Charlie',
    communications_kind: 'vtc',
    coordinator: 'Ground lead',
    conference_id: 'existing-bridge',
    previous_leg_id: 'leg-1',
    next_leg_id: 'leg-2',
    note: 'Keep every call detail',
    status: 'delayed',
  };
  call.time = {
    ...call.time,
    planned_start_at: '2026-10-28T23:45:12.123456Z',
    planned_end_at: '2026-10-29T00:15:12.123456Z',
    occurred_at: '2026-10-28T23:48:00Z',
    ended_at: null,
    precision: 'approximate',
    end_state: 'ongoing',
  };
  return call;
}
async function prepareInline() {
  const call = retainedCall();
  const mounted = mount(call, false, false, undefined, {}, health, {
    associationMode: 'manual',
    associationExpanded: true,
    call: {
      lead: '1.5',
      duration: '12.',
      shift: '-2',
      unit: 'hours',
      originalTime: call.time,
      originalDuration: '30',
      timeParts: { occurred_at: { date: '2026-10-28', time: '23:' } },
    },
  });
  await screen.findByLabelText('Party / Participant (Optional)');
  const parent = mounted.registry.resumeDraft(mounted.draft.draftId)!;
  fireEvent.click(screen.getByRole('button', { name: 'Create Conference' }));
  await screen.findByLabelText('Conference name (optional)');
  const child = mounted.registry
    .listDrafts()
    .find((draft) => draft.input.record_type === 'conference')!;
  return { ...mounted, parent, child };
}
function savedInline(title = 'Charlie bridge') {
  return {
    ...record,
    ...conferenceDraft('mission-a'),
    record_id: 'new-bridge',
    payload: { ...conferenceDraft('mission-a').payload, title },
  };
}

it('parks all call input and editor state and returns unchanged when inline creation is canceled', async () => {
  const { registry, parent, child } = await prepareInline();
  expect(child.target).toMatchObject({
    storeId: parent.target.storeId,
    epoch: parent.target.epoch,
    sourceMode: parent.target.sourceMode,
    simulationRunId: parent.target.simulationRunId,
    missionId: parent.target.missionId,
  });
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Parked bridge' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Back To Call' }));
  await screen.findByLabelText('Party / Participant (Optional)');
  const returned = registry.resumeDraft(parent.draftId)!;
  expect(returned.input).toEqual(parent.input);
  expect(returned.editorState?.call).toEqual(parent.editorState?.call);
  expect(returned.editorState?.associationMode).toBe('manual');
  expect(
    (
      screen.getByLabelText(
        'Duration Minutes (blank = unknown)'
      ) as HTMLInputElement
    ).value
  ).toBe('12.');
  expect(
    (
      screen.getByLabelText(
        'Preparation Lead Minutes (blank = unknown)'
      ) as HTMLInputElement
    ).value
  ).toBe('1.5');
  expect(
    (screen.getByLabelText('Shift amount') as HTMLInputElement).value
  ).toBe('-2');
  expect((screen.getByLabelText('Shift Unit') as HTMLSelectElement).value).toBe(
    'hours'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Create Conference' }));
  expect(
    (
      (await screen.findByLabelText(
        'Conference name (optional)'
      )) as HTMLInputElement
    ).value
  ).toBe('Parked bridge');
  expect(registry.listDrafts()).toHaveLength(2);
});

it('selects an independently saved conference only after its authoritative read and keeps it when the call is discarded', async () => {
  const saved = savedInline();
  let resolveRead!: (value: ReturnType<typeof page>['items'][number]) => void;
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveRead = resolve;
      })
  );
  const { registry, parent, child } = await prepareInline();
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Charlie bridge' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await waitFor(() =>
    expect(api.readOperatorRecord).toHaveBeenCalledWith('new-bridge')
  );
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual(parent.input);
  expect(registry.resumeDraft(child.draftId)).not.toBeNull();
  expect(screen.queryByLabelText('Party / Participant (Optional)')).toBeNull();
  await act(async () => resolveRead(page([saved]).items[0]));
  await screen.findByLabelText('Party / Participant (Optional)');
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual({
    ...parent.input,
    payload: { ...parent.input.payload, conference_id: 'new-bridge' },
  });
  expect(registry.resumeDraft(parent.draftId)?.editorState?.call).toEqual(
    parent.editorState?.call
  );
  expect(registry.resumeDraft(child.draftId)).toBeNull();
  expect(
    (screen.getByLabelText('Conference (Optional)') as HTMLSelectElement).value
  ).toBe('new-bridge');
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(registry.listDrafts()).toHaveLength(0);
  expect(api.saveOperatorCommand).toHaveBeenCalledTimes(1);
  expect(api.saveOperatorCommand).toHaveBeenCalledWith(
    expect.objectContaining({
      operation: 'create',
      body: expect.objectContaining({ record_type: 'conference' }),
    }),
    expect.any(String),
    'epoch-a'
  );
});

it('retains both drafts after a failed conference save and retries the retained conference', async () => {
  const saved = savedInline();
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(
      Object.assign(new Error('Conference rejected'), {
        response: {
          status: 400,
          data: {
            error: {
              code: 'invalid_input',
              message: 'Conference rejected',
              retryable: false,
            },
          },
        },
      })
    )
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [saved],
    });
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([saved]).items[0]);
  const { registry, parent, child } = await prepareInline();
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Charlie bridge' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await screen.findByText('Conference rejected');
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual(parent.input);
  expect(registry.resumeDraft(child.draftId)?.input.payload.title).toBe(
    'Charlie bridge'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await screen.findByLabelText('Party / Participant (Optional)');
  expect(save).toHaveBeenCalledTimes(2);
  expect(registry.resumeDraft(parent.draftId)?.input.payload).toHaveProperty(
    'conference_id',
    'new-bridge'
  );
});

it('resolves an uncertain inline save with its exact command key and body without creating a second conference', async () => {
  const saved = savedInline();
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('lost conference receipt'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [saved],
    });
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([saved]).items[0]);
  const { registry, parent, child } = await prepareInline();
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Charlie bridge' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  const retry = await screen.findByRole('button', {
    name: 'Retry exact conference save',
  });
  expect(
    (
      screen.getByRole('button', {
        name: 'Save Conference',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual(parent.input);
  expect(registry.resumeDraft(child.draftId)?.input.payload.title).toBe(
    'Charlie bridge'
  );
  fireEvent.click(retry);
  await screen.findByLabelText('Party / Participant (Optional)');
  expect(save).toHaveBeenCalledTimes(2);
  expect(save.mock.calls[1]).toEqual(save.mock.calls[0]);
  expect(registry.listDrafts()).toHaveLength(1);
});

it('keeps an accepted unreadable inline conference and rereads it before selecting without resubmission', async () => {
  const saved = savedInline();
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord')
    .mockRejectedValueOnce(new Error('read unavailable'))
    .mockResolvedValue(page([saved]).items[0]);
  const { registry, parent, child } = await prepareInline();
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Charlie bridge' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  const reconcile = await screen.findByRole('button', {
    name: 'Reread and reconcile',
  });
  expect(registry.resumeDraft(child.draftId)).not.toBeNull();
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual(parent.input);
  expect(
    (
      screen.getByRole('button', {
        name: 'Save Conference',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  fireEvent.click(reconcile);
  await screen.findByLabelText('Party / Participant (Optional)');
  expect(save).toHaveBeenCalledTimes(1);
});

it('recovers an accepted unreadable inline conference after reload without submitting it again', async () => {
  const saved = savedInline();
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord')
    .mockRejectedValueOnce(new Error('read unavailable'))
    .mockResolvedValue(page([saved]).items[0]);
  const { registry, parent, child } = await prepareInline();
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await screen.findByRole('button', { name: 'Reread and reconcile' });
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  const recovered = new DraftRegistry(sessionStorage);
  const retained = recovered.resumeDraft(child.draftId)!;
  mount(retained.input, false, false, undefined, {}, health, undefined, {
    registry: recovered,
    draftId: child.draftId,
  });
  const reread = await screen.findByRole('button', {
    name: 'Reread saved conference',
  });
  expect(
    (
      screen.getByRole('button', {
        name: 'Save Conference',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  fireEvent.click(reread);
  await screen.findByLabelText('Party / Participant (Optional)');
  expect(screen.getByRole('option', { name: 'Charlie bridge' })).toBeTruthy();
  expect(recovered.resumeDraft(parent.draftId)?.input.payload).toHaveProperty(
    'conference_id',
    'new-bridge'
  );
  expect(save).toHaveBeenCalledTimes(1);
  expect(registry.resumeDraft(parent.draftId)?.input).toEqual(parent.input);
});

it('retains partial explicit Zulu controls for a historical issue occurrence while parked', async () => {
  const { issueInput } = await import('../issueForms');
  const initial = issueInput('mission-a');
  initial.payload.corrects_version = 1;
  initial.payload.corrected_update_at = '2026-10-28T23:45:12.123456Z';
  const saved = { ...record, ...initial };
  const { registry, draft } = mount(initial, false, false, saved, {
    correctionVersion: 1,
  });
  const hour = await screen.findByLabelText('Corrected Occurrence hour (Zulu)');
  expect((hour as HTMLSelectElement).value).toBe('23');
  fireEvent.change(hour, { target: { value: '' } });
  expect(
    registry.resumeDraft(draft.draftId)?.editorState?.correctedOccurrenceParts
  ).toEqual({ date: '2026-10-28', time: ':45' });
  expect(registry.resumeDraft(draft.draftId)?.input.payload).toHaveProperty(
    'corrected_update_at',
    null
  );
});

it('uses the shared ad hoc transport catalog for reusable conference configuration', async () => {
  vi.mocked(transportCatalog.readTransportCatalog).mockResolvedValue({
    schema_version: 1,
    version: 1,
    services: [],
    transports: [
      {
        id: 'mission-sat',
        name: 'Mission satellite',
        enabled: true,
        archived: false,
      },
    ],
  });
  const { registry, draft } = mount(conferenceDraft('mission-a'));
  await screen.findAllByRole('option', { name: 'Mission satellite' });
  fireEvent.change(screen.getByLabelText('Intended Transport'), {
    target: { value: 'mission-sat' },
  });
  expect(registry.resumeDraft(draft.draftId)?.input.payload).toHaveProperty(
    'intended_transport',
    'mission-sat'
  );
});

it('keeps the independent conference when its parked parent call was discarded during the accepted read', async () => {
  const saved = savedInline();
  let resolveRead!: (value: ReturnType<typeof page>['items'][number]) => void;
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveRead = resolve;
      })
  );
  const { registry, parent, child } = await prepareInline();
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await waitFor(() => expect(api.readOperatorRecord).toHaveBeenCalled());
  registry.discardDraft(parent.draftId);
  await act(async () => resolveRead(page([saved]).items[0]));
  await waitFor(() => expect(registry.resumeDraft(child.draftId)).toBeNull());
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(save).toHaveBeenCalledTimes(1);
});

it('retains conference edits made during the accepted read as a correction to the saved conference', async () => {
  const saved = savedInline();
  let resolveRead!: (value: ReturnType<typeof page>['items'][number]) => void;
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [saved],
  });
  vi.spyOn(api, 'readOperatorRecord').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveRead = resolve;
      })
  );
  const { registry, child } = await prepareInline();
  fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
  await waitFor(() => expect(api.readOperatorRecord).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('Conference name (optional)'), {
    target: { value: 'Newer unsent name' },
  });
  await act(async () => resolveRead(page([saved]).items[0]));
  await screen.findByLabelText('Party / Participant (Optional)');
  const retained = registry.resumeDraft(child.draftId)!;
  expect(retained.target.recordId).toBe('new-bridge');
  expect(retained.baseVersion).toBe(saved.version);
  expect(retained.input.payload.title).toBe('Newer unsent name');
  expect(retained.editorState?.inlineParentCallDraftId).toBeUndefined();
  expect(retained.editorState?.inlineConferenceAccepted).toBeUndefined();
});

it.each([false, true])(
  'blocks inline entry during a pending parent create and updates that same saved call (newer input: %s)',
  async (newerInput) => {
    const call = callDraft(undefined, 'planned', 'mission-a');
    call.time.planned_start_at = '2026-10-28T12:00:00Z';
    const savedCall = { ...record, ...call, record_id: 'saved-call' };
    const bridge = savedInline();
    let resolveSave!: (
      value: Awaited<ReturnType<typeof api.saveOperatorCommand>>
    ) => void;
    const save = vi
      .spyOn(api, 'saveOperatorCommand')
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSave = resolve;
          })
      )
      .mockResolvedValueOnce({
        schema_version: 1,
        command_id: 'bridge-receipt',
        saved_records: [bridge],
      })
      .mockResolvedValueOnce({
        schema_version: 1,
        command_id: 'call-update',
        saved_records: [
          {
            ...savedCall,
            version: 2,
            payload: { ...savedCall.payload, conference_id: bridge.record_id },
          },
        ],
      });
    vi.spyOn(api, 'readOperatorRecord').mockImplementation(
      async (id) =>
        page([id === bridge.record_id ? bridge : savedCall]).items[0]
    );
    const { registry, draft } = mount(call);
    await screen.findByLabelText('Party / Participant (Optional)');
    fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    if (newerInput)
      fireEvent.change(
        screen.getByLabelText('Party / Participant (Optional)'),
        { target: { value: 'Newer retained party' } }
      );
    const submitted = registry.resumeDraft(draft.draftId)!;
    const inline = screen.getByRole('button', { name: 'Create Conference' });
    expect((inline as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(inline);
    expect(registry.listDrafts()).toHaveLength(1);
    expect(registry.resumeDraft(draft.draftId)?.revision).toBe(
      submitted.revision
    );
    await act(async () =>
      resolveSave({
        schema_version: 1,
        command_id: 'call-receipt',
        saved_records: [savedCall],
      })
    );
    if (newerInput) {
      await waitFor(() =>
        expect(registry.resumeDraft(draft.draftId)?.target.recordId).toBe(
          savedCall.record_id
        )
      );
      expect(registry.resumeDraft(draft.draftId)?.baseVersion).toBe(
        savedCall.version
      );
      expect(registry.resumeDraft(draft.draftId)?.input.payload).toMatchObject({
        party: 'Newer retained party',
      });
      expect(registry.resumeDraft(draft.draftId)?.target.newDraftId).toBeNull();
    } else {
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
      expect(registry.listDrafts()).toHaveLength(0);
      cleanup();
      mount(call, false, false, savedCall);
      await screen.findByLabelText('Party / Participant (Optional)');
    }
    await waitFor(() =>
      expect(
        (
          screen.getByRole('button', {
            name: 'Create Conference',
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );
    fireEvent.click(screen.getByRole('button', { name: 'Create Conference' }));
    await screen.findByLabelText('Conference name (optional)');
    fireEvent.click(screen.getByRole('button', { name: 'Save Conference' }));
    await screen.findByLabelText('Party / Participant (Optional)');
    fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(3));
    expect(
      save.mock.calls.filter(
        ([command]) =>
          command.operation === 'create' && command.body.record_type === 'call'
      )
    ).toHaveLength(1);
    expect(save.mock.calls[2][0]).toMatchObject({
      operation: 'update',
      record_id: 'saved-call',
      body: { payload: { conference_id: bridge.record_id } },
    });
  }
);
it('keeps inline entry blocked after the parent response is lost without modifying the submitted parent revision', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValue(new Error('Parent receipt lost'));
  const call = callDraft(undefined, 'planned', 'mission-a');
  call.time.planned_start_at = '2026-10-28T12:00:00Z';
  const { registry, draft } = mount(call);
  await screen.findByLabelText('Party / Participant (Optional)');
  fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
  await screen.findByText(/^uncertain ·/);
  const submitted = registry.resumeDraft(draft.draftId)!;
  const inline = screen.getByRole('button', { name: 'Create Conference' });
  expect((inline as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(inline);
  expect(registry.listDrafts()).toHaveLength(1);
  expect(registry.resumeDraft(draft.draftId)).toEqual(submitted);
  expect(save).toHaveBeenCalledTimes(1);
});

it('retargets newer parent input after acceptance but blocks saving and inline entry until the accepted call can be read', async () => {
  const call = callDraft(undefined, 'planned', 'mission-a');
  call.time.planned_start_at = '2026-10-28T12:00:00Z';
  const saved = { ...record, ...call, record_id: 'accepted-parent' };
  let resolveSave!: (
    value: Awaited<ReturnType<typeof api.saveOperatorCommand>>
  ) => void;
  const save = vi.spyOn(api, 'saveOperatorCommand').mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveSave = resolve;
      })
  );
  vi.spyOn(api, 'readOperatorRecord')
    .mockRejectedValueOnce(new Error('Read unavailable'))
    .mockResolvedValue(page([saved]).items[0]);
  const { registry, draft } = mount(call);
  await screen.findByLabelText('Party / Participant (Optional)');
  fireEvent.click(screen.getByRole('button', { name: 'Save Call' }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText('Party / Participant (Optional)'), {
    target: { value: 'Retained after acceptance' },
  });
  await act(async () =>
    resolveSave({
      schema_version: 1,
      command_id: 'parent-receipt',
      saved_records: [saved],
    })
  );
  const reread = await screen.findByRole('button', {
    name: 'Reread and reconcile',
  });
  expect(registry.resumeDraft(draft.draftId)?.target.recordId).toBe(
    saved.record_id
  );
  expect(
    (screen.getByRole('button', { name: 'Save Call' }) as HTMLButtonElement)
      .disabled
  ).toBe(true);
  expect(
    (
      screen.getByRole('button', {
        name: 'Create Conference',
      }) as HTMLButtonElement
    ).disabled
  ).toBe(true);
  fireEvent.click(reread);
  await waitFor(() =>
    expect(
      (
        screen.getByRole('button', {
          name: 'Create Conference',
        }) as HTMLButtonElement
      ).disabled
    ).toBe(false)
  );
  expect(registry.resumeDraft(draft.draftId)?.input.payload).toMatchObject({
    party: 'Retained after acceptance',
  });
  expect(save).toHaveBeenCalledTimes(1);
});
