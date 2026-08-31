import { useEffect, useRef } from 'react';
import L, {
  type Layer,
  type LayerGroup,
  type Map as LeafletMap,
} from 'leaflet';

import {
  OPERATIONAL_LAYERS,
  VECTOR_LAYER_IDS,
} from './operational-map-contract';
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

const contractById = new Map<string, (typeof OPERATIONAL_LAYERS)[number]>(
  OPERATIONAL_LAYERS.map((layer) => [layer.id, layer])
);

type FeatureLayer = Layer & { operationalFeature?: OperationalFeature };

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
    exposeLayerGroups(map, groups.current);
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
        created.on('add', () =>
          applyHeading(created, (created as FeatureLayer).operationalFeature)
        );
        group.addLayer(created);
        applyHeading(created, feature);
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

function exposeLayerGroups(
  map: LeafletMap,
  groups: Map<VectorLayerId, LayerGroup>
): void {
  const panes = map.getPanes() as Record<string, HTMLElement | undefined>;
  for (const [id, group] of groups) {
    const pane = panes[id] as
      | (HTMLElement & { __overviewLeafletLayer?: LayerGroup })
      | undefined;
    if (pane) pane.__overviewLeafletLayer = group;
  }
}

function createLayer(
  feature: OperationalFeature,
  onSelect: (id: string) => void
): Layer {
  const layer =
    feature.geometry.type === 'point'
      ? L.marker([feature.geometry.latitude, feature.geometry.longitude], {
          icon: iconFor(feature),
          pane: feature.layerId,
        })
      : L.polyline(
          feature.geometry.points.map((point) => [
            point.latitude,
            point.longitude,
          ]),
          {
            color: colors[feature.layerId] ?? '#f8fafc',
            dashArray: dashFor(feature),
            opacity: contractById.get(feature.layerId)?.opacity ?? 0.9,
            pane: feature.layerId,
            weight: lineWidth(feature.layerId),
          }
        );
  bindLabel(layer, feature);
  (layer as FeatureLayer).operationalFeature = feature;
  layer.on('click', () => onSelect(feature.id));
  return layer;
}

function updateLayer(layer: Layer, feature: OperationalFeature): void {
  (layer as FeatureLayer).operationalFeature = feature;
  if (layer instanceof L.Marker && feature.geometry.type === 'point') {
    layer.setLatLng([feature.geometry.latitude, feature.geometry.longitude]);
  }
  if (layer instanceof L.Polyline && feature.geometry.type === 'line') {
    layer.setLatLngs(
      feature.geometry.points.map((point) => [point.latitude, point.longitude])
    );
    layer.setStyle({
      color: colors[feature.layerId] ?? '#f8fafc',
      dashArray: dashFor(feature),
      opacity: contractById.get(feature.layerId)?.opacity ?? 0.9,
      pane: feature.layerId,
      weight: lineWidth(feature.layerId),
    });
  }
  if (layer instanceof L.Marker && feature.geometry.type === 'point') {
    layer.setIcon(iconFor(feature));
    bindLabel(layer, feature);
  }
  applyHeading(layer, feature);
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
  const size = markerSize(feature.layerId);
  return L.icon({
    iconUrl: url,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    className:
      feature.id === 'current-position' ? 'operational-map__aircraft' : '',
  });
}

function bindLabel(layer: Layer, feature: OperationalFeature): void {
  if (!(layer instanceof L.Marker)) return;
  const label = document.createElement('span');
  label.textContent =
    feature.kind === 'ground-entry-point' ? 'GEP' : feature.label;
  label.style.fontSize = '12px';
  layer.bindTooltip(label, {
    direction: 'bottom',
    offset: [0, markerTextOffset(feature.layerId)],
    opacity: 1,
    permanent: true,
  });
}

function lineWidth(layerId: string): number {
  const contract = contractById.get(layerId);
  return contract && 'width' in contract ? (contract.width ?? 3) : 3;
}

function markerSize(layerId: string): number {
  const contract = contractById.get(layerId);
  return contract && 'size' in contract ? (contract.size ?? 15) : 15;
}

function markerTextOffset(layerId: string): number {
  const contract = contractById.get(layerId);
  return contract && 'textOffsetPx' in contract
    ? (contract.textOffsetPx ?? 25)
    : 25;
}

function applyHeading(
  layer: Layer,
  feature: OperationalFeature | undefined
): void {
  const element = layer instanceof L.Marker ? layer.getElement() : null;
  if (!feature) return;
  if (!element || feature.id !== 'current-position') return;
  element.style.setProperty(
    '--aircraft-heading',
    `${feature.details[0]?.value ?? 0}deg`
  );
}

function dashFor(feature: OperationalFeature): string | undefined {
  return feature.kind === 'active-link' && feature.layerId.endsWith('warning')
    ? '6 4'
    : undefined;
}
