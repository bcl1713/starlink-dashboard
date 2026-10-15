export const MERCATOR_LIMIT = Math.atan(Math.sinh(Math.PI));
export function mercatorUv(lat: number, lon: number): [number, number] | null {
  const latitude = (lat * Math.PI) / 180;
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lon) ||
    Math.abs(latitude) > MERCATOR_LIMIT
  )
    return null;
  const u = (((lon / 360 + 0.5) % 1) + 1) % 1;
  const v =
    0.5 - Math.log(Math.tan(Math.PI / 4 + latitude / 2)) / (2 * Math.PI);
  return [u, Math.max(0, Math.min(1, v))];
}
export function weatherUvFromPosition(
  position: [number, number, number]
): [number, number] | null {
  const [x, y, z] = position;
  const radius = Math.hypot(x, y, z);
  if (!Number.isFinite(radius) || radius === 0) return null;
  return mercatorUv(
    (Math.asin(y / radius) * 180) / Math.PI,
    (Math.atan2(-z, x) * 180) / Math.PI
  );
}
