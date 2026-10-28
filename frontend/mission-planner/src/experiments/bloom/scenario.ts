import { Vector3 } from 'three';
import { globePosition } from '../../pages/globe-coordinates';
import { seededRandom } from './contracts';
import type { FlowPoint } from '../../pages/overview-animated-flow-line-rendering';

export const SCENARIO = 'synthetic-bloom-v1';
export const SUN: [number, number, number] = [-8, 3, -4];
export const INITIAL_CAMERA: [number, number, number] = [0, 2, 6.8];
export const POIS = [
  { id: 'alpha', latitude: 35, longitude: -90, color: '#fbbf24' },
  { id: 'bravo', latitude: 42, longitude: -30, color: '#ef4444' },
  { id: 'charlie', latitude: 16, longitude: -65, color: '#22d3ee' },
  { id: 'overlap', latitude: 35.4, longitude: -89.7, color: '#a78bfa' },
  { id: 'far-side', latitude: 0, longitude: 90, color: '#ef4444' },
] as const;
function arc(a: FlowPoint, b: FlowPoint, height: number): FlowPoint[] {
  const start = new Vector3(...a),
    end = new Vector3(...b);
  return Array.from({ length: 65 }, (_, i) => {
    const t = i / 64;
    return start
      .clone()
      .lerp(end, t)
      .normalize()
      .multiplyScalar(2.006 + height * Math.sin(Math.PI * t))
      .toArray() as [number, number, number];
  });
}
export const ROUTE = arc(
  globePosition(35, -110, 2.006),
  globePosition(45, -15, 2.006),
  0.002
);
export const LINKS = [
  arc(globePosition(16, -100, 2.006), globePosition(60, -15, 2.006), 0.15),
  [globePosition(35, -90, 2.006), globePosition(55, -65, 2.6)],
  arc(globePosition(10, 60, 2.006), globePosition(45, 140, 2.006), 0.2),
];
export const TRAFFIC = Array.from({ length: 36 }, (_, i) => {
  const random = seededRandom(429 + i);
  return {
    id: i,
    latitude: random() * 75 - 15,
    longitude: random() * 180 - 150,
    heading: random() * 360,
  };
});
export const WIND_PATHS = Array.from({ length: 12 }, (_, i) =>
  arc(
    globePosition(i * 5 - 10, -110, 2.008),
    globePosition(i * 5 - 5, -40, 2.008),
    0.002
  )
);
