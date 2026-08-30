import { type CSSProperties, type ReactNode } from 'react';

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
                  label: 'Download mean',
                  value: formatThroughputMbps(data.download.mean),
                },
                {
                  label: 'Download min',
                  value: formatThroughputMbps(data.download.min),
                },
                {
                  label: 'Download max',
                  value: formatThroughputMbps(data.download.max),
                },
                {
                  label: 'Upload current',
                  value: formatThroughputMbps(data.upload.current),
                },
                {
                  label: 'Upload mean',
                  value: formatThroughputMbps(data.upload.mean),
                },
                {
                  label: 'Upload min',
                  value: formatThroughputMbps(data.upload.min),
                },
                {
                  label: 'Upload max',
                  value: formatThroughputMbps(data.upload.max),
                },
              ]}
            />
            <div style={chartHeight(props.presentation)}>
              <TimeSeriesChart
                accessibleName="Download/Upload Throughput chart"
                rows={data.chartRows}
                series={SERIES}
                yRange="auto"
                zeroBaseline
                emptyText="No throughput history available."
              />
            </div>
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

function chartHeight(
  presentation: HistoryMetricPanelProps['presentation']
): CSSProperties {
  return {
    '--time-series-chart-height':
      presentation === 'compact' ? '180px' : '240px',
  } as CSSProperties;
}
