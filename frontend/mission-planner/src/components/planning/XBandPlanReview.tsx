import type {
  ExpectedLeg,
  PlanningDraft,
  PlanningEvaluation,
  PlanningProposal,
  PlanningSatelliteOptions,
  RouteAnchor,
} from '../../types/planning';
import type { RoutePoint } from '../../services/routes';
import { createClientId } from '../../lib/clientId';
import { PlanningXDraft } from './PlanningXDraft';
import { ProposalComparison } from './ProposalComparison';
import { TimelinePreviewSection } from '../timeline/TimelinePreviewSection';
import { Button } from '../ui/button';

export function XBandPlanReview({
  leg,
  draft,
  options,
  onChange,
  evaluation,
  proposal,
  onApply,
  onReoptimize,
  disabled = false,
  routePoints = [],
}: {
  leg: ExpectedLeg;
  draft: PlanningDraft;
  options: PlanningSatelliteOptions;
  onChange: (updates: Partial<PlanningDraft>) => void;
  evaluation?: PlanningEvaluation | null;
  proposal?: PlanningProposal | null;
  onApply?: () => void;
  onReoptimize?: () => void;
  disabled?: boolean;
  routePoints?: RoutePoint[];
}) {
  const locks = draft.locks ?? [];
  const anchor = (index: string): RouteAnchor | undefined => {
    const point = routePoints[Number(index)];
    if (
      index === '' ||
      !point?.occurrence_id ||
      !point.expected_arrival_time ||
      !leg.route
    )
      return;
    return {
      route_id: leg.route.route_id,
      content_hash: leg.route.content_hash,
      segment_index: Number(index),
      fraction: 0,
      occurrence_id: point.occurrence_id,
      source_time: point.expected_arrival_time,
      latitude: point.latitude,
      longitude: point.longitude,
      timing_mode: 'route_bound',
    };
  };
  const occurrences = (
    <>
      <option value="">Select timed occurrence</option>
      {routePoints.map(
        (point, index) =>
          point.occurrence_id &&
          point.expected_arrival_time && (
            <option key={index} value={index}>
              {point.expected_arrival_time} · {point.occurrence_id}
            </option>
          )
      )}
    </>
  );
  return (
    <div className="min-w-0 space-y-4">
      <PlanningXDraft
        leg={leg}
        draft={draft}
        options={options}
        onChange={onChange}
      />
      <label className="flex min-h-11 items-center gap-2">
        <input
          type="checkbox"
          aria-label="Lock initial satellite"
          checked={locks.some((lock) => lock.kind === 'initial')}
          disabled={!draft.initial_x_satellite_id}
          onChange={(e) =>
            onChange({
              locks: e.target.checked
                ? [
                    ...locks,
                    {
                      id: createClientId(),
                      kind: 'initial',
                      target_satellite_id: draft.initial_x_satellite_id!,
                    },
                  ]
                : locks.filter((lock) => lock.kind !== 'initial'),
            })
          }
        />
        Lock initial satellite
      </label>
      {draft.swaps?.map((swap, index) => (
        <div key={swap.id} className="space-y-2 rounded border p-3">
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              aria-label={`Lock swap ${index + 1}`}
              checked={locks.some((lock) => lock.swap_id === swap.id)}
              onChange={(e) =>
                onChange({
                  locks: e.target.checked
                    ? [
                        ...locks,
                        {
                          id: createClientId(),
                          kind: 'swap',
                          swap_id: swap.id,
                          target_satellite_id: swap.target_satellite_id,
                          anchor: swap.anchor,
                        },
                      ]
                    : locks.filter((lock) => lock.swap_id !== swap.id),
                })
              }
            />
            Lock swap {index + 1}
          </label>
          <label className="block">
            Move swap {index + 1} to occurrence
            <select
              aria-label={`Move swap ${index + 1} to occurrence`}
              className="block min-h-11 w-full bg-background"
              value=""
              disabled={locks.some((lock) => lock.swap_id === swap.id)}
              onChange={(e) => {
                const next = anchor(e.target.value);
                if (next)
                  onChange({
                    swaps: draft.swaps?.map((s) =>
                      s.id === swap.id
                        ? { ...s, anchor: next, origin: 'manual' }
                        : s
                    ),
                    evaluation_context: null,
                  });
              }}
            >
              {occurrences}
            </select>
          </label>
        </div>
      ))}
      {draft.unresolved_x_transitions?.map((transition) => (
        <div key={transition.id} className="space-y-2 rounded border p-3">
          <p role="alert">
            Unresolved swap {transition.id}: {transition.latitude},{' '}
            {transition.longitude} → {transition.target_satellite_id}
          </p>
          <label className="block">
            Resolve swap {transition.id}
            <select
              className="block min-h-11 w-full bg-background"
              aria-label={`Resolve swap ${transition.id}`}
              value=""
              onChange={(e) => {
                const next = anchor(e.target.value);
                if (next)
                  onChange({
                    swaps: [
                      ...(draft.swaps ?? []).filter(
                        (s) => s.id !== transition.id
                      ),
                      {
                        id: transition.id,
                        target_satellite_id: transition.target_satellite_id,
                        anchor: next,
                        origin: 'manual',
                      },
                    ],
                    unresolved_x_transitions:
                      draft.unresolved_x_transitions?.filter(
                        (t) => t.id !== transition.id
                      ),
                    evaluation_context: null,
                  });
              }}
            >
              {occurrences}
            </select>
          </label>
          <Button
            variant="outline"
            onClick={() =>
              onChange({
                unresolved_x_transitions:
                  draft.unresolved_x_transitions?.filter(
                    (t) => t.id !== transition.id
                  ),
              })
            }
          >
            Discard pending swap {transition.id}
          </Button>
        </div>
      ))}
      {onReoptimize && (
        <Button variant="outline" onClick={onReoptimize} disabled={disabled}>
          Re-optimize
        </Button>
      )}
      {proposal && onApply && (
        <ProposalComparison
          proposal={proposal}
          onApply={onApply}
          disabled={disabled}
        />
      )}
      {evaluation && (
        <TimelinePreviewSection
          timeline={null}
          isCalculating={false}
          planningEvaluation={evaluation}
        />
      )}
    </div>
  );
}
