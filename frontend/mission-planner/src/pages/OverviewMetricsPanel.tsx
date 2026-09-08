import type { StatusResponse } from '@/services/status';

interface OverviewMetricsPanelProps {
  status?: StatusResponse;
  telemetryState: string;
}

interface MetricProps {
  label: string;
  value?: number;
  unit: string;
}

function formatTimestamp(timestamp?: string) {
  if (!timestamp) {
    return 'Unavailable';
  }

  const observedAt = new Date(timestamp);

  if (!Number.isFinite(observedAt.getTime())) {
    return 'Unavailable';
  }

  return `${observedAt.toISOString().slice(0, 19).replace('T', ' ')} UTC`;
}

function formatMetric({ value, unit }: MetricProps) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'Unavailable';
  }

  const formattedValue = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 1,
  }).format(value);

  return unit === '%' ? `${formattedValue}%` : `${formattedValue} ${unit}`;
}

export function OverviewMetricsPanel({
  status,
  telemetryState,
}: OverviewMetricsPanelProps) {
  const metrics: MetricProps[] = [
    {
      label: 'Latency',
      value: status?.network?.latency_ms,
      unit: 'ms',
    },
    {
      label: 'Downlink',
      value: status?.network?.throughput_down_mbps,
      unit: 'Mbps',
    },
    {
      label: 'Uplink',
      value: status?.network?.throughput_up_mbps,
      unit: 'Mbps',
    },
    {
      label: 'Packet loss',
      value: status?.network?.packet_loss_percent,
      unit: '%',
    },
    {
      label: 'Signal quality',
      value: status?.environmental?.signal_quality_percent,
      unit: '%',
    },
  ];

  return (
    <aside className="overview-metrics" aria-label="Current network metrics">
      <p className="overview-metrics__title">Current network metrics</p>
      <p className="overview-metrics__state">{telemetryState}</p>
      <p className="overview-metrics__updated">
        Updated {formatTimestamp(status?.timestamp)}
      </p>
      <dl className="overview-metrics__grid">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <dt>{metric.label}</dt>
            <dd>{formatMetric(metric)}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
