interface TimedPoint {
  latitude: number;
  longitude: number;
  altitude?: number | null;
  expected_arrival_time: string | null;
}
type MotionPoint = TimedPoint & { time: number };
const radians = (degrees: number) => (degrees * Math.PI) / 180;
const wrap = (longitude: number) =>
  ((((longitude + 180) % 360) + 360) % 360) - 180;

/** Parse the server's normalized, confirmed route once per selection. */
export function prepareRunMotion(
  points: readonly TimedPoint[]
): MotionPoint[] | null {
  if (points.length < 2) return null;
  const path = points.map((point) => ({
    ...point,
    time: Date.parse(point.expected_arrival_time ?? ''),
  }));
  return path.every(
    (point, index) =>
      Number.isFinite(point.time) &&
      (index === 0 || point.time > path[index - 1].time)
  )
    ? path
    : null;
}

/** Display projection only; producer observations and events remain authoritative. */
export function projectRunMotion(
  path: readonly MotionPoint[] | null,
  time: number
) {
  if (!path || !Number.isFinite(time)) return null;
  let low = 1,
    high = path.length - 1;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (path[mid].time <= time) low = mid + 1;
    else high = mid;
  }
  const a = path[low - 1],
    b = path[low];
  const fraction = Math.max(
    0,
    Math.min(1, (time - a.time) / (b.time - a.time))
  );
  const delta = wrap(b.longitude - a.longitude);
  const latitude = a.latitude + (b.latitude - a.latitude) * fraction;
  const longitude =
    fraction === 0
      ? a.longitude
      : fraction === 1
        ? b.longitude
        : wrap(a.longitude + delta * fraction);
  const altitudeA = a.altitude ?? b.altitude ?? 10668;
  const altitudeB = b.altitude ?? a.altitude ?? 10668;
  const x =
    Math.cos(radians(a.latitude)) * Math.sin(radians(b.latitude)) -
    Math.sin(radians(a.latitude)) *
      Math.cos(radians(b.latitude)) *
      Math.cos(radians(delta));
  const y = Math.sin(radians(delta)) * Math.cos(radians(b.latitude));
  return {
    latitude,
    longitude,
    altitude: (altitudeA + (altitudeB - altitudeA) * fraction) * 3.28084,
    heading: ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360,
  };
}
