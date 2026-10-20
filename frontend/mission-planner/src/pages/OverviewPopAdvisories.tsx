import type { StatusResponse } from '@/services/status';
import { isStatusStale } from './status-freshness';
import './OverviewPopAdvisories.css';

/** Customer-facing 10-foot cue; planning and diagnostic details stay off the map. */
export function OverviewPopAdvisories({
  status,
  realNowMs,
  refreshFailed,
}: {
  status?: StatusResponse;
  realNowMs: number;
  refreshFailed: boolean;
}) {
  if (
    !status ||
    refreshFailed ||
    isStatusStale(status.timestamp, realNowMs) ||
    status.pop_forecast?.status === 'disabled'
  )
    return null;
  const active = status.pop_advisories?.find(
    ({ kind }) => kind === 'window' || kind === 'overdue' || kind === 'mismatch'
  );
  if (!active) return null;
  return (
    <section
      role="status"
      className="overview-starshield-advisory"
      aria-label="Starshield advisory"
    >
      <strong>
        {active.kind === 'window'
          ? 'Starshield transition window'
          : 'Starshield transition possible'}
      </strong>
      <span>Brief interruption possible</span>
    </section>
  );
}
