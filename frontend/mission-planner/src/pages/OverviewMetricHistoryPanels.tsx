import { useState } from 'react';
import type { OverviewHistoryBundle } from '../services/overview-history';
import type { StatusResponse } from '../services/status';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import {
  networkStatusState,
  statusMetricReadout,
} from './overview-metric-readout';
import { OverviewMetricHistoryPanel } from './OverviewMetricHistoryPanel';
import { statusObservationAgeMs } from './status-freshness';

interface Props {
  history: OverviewHistoryBundle | undefined;
  error: boolean;
  status: StatusResponse | undefined;
  statusError: boolean;
  selectedWindowSeconds: number | undefined;
  nowMs: number;
}

/** All five panels consume the parent's shared queries, never their own poll. */
export function OverviewMetricHistoryPanels({
  history,
  error,
  status,
  statusError,
  selectedWindowSeconds,
  nowMs,
}: Props) {
  const [acceptedStatus, setAcceptedStatus] = useState<StatusResponse>();
  const timestamp = status ? Date.parse(status.timestamp) : NaN;
  const validTimestamp =
    status &&
    typeof status.timestamp === 'string' &&
    statusObservationAgeMs(status.timestamp, nowMs) !== null;
  if (
    status &&
    status !== acceptedStatus &&
    validTimestamp &&
    (!acceptedStatus || timestamp >= Date.parse(acceptedStatus.timestamp))
  ) {
    // Adjust this component's retained state before committing a render; an
    // effect would briefly paint the previous sample on an accepted refresh.
    setAcceptedStatus(status);
  }
  // Reject malformed/excessively future responses without certifying prior data.
  // Failed requests retain the accepted sample, explicitly projected as stale.
  const readoutStatus = status && !validTimestamp ? status : acceptedStatus;
  const readouts = OVERVIEW_METRIC_GRAPHS.map((descriptor) =>
    statusMetricReadout(readoutStatus, descriptor, nowMs, statusError)
  );
  const state = networkStatusState(readouts);
  const observedAge = readouts.find((readout) => readout !== null)?.ageMs;
  const windowSeconds =
    selectedWindowSeconds ?? history?.window_seconds ?? 1800;
  const display =
    windowSeconds % 60 === 0
      ? `${windowSeconds / 60} MIN`
      : `${windowSeconds} SEC`;
  return (
    <section
      className="overview-metric-history-panels"
      aria-label="Overview metric history"
    >
      <header
        className="overview-metric-history-panels__header"
        aria-label="Network history context"
      >
        <div className="overview-metric-history-panels__freshness">
          <p role="status">
            Network
            <span
              className={
                state === 'fresh' ? 'overview-visually-hidden' : undefined
              }
            >
              {' '}
              {state}
            </span>
          </p>
          {observedAge !== undefined && (
            <span className="overview-metric-history-panels__age">
              <span aria-hidden="true">- </span>
              {state === 'fresh' ? 'Updated' : 'Last observed'}{' '}
              {Math.floor(observedAge / 1000)}s ago
            </span>
          )}
        </div>
        <div className="overview-metric-history-panels__windows">
          <p>LAST {display}</p>
          <p className="overview-visually-hidden">
            Rolling statistics: 5 minutes
          </p>
        </div>
        {(statusError || error) && (
          <p className="overview-metric-history-panels__error">
            {statusError && <span>Status refresh unavailable</span>}
            {error && <span>History refresh unavailable</span>}
          </p>
        )}
        <ul
          className="overview-metric-history__legend overview-visually-hidden"
          aria-label="Graph traces"
        >
          <li>
            <span
              className="overview-metric-history__key--observed"
              aria-hidden="true"
            />
            Observed
          </li>
          <li>
            <span
              className="overview-metric-history__key--average"
              aria-hidden="true"
            />
            Average (5m)
          </li>
          <li>
            <span
              className="overview-metric-history__key--envelope"
              aria-hidden="true"
            />
            Low–high envelope (5m)
          </li>
        </ul>
      </header>
      {OVERVIEW_METRIC_GRAPHS.map((descriptor, index) => (
        <div data-metric-panel={descriptor.id} key={descriptor.id}>
          <OverviewMetricHistoryPanel
            descriptor={descriptor}
            history={history}
            error={error}
            selectedWindowSeconds={windowSeconds}
            nowMs={nowMs}
            readout={readouts[index]}
          />
        </div>
      ))}
    </section>
  );
}
