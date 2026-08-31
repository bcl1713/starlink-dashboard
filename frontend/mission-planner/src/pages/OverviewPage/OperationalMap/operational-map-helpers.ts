import type { LatLng, Map as LeafletMap } from 'leaflet';

export function buildMeasurementText(
  map: LeafletMap | null,
  points: readonly LatLng[]
): string {
  if (!map || points.length < 2) return 'Measurement: no distance selected';
  let meters = 0;
  for (let index = 1; index < points.length; index += 1) {
    meters += map.distance(points[index - 1], points[index]);
  }
  return `Measurement: ${(meters / 1852).toFixed(1)} nautical miles`;
}

export function prefersReducedMotion(): boolean {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  );
}
