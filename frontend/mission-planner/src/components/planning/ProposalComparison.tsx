import type { PlanningProposal } from '../../types/planning';
import { Button } from '../ui/button';

export function ProposalComparison({
  proposal,
  onApply,
  disabled = false,
}: {
  proposal: PlanningProposal;
  onApply: () => void;
  disabled?: boolean;
}) {
  const labels = {
    current: 'Current plan',
    lock_feasible: 'Feasible locked baseline',
    best_constant: 'Best constant baseline',
  };
  return (
    <section
      aria-label="Proposal comparison"
      className="min-w-0 space-y-3 rounded border p-4"
    >
      <h2 className="font-semibold">Compare proposal</h2>
      {proposal.retained_current_draft && (
        <p>Current plan retained — no improved generated candidate.</p>
      )}
      <p className="text-sm">
        Search compares generated swaps on the shared 60-second grid and exact
        boundaries, preserving locks, with the valid current draft. Generated
        swap buffers do not overlap each other.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th>Plan</th>
              <th>X outage seconds</th>
              <th>Swaps</th>
              <th>Longest X outage seconds</th>
            </tr>
          </thead>
          <tbody>
            {[
              [
                labels[proposal.baseline_kind ?? 'current'],
                proposal.baseline_evaluation,
              ],
              ['Proposal', proposal.candidate_evaluation],
            ].map(([label, raw]) => {
              const value = raw as PlanningProposal['candidate_evaluation'];
              return (
                <tr key={String(label)}>
                  <th>{String(label)}</th>
                  <td>{value?.outage_seconds ?? 'Unavailable'}</td>
                  <td>{value?.swap_count ?? '—'}</td>
                  <td>{value?.longest_gap_seconds ?? '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p>
        Initial satellite:{' '}
        {proposal.proposed_draft?.initial_x_satellite_id ?? 'Unassigned'}
      </p>
      {proposal.proposed_draft?.swaps?.map((swap) => (
        <p key={swap.id} className="break-words">
          UTC {swap.anchor.source_time} → {swap.target_satellite_id} ·{' '}
          {swap.origin ?? 'manual'}
        </p>
      ))}
      {proposal.errors?.map((error, i) => (
        <p role="alert" key={i}>
          {error.message}
        </p>
      ))}
      {proposal.state === 'stale' && (
        <p role="alert">
          Proposal is stale. Re-optimize to compare current inputs.
        </p>
      )}
      <Button
        onClick={onApply}
        disabled={
          disabled || proposal.state !== 'ready' || !proposal.proposed_draft
        }
      >
        Apply proposal
      </Button>
    </section>
  );
}
