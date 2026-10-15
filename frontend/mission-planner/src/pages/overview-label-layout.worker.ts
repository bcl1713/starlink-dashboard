import {
  layoutOverviewLabels,
  type LabelBounds,
  type OverviewLabelLayoutResult,
  type OverviewLabelOffset,
  type ProjectedOverviewLabel,
  type OverviewLabelGeometry,
} from './overview-label-layout';

export interface LabelLayoutRequest {
  revision: number;
  labels: ProjectedOverviewLabel[];
  viewport: { width: number; height: number };
  reserved: LabelBounds[];
  previous: Record<string, OverviewLabelOffset>;
  geometry?: OverviewLabelGeometry;
}
export interface LabelLayoutResponse {
  revision: number;
  layout: OverviewLabelLayoutResult;
}

self.onmessage = ({ data }: MessageEvent<LabelLayoutRequest>) => {
  const response: LabelLayoutResponse = {
    revision: data.revision,
    layout: layoutOverviewLabels(
      data.labels,
      data.viewport,
      data.reserved,
      data.previous,
      data.geometry
    ),
  };
  self.postMessage(response);
};
