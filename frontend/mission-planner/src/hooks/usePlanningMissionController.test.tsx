/** @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { usePlanning } from './api/usePlanning';
import { planningApi } from '../services/planning';
import { StrictMode, type ReactNode } from 'react';
import type { PlanningEvaluation, PlanningView } from '../types/planning';
import { usePlanningMissionController } from './usePlanningMissionController';

const view = (revision: number, identity = 'a') =>
  ({
    mission: { id: 'mission', legs: [] },
    revision,
    expected_legs: [{ leg: { id: 'leg' }, input_identity: identity }],
  }) as unknown as PlanningView;
const evaluation = {} as PlanningEvaluation;
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function setup() {
  const client = new QueryClient();
  client.setQueryData(['planning', 'mission'], view(1));
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}
it('shares one mission queue and reads the newest revision at each write', async () => {
  const { client, wrapper } = setup();
  const a = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  const b = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  expect(a.result.current).toBe(b.result.current);
  let release!: () => void;
  const barrier = new Promise<void>((resolve) => {
    release = resolve;
  });
  const seen: number[] = [];
  const first = a.result.current.enqueueMutation(
    async (current) => {
      seen.push(current.revision);
      await barrier;
      return view(2);
    },
    (result) => result
  );
  const second = b.result.current.enqueueMutation(
    async (current) => {
      seen.push(current.revision);
      return view(3);
    },
    (result) => result
  );
  await act(async () => {
    await Promise.resolve();
    expect(seen).toEqual([1]);
    release();
    await Promise.all([first, second]);
  });
  expect(seen).toEqual([1, 2]);
  expect(client.getQueryData(['planning', 'mission'])).toEqual(view(3));
});
it('rejects obsolete previews without discarding edits or another leg revision', () => {
  const { client, wrapper } = setup();
  const hook = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  const old = hook.result.current.beginPreview('leg', 'draft-one');
  const current = hook.result.current.beginPreview('leg', 'draft-two');
  client.setQueryData(['planning', 'mission'], view(2));
  expect(hook.result.current.acceptPreview(old, evaluation)).toBe(false);
  expect(hook.result.current.acceptPreview(current, evaluation)).toBe(true);
  const changed = hook.result.current.beginPreview('leg', 'draft-three');
  client.setQueryData(['planning', 'mission'], view(3, 'new-input'));
  expect(hook.result.current.acceptPreview(changed, evaluation)).toBe(false);
});
it('retains a failed write and does not blindly retry a conflict', async () => {
  const { client, wrapper } = setup();
  const hook = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  let calls = 0;
  const localDraft = { note: 'retain me' };
  await expect(
    hook.result.current.enqueueMutation(
      async () => {
        calls++;
        throw new Error('409');
      },
      () => null
    )
  ).rejects.toThrow('409');
  expect(calls).toBe(1);
  expect(localDraft).toEqual({ note: 'retain me' });
  expect(client.getQueryData(['planning', 'mission'])).toEqual(view(1));
  const done = await hook.result.current.enqueueMutation(
    async () => view(2),
    (result) => result
  );
  expect(done.revision).toBe(2);
});
it('finishes an owned write in cache after the last component unmounts', async () => {
  const { client, wrapper } = setup();
  const hook = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  let release!: () => void;
  const barrier = new Promise<void>((resolve) => {
    release = resolve;
  });
  const pending = hook.result.current.enqueueMutation(
    async () => {
      await barrier;
      return view(2);
    },
    (result) => result
  );
  hook.unmount();
  release();
  await pending;
  expect(client.getQueryData(['planning', 'mission'])).toEqual(view(2));
});

it('serializes writes from two API hook instances for different legs', async () => {
  const { client, wrapper } = setup();
  const initial = view(1);
  initial.expected_legs.push({
    ...initial.expected_legs[0],
    leg: { ...initial.expected_legs[0].leg, id: 'other' },
    input_identity: 'b',
  });
  client.setQueryData(['planning', 'mission'], initial);
  const a = renderHook(() => usePlanning('mission', false), { wrapper });
  const b = renderHook(() => usePlanning('mission', false), { wrapper });
  let release!: (value: PlanningView) => void;
  const save = vi
    .spyOn(planningApi, 'saveDraft')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve;
        })
    )
    .mockImplementation(async () => ({ ...initial, revision: 3 }));
  const first = a.result.current.saveDraft.mutateAsync({
    legId: 'leg',
    draft: { starshield_enabled: false },
    expectedRevision: 1,
    inputIdentity: 'a',
  });
  const second = b.result.current.saveDraft.mutateAsync({
    legId: 'other',
    draft: { starshield_enabled: false },
    expectedRevision: 1,
    inputIdentity: 'b',
  });
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(save).toHaveBeenCalledTimes(1);
  const committed = {
    ...initial,
    revision: 2,
    expected_legs: initial.expected_legs.map((card) =>
      card.leg.id === 'leg' ? { ...card, input_identity: 'a2' } : card
    ),
  };
  await act(async () => {
    release(committed);
    await Promise.all([first, second]);
  });
  expect(save.mock.calls.map((call) => call[2].expected_revision)).toEqual([
    1, 2,
  ]);
});
it('rejects a changed leg before overwriting it from a queued stale local draft', async () => {
  const { client, wrapper } = setup();
  const hook = renderHook(() => usePlanning('mission', false), { wrapper });
  const save = vi.spyOn(planningApi, 'saveDraft');
  const draft = { starshield_enabled: false };
  client.setQueryData(['planning', 'mission'], view(2, 'changed'));
  await expect(
    hook.result.current.saveDraft.mutateAsync({
      legId: 'leg',
      draft,
      expectedRevision: 1,
      inputIdentity: 'a',
    })
  ).rejects.toMatchObject({ response: { status: 409 } });
  expect(save).not.toHaveBeenCalled();
  expect(draft.starshield_enabled).toBe(false);
});

it('does not let an earlier read replace a committed mutation', async () => {
  const { client, wrapper } = setup();
  let release!: (value: PlanningView) => void;
  vi.spyOn(planningApi, 'read').mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve;
      })
  );
  vi.spyOn(planningApi, 'saveDraft').mockResolvedValue(view(2, 'saved'));
  const hook = renderHook(() => usePlanning('mission'), { wrapper });
  await waitFor(() => expect(release).toBeDefined());
  await act(async () => {
    await hook.result.current.saveDraft.mutateAsync({
      legId: 'leg',
      draft: {},
      expectedRevision: 1,
      inputIdentity: 'a',
    });
    release(view(1));
  });
  await waitFor(() => expect(hook.result.current.data?.revision).toBe(2));
  expect(client.getQueryData(['planning', 'mission'])).toEqual(
    view(2, 'saved')
  );
});
it('shares a controller after React Strict Mode effect replay', async () => {
  const { client } = setup();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <StrictMode>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </StrictMode>
  );
  const first = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  await act(async () => {
    await Promise.resolve();
  });
  const second = renderHook(() => usePlanningMissionController('mission'), {
    wrapper,
  });
  expect(second.result.current).toBe(first.result.current);
});
