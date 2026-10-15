import type { FlowPoint } from '../overview-animated-flow-line-rendering';
import { EARTH_RADIUS_KM } from './types';

export function ecefKmToScene([x, y, z]: FlowPoint): FlowPoint {
  const scale = 2 / EARTH_RADIUS_KM;
  return [x * scale, z * scale, -y * scale];
}
export function sceneToEcefKm([x, y, z]: FlowPoint): FlowPoint {
  const scale = EARTH_RADIUS_KM / 2;
  return [x * scale, -z * scale, y * scale];
}
