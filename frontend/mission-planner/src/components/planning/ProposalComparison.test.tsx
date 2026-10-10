/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { ProposalComparison } from './ProposalComparison';
import type { PlanningProposal } from '../../types/planning';
afterEach(cleanup);
const evaluation = {
  context: { input_identity: 'ctx' },
  outage_seconds: 120,
  swap_count: 0,
  longest_gap_seconds: 60,
};
const proposal: PlanningProposal = {
  id: 'p',
  expected_revision: 2,
  input_identity: 'draft',
  context: evaluation.context,
  state: 'ready',
  baseline_kind: 'lock_feasible',
  retained_current_draft: false,
  baseline_evaluation: evaluation,
  candidate_evaluation: { ...evaluation, outage_seconds: 30 },
  proposed_draft: {
    initial_x_satellite_id: 'WEST',
    swaps: [
      {
        id: 's',
        target_satellite_id: 'SOUTH',
        origin: 'generated',
        anchor: {
          route_id: 'r',
          content_hash: 'h',
          segment_index: 0,
          fraction: 0.5,
          occurrence_id: 'a',
          source_time: '2026-10-25T12:04:17Z',
          latitude: 1,
          longitude: 2,
          timing_mode: 'fixed_utc',
        },
      },
    ],
  },
};
it('compares the honest baseline and exact UTC swaps; applies only on explicit action', () => {
  const apply = vi.fn();
  render(<ProposalComparison proposal={proposal} onApply={apply} />);
  expect(screen.getByText('Feasible locked baseline')).toBeInTheDocument();
  expect(screen.getByText(/2026-10-25T12:04:17Z/)).toBeInTheDocument();
  expect(apply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Apply proposal' }));
  expect(apply).toHaveBeenCalledOnce();
});
it('discloses retained current draft and prevents stale Apply', () => {
  render(
    <ProposalComparison
      proposal={{ ...proposal, state: 'stale', retained_current_draft: true }}
      onApply={vi.fn()}
    />
  );
  expect(screen.getByText(/Current plan retained/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Apply proposal' })).toBeDisabled();
});
