import type { ReactNode } from 'react';

import { useOverviewLayoutMode } from './overview-layout';
export type { OverviewLayoutMode } from './overview-layout';
export type {
  OverviewFullscreenController,
  OverviewFullscreenMode,
} from './overview-fullscreen';

export interface OverviewGridProps {
  readonly map: ReactNode;
  readonly groundEntryPoint: ReactNode;
  readonly obstruction: ReactNode;
  readonly packetLoss: ReactNode;
  readonly poiQuickReference: ReactNode;
  readonly latency: ReactNode;
  readonly throughput: ReactNode;
}

export function OverviewGrid(props: OverviewGridProps) {
  const mode = useOverviewLayoutMode();

  return (
    <div
      className={`overview-primary-grid overview-primary-grid--${mode}`}
      data-layout-mode={mode}
      data-testid="overview-grid"
    >
      <section
        className="overview-map-panel"
        aria-label="Current Position"
        aria-labelledby="current-position-heading"
      >
        <h2 id="current-position-heading" className="sr-only">
          Current Position
        </h2>
        <div className="overview-map-region">{props.map}</div>
      </section>
      <section
        className="overview-summary-region"
        aria-label="Operational summaries"
        aria-labelledby="operational-summaries-heading"
      >
        <h2 id="operational-summaries-heading" className="sr-only">
          Operational summaries
        </h2>
        {props.groundEntryPoint}
        {props.obstruction}
        {props.packetLoss}
      </section>
      <section
        className="overview-right-rail"
        aria-label="Operations right rail"
      >
        <section className="overview-poi-region">
          {props.poiQuickReference}
        </section>
        <section className="overview-latency-region">{props.latency}</section>
        <section className="overview-throughput-region">
          {props.throughput}
        </section>
      </section>
    </div>
  );
}
