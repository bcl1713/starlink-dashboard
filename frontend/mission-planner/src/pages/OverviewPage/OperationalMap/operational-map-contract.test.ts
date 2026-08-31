import { describe, expect, it } from 'vitest';

import {
  ARCGIS_WORLD_IMAGERY_ATTRIBUTION,
  ARCGIS_WORLD_IMAGERY_URL,
  OPERATIONAL_LAYERS,
  createDefaultLayerVisibility,
} from './operational-map-contract';

describe('operational map layer contract', () => {
  it('publishes the exact ordered operational inventory', () => {
    expect(OPERATIONAL_LAYERS.map((layer) => layer.id)).toEqual([
      'weather-radar',
      'planned-route-west',
      'planned-route-east',
      'active-x-band-normal',
      'active-x-band-warning',
      'position-history-west',
      'position-history-east',
      'flight-route-markers',
      'satellites',
      'mission-events',
      'ground-entry-point-layer',
      'current-position-layer',
    ]);
    expect(OPERATIONAL_LAYERS.map((layer) => layer.label)).toEqual([
      'Weather Radar',
      'Planned Route — western segment',
      'Planned Route — eastern segment',
      'Active X-band Link — normal',
      'Active X-band Link — warning',
      'Position History — western segments',
      'Position History — eastern segments',
      'Flight route/POI markers',
      'Satellites',
      'Mission events',
      'Ground entry point',
      'Current position',
    ]);
    expect(OPERATIONAL_LAYERS.map((layer) => layer.pane)).toEqual([
      200, 300, 310, 320, 330, 340, 350, 400, 410, 420, 430, 440,
    ]);
  });

  it('keeps basemap and layer style constants contract-visible', () => {
    expect(ARCGIS_WORLD_IMAGERY_URL).toBe(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    );
    expect(ARCGIS_WORLD_IMAGERY_ATTRIBUTION).toBe('Tiles © Esri');
    expect(OPERATIONAL_LAYERS[0]).toMatchObject({
      id: 'weather-radar',
      opacity: 0.7,
      minZoom: 0,
      maxZoom: 7,
      attribution: 'Weather radar © Rain Viewer / MeteoLab Inc.',
    });
    expect(
      OPERATIONAL_LAYERS.slice(1).map((layer) =>
        'styleToken' in layer ? layer.styleToken : null
      )
    ).toEqual([
      'dark-orange',
      'dark-orange',
      'green',
      'yellow',
      'blue',
      'blue',
      'dark-orange',
      'purple',
      'yellow',
      'blue',
      'green',
    ]);
  });

  it('creates default visibility with radar controlled by the caller', () => {
    expect(createDefaultLayerVisibility()).toMatchObject({
      'weather-radar': true,
      'current-position-layer': true,
    });
    expect(createDefaultLayerVisibility(false)['weather-radar']).toBe(false);
    expect(Object.values(createDefaultLayerVisibility(true))).toEqual(
      Array.from({ length: 12 }, () => true)
    );
  });
});
