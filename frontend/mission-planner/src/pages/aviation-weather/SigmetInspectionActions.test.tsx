// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SigmetInspectionActions } from './SigmetInspectionActions';
const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
  ack: vi.fn(),
  snapshot: null as unknown,
}));
vi.mock('@/hooks/api/useRouteSigmets', () => ({
  useRouteSigmets: () => ({ snapshot: mocks.snapshot, available: true }),
  useSelectSigmet: () => ({
    mutate: mocks.mutate,
    isPending: false,
    error: null,
  }),
  useSetSigmetAcknowledgement: () => ({
    mutate: mocks.ack,
    isPending: false,
    error: null,
  }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it('allows inspection without creating a selection when there is no route', () => {
  mocks.snapshot = null;
  render(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).not.toHaveBeenCalled();
  expect(screen.getByText(/Select a route/)).toBeDefined();
});
it('adds a chosen report once while overlapping candidates wait for a choice', () => {
  mocks.snapshot = {
    context: { context_key: 'c' },
    entries: [],
    selected_entries: [],
    selection_candidates: [
      { bulletin_key: 'b', semantic_digest: 's', feature_ids: ['off-route'] },
    ],
  };
  const { rerender } = render(
    <SigmetInspectionActions featureId="off-route" autoSelect={false} />
  );
  expect(mocks.mutate).not.toHaveBeenCalled();
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
});

it('does not undo acknowledgement on another display while inspection stays open', () => {
  const entry = {
    notice_key: 'n',
    semantic_digest: 's',
    feature_ids: ['off-route'],
    acknowledged: false,
  };
  const state = {
    context: { context_key: 'c' },
    entries: [entry],
    selected_entries: [],
    selection_candidates: [
      { bulletin_key: 'b', semantic_digest: 's', feature_ids: ['off-route'] },
    ],
  };
  mocks.snapshot = state;
  const { rerender } = render(
    <SigmetInspectionActions featureId="off-route" autoSelect />
  );
  mocks.snapshot = { ...state, entries: [{ ...entry, acknowledged: true }] };
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).not.toHaveBeenCalled();
});
it('does not select into a replacement route without a fresh inspection gesture', () => {
  const state = {
    context: { context_key: 'old' },
    entries: [],
    selected_entries: [],
    selection_candidates: [
      { bulletin_key: 'b', semantic_digest: 's', feature_ids: ['off-route'] },
    ],
  };
  mocks.snapshot = state;
  const { rerender } = render(
    <SigmetInspectionActions featureId="off-route" autoSelect />
  );
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
  mocks.snapshot = { ...state, context: { context_key: 'new' } };
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Route changed/)).toBeDefined();
});
it('focuses an already pending bulletin without issuing another selection write', () => {
  mocks.snapshot = {
    context: { context_key: 'c' },
    entries: [
      {
        notice_key: 'n',
        semantic_digest: 's',
        feature_ids: ['off-route'],
        acknowledged: false,
      },
    ],
    selected_entries: [],
    selection_candidates: [
      { bulletin_key: 'b', semantic_digest: 's', feature_ids: ['off-route'] },
    ],
  };
  const focus = vi.fn();
  render(
    <SigmetInspectionActions
      featureId="off-route"
      autoSelect
      onFocused={focus}
    />
  );
  expect(focus).toHaveBeenCalledWith('n');
  expect(mocks.mutate).not.toHaveBeenCalled();
});
