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
function cross(
  [leftX, leftY, leftZ]: [number, number, number],
  [rightX, rightY, rightZ]: [number, number, number]
): [number, number, number] {
  return [
    leftY * rightZ - leftZ * rightY,
    leftZ * rightX - leftX * rightZ,
    leftX * rightY - leftY * rightX,
  ];
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

  if (angle < Number.EPSILON) {
    const [x, y, z] = globePosition(start.latitude, start.longitude, radius);

    return Array.from(
      { length: segments + 1 },
      () => [x, y, z] as [number, number, number]
    );
  }

  if (Math.PI - angle < Number.EPSILON) {
    const [startX, startY, startZ] = startUnit;
    const referenceAxis: [number, number, number] =
      Math.abs(startX) <= Math.abs(startY) &&
      Math.abs(startX) <= Math.abs(startZ)
        ? [1, 0, 0]
        : Math.abs(startY) <= Math.abs(startZ)
          ? [0, 1, 0]
          : [0, 0, 1];

    const orthogonalUnit = normalize(cross(startUnit, referenceAxis), 1);

    return Array.from({ length: segments + 1 }, (_, index) => {
      if (index === 0) {
        return globePosition(start.latitude, start.longitude, radius);
      }

      if (index === segments) {
        return globePosition(end.latitude, end.longitude, radius);
      }

      const progress = index / segments;

      return normalize(
        [
          startUnit[0] * Math.cos(Math.PI * progress) +
            orthogonalUnit[0] * Math.sin(Math.PI * progress),
          startUnit[1] * Math.cos(Math.PI * progress) +
            orthogonalUnit[1] * Math.sin(Math.PI * progress),
          startUnit[2] * Math.cos(Math.PI * progress) +
            orthogonalUnit[2] * Math.sin(Math.PI * progress),
        ],
        radius
      );
    });
  }

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
