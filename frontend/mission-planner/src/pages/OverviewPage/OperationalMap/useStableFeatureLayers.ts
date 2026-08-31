import { useEffect, useRef } from 'react';
import L, {
  type Layer,
  type LayerGroup,
  type Map as LeafletMap,
} from 'leaflet';

import { VECTOR_LAYER_IDS } from './operational-map-contract';
import type {
  OperationalFeature,
  OperationalLayerVisibility,
  VectorLayerId,
} from './operational-map-types';

const colors: Record<string, string> = {
  'planned-route-west': '#f97316',
  'planned-route-east': '#f97316',
  'active-x-band-normal': '#22c55e',
  'active-x-band-warning': '#eab308',
  'position-history-west': '#3b82f6',
  'position-history-east': '#3b82f6',
};

export function useStableFeatureLayers({
  features,
  map,
  onSelect,
  visibility,
}: {
  readonly features: readonly OperationalFeature[];
  readonly map: LeafletMap | null;
  readonly onSelect: (id: string) => void;
  readonly visibility: OperationalLayerVisibility;
}) {
  const groups = useRef<Map<VectorLayerId, LayerGroup> | null>(null);
  const registry = useRef<Map<string, Layer>>(new Map());

  if (groups.current === null) {
    groups.current = new Map(
      VECTOR_LAYER_IDS.map((id) => [id, L.layerGroup()])
    );
  }

  useEffect(() => {
    if (!map || !groups.current) return;
    for (const [id, group] of groups.current) {
      if (visibility[id] && !map.hasLayer(group)) group.addTo(map);
      if (!visibility[id] && map.hasLayer(group)) group.removeFrom(map);
    }
  }, [map, visibility]);

  useEffect(() => {
    if (!map || !groups.current) return;
    const next = new Set(features.map((feature) => feature.id));
    for (const feature of features) {
      const group = groups.current.get(feature.layerId);
      if (!group) continue;
      const layer = registry.current.get(feature.id);
      if (layer) updateLayer(layer, feature);
      else {
        const created = createLayer(feature, onSelect);
        registry.current.set(feature.id, created);
        group.addLayer(created);
      }
    }
    for (const [id, layer] of registry.current) {
      if (!next.has(id)) {
        for (const group of groups.current.values()) group.removeLayer(layer);
        registry.current.delete(id);
      }
    }
  }, [features, map, onSelect]);

  useEffect(
    () => () => {
      for (const layer of registry.current.values()) layer.remove();
      registry.current.clear();
      groups.current?.forEach((group) => group.remove());
    },
    []
  );
}

function createLayer(
  feature: OperationalFeature,
  onSelect: (id: string) => void
): Layer {
  const layer =
    feature.geometry.type === 'point'
      ? L.marker([feature.geometry.latitude, feature.geometry.longitude], {
          icon: iconFor(feature),
        })
      : L.polyline(
          feature.geometry.points.map((point) => [
            point.latitude,
            point.longitude,
          ]),
          {
            color: colors[feature.layerId] ?? '#f8fafc',
            weight: 3,
            opacity: 0.9,
          }
        );
  layer.on('click', () => onSelect(feature.id));
  return layer;
}

function updateLayer(layer: Layer, feature: OperationalFeature): void {
  if (layer instanceof L.Marker && feature.geometry.type === 'point') {
    layer.setLatLng([feature.geometry.latitude, feature.geometry.longitude]);
  }
  if (layer instanceof L.Polyline && feature.geometry.type === 'line') {
    layer.setLatLngs(
      feature.geometry.points.map((point) => [point.latitude, point.longitude])
    );
  }
  const element = layer instanceof L.Marker ? layer.getElement() : null;
  if (element && feature.id === 'current-position') {
    element.style.setProperty(
      '--aircraft-heading',
      `${feature.details[0]?.value ?? 0}deg`
    );
  }
}

function iconFor(feature: OperationalFeature) {
  const url =
    feature.id === 'current-position'
      ? '/assets/overview-map/aircraft.svg'
      : feature.kind === 'satellite'
        ? '/assets/overview-map/satellite.svg'
        : feature.kind === 'mission-event'
          ? '/assets/overview-map/event-circle.svg'
          : feature.kind === 'ground-entry-point'
            ? '/assets/overview-map/gep-circle.svg'
            : '/assets/overview-map/poi-x.svg';
  return L.icon({
    iconUrl: url,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    className:
      feature.id === 'current-position' ? 'operational-map__aircraft' : '',
  });
}
