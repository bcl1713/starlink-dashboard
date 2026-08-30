import 'uplot/dist/uPlot.min.css';

import { type ReactNode } from 'react';

import { cn } from '../../../lib/utils';
import { useUPlotChart } from './use-uplot-chart';
import type { TimeSeriesChartProps } from './metric-panel-types';

export function TimeSeriesChart(props: TimeSeriesChartProps): ReactNode {
  const hostRef = useUPlotChart(props);
  return (
    <div className={cn('space-y-2', props.className)}>
      <div
        ref={hostRef}
        className="min-h-[240px] w-full"
        data-testid="time-series-chart-host"
      />
      {props.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{props.emptyText}</p>
      ) : null}
    </div>
  );
}
