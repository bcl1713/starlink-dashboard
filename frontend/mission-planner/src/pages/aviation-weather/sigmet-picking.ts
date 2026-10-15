import * as THREE from 'three';
import {
  activeFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { AviationView } from './aviation-controller';
import type { AviationSelection } from './aviation-inspection';
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

type ClipVertex = { world: THREE.Vector3; clip: THREE.Vector4 };
const planes = [
  (v: THREE.Vector4) => v.w + v.x,
  (v: THREE.Vector4) => v.w - v.x,
  (v: THREE.Vector4) => v.w + v.y,
  (v: THREE.Vector4) => v.w - v.y,
  (v: THREE.Vector4) => v.w + v.z,
  (v: THREE.Vector4) => v.w - v.z,
];
function clipTriangle(vertices: ClipVertex[]): ClipVertex[] {
  let polygon = vertices;
  for (const distance of planes) {
    const output: ClipVertex[] = [];
    for (let i = 0; i < polygon.length; i++) {
      const current = polygon[i],
        previous = polygon[(i + polygon.length - 1) % polygon.length];
      const a = distance(previous.clip),
        b = distance(current.clip);
      if (a >= 0 !== b >= 0) {
        const t = a / (a - b);
        output.push({
          world: previous.world.clone().lerp(current.world, t),
          clip: previous.clip.clone().lerp(current.clip, t),
        });
      }
      if (b >= 0) output.push(current);
    }
    polygon = output;
    if (!polygon.length) break;
  }
  return polygon;
}
const visibilityCache = new WeakMap<
  object,
  WeakMap<
    THREE.Camera,
    {
      signature: string;
      data: unknown;
      state: string;
      from: number;
      until: number;
      items: AviationSelection[];
    }
  >
>();
export function visibleSigmetReports(
  view: AviationView,
  camera: THREE.Camera,
  viewport: Viewport
): AviationSelection[] {
  const layer = view.layers.sigmet,
    drawing = layer.drawing;
  if (
    !drawing ||
    !layer.data ||
    !['current', 'stale'].includes(layer.state) ||
    viewport.width <= 0 ||
    viewport.height <= 0
  )
    return [];
  camera.updateMatrixWorld();
  const signature = [
    ...camera.matrixWorld.elements,
    ...camera.projectionMatrix.elements,
    viewport.width,
    viewport.height,
  ].join(',');
  const cache = visibilityCache.get(drawing)?.get(camera);
  if (
    cache &&
    cache.signature === signature &&
    cache.data === layer.data &&
    cache.state === layer.state &&
    view.now >= cache.from &&
    view.now < cache.until
  )
    return cache.items;
  const mesh = drawing.object.getObjectByName(
    'Native international SIGMET advisories'
  ) as THREE.Mesh | undefined;
  if (!mesh?.geometry) return [];
  drawing.object.updateMatrixWorld(true);
  const positions = mesh.geometry.getAttribute('position'),
    indices = mesh.geometry.getIndex();
  const admitted = new Set(reports(view).map((report) => report.id)),
    visible = new Set<string>();
  const count = indices?.count ?? positions.count;
  // Clip the same tessellated triangles that are drawn: holes, dateline splits,
  // and polygons whose original vertices are all outside the viewport agree
  // with the visible map. The cache avoids rescanning an unchanged scene.
  for (let offset = 0; offset < count; offset += 3) {
    const id = drawing.featureAt(offset / 3);
    if (!id || !admitted.has(id) || visible.has(id)) continue;
    const vertices: ClipVertex[] = [];
    for (let j = 0; j < 3; j++) {
      const index = indices ? indices.getX(offset + j) : offset + j;
      const world = new THREE.Vector3()
        .fromBufferAttribute(positions, index)
        .applyMatrix4(mesh.matrixWorld);
      const clip = new THREE.Vector4(world.x, world.y, world.z, 1)
        .applyMatrix4(camera.matrixWorldInverse)
        .applyMatrix4(camera.projectionMatrix);
      vertices.push({ world, clip });
    }
    const polygon = clipTriangle(vertices);
    if (!polygon.length) continue;
    const center = polygon
      .reduce((sum, vertex) => sum.add(vertex.world), new THREE.Vector3())
      .divideScalar(polygon.length);
    if (
      isStarMarkerVisible(center, camera) ||
      polygon.some((vertex) => isStarMarkerVisible(vertex.world, camera))
    )
      visible.add(id);
  }
  const items = [...visible]
    .sort()
    .map((id) => ({ layer: 'sigmet' as const, id }));
  let cameras = visibilityCache.get(drawing);
  if (!cameras) {
    cameras = new WeakMap();
    visibilityCache.set(drawing, cameras);
  }
  let until = Infinity;
  for (const feature of layer.data.features as AviationAdvisory[]) {
    for (const time of [
      feature.properties.valid_from_ms,
      feature.properties.expires_at_ms,
    ])
      if (time > view.now) until = Math.min(until, time);
  }
  cameras.set(camera, {
    signature,
    data: layer.data,
    state: layer.state,
    from: view.now,
    until,
    items,
  });
  return items;
}
