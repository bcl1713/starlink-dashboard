import * as THREE from 'three';
import {
  activeFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { AviationView } from './aviation-controller';
import type { AviationSelection } from './aviation-inspection';
import { earthPoint } from './aviation-renderer';
import { isStarMarkerVisible } from '../overview-star-marker-rendering';

type Viewport = { width: number; height: number };
function reports(view: AviationView): AviationAdvisory[] {
  const layer = view.layers.sigmet;
  return layer.data &&
    layer.drawing &&
    ['current', 'stale'].includes(layer.state)
    ? (activeFeatures(layer.data, 'sigmet', view.now) as AviationAdvisory[])
    : [];
}
function inRing(lon: number, lat: number, ring: number[][]): boolean {
  // Normalized polygons are split at the dateline; choose the equivalent point
  // longitude closest to their coordinate domain without distorting each edge.
  const middle =
    (Math.min(...ring.map((p) => p[0])) + Math.max(...ring.map((p) => p[0]))) /
    2;
  const x = lon + 360 * Math.round((middle - lon) / 360);
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i],
      b = ring[j];
    const dx = b[0] - a[0],
      dy = b[1] - a[1];
    const t = Math.max(
      0,
      Math.min(
        1,
        ((x - a[0]) * dx + (lat - a[1]) * dy) / (dx * dx + dy * dy || 1)
      )
    );
    if (Math.hypot(x - a[0] - t * dx, lat - a[1] - t * dy) < 1e-7) return true;
    if (
      a[1] > lat !== b[1] > lat &&
      x < ((b[0] - a[0]) * (lat - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}
export function pickSigmetFeatures(
  view: AviationView,
  camera: THREE.Camera,
  point: { x: number; y: number },
  viewport: Viewport
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
  const caster = new THREE.Raycaster();
  caster.setFromCamera(
    new THREE.Vector2(
      (point.x / viewport.width) * 2 - 1,
      1 - (point.y / viewport.height) * 2
    ),
    camera
  );
  const hit = caster.ray.intersectSphere(
    new THREE.Sphere(new THREE.Vector3(), 2.026),
    new THREE.Vector3()
  );
  if (!hit) return [];
  const lat = (Math.asin(hit.y / hit.length()) * 180) / Math.PI;
  const lon = (Math.atan2(-hit.z, hit.x) * 180) / Math.PI;
  return reports(view)
    .filter((report) => {
      if (!report.geometry) return false;
      const polygons =
        report.geometry.type === 'Polygon'
          ? [report.geometry.coordinates]
          : report.geometry.coordinates;
      return polygons.some(
        (rings) =>
          inRing(lon, lat, rings[0]) &&
          !rings.slice(1).some((hole) => inRing(lon, lat, hole))
      );
    })
    .map((report) => ({ layer: 'sigmet' as const, id: report.id }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

export function visibleSigmetReports(
  view: AviationView,
  camera: THREE.Camera,
  viewport: Viewport
): AviationSelection[] {
  camera.updateMatrixWorld();
  const visible = new Set<string>();
  for (const x of [0, 0.25, 0.5, 0.75, 1])
    for (const y of [0, 0.25, 0.5, 0.75, 1])
      for (const selection of pickSigmetFeatures(
        view,
        camera,
        { x: x * viewport.width, y: y * viewport.height },
        viewport
      ))
        visible.add(selection.id);
  for (const report of reports(view)) {
    if (!report.geometry || visible.has(report.id)) continue;
    const polygons =
      report.geometry.type === 'Polygon'
        ? [report.geometry.coordinates]
        : report.geometry.coordinates;
    if (
      polygons.some((rings) =>
        rings.some((ring) =>
          ring.some(([lon, lat]) => {
            const position = earthPoint(lat, lon);
            if (!isStarMarkerVisible(position, camera)) return false;
            const clip = position.project(camera);
            return (
              Math.abs(clip.x) <= 1 &&
              Math.abs(clip.y) <= 1 &&
              clip.z >= -1 &&
              clip.z <= 1
            );
          })
        )
      )
    )
      visible.add(report.id);
  }
  return [...visible].sort().map((id) => ({ layer: 'sigmet', id }));
}
