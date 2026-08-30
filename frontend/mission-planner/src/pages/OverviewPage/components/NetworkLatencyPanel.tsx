import { type CSSProperties, type ReactNode } from 'react';

import { classifyLatency, formatLatencyMs } from '../formatters';
import { buildLatencyPanelData } from './metric-panel-data';
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
    key: 'current',
    label: 'Current',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
  {
    key: 'min',
    label: 'Min (5m)',
    color: '#177a55',
    unit: 'ms',
    display: 'signed',
  },
  {
    key: 'avg',
    label: 'Avg (5m)',
    color: '#a96900',
    unit: 'ms',
    display: 'signed',
  },
  {
    key: 'max',
    label: 'Max (5m)',
    color: '#b42318',
    unit: 'ms',
    display: 'signed',
  },
]);

export function NetworkLatencyPanel(props: HistoryMetricPanelProps): ReactNode {
  return (
    <OverviewPanelState
      title="Network Latency"
      slot={props.slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(history) => {
        const data = buildLatencyPanelData(history, props.now);
        const threshold = classifyLatency(data.summary.current);
        return (
          <div className="space-y-4">
            <MetricSummaryView
              currentLabel={`Current ${formatLatencyMs(data.summary.current)}`}
              status={threshold.label}
              tone={threshold.state === 'ok' ? 'normal' : threshold.state}
              presentation={props.presentation}
              items={[
                {
                  label: 'Current',
                  value: formatLatencyMs(data.summary.current),
                },
                { label: 'Min', value: formatLatencyMs(data.summary.min) },
                { label: 'Mean', value: formatLatencyMs(data.summary.mean) },
                { label: 'Max', value: formatLatencyMs(data.summary.max) },
              ]}
            />
            <div style={chartHeight(props.presentation)}>
              <TimeSeriesChart
                accessibleName="Network Latency chart"
                rows={data.chartRows}
                series={SERIES}
                yRange="auto"
                zeroBaseline
                emptyText="No latency history available."
              />
            </div>
            <MetricHistoryDisclosure
              rows={data.tableRows}
              series={SERIES}
              caption="Network latency history"
            />
          </div>
        );
      }}
    </OverviewPanelState>
  );
}

function chartHeight(
  presentation: HistoryMetricPanelProps['presentation']
): CSSProperties {
  return {
    '--time-series-chart-height':
      presentation === 'compact' ? '180px' : '240px',
  } as CSSProperties;
}
