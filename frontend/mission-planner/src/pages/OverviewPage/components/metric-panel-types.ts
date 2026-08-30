import type { ReactNode } from 'react';

import type { OverviewSourceSlot } from '../overview-data-types';
import type { MonitoringHistory } from '../../../types/monitoring';

export type RetryOverviewPanel = () => void | Promise<void>;
export type TimeSeriesUnit = 'ms' | 'Mbps' | 'percent';
export type TimeSeriesDisplayMode = 'signed' | 'magnitude';
export type MetricPanelPresentation = 'standard' | 'compact';

export interface MetricSummary {
  readonly current: number | null;
  readonly min: number | null;
  readonly mean: number | null;
  readonly max: number | null;
}

export interface TimeSeriesDefinition {
  readonly key: string;
  readonly label: string;
  readonly color: string;
  readonly unit: TimeSeriesUnit;
  readonly display: TimeSeriesDisplayMode;
}

export interface TimeSeriesRow {
  readonly timestamp: string;
  readonly epochSeconds: number;
  readonly values: readonly (number | null)[];
}

export interface TimeSeriesChartProps {
  readonly accessibleName: string;
  readonly rows: readonly TimeSeriesRow[];
  readonly series: readonly TimeSeriesDefinition[];
  readonly yRange: readonly [number, number] | 'auto';
  readonly zeroBaseline: boolean;
  readonly emptyText: string;
  readonly className?: string;
}

export interface HistoryMetricPanelProps {
  readonly slot: OverviewSourceSlot<MonitoringHistory>;
  readonly now: string;
  readonly retryPending: boolean;
  readonly onRetry?: RetryOverviewPanel;
  readonly presentation?: MetricPanelPresentation;
  readonly headingAs?: 'h2' | 'h3';
}

export interface OverviewPanelStateProps<T> {
  readonly title: string;
  readonly slot: OverviewSourceSlot<T>;
  readonly retryPending: boolean;
  readonly onRetry?: RetryOverviewPanel;
  readonly headingAs?: 'h2' | 'h3';
  readonly children: (data: T) => ReactNode;
}

export interface LatencyPanelData {
  readonly chartRows: readonly TimeSeriesRow[];
  readonly tableRows: readonly TimeSeriesRow[];
  readonly summary: MetricSummary;
}

export interface ThroughputPanelData {
  readonly chartRows: readonly TimeSeriesRow[];
  readonly tableRows: readonly TimeSeriesRow[];
  readonly download: MetricSummary;
  readonly upload: MetricSummary;
}

export interface PacketLossPanelData {
  readonly chartRows: readonly TimeSeriesRow[];
  readonly tableRows: readonly TimeSeriesRow[];
  readonly summary: Readonly<Pick<MetricSummary, 'current' | 'mean' | 'max'>>;
}
