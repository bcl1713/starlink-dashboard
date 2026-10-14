import { useState } from 'react';
import type {
  ExpectedLeg,
  PlanningDraft,
  RouteAnchor,
} from '../../types/planning';
import type { RoutePoint } from '../../services/routes';
import { Button } from '../ui/button';

export function UnresolvedARWindows({
  leg,
  draft,
  routePoints,
  onChange,
}: {
  leg: ExpectedLeg;
  draft: PlanningDraft;
  routePoints: RoutePoint[];
  onChange: (update: Partial<PlanningDraft>) => void;
}) {
  const [endpoints, setEndpoints] = useState<
    Record<string, { start?: string; end?: string }>
  >({});
  const anchor = (index: string | undefined): RouteAnchor | undefined => {
    if (index === undefined || index === '' || !leg.route) return;
    const point = routePoints[Number(index)];
    if (!point?.occurrence_id || !point.expected_arrival_time) return;
    return {
      route_id: leg.route.route_id,
      content_hash: leg.route.content_hash,
      segment_index: Number(index),
      fraction: 0,
      latitude: point.latitude,
      longitude: point.longitude,
      occurrence_id: point.occurrence_id,
      source_time: point.expected_arrival_time,
      timing_mode: 'route_bound',
    };
  };
  return (
    <>
      {draft.unresolved_aar_windows?.map((window) => {
        const pair = endpoints[window.id] ?? {};
        const start = anchor(pair.start);
        const end = anchor(pair.end);
        const valid =
          start &&
          end &&
          Date.parse(start.source_time) < Date.parse(end.source_time) &&
          start.segment_index < end.segment_index;
        return (
          <section
            key={window.id}
            className="min-w-0 space-y-2 rounded border p-3"
          >
            <p role="alert">
              Pending AR {window.id}: {window.start_waypoint_name} →{' '}
              {window.end_waypoint_name}. Choose accepted timed occurrences,
              then confirm height and units below.
            </p>
            {(['start', 'end'] as const).map((side) => (
              <label key={side} className="block">
                AR {window.id} {side} occurrence
                <select
                  aria-label={`AR ${window.id} ${side} occurrence`}
                  className="block min-h-11 w-full bg-background"
                  value={pair[side] ?? ''}
                  onChange={(e) =>
                    setEndpoints({
                      ...endpoints,
                      [window.id]: { ...pair, [side]: e.target.value },
                    })
                  }
                >
                  <option value="">Select timed occurrence</option>
                  {routePoints.map(
                    (p, i) =>
                      p.occurrence_id &&
                      p.expected_arrival_time && (
                        <option key={i} value={i}>
                          {p.expected_arrival_time} · {p.occurrence_id}
                        </option>
                      )
                  )}
                </select>
              </label>
            ))}
            <Button
              disabled={!valid}
              onClick={() => {
                if (!valid) return;
                const rows = draft.ar_corrections ?? leg.ar_rows ?? [];
                const previous = rows.find((row) => row.id === window.id);
                onChange({
                  unresolved_aar_windows: draft.unresolved_aar_windows?.filter(
                    (row) => row.id !== window.id
                  ),
                  ar_corrections: [
                    ...rows.filter((row) => row.id !== window.id),
                    {
                      ...previous,
                      id: window.id,
                      track:
                        previous?.track ??
                        `${window.start_waypoint_name} → ${window.end_waypoint_name}`,
                      entry_time: start.source_time,
                      exit_time: end.source_time,
                      source_time_precision: 'second',
                      start_anchor: start,
                      end_anchor: end,
                      match_status: 'matched',
                      confirmed: false,
                    },
                  ],
                  no_ars_confirmed: false,
                  evaluation_context: null,
                });
              }}
            >
              Resolve AR {window.id}
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                onChange({
                  unresolved_aar_windows: draft.unresolved_aar_windows?.filter(
                    (row) => row.id !== window.id
                  ),
                })
              }
            >
              Discard pending AR {window.id}
            </Button>
          </section>
        );
      })}
    </>
  );
}
