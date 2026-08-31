export const LIFECYCLE_LAYER_PANES: Readonly<Record<string, string>> = {
  'Weather Radar': 'weather-radar',
  'Planned Route — western segment': 'planned-route-west',
  'Planned Route — eastern segment': 'planned-route-east',
  'Active X-band Link — normal': 'active-x-band-normal',
  'Active X-band Link — warning': 'active-x-band-warning',
  'Position History — western segments': 'position-history-west',
  'Position History — eastern segments': 'position-history-east',
  'Flight route/POI markers': 'flight-route-markers',
  Satellites: 'satellites',
  'Mission events': 'mission-events',
  'Ground entry point': 'ground-entry-point-layer',
  'Current position': 'current-position-layer',
};

export const LIFECYCLE_OWNERSHIP_SELECTOR =
  'svg,path,img,.leaflet-layer,.leaflet-tile-container';
