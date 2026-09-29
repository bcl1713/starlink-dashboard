import type { OverviewHistoryBundle } from '../services/overview-history';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import { OverviewMetricHistoryPanel } from './OverviewMetricHistoryPanel';

interface Props {
  history: OverviewHistoryBundle | undefined;
  error: boolean;
  selectedWindowSeconds: number | undefined;
  nowMs: number;
}

/** All five panels consume the parent's single history query, never their own poll. */
export function OverviewMetricHistoryPanels({
  history,
  error,
  selectedWindowSeconds,
  nowMs,
}: Props) {
  return (
    <section
      className="overview-metric-history-panels"
      aria-label="Overview metric history"
    >
      {OVERVIEW_METRIC_GRAPHS.map((descriptor) => (
        <div data-metric-panel={descriptor.id} key={descriptor.id}>
          <OverviewMetricHistoryPanel
            descriptor={descriptor}
            history={history}
            error={error}
            selectedWindowSeconds={
              selectedWindowSeconds ?? history?.window_seconds ?? 1800
            }
            nowMs={nowMs}
          />
        </div>
      ))}
    </section>
  );
}
