import type {
  OperationalLayerId,
  OperationalLayerVisibility,
} from './operational-map-types';

export const ARCGIS_WORLD_IMAGERY_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
export const ARCGIS_WORLD_IMAGERY_ATTRIBUTION = 'Tiles © Esri';
export const RADAR_ATTRIBUTION = 'Weather radar © Rain Viewer / MeteoLab Inc.';

export type OperationalStyleToken =
  | 'dark-orange'
  | 'green'
  | 'yellow'
  | 'blue'
  | 'purple';

export interface OperationalLayerContract {
  readonly id: OperationalLayerId;
  readonly label: string;
  readonly pane: number;
  readonly defaultVisible: boolean;
  readonly styleToken?: OperationalStyleToken;
  readonly width?: number;
  readonly opacity: number;
  readonly size?: number;
  readonly textOffsetPx?: number;
  readonly minZoom?: number;
  readonly maxZoom?: number;
  readonly attribution?: string;
}

export const BASEMAP_PANE = 100;

export const OPERATIONAL_LAYERS = [
  {
    id: 'weather-radar',
    label: 'Weather Radar',
    pane: 200,
    defaultVisible: true,
    opacity: 0.7,
    minZoom: 0,
    maxZoom: 7,
    attribution: RADAR_ATTRIBUTION,
  },
  lineLayer(
    'planned-route-west',
    'Planned Route — western segment',
    300,
    'dark-orange',
    2,
    0.9
  ),
  lineLayer(
    'planned-route-east',
    'Planned Route — eastern segment',
    310,
    'dark-orange',
    2,
    1
  ),
  lineLayer(
    'active-x-band-normal',
    'Active X-band Link — normal',
    320,
    'green',
    4,
    0.9
  ),
  lineLayer(
    'active-x-band-warning',
    'Active X-band Link — warning',
    330,
    'yellow',
    4,
    0.9
  ),
  lineLayer(
    'position-history-west',
    'Position History — western segments',
    340,
    'blue',
    3,
    0.7
  ),
  lineLayer(
    'position-history-east',
    'Position History — eastern segments',
    350,
    'blue',
    3,
    0.7
  ),
  pointLayer(
    'flight-route-markers',
    'Flight route/POI markers',
    400,
    'dark-orange',
    12,
    25
  ),
  pointLayer('satellites', 'Satellites', 410, 'purple', 15, 25),
  pointLayer('mission-events', 'Mission events', 420, 'yellow', 15, 50),
  pointLayer(
    'ground-entry-point-layer',
    'Ground entry point',
    430,
    'blue',
    12,
    18
  ),
  pointLayer('current-position-layer', 'Current position', 440, 'green', 15, 0),
] as const satisfies readonly OperationalLayerContract[];

export const VECTOR_LAYER_IDS = OPERATIONAL_LAYERS.filter(
  (layer) => layer.id !== 'weather-radar'
).map((layer) => layer.id) as Exclude<OperationalLayerId, 'weather-radar'>[];

export function createDefaultLayerVisibility(
  radarEnabled = true
): OperationalLayerVisibility {
  return Object.fromEntries(
    OPERATIONAL_LAYERS.map((layer) => [
      layer.id,
      layer.id === 'weather-radar' ? radarEnabled : layer.defaultVisible,
    ])
  ) as OperationalLayerVisibility;
}

function lineLayer(
  id: OperationalLayerId,
  label: string,
  pane: number,
  styleToken: OperationalStyleToken,
  width: number,
  opacity: number
): OperationalLayerContract {
  return { id, label, pane, defaultVisible: true, styleToken, width, opacity };
}

function pointLayer(
  id: OperationalLayerId,
  label: string,
  pane: number,
  styleToken: OperationalStyleToken,
  size: number,
  textOffsetPx: number
): OperationalLayerContract {
  return {
    id,
    label,
    pane,
    defaultVisible: true,
    styleToken,
    size,
    textOffsetPx,
    opacity: 1,
  };
}
