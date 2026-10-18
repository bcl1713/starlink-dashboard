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
import { health, input } from '@/test/operator-fixtures';
import * as api from '@/services/operator';
import type { DraftTarget } from './types';

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
function mount() {
  const registry = new DraftRegistry(sessionStorage);
  const draft = registry.createDraft(target, input);
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
