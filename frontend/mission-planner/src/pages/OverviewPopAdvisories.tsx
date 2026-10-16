import type { StatusResponse } from '@/services/status';
import { PopForecastPanel } from '@/components/timeline/PopForecastPanel';
import { projectPopAdvisories } from './pop-advisory-projection';
import { isStatusStale } from './status-freshness';

export function OverviewPopAdvisories({
  status,
  nowMs,
  realNowMs,
  refreshFailed,
}: {
  status?: StatusResponse;
  nowMs: number;
  realNowMs: number;
  refreshFailed: boolean;
}) {
  if (status?.pop_forecast?.status === 'disabled') return null;
  const view = projectPopAdvisories(status);
  const stale =
    refreshFailed || !status || isStatusStale(status.timestamp, realNowMs);
  return (
    <section
      aria-label="Starshield PoP advisories"
      className="pointer-events-auto min-w-0 max-w-sm rounded border border-border bg-card/95 p-3 text-sm space-y-2"
    >
      {stale && (
        <p role="status">PoP status last known · refresh unavailable.</p>
      )}
      <p>{view.observation}</p>
      <p>Remaining mission: {view.continuity}</p>
      {view.advisories.length > 0 && (
        <div role="status" className="space-y-2">
          {view.advisories.map((message, index) => (
            <p key={index}>{message}</p>
          ))}
        </div>
      )}
      <details
        open={
          status?.pop_forecast?.status === 'ready' &&
          status.pop_forecast.transitions.length > 0
        }
      >
        <summary className="min-h-11 cursor-pointer">
          PoP forecast · {view.summary}
        </summary>
        <PopForecastPanel
          forecast={status?.pop_forecast}
          continuity={status?.call_continuity}
          continuityBasis="Remaining mission"
          nowMs={nowMs}
        />
      </details>
    </section>
  );
}
