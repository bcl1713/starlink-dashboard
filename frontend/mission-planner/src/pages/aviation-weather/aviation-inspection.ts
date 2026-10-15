import * as THREE from 'three';
import type { AviationView } from './aviation-controller';
import type { AviationLayer } from '@/services/aviation-weather';
import {
  activeFeatures,
  type AviationFeature,
} from '@/services/aviation-features';
import { earthPoint } from './aviation-renderer';
import { isStarMarkerVisible } from '../overview-star-marker-rendering';

export type AviationSelection = { layer: AviationLayer; id: string };
export const aviationSelectionKey = (selection: AviationSelection) =>
  `${selection.layer}:${selection.id}`;

export function inspectionReports(view: AviationView) {
  return (['metar', 'taf', 'sigmet'] as const).flatMap((layer) => {
    const item = view.layers[layer];
    if (!item.data || !['current', 'stale'].includes(item.state)) return [];
    return activeFeatures(item.data, layer, view.now).map((feature) => ({
      selection: { layer, id: feature.id },
      feature,
    }));
  });
}
export function resolveAviationSelection(
  view: AviationView,
  selection: AviationSelection | null
): AviationFeature | null {
  if (!selection) return null;
  const item = view.layers[selection.layer];
  if (!item.data || !['current', 'stale'].includes(item.state)) return null;
  return (
    activeFeatures(item.data, selection.layer, view.now).find(
      (f) => f.id === selection.id
    ) ?? null
  );
}
export function aviationReportLabel(feature: AviationFeature) {
  return 'station_id' in feature.properties
    ? `${feature.properties.report_type} · ${feature.properties.station_id}`
    : `SIGMET · ${feature.properties.issuer ?? 'Unknown issuer'} ${feature.properties.series ?? ''} · ${feature.properties.phenomenon ?? 'Unknown phenomenon'}${feature.geometry ? '' : ' · unlocated'}`;
}

function insideGlyph(point: THREE.Vector2, corners: THREE.Vector2[]) {
  let inside = false;
  for (let i = 0, j = corners.length - 1; i < corners.length; j = i++) {
    const a = corners[i],
      b = corners[j];
    if (
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x
    )
      inside = !inside;
    const delta = b.clone().sub(a);
    const t = delta.lengthSq()
      ? THREE.MathUtils.clamp(
          point.clone().sub(a).dot(delta) / delta.lengthSq(),
          0,
          1
        )
      : 0;
    if (point.distanceTo(a.clone().addScaledVector(delta, t)) <= 5) return true;
  }
  return inside;
}

export function pickAviationFeatures(
  view: AviationView,
  camera: THREE.Camera,
  point: { x: number; y: number },
  viewport: { width: number; height: number }
): AviationSelection[] {
  if (
    viewport.width <= 0 ||
    viewport.height <= 0 ||
    point.x < 0 ||
    point.y < 0 ||
    point.x > viewport.width ||
    point.y > viewport.height
  )
    return [];
  camera.updateMatrixWorld();
  const picked: AviationSelection[] = [];
  const ray = new THREE.Raycaster();
  ray.setFromCamera(
    new THREE.Vector2(
      (2 * point.x) / viewport.width - 1,
      1 - (2 * point.y) / viewport.height
    ),
    camera
  );
  for (const layer of ['metar', 'taf', 'sigmet'] as const) {
    const item = view.layers[layer];
    if (
      !item.data ||
      !item.drawing ||
      !['current', 'stale'].includes(item.state)
    )
      continue;
    const active = activeFeatures(item.data, layer, view.now);
    if (layer === 'sigmet') {
      item.drawing.object.updateWorldMatrix(true, false);
      const ids = new Set<string>();
      for (const hit of ray.intersectObject(item.drawing.object, false)) {
        if (hit.faceIndex == null || !isStarMarkerVisible(hit.point, camera))
          continue;
        const id = item.drawing.featureAt(hit.faceIndex);
        if (id && active.some((f) => f.id === id)) ids.add(id);
      }
      for (const id of ids) picked.push({ layer, id });
    } else {
      const object = item.drawing.object as THREE.Points | THREE.LineSegments;
      const positions = object.geometry.getAttribute('position');
      const offsets = new Map<string, number>();
      if (layer === 'taf')
        for (let i = 0; i < positions.count; i += 8) {
          const id = item.drawing.featureAt(i);
          if (id) offsets.set(id, i);
        }
      for (const feature of active) {
        if (!feature.geometry || feature.geometry.type !== 'Point') continue;
        const [lon, lat] = feature.geometry.coordinates;
        const position = earthPoint(lat, lon);
        if (!isStarMarkerVisible(position, camera)) continue;
        const depth = -position.clone().applyMatrix4(camera.matrixWorldInverse)
          .z;
        const clip = position.project(camera);
        const center = new THREE.Vector2(
          ((clip.x + 1) * viewport.width) / 2,
          ((1 - clip.y) * viewport.height) / 2
        );
        const click = new THREE.Vector2(point.x, point.y);
        let radius = 10;
        if (layer === 'metar') {
          const material = object.material as THREE.PointsMaterial;
          const diameter =
            material.sizeAttenuation &&
            camera instanceof THREE.PerspectiveCamera
              ? (material.size * viewport.height) / 2 / depth
              : material.size;
          radius = Math.max(radius, diameter / 2 + 3);
        }
        let hit =
          layer === 'metar'
            ? Math.max(
                Math.abs(click.x - center.x),
                Math.abs(click.y - center.y)
              ) <= radius
            : click.distanceTo(center) <= radius;
        const offset = offsets.get(feature.id);
        if (!hit && offset !== undefined) {
          const corners = [0, 2, 4, 6].map((i) => {
            const p = new THREE.Vector3()
              .fromBufferAttribute(positions, offset + i)
              .project(camera);
            return new THREE.Vector2(
              ((p.x + 1) * viewport.width) / 2,
              ((1 - p.y) * viewport.height) / 2
            );
          });
          hit = insideGlyph(click, corners);
        }
        if (hit) picked.push({ layer, id: feature.id });
      }
    }
  }
  return picked;
}
