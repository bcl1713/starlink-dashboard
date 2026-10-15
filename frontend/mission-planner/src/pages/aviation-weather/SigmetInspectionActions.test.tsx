// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SigmetInspectionActions } from './SigmetInspectionActions';
const mocks = vi.hoisted(() => ({mutate:vi.fn(), ack:vi.fn(), snapshot:null as unknown}));
vi.mock('@/hooks/api/useRouteSigmets', () => ({
  useRouteSigmets: () => ({snapshot:mocks.snapshot, available:true}),
  useSelectSigmet: () => ({mutate:mocks.mutate,isPending:false,error:null}),
  useSetSigmetAcknowledgement: () => ({mutate:mocks.ack,isPending:false,error:null}),
}));
afterEach(() => {cleanup();vi.clearAllMocks();});
it('allows inspection without creating a selection when there is no route', () => {
  mocks.snapshot = null;
  render(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).not.toHaveBeenCalled();
  expect(screen.getByText(/Select a route/)).toBeDefined();
});
it('adds a chosen report once while overlapping candidates wait for a choice', () => {
  mocks.snapshot = {context:{context_key:'c'},entries:[],selected_entries:[],selection_candidates:[{bulletin_key:'b',semantic_digest:'s',feature_ids:['off-route']}]};
  const {rerender} = render(<SigmetInspectionActions featureId="off-route" autoSelect={false} />);
  expect(mocks.mutate).not.toHaveBeenCalled();
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
  rerender(<SigmetInspectionActions featureId="off-route" autoSelect />);
  expect(mocks.mutate).toHaveBeenCalledTimes(1);
});
