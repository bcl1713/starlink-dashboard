import * as THREE from 'three';
import { globePosition } from '../globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from '../globe-render-radii';
import type { AdsbContactView } from './overview-adsb-state';

export const ADSB_MARKER_RADIUS = ROUTE_OVERLAY_RADIUS + 0.003;
export interface AdsbMarkerBatch {
  hexes: string[];
  matrices: Float32Array;
  positions: THREE.Vector3[];
}
export interface AdsbMarkerInstances {
  current: AdsbMarkerBatch;
  stale: AdsbMarkerBatch;
}
export function buildAdsbMarkerInstances(
  contacts: readonly AdsbContactView[]
): AdsbMarkerInstances {
  const build = (freshness: AdsbContactView['freshness']): AdsbMarkerBatch => {
    const selected = contacts.filter((c) => c.freshness === freshness);
    const matrices = new Float32Array(selected.length * 16);
    const positions: THREE.Vector3[] = [];
    selected.forEach((c, i) => {
      const lat = THREE.MathUtils.degToRad(c.latitude),
        lon = THREE.MathUtils.degToRad(c.longitude);
      const track = THREE.MathUtils.degToRad(c.track_degrees ?? 0);
      const out = new THREE.Vector3(
        ...globePosition(c.latitude, c.longitude, 1)
      );
      const north = new THREE.Vector3(
        -Math.sin(lat) * Math.cos(lon),
        Math.cos(lat),
        Math.sin(lat) * Math.sin(lon)
      );
      const east = new THREE.Vector3(-Math.sin(lon), 0, -Math.cos(lon));
      const forward = north
        .multiplyScalar(Math.cos(track))
        .add(east.multiplyScalar(Math.sin(track)));
      const right = forward.clone().cross(out);
      const position = new THREE.Vector3(
        ...globePosition(c.latitude, c.longitude, ADSB_MARKER_RADIUS)
      );
      positions.push(position);
      new THREE.Matrix4()
        .makeBasis(right, forward, out)
        .scale(new THREE.Vector3(0.032, 0.032, 0.032))
        .setPosition(position)
        .toArray(matrices, i * 16);
    });
    return { hexes: selected.map((c) => c.hex), matrices, positions };
  };
  return { current: build('current'), stale: build('stale') };
}
/** The Earth also blocks interaction even if its mesh has no pointer handler. */
export function isAdsbMarkerVisible(
  point: THREE.Vector3,
  camera: THREE.Camera
): boolean {
  const clip = point.clone().project(camera);
  if (Math.abs(clip.x) > 1 || Math.abs(clip.y) > 1 || clip.z < -1 || clip.z > 1)
    return false;
  const origin = new THREE.Vector3().setFromMatrixPosition(camera.matrixWorld);
  const ray = point.clone().sub(origin);
  const a = ray.lengthSq(),
    b = 2 * origin.dot(ray),
    d = b * b - 4 * a * (origin.lengthSq() - 4);
  if (d < 0) return true;
  const hit = (-b - Math.sqrt(d)) / (2 * a);
  return !(hit > 0 && hit < 1 - 1e-6);
}
export interface AdsbPointerGesture {
  x: number;
  y: number;
  maxDistance: number;
  cancelled: boolean;
}
export function adsbClickAllowed(
  start: AdsbPointerGesture,
  end: { x: number; y: number }
): boolean {
  return (
    !start.cancelled &&
    Math.max(start.maxDistance, Math.hypot(end.x - start.x, end.y - start.y)) <=
      5
  );
}
