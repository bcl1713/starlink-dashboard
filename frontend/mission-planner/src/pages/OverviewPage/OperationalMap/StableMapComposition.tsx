import { useEffect } from 'react';
import L, { type Map as LeafletMap } from 'leaflet';
import { useMap } from 'react-leaflet';

import {
  ARCGIS_WORLD_IMAGERY_ATTRIBUTION,
  ARCGIS_WORLD_IMAGERY_URL,
  BASEMAP_PANE,
  OPERATIONAL_LAYERS,
  createDefaultLayerVisibility,
} from './operational-map-contract';
import type {
  BasemapStatus,
  OperationalFeature,
  OperationalMapProps,
} from './operational-map-types';
import { RadarGridLayer } from './RadarGridLayer';
import { useStableFeatureLayers } from './useStableFeatureLayers';

export function StableMapComposition({
  features,
  mapRef,
  mobileActive,
  mobileLocked,
  onMapReady,
  onBasemapStatusChange,
  onSelect,
  radarEnabled,
  radarRefreshToken,
  reportRadarResult,
  visibility,
}: {
  readonly features: readonly OperationalFeature[];
  readonly mapRef: React.MutableRefObject<LeafletMap | null>;
  readonly mobileActive: boolean;
  readonly mobileLocked: boolean;
  readonly onMapReady: ((map: LeafletMap) => void) | undefined;
  readonly onBasemapStatusChange: (status: BasemapStatus) => void;
  readonly onSelect: (id: string) => void;
  readonly radarEnabled: boolean;
  readonly radarRefreshToken: number;
  readonly reportRadarResult: OperationalMapProps['reportRadarResult'];
  readonly visibility: OperationalMapProps['initialLayerVisibility'];
}) {
  const map = useMap();
  useStableMapBase(map, mapRef, onMapReady, onBasemapStatusChange);
  useStableFeatureLayers({
    features,
    map,
    onSelect,
    visibility: visibility ?? createDefaultLayerVisibility(),
  });
  useMapInteraction(map, mobileLocked, mobileActive);
  return (
    <RadarGridLayer
      enabled={radarEnabled}
      radarRefreshToken={radarRefreshToken}
      reportRadarResult={reportRadarResult}
    />
  );
}

function useStableMapBase(
  map: LeafletMap,
  mapRef: React.MutableRefObject<LeafletMap | null>,
  onMapReady: ((map: LeafletMap) => void) | undefined,
  onBasemapStatusChange: (status: BasemapStatus) => void
) {
  useEffect(() => {
    if (mapRef.current) return;
    mapRef.current = map;
    map.createPane('operational-basemap').style.zIndex = String(BASEMAP_PANE);
    for (const layer of OPERATIONAL_LAYERS) {
      map.createPane(layer.id).style.zIndex = String(layer.pane);
    }
    const basemap = L.tileLayer(ARCGIS_WORLD_IMAGERY_URL, {
      attribution: ARCGIS_WORLD_IMAGERY_ATTRIBUTION,
      pane: 'operational-basemap',
    });
    const markReady = () =>
      onBasemapStatusChange({
        phase: 'ready',
        message: 'Basemap tiles loaded.',
      });
    const markFailed = () =>
      onBasemapStatusChange({
        phase: 'unavailable',
        message: 'Unable to load basemap tiles.',
      });
    basemap.on('tileload', markReady);
    basemap.on('tileerror', markFailed);
    basemap.addTo(map);
    L.control.scale().addTo(map);
    onMapReady?.(map);
    return () => {
      basemap.off('tileload', markReady);
      basemap.off('tileerror', markFailed);
      basemap.remove();
    };
  }, [map, mapRef, onBasemapStatusChange, onMapReady]);
}

function useMapInteraction(
  map: LeafletMap,
  mobileLocked: boolean,
  mobileActive: boolean
) {
  useEffect(() => {
    const enabled = !mobileLocked || mobileActive;
    const handlers = [
      map.dragging,
      map.scrollWheelZoom,
      map.touchZoom,
      map.doubleClickZoom,
      map.boxZoom,
      map.keyboard,
    ];
    for (const handler of handlers) {
      if (enabled) handler.enable();
      else handler.disable();
    }
    map.getContainer().tabIndex = enabled ? 0 : -1;
  }, [map, mobileActive, mobileLocked]);
}
