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
  const active = status.pop_advisories?.find(({ kind }) => kind === 'window');
  if (!active) return null;
  return (
    <section
      role="status"
      className="overview-starshield-advisory"
      aria-label="Starshield advisory"
    >
      <strong>Starshield transition window</strong>
      <span>Brief interruption possible</span>
    </section>
  );
}
