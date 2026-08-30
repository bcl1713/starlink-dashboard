import 'uplot/dist/uPlot.min.css';

import { type ReactNode } from 'react';

import { useUPlotChart } from './use-uplot-chart';
import type { TimeSeriesChartProps } from './metric-panel-types';

export function TimeSeriesChart(props: TimeSeriesChartProps): ReactNode {
  const hostRef = useUPlotChart(props);
  return (
    <div className="space-y-2">
      <div
        ref={hostRef}
        className="min-h-[var(--time-series-chart-height,240px)] w-full"
        data-testid="time-series-chart-host"
      />
      {props.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{props.emptyText}</p>
      ) : null}
    </div>
  );
}
