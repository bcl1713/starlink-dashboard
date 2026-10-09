import { PerspectiveCamera, Vector3 } from 'three';
import { overviewCameraFrame } from '../pages/overview-camera-frame';
import { routeHemisphere } from '../pages/overview-route-hemisphere';
import { projectRouteArc } from '../pages/globe-route-projection';
import {
  mapViewportSchema,
  type MapViewport,
  type MissionMapInput,
} from './protocol';

export const MAP_WIDTH = 1920;
export const MAP_HEIGHT = 1080;
export interface MissionMapView {
  id: string;
  width: number;
  height: number;
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
function fit(points: [number, number, number][], viewport: MapViewport) {
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
    width: viewport.width,
    height: viewport.height,
    fov: 38,
    // Leave a small inset for the stars at the actual PDF card aspect ratio.
    safeRect: {
      x: 64,
      y: 64,
      width: viewport.width - 128,
      height: viewport.height - 128,
    },
    route: points,
    direction,
  });
  return frame.routeFit === 'complete' ? frame : null;
}
/** Greedy longest consecutive fitting arc; shared endpoints preserve every edge. */
export function frameMissionRoute(
  input: MissionMapInput,
  size: MapViewport = { width: MAP_WIDTH, height: MAP_HEIGHT }
): MissionMapView[] {
  const viewport = mapViewportSchema.parse(size);
  const points = projectRouteArc(input.route, 2.025, 32);
  const views: MissionMapView[] = [];
  let start = 0;
  while (start < points.length - 1) {
    let low = start + 1;
    let high = points.length - 1;
    if (!fit(points.slice(start, low + 1), viewport))
      throw new Error('Route segment cannot fit');
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (fit(points.slice(start, middle + 1), viewport)) low = middle;
      else high = middle - 1;
    }
    const subset = points.slice(start, low + 1);
    const frame = fit(subset, viewport)!;
    views.push({
      id: `${input.legId}/view-${views.length + 1}`,
      ...viewport,
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
    view.width,
    view.height,
    view.offsetX,
    view.offsetY,
    view.width,
    view.height
  );
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
}
