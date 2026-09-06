import { globePosition } from './globe-coordinates';
import { greatCirclePoints, type GlobeCoordinate } from './globe-route';

export function projectRoutePoints(
  points: readonly GlobeCoordinate[],
  radius: number
): [number, number, number][] {
  return points.map((point) =>
    globePosition(point.latitude, point.longitude, radius)
  );
}

export function projectRouteArc(
  points: readonly GlobeCoordinate[],
  radius: number,
  segmentsPerLeg: number
): [number, number, number][] {
  if (points.length < 2) {
    return projectRoutePoints(points, radius);
  }

  return points.flatMap((point, index) => {
    if (index === points.length - 1) {
      return [];
    }

    const leg = greatCirclePoints(
      point,
      points[index + 1],
      radius,
      segmentsPerLeg
    );

    return index === 0 ? leg : leg.slice(1);
  });
}
