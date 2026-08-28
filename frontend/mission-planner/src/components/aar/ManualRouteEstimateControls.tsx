import type { ManualAARTrack, ManualRouteSplice } from '../../types/aar';
import type { DerivedRouteEstimate } from '../../services/timeline';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

interface ManualRouteEstimateControlsProps {
  tracks: ManualAARTrack[];
  splice?: ManualRouteSplice;
  estimate?: DerivedRouteEstimate | null;
  onChange: (splice?: ManualRouteSplice) => void;
}

function valueOrEmpty(value?: number | null): string {
  return value === undefined || value === null ? '' : String(value);
}

function toOptionalNumber(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatDuration(seconds?: number): string {
  if (typeof seconds !== 'number') return 'Unavailable';
  const sign = seconds > 0 ? '+' : seconds < 0 ? '−' : '';
  return `${sign}${Math.round(Math.abs(seconds) / 60)} min`;
}

function formatSpeedSource(source?: string | null): string {
  if (source === 'assumed_400_ktas') return 'assumed 400 KTAS';
  if (source === 'operator_override') return 'operator override';
  if (source === 'local_weighted_median') return 'local planned-route timing';
  if (source === 'global_weighted_median') return 'planned-route timing';
  if (source === 'planned_total_distance_duration') {
    return 'planned route total duration';
  }
  return source || 'unknown source';
}

/** Controls only persist selection/overrides; preview geometry and ETA stay ephemeral. */
export function ManualRouteEstimateControls({
  tracks,
  splice,
  estimate,
  onChange,
}: ManualRouteEstimateControlsProps) {
  const update = (updates: Partial<ManualRouteSplice>) => {
    if (!splice) return;
    onChange({ ...splice, ...updates });
  };

  return (
    <section
      className="space-y-4 rounded-lg border border-border bg-muted/40 p-4"
      aria-labelledby="manual-route-estimate-heading"
    >
      <div>
        <h3
          id="manual-route-estimate-heading"
          className="text-base font-semibold"
        >
          Estimated replacement route
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose one Manual AR track to estimate a replacement route. The
          planned route remains the reference; only the selected track and
          optional overrides are saved.
        </p>
      </div>

      {tracks.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Save a Manual AR track before selecting an estimated replacement.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {tracks.map((track) => (
            <Button
              key={track.id}
              type="button"
              variant={
                splice?.enabled_track_id === track.id ? 'default' : 'outline'
              }
              className="h-auto min-h-11 justify-start whitespace-normal text-left"
              aria-pressed={splice?.enabled_track_id === track.id}
              onClick={() => onChange({ enabled_track_id: track.id })}
            >
              Use {track.name} as estimated route
            </Button>
          ))}
        </div>
      )}

      {splice && (
        <>
          <Button
            type="button"
            variant="outline"
            onClick={() => onChange(undefined)}
          >
            Revert to planned route
          </Button>
          <details className="rounded border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Optional anchor and speed overrides
            </summary>
            <p className="mt-2 text-xs text-muted-foreground">
              Overrides are checked by the same forward-progress and 100 NM
              connector rules as automatic anchors.
            </p>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Input
                aria-label="Leave segment override"
                type="number"
                min="0"
                value={valueOrEmpty(splice.leave_segment_index)}
                onChange={(event) =>
                  update({
                    leave_segment_index: toOptionalNumber(event.target.value),
                  })
                }
                placeholder="Leave segment"
              />
              <Input
                aria-label="Leave fraction override"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={valueOrEmpty(splice.leave_fraction)}
                onChange={(event) =>
                  update({
                    leave_fraction: toOptionalNumber(event.target.value),
                  })
                }
                placeholder="Leave fraction (0–1)"
              />
              <Input
                aria-label="Rejoin segment override"
                type="number"
                min="0"
                value={valueOrEmpty(splice.rejoin_segment_index)}
                onChange={(event) =>
                  update({
                    rejoin_segment_index: toOptionalNumber(event.target.value),
                  })
                }
                placeholder="Rejoin segment"
              />
              <Input
                aria-label="Rejoin fraction override"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={valueOrEmpty(splice.rejoin_fraction)}
                onChange={(event) =>
                  update({
                    rejoin_fraction: toOptionalNumber(event.target.value),
                  })
                }
                placeholder="Rejoin fraction (0–1)"
              />
              <Input
                aria-label="Estimated route speed override"
                type="number"
                min="1"
                max="1000"
                step="1"
                value={valueOrEmpty(splice.speed_knots)}
                onChange={(event) =>
                  update({ speed_knots: toOptionalNumber(event.target.value) })
                }
                placeholder="Speed knots"
              />
            </div>
          </details>
        </>
      )}

      {splice && estimate && (
        <div
          className="rounded border border-border bg-card p-3 text-sm"
          role={estimate.available ? 'status' : 'alert'}
        >
          <p className="font-semibold">
            {estimate.available
              ? 'Estimated route active'
              : 'Planned route retained'}
          </p>
          {!estimate.available ? (
            <p className="mt-1 text-muted-foreground">
              No feasible estimate (
              {estimate.unavailable_reason || 'unavailable'}). The planned route
              and timeline remain in use.
            </p>
          ) : (
            <>
              <p className="mt-1">
                Basis: derived estimate; confidence:{' '}
                {estimate.confidence || 'unknown'}.
              </p>
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-muted-foreground sm:grid-cols-3">
                <div>
                  <dt>Distance delta</dt>
                  <dd>
                    {typeof estimate.derived_distance_nm === 'number' &&
                    typeof estimate.planned_distance_nm === 'number'
                      ? `${(estimate.derived_distance_nm - estimate.planned_distance_nm).toFixed(1)} NM`
                      : 'Unavailable'}
                  </dd>
                </div>
                <div>
                  <dt>Timeline delta</dt>
                  <dd>{formatDuration(estimate.delta_seconds)}</dd>
                </div>
                <div>
                  <dt>Speed</dt>
                  <dd>
                    {estimate.speed_knots
                      ? `${estimate.speed_knots.toFixed(0)} KTAS (${formatSpeedSource(estimate.speed_source)})`
                      : 'Unavailable'}
                  </dd>
                </div>
                <div>
                  <dt>Leave progress</dt>
                  <dd>
                    {estimate.leave_anchor
                      ? `${estimate.leave_anchor.progress_nm.toFixed(1)} NM`
                      : 'Unavailable'}
                  </dd>
                </div>
                <div>
                  <dt>Rejoin progress</dt>
                  <dd>
                    {estimate.rejoin_anchor
                      ? `${estimate.rejoin_anchor.progress_nm.toFixed(1)} NM`
                      : 'Unavailable'}
                  </dd>
                </div>
              </dl>
              {estimate.warnings?.map((warning) => (
                <p key={warning} className="mt-2 text-muted-foreground">
                  Warning: {warning}
                </p>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  );
}
