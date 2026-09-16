import { globePosition } from './globe-coordinates';

type NumericSample = readonly [number, number];
type OverviewHistorySeries = Record<
  string,
  readonly NumericSample[] | undefined
>;
const LATITUDE_METRIC = 'starlink_dish_latitude_degrees';
const LONGITUDE_METRIC = 'starlink_dish_longitude_degrees';
function isValidCoordinate(latitude: number, longitude: number) {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}
export function projectAircraftHistory(
  series: OverviewHistorySeries,
  radius: number
): [number, number, number][] {
  const latitudes = series[LATITUDE_METRIC] ?? [];
  const longitudes = series[LONGITUDE_METRIC] ?? [];
  const longitudeByTimestamp = new Map(longitudes);
  return [...latitudes]
    .sort(([leftTimestamp], [rightTimestamp]) => leftTimestamp - rightTimestamp)
    .flatMap(([timestamp, latitude]) => {
      const longitude = longitudeByTimestamp.get(timestamp);
      if (longitude === undefined || !isValidCoordinate(latitude, longitude)) {
        return [];
      }
      return [globePosition(latitude, longitude, radius)];
    });
}
