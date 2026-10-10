import type {
  ExpectedLeg,
  PlanningDraft,
  PlanningSatelliteOptions,
} from '../../types/planning';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { routesApi } from '../../services/routes';
import { createClientId } from '../../lib/clientId';
import { Button } from '../ui/button';
export function PlanningXDraft({
  leg,
  draft,
  onChange,
  options,
}: {
  leg: ExpectedLeg;
  draft: PlanningDraft;
  onChange: (updates: Partial<PlanningDraft>) => void;
  options: PlanningSatelliteOptions;
}) {
  const [pointIndex, setPointIndex] = useState('');
  const [target, setTarget] = useState('');
  const route = useQuery({
    queryKey: ['planning-route-detail', leg.route?.route_id],
    queryFn: () => routesApi.get(leg.route!.route_id),
    enabled: !!leg.route,
  });
  const permitted = options.satellites.filter(
    (satellite) =>
      satellite.transport === 'X' &&
      satellite.eligible &&
      draft.permitted_satellite_ids?.includes(satellite.id)
  );
  const choices = (current?: string | null) => (
    <>
      <option value="">Select satellite</option>
      {current && !permitted.some((s) => s.id === current) && (
        <option value={current}>{current} — outside permitted set</option>
      )}
      {permitted.map((s) => (
        <option value={s.id} key={s.id}>
          {s.label}
        </option>
      ))}
    </>
  );
  const swaps = draft.swaps ?? [];
  const points = route.data?.points ?? [];
  const point = points[Number(pointIndex)];
  const add = () => {
    if (
      !leg.route ||
      pointIndex === '' ||
      !point?.occurrence_id ||
      !point.expected_arrival_time ||
      !permitted.some((s) => s.id === target)
    )
      return;
    onChange({
      swaps: [
        ...swaps,
        {
          id: createClientId(),
          target_satellite_id: target,
          origin: 'manual' as const,
          anchor: {
            route_id: leg.route.route_id,
            content_hash: leg.route.content_hash,
            segment_index: Number(pointIndex),
            fraction: 0,
            occurrence_id: point.occurrence_id,
            source_time: point.expected_arrival_time,
            latitude: point.latitude,
            longitude: point.longitude,
            timing_mode: 'route_bound' as const,
          },
        },
      ].sort(
        (a, b) =>
          Date.parse(a.anchor.source_time) - Date.parse(b.anchor.source_time)
      ),
    });
    setPointIndex('');
    setTarget('');
  };
  return (
    <section aria-label="Manual X-band draft" className="min-w-0 space-y-4">
      <h2 className="font-semibold">X-band plan</h2>
      <p className="text-sm text-muted-foreground">
        Edit the draft manually. These assignments remain provisional until
        route, AR, service access and availability validation is available. No
        automatic proposal is generated here.
      </p>
      <label className="block">
        Initial X-band satellite
        <select
          aria-label="Initial X-band satellite"
          className="block min-h-11 w-full rounded border bg-background p-2"
          value={draft.initial_x_satellite_id ?? ''}
          disabled={draft.locks?.some((lock) => lock.kind === 'initial')}
          onChange={(e) =>
            onChange({ initial_x_satellite_id: e.target.value || null })
          }
        >
          {choices(draft.initial_x_satellite_id)}
        </select>
      </label>
      {swaps.map((swap, index) => {
        const locked = draft.locks?.some(
          (lock) =>
            lock.swap_id === swap.id ||
            (lock.kind === 'swap' &&
              lock.anchor?.source_time === swap.anchor.source_time)
        );
        return (
          <fieldset
            key={swap.id}
            className="min-w-0 space-y-2 rounded border p-3"
          >
            <legend>
              Swap {index + 1}
              {locked ? ' · locked' : ''}
            </legend>
            <p className="break-words text-sm">
              UTC {swap.anchor.source_time} · {swap.anchor.latitude.toFixed(5)},{' '}
              {swap.anchor.longitude.toFixed(5)} · occurrence{' '}
              {swap.anchor.occurrence_id} ·{' '}
              {swap.anchor.fraction === 0 ? 'exact' : 'interpolated'}
            </p>
            <label>
              Swap {index + 1} satellite
              <select
                aria-label={`Swap ${index + 1} satellite`}
                className="block min-h-11 w-full rounded border bg-background p-2"
                value={swap.target_satellite_id}
                disabled={locked}
                onChange={(e) =>
                  onChange({
                    swaps: swaps.map((s) =>
                      s.id === swap.id
                        ? { ...s, target_satellite_id: e.target.value }
                        : s
                    ),
                  })
                }
              >
                {choices(swap.target_satellite_id)}
              </select>
            </label>
            <Button
              variant="outline"
              disabled={locked}
              onClick={() =>
                onChange({ swaps: swaps.filter((s) => s.id !== swap.id) })
              }
            >
              Remove swap {index + 1}
            </Button>
          </fieldset>
        );
      })}
      <div className="grid min-w-0 gap-3 sm:grid-cols-2">
        <label>
          New swap route occurrence
          <select
            aria-label="New swap route occurrence"
            className="block min-h-11 w-full rounded border bg-background p-2"
            value={pointIndex}
            onChange={(e) => setPointIndex(e.target.value)}
          >
            <option value="">Select timed occurrence</option>
            {points.map((p, index) =>
              p.occurrence_id && p.expected_arrival_time ? (
                <option key={`${p.occurrence_id}-${index}`} value={index}>
                  {p.expected_arrival_time} · {p.occurrence_id} ·{' '}
                  {p.latitude.toFixed(5)}, {p.longitude.toFixed(5)}
                </option>
              ) : null
            )}
          </select>
        </label>
        <label>
          New swap satellite
          <select
            aria-label="New swap satellite"
            className="block min-h-11 w-full rounded border bg-background p-2"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            {choices()}
          </select>
        </label>
      </div>
      <Button
        variant="outline"
        onClick={add}
        disabled={!leg.route || pointIndex === '' || !target}
      >
        Add manual swap
      </Button>
      {route.error && (
        <p role="alert">
          Unable to load timed route occurrences. Existing draft entries are
          preserved.
        </p>
      )}
    </section>
  );
}
