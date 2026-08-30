import { type ReactNode } from 'react';

import { classifyObstruction, formatPercent } from '../formatters';
import type { OverviewStatus } from '../../../types/monitoring';
import { MetricSummaryView } from './MetricSummaryView';
import { OverviewPanelState } from './OverviewPanelState';
import type { RetryOverviewPanel } from './metric-panel-types';
import type { OverviewSourceSlot } from '../overview-data-types';

export interface ObstructionGaugeProps {
  readonly slot: OverviewSourceSlot<OverviewStatus>;
  readonly retryPending: boolean;
  readonly onRetry?: RetryOverviewPanel;
  readonly headingAs?: 'h2' | 'h3';
}

export function ObstructionGauge(props: ObstructionGaugeProps): ReactNode {
  return (
    <OverviewPanelState
      title="Obstruction %"
      slot={props.slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(status) => {
        const value = status.obstruction.obstruction_percent;
        const classified = classifyObstruction(value);
        const available = classified.displayValue !== null;
        return (
          <div className="space-y-4">
            <div
              role="meter"
              aria-label="Obstruction percentage"
              aria-valuemin={0}
              aria-valuemax={20}
              aria-valuenow={available ? classified.displayValue : undefined}
              aria-valuetext={
                available
                  ? `${formatPercent(value)} - ${classified.label}${classified.outOfDisplayRange ? ', above 20% display range' : ''}`
                  : 'Unavailable'
              }
              className="h-4 rounded bg-muted"
            >
              <div
                className="h-full rounded bg-[#1769aa]"
                style={{
                  width: `${available ? (classified.displayValue / 20) * 100 : 0}%`,
                }}
              />
            </div>
            <MetricSummaryView
              currentLabel={`Current ${formatPercent(value)}`}
              status={`${classified.label}${classified.outOfDisplayRange ? ', above display range' : ''}`}
              tone={classified.state === 'ok' ? 'normal' : classified.state}
              items={[{ label: 'Display range', value: '0-20%' }]}
            />
          </div>
        );
      }}
    </OverviewPanelState>
  );
}
