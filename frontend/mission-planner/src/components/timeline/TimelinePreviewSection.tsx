import React, { useState } from 'react';
import type { Timeline } from '../../services/timeline';
import { TimelineTable } from './TimelineTable';

interface TimelinePreviewSectionProps {
  timeline: Timeline | null;
  isCalculating: boolean;
  isUnsaved?: boolean;
  error?: Error | null;
}

export const TimelinePreviewSection: React.FC<TimelinePreviewSectionProps> = ({
  timeline,
  isCalculating,
  isUnsaved = false,
  error = null,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <section
      className="overflow-hidden rounded-xl border border-border bg-card"
      aria-labelledby="timeline-preview-heading"
    >
      <div className="flex items-center justify-between gap-4 bg-muted/70 p-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-expanded={isExpanded}
            aria-controls="timeline-preview-content"
            aria-label={
              isExpanded
                ? 'Collapse timeline preview'
                : 'Expand timeline preview'
            }
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? '⌄' : '›'}
          </button>
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
              Operational timeline
            </p>
            <h3
              id="timeline-preview-heading"
              className="text-lg font-semibold text-foreground"
            >
              Timeline Preview
            </h3>
          </div>
          {isUnsaved && (
            <span className="status-critical rounded px-2 py-1 text-xs font-semibold">
              Unsaved
            </span>
          )}
          {isCalculating && (
            <span className="text-xs text-muted-foreground">Calculating…</span>
          )}
        </div>
        {timeline?.segments && (
          <span className="shrink-0 text-sm text-muted-foreground">
            {timeline.segments.length} segments
          </span>
        )}
      </div>

      {isExpanded && (
        <div id="timeline-preview-content" className="p-4">
          {error && (
            <div
              className="status-critical mb-4 rounded border border-destructive/30 p-3 text-sm"
              role="alert"
            >
              {error.message}
            </div>
          )}

          <TimelineTable timeline={timeline} isLoading={isCalculating} />

          {timeline?.statistics && (
            <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
              <TimelineMetric
                label="Total duration"
                value={timeline.statistics.total_duration_seconds}
              />
              <TimelineMetric
                label="Degraded time"
                value={timeline.statistics.degraded_seconds}
                tone="degraded"
              />
              <TimelineMetric
                label="Critical time"
                value={timeline.statistics.critical_seconds}
                tone="critical"
              />
              <TimelineMetric
                label="Nominal time"
                value={timeline.statistics.nominal_seconds}
                tone="nominal"
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
};

function TimelineMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: unknown;
  tone?: 'nominal' | 'degraded' | 'critical';
}) {
  return (
    <div>
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div
        className="text-lg font-semibold text-foreground"
        style={tone ? { color: `var(--status-${tone})` } : undefined}
      >
        {typeof value === 'number' ? `${Math.round(value / 60)}m` : '0m'}
      </div>
    </div>
  );
}
