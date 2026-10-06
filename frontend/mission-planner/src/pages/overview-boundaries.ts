import { globePosition } from './globe-coordinates';

export type BoundaryKind = 'countries' | 'subdivisions';
export interface BoundaryData {
  version: 1;
  lines: { disputed: boolean; points: [number, number][] }[];
}
export const BOUNDARY_RADIUS = 2.0002;
const MAX_POINTS = 120_000;
const MAX_SEGMENTS = 250_000;
export const MAX_BOUNDARY_BYTES = 4_000_000;

/** Validate optional data before handing any geometry to the renderer. */
export function parseBoundaries(input: unknown): BoundaryData {
  if (
    !input ||
    typeof input !== 'object' ||
    !('version' in input) ||
    input.version !== 1 ||
    !('lines' in input) ||
    !Array.isArray(input.lines) ||
    input.lines.length > MAX_POINTS / 2
  ) {
    throw new Error('Invalid boundary data');
  }
  let count = 0;
  for (const line of input.lines) {
    if (
      !line ||
      typeof line !== 'object' ||
      typeof line.disputed !== 'boolean' ||
      !Array.isArray(line.points) ||
      line.points.length < 2
    )
      throw new Error('Invalid boundary line');
    count += line.points.length;
    if (count > MAX_POINTS) throw new Error('Boundary point budget exceeded');
    for (const point of line.points) {
      if (
        !Array.isArray(point) ||
        point.length !== 2 ||
        !point.every(
          (value) => typeof value === 'number' && Number.isFinite(value)
        ) ||
        Math.abs(point[0]) > 180 ||
        Math.abs(point[1]) > 90
      )
        throw new Error('Invalid boundary coordinate');
    }
  }
  return input as BoundaryData;
}

/** Independent surface segments avoid multipart joins and date-line chords. */
export function projectBoundaries(data: BoundaryData) {
  const standard: number[] = [],
    disputed: number[] = [];
  let segments = 0;
  for (const line of data.lines) {
    const target = line.disputed ? disputed : standard;
    for (let index = 1; index < line.points.length; index++) {
      const [lon, lat] = line.points[index - 1];
      const [nextLon, nextLat] = line.points[index];
      const longitudeDelta = ((nextLon - lon + 540) % 360) - 180;
      const latitudeDelta = nextLat - lat;
      // Geographic interpolation retains parallels; <=0.5 degrees keeps chords
      // above the surface at this radius, including at high latitudes.
      const steps = Math.max(
        1,
        Math.ceil(
          Math.max(Math.abs(longitudeDelta), Math.abs(latitudeDelta)) / 0.5
        )
      );
      segments += steps;
      if (segments > MAX_SEGMENTS)
        throw new Error('Boundary segment budget exceeded');
      let previous = globePosition(lat, lon, BOUNDARY_RADIUS);
      for (let step = 1; step <= steps; step++) {
        const fraction = step / steps;
        const next = globePosition(
          lat + latitudeDelta * fraction,
          lon + longitudeDelta * fraction,
          BOUNDARY_RADIUS
        );
        target.push(...previous, ...next);
        previous = next;
      }
    }
  }
  return {
    standard: new Float32Array(standard),
    disputed: new Float32Array(disputed),
  };
}
