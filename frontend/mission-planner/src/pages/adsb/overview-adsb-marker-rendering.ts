import * as THREE from 'three';
import { DEFAULT_CHEVRON_SETTINGS } from '../overview-chevron-settings';
import { globePosition } from '../globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from '../globe-render-radii';
import {
  isStarMarkerVisible,
  setStarMarkerChevronMatrix,
} from '../overview-star-marker-rendering';
import type { AdsbContactView } from './overview-adsb-state';

export const ADSB_MARKER_RADIUS = ROUTE_OVERLAY_RADIUS + 0.003;

/** Label occlusion against the existing radius-two globe, without triangle scans. */
export function createAdsbEarthOccluder(globe: {
  current: THREE.Group;
}): THREE.Object3D {
  const earth = new THREE.Object3D();
  const local = new THREE.Sphere(new THREE.Vector3(), 2);
  const world = new THREE.Sphere(),
    point = new THREE.Vector3();
  earth.raycast = (raycaster, intersections) => {
    world.copy(local).applyMatrix4(globe.current.matrixWorld);
    if (!raycaster.ray.intersectSphere(world, point)) return;
    const distance = raycaster.ray.origin.distanceTo(point);
    if (distance >= raycaster.near && distance <= raycaster.far)
      intersections.push({ distance, point: point.clone(), object: earth });
  };
  return earth;
}
export interface AdsbMarkerBatch {
  hexes: string[];
  matrices: Float32Array;
  positions: THREE.Vector3[];
  forwards: THREE.Vector3[];
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
    const forwards: THREE.Vector3[] = [];
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
      forwards.push(forward);
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
    return { hexes: selected.map((c) => c.hex), matrices, positions, forwards };
  };
  return { current: build('current'), stale: build('stale') };
}
/** Map overlays and picking share the same center-based Earth visibility rule. */
export const isAdsbMarkerVisible = isStarMarkerVisible;
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

/** Update the real instance transforms so picking follows screen-sized glyphs. */
export function resizeAdsbMarkerMeshes(
  group: THREE.Group,
  camera: THREE.Camera,
  viewportHeight: number,
  matrix: THREE.Matrix4,
  sizePixels = DEFAULT_CHEVRON_SETTINGS.trafficSizePixels
) {
  camera.updateMatrixWorld();
  for (const child of group.children) {
    if (!(child instanceof THREE.InstancedMesh)) continue;
    const batch = child.userData.adsbBatch as AdsbMarkerBatch | undefined;
    if (!batch) continue;
    for (let i = 0; i < batch.positions.length; i++) {
      setStarMarkerChevronMatrix(
        matrix,
        batch.positions[i],
        batch.forwards[i],
        camera,
        viewportHeight,
        sizePixels
      );
      if (!isStarMarkerVisible(batch.positions[i], camera)) {
        matrix.elements.fill(0, 0, 12);
      }
      child.setMatrixAt(i, matrix);
    }
    child.instanceMatrix.needsUpdate = true;
    child.computeBoundingSphere();
  }
}
