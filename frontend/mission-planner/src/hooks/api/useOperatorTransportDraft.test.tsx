/** @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useOperatorTransportDraft } from './useOperatorTransportDraft';
import { newTransportDraft } from '@/components/operator/transportForms';
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it('retains stable rows across reload and isolates store/mission keys', () => {
  const initial = newTransportDraft('synthetic-a');
  const first = renderHook(() =>
    useOperatorTransportDraft('store-a:mission-a', initial)
  );
  act(() =>
    first.result.current.setDraft({
      ...initial,
      input: {
        ...initial.input,
        payload: {
          ...initial.input.payload,
          reason: 'Retrospective correction',
        },
      },
    })
  );
  first.unmount();
  const second = renderHook(() =>
    useOperatorTransportDraft(
      'store-a:mission-a',
      newTransportDraft('synthetic-a')
    )
  );
  expect(second.result.current.draft.input.payload.services[0].row_id).toBe(
    initial.input.payload.services[0].row_id
  );
  expect(second.result.current.draft.input.payload.reason).toBe(
    'Retrospective correction'
  );
  const third = renderHook(() =>
    useOperatorTransportDraft('store-b:mission-a', initial)
  );
  expect(third.result.current.draft.input.payload.reason).toBe('');
});
it('keeps entry possible when tab storage fails', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('full');
  });
  const { result } = renderHook(() =>
    useOperatorTransportDraft('store', newTransportDraft('synthetic-a'))
  );
  act(() => result.current.setDraft(result.current.draft));
  expect(result.current.storageError).toContain('Keep this page open');
  expect(result.current.draft.input.mission_id).toBe('synthetic-a');
});
it('rejects malformed persisted draft without crashing entry', () => {
  sessionStorage.setItem('broken', '{"input":null}');
  const { result } = renderHook(() =>
    useOperatorTransportDraft('broken', newTransportDraft('synthetic-a'))
  );
  expect(result.current.draft.input.payload.services.length).toBe(1);
  expect(result.current.storageError).toBeTruthy();
});
