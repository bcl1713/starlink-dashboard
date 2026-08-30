import { type ReactNode } from 'react';

import { classifyPacketLoss, formatPercent } from '../formatters';
import { buildPacketLossPanelData } from './metric-panel-data';
import { MetricHistoryDisclosure } from './MetricHistoryDisclosure';
import { MetricSummaryView } from './MetricSummaryView';
import { OverviewPanelState } from './OverviewPanelState';
import { TimeSeriesChart } from './TimeSeriesChart';
import type {
  HistoryMetricPanelProps,
  TimeSeriesDefinition,
} from './metric-panel-types';

const SERIES: readonly TimeSeriesDefinition[] = Object.freeze([
  {
    key: 'packetLoss',
    label: 'Packet loss',
    color: '#b42318',
    unit: 'percent',
    display: 'signed',
  },
]);

export function PacketLossPanel(props: HistoryMetricPanelProps): ReactNode {
  return (
    <OverviewPanelState
      title="Packet Loss"
      slot={props.slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(history) => {
        const data = buildPacketLossPanelData(history, props.now);
        const threshold = classifyPacketLoss(data.summary.current);
        return (
          <div className="space-y-4">
            <MetricSummaryView
              currentLabel={`Current ${formatPercent(data.summary.current)}`}
              status={threshold.label}
              tone={threshold.state === 'ok' ? 'normal' : threshold.state}
              presentation={props.presentation}
              items={[
                {
                  label: 'Current',
                  value: formatPercent(data.summary.current),
                },
                { label: 'Mean', value: formatPercent(data.summary.mean) },
                { label: 'Max', value: formatPercent(data.summary.max) },
              ]}
            />
            <TimeSeriesChart
              accessibleName="Packet Loss chart"
              rows={data.chartRows}
              series={SERIES}
              yRange={[0, 100]}
              zeroBaseline
              emptyText="No packet loss history available."
              className={
                props.presentation === 'compact'
                  ? '[&_[data-testid=time-series-chart-host]]:min-h-[180px]'
                  : '[&_[data-testid=time-series-chart-host]]:min-h-[240px]'
              }
            />
            <MetricHistoryDisclosure
              rows={data.tableRows}
              series={SERIES}
              caption="Packet loss history"
            />
          </div>
        );
      }}
    </OverviewPanelState>
  );
}
