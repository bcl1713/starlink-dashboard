import { PerspectiveCamera, Vector3 } from 'three';
import { overviewCameraFrame } from '../pages/overview-camera-frame';
import { routeHemisphere } from '../pages/overview-route-hemisphere';
import { projectRouteArc } from '../pages/globe-route-projection';
import type { MissionMapInput } from './protocol';

export const MAP_WIDTH = 1920;
export const MAP_HEIGHT = 1080;
const SAFE_RECT = { x: 128, y: 160, width: 1664, height: 736 };
export interface MissionMapView {
  id: string;
  startIndex: number;
  endIndex: number;
  endsRoute: boolean;
  endpointLabels?: MissionMapInput['endpointLabels'];
  points: [number, number, number][];
  markers: (MissionMapInput['markers'][number] & {
    point: [number, number, number];
  })[];
  direction: [number, number, number];
  distance: number;
  offsetX: number;
  offsetY: number;
}
function fit(points: [number, number, number][]) {
  const vectors = points.map((p) => new Vector3(...p));
  const direction = routeHemisphere(vectors);
  // An interior cap also reserves useful globe scale near the limb.
  if (
    !direction ||
    vectors.some(
      (p) =>
        p.clone().normalize().dot(direction) < Math.cos((75 * Math.PI) / 180)
    )
  )
    return null;
  const frame = overviewCameraFrame({
    width: MAP_WIDTH,
    height: MAP_HEIGHT,
    fov: 38,
    safeRect: SAFE_RECT,
    route: points,
    direction,
  });
  return frame.routeFit === 'complete' ? frame : null;
}
/** Greedy longest consecutive fitting arc; shared endpoints preserve every edge. */
export function frameMissionRoute(input: MissionMapInput): MissionMapView[] {
  const points = projectRouteArc(input.route, 2.025, 32);
  const views: MissionMapView[] = [];
  let start = 0;
  while (start < points.length - 1) {
    let low = start + 1;
    let high = points.length - 1;
    if (!fit(points.slice(start, low + 1)))
      throw new Error('Route segment cannot fit');
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (fit(points.slice(start, middle + 1))) low = middle;
      else high = middle - 1;
    }
    const subset = points.slice(start, low + 1);
    const frame = fit(subset)!;
    views.push({
      id: `${input.legId}/view-${views.length + 1}`,
      startIndex: start,
      endIndex: low,
      endsRoute: low === points.length - 1,
      points: subset,
      endpointLabels: input.endpointLabels,
      direction: frame.direction!.toArray(),
      distance: frame.distance + 0.02,
      offsetX: frame.offsetX,
      offsetY: frame.offsetY,
      markers: input.markers
        .filter((m) => m.routeIndex * 32 >= start && m.routeIndex * 32 <= low)
        .map((m) => ({ ...m, point: points[m.routeIndex * 32] })),
    });
    start = low;
  }
  return views;
}
export function applyCameraFrame(
  camera: PerspectiveCamera,
  view: MissionMapView
): void {
  camera.position.copy(
    new Vector3(...view.direction).multiplyScalar(view.distance)
  );
  camera.up.set(0, 1, 0);
  camera.lookAt(0, 0, 0);
  camera.setViewOffset(
    MAP_WIDTH,
    MAP_HEIGHT,
    view.offsetX,
    view.offsetY,
    MAP_WIDTH,
    MAP_HEIGHT
  );
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
}
