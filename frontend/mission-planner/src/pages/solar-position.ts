import { globePosition } from './globe-coordinates';

export interface SubsolarPoint {
  latitude: number;
  longitude: number;
}

export function subsolarPoint(date: Date): SubsolarPoint {
  const year = date.getUTCFullYear();
  const dayOfYear = utcDayOfYear(date);
  const hours =
    date.getUTCHours() +
    date.getUTCMinutes() / 60 +
    date.getUTCSeconds() / 3600;

  const daysInYear = isLeapYear(year) ? 366 : 365;
  const fractionalYear =
    ((2 * Math.PI) / daysInYear) * (dayOfYear - 1 + (hours - 12) / 24);

  const equationOfTime =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(fractionalYear) -
      0.032077 * Math.sin(fractionalYear) -
      0.014615 * Math.cos(2 * fractionalYear) -
      0.040849 * Math.sin(2 * fractionalYear));

  const solarDeclination =
    0.006918 -
    0.399912 * Math.cos(fractionalYear) +
    0.070257 * Math.sin(fractionalYear) -
    0.006758 * Math.cos(2 * fractionalYear) +
    0.000907 * Math.sin(2 * fractionalYear) -
    0.002697 * Math.cos(3 * fractionalYear) +
    0.00148 * Math.sin(3 * fractionalYear);

  return {
    latitude: radiansToDegrees(solarDeclination),
    longitude: normalizeLongitude((720 - hours * 60 - equationOfTime) / 4),
  };
}
export function sunLightPosition(
  date: Date,
  distance: number
): [number, number, number] {
  const sun = subsolarPoint(date);

  return globePosition(sun.latitude, sun.longitude, distance);
}

function utcDayOfYear(date: Date): number {
  const startOfYear = Date.UTC(date.getUTCFullYear(), 0, 0);
  const millisecondsPerDay = 24 * 60 * 60 * 1000;

  return Math.floor((date.getTime() - startOfYear) / millisecondsPerDay);
}

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function radiansToDegrees(radians: number): number {
  return (radians * 180) / Math.PI;
}

function normalizeLongitude(longitude: number): number {
  return ((((longitude + 180) % 360) + 360) % 360) - 180;
}
