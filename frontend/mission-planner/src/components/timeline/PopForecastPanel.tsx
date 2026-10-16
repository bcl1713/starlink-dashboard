import { useId, useState } from 'react';
import type { CallContinuityProjection, PopForecast } from '@/types/pop';
import type { TimelineSegment } from '@/services/timeline';
import {
  POP_NOTE,
  POP_CAUTION,
  popCities,
  projectPopAdvisories,
} from '@/pages/pop-advisory-projection';
import { PopTransitionMarkers } from './PopTransitionMarkers';
import { formatUtc } from './formatting';

interface Props {
  forecast?: PopForecast | null;
  continuity?: CallContinuityProjection | null;
  continuityBasis?: 'Full mission' | 'Remaining mission';
  segments?: TimelineSegment[];
  nowMs?: number;
}
/** Shared planner/live view. Exact backend bounds remain the canonical evidence. */
export function PopForecastPanel({
  forecast,
  continuity,
  continuityBasis = 'Full mission',
  segments = [],
  nowMs,
}: Props) {
  const selectId = useId();
  const [selection, setSelection] = useState<{
    revision: string;
    id: string;
  } | null>(null);
  if (forecast?.status === 'disabled') return null;
  const view = projectPopAdvisories({
    pop_forecast: forecast,
    call_continuity: continuity,
  });
  const transitions = forecast?.status === 'ready' ? forecast.transitions : [];
  const selected =
    transitions.find(
      (item) =>
        selection?.revision === forecast?.revision &&
        item.crossing.id === selection?.id
    ) ?? transitions[0];
  const startUtc = segments[0]?.start_time ?? transitions[0]?.window_start_utc;
  const endUtc =
    segments.at(-1)?.end_time ?? transitions.at(-1)?.window_end_utc;
  const start = Date.parse(startUtc ?? ''),
    end = Date.parse(endUtc ?? '');
  const duration = end - start;
  const validBounds = Number.isFinite(duration) && duration > 0;
  const current =
    nowMs === undefined || !validBounds
      ? null
      : (100 * (nowMs - start)) / duration;
  return (
    <section
      aria-label="Starshield PoP predictions"
      className="min-w-0 rounded border border-border bg-card p-3 text-sm space-y-2"
    >
      <h4 className="font-semibold">Starshield PoP predictions</h4>
      <p>{view.summary}</p>
      <p>
        {continuityBasis}: {view.continuity}
      </p>
      {transitions.length > 0 && (
        <>
          <p>{POP_NOTE}</p>
          <p className="text-xs">
            Outlined bands: possible PoP transition. Shading: existing
            Starshield availability.
          </p>
          {validBounds && (
            <>
              <div className="flex justify-between gap-2 text-xs">
                <span>UTC {formatUtc(startUtc!)}</span>
                <span>UTC {formatUtc(endUtc!)}</span>
              </div>
              <div
                className="relative isolate"
                aria-label="Starshield timeline"
              >
                <div
                  aria-hidden="true"
                  className="absolute inset-0 flex bg-muted/30"
                >
                  {segments.map((segment) => (
                    <span
                      key={segment.id}
                      className={
                        segment.ku_state === 'available'
                          ? 'bg-green-600/15'
                          : ['unavailable', 'offline', 'blocked'].includes(
                                segment.ku_state ?? ''
                              )
                            ? 'bg-destructive/25'
                            : 'bg-muted/50'
                      }
                      style={{
                        width: `${(100 * (Date.parse(segment.end_time) - Date.parse(segment.start_time))) / duration}%`,
                      }}
                    />
                  ))}
                </div>
                <PopTransitionMarkers
                  forecast={forecast}
                  startUtc={startUtc}
                  endUtc={endUtc}
                  onSelect={(item) =>
                    setSelection({
                      revision: forecast!.revision,
                      id: item.crossing.id,
                    })
                  }
                />
                {current !== null && current >= 0 && current <= 100 && (
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-y-0 border-l-2 border-foreground"
                    style={{ left: `${current}%` }}
                  />
                )}
              </div>
            </>
          )}
          <label htmlFor={selectId} className="block">
            PoP transition details
          </label>
          <select
            id={selectId}
            className="min-h-11 w-full rounded border border-border bg-card px-2"
            value={selected?.crossing.id ?? ''}
            onChange={(event) =>
              setSelection({
                revision: forecast!.revision,
                id: event.target.value,
              })
            }
          >
            {transitions.map((item) => (
              <option key={item.crossing.id} value={item.crossing.id}>
                {popCities(item)} · UTC {formatUtc(item.crossing_utc)}
              </option>
            ))}
          </select>
          {selected && (
            <div aria-live="polite" className="break-words space-y-1">
              <p className="font-medium">{popCities(selected)}</p>
              <p>Estimated crossing UTC {formatUtc(selected.crossing_utc)}</p>
              <p>
                Planning window UTC {formatUtc(selected.window_start_utc)} →{' '}
                {formatUtc(selected.window_end_utc)}
              </p>
              <p>{POP_CAUTION}</p>
              {(
                view.transitionDetails[selected.crossing.id] ?? [
                  'Call continuity unresolved.',
                ]
              ).map((message) => (
                <p key={message}>{message}</p>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
