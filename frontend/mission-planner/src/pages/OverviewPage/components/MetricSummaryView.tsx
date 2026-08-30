import { type ReactNode } from 'react';

import { cn } from '../../../lib/utils';
import type { MetricPanelPresentation } from './metric-panel-types';

export type ThresholdTone = 'normal' | 'warning' | 'critical' | 'unavailable';

interface SummaryItem {
  readonly label: string;
  readonly value: string;
  readonly compactPriority?: 'current' | 'mean';
}

interface MetricSummaryViewProps {
  readonly currentLabel: string;
  readonly status: string;
  readonly tone: ThresholdTone;
  readonly items: readonly SummaryItem[];
  readonly presentation?: MetricPanelPresentation;
}

export function MetricSummaryView(props: MetricSummaryViewProps): ReactNode {
  const visible =
    props.presentation === 'compact' ? compactItems(props.items) : props.items;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">
          {props.currentLabel}
        </span>
        <span className={cn('text-sm font-semibold', toneClass(props.tone))}>
          {props.status}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {visible.map((item) => (
          <div key={item.label} className="min-w-0">
            <dt className="text-xs text-muted-foreground">{item.label}</dt>
            <dd className="truncate text-sm font-semibold">{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function compactItems(items: readonly SummaryItem[]): readonly SummaryItem[] {
  const prioritized = items.filter(
    (item) => item.compactPriority !== undefined
  );
  return prioritized.length > 0 ? prioritized : items.slice(0, 2);
}

function toneClass(tone: ThresholdTone): string {
  if (tone === 'critical') return 'text-[#b42318]';
  if (tone === 'warning') return 'text-[#8a5700]';
  if (tone === 'normal') return 'text-[#177a55]';
  return 'text-muted-foreground';
}
