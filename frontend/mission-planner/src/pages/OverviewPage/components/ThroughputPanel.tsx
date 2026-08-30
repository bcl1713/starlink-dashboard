import { type ReactNode } from 'react';

import { formatThroughputMbps } from '../formatters';
import { buildThroughputPanelData } from './metric-panel-data';
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
    key: 'download',
    label: 'Download',
    color: '#1769aa',
    unit: 'Mbps',
    display: 'magnitude',
  },
  {
    key: 'upload',
    label: 'Upload',
    color: '#177a55',
    unit: 'Mbps',
    display: 'magnitude',
  },
]);

export function ThroughputPanel(props: HistoryMetricPanelProps): ReactNode {
  return (
    <OverviewPanelState
      title="Download/Upload Throughput"
      slot={props.slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(history) => {
        const data = buildThroughputPanelData(history, props.now);
        return (
          <div className="space-y-4">
            <MetricSummaryView
              currentLabel={`Download ${formatThroughputMbps(data.download.current)} / Upload ${formatThroughputMbps(data.upload.current)}`}
              status="Magnitude display"
              tone="normal"
              presentation={props.presentation}
              items={[
                {
                  label: 'Download current',
                  value: formatThroughputMbps(data.download.current),
                },
                {
                  label: 'Upload current',
                  value: formatThroughputMbps(data.upload.current),
                },
                {
                  label: 'Download mean',
                  value: formatThroughputMbps(data.download.mean),
                },
                {
                  label: 'Upload mean',
                  value: formatThroughputMbps(data.upload.mean),
                },
              ]}
            />
            <TimeSeriesChart
              accessibleName="Download/Upload Throughput chart"
              rows={data.chartRows}
              series={SERIES}
              yRange="auto"
              zeroBaseline
              emptyText="No throughput history available."
              className={
                props.presentation === 'compact'
                  ? '[&_[data-testid=time-series-chart-host]]:min-h-[180px]'
                  : '[&_[data-testid=time-series-chart-host]]:min-h-[240px]'
              }
            />
            <MetricHistoryDisclosure
              rows={data.tableRows}
              series={SERIES}
              caption="Throughput history"
            />
          </div>
        );
      }}
    </OverviewPanelState>
  );
}
