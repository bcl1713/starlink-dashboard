import { globePosition } from './globe-coordinates';

export interface GlobeCoordinate {
  latitude: number;
  longitude: number;
}

function dot(
  [leftX, leftY, leftZ]: [number, number, number],
  [rightX, rightY, rightZ]: [number, number, number]
): number {
  return leftX * rightX + leftY * rightY + leftZ * rightZ;
}

function normalize(
  [x, y, z]: [number, number, number],
  radius: number
): [number, number, number] {
  const magnitude = Math.hypot(x, y, z);

  return [
    (x / magnitude) * radius,
    (y / magnitude) * radius,
    (z / magnitude) * radius,
  ];
}

export function greatCirclePoints(
  start: GlobeCoordinate,
  end: GlobeCoordinate,
  radius: number,
  segments: number
): [number, number, number][] {
  const startUnit = globePosition(start.latitude, start.longitude, 1);
  const endUnit = globePosition(end.latitude, end.longitude, 1);
  const angle = Math.acos(Math.min(1, Math.max(-1, dot(startUnit, endUnit))));
  const sineOfAngle = Math.sin(angle);

  return Array.from({ length: segments + 1 }, (_, index) => {
    const progress = index / segments;
    const startWeight = Math.sin((1 - progress) * angle) / sineOfAngle;
    const endWeight = Math.sin(progress * angle) / sineOfAngle;

    return normalize(
      [
        startUnit[0] * startWeight + endUnit[0] * endWeight,
        startUnit[1] * startWeight + endUnit[1] * endWeight,
        startUnit[2] * startWeight + endUnit[2] * endWeight,
      ],
      radius
    );
  });
}
