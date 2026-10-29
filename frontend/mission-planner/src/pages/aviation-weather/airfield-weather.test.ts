import { expect, it } from 'vitest';
import { airfieldCollection, routeAirfields } from './airfield-weather';
import { parseAviationFeatures } from '@/services/aviation-features';
import { collection, station } from './fixtures';

it('uses labelled airfields before route line endpoints', () => {
  expect(
    routeAirfields({
      points: [
        { latitude: 0, longitude: 0 },
        { latitude: 2, longitude: 2 },
      ],
      waypoints: [
        { role: 'arrival', latitude: 3, longitude: 3 },
        { role: 'departure', latitude: 1, longitude: 1 },
      ],
    })
  ).toEqual({
    departure: { role: 'departure', latitude: 1, longitude: 1 },
    arrival: { role: 'arrival', latitude: 3, longitude: 3 },
  });
  expect(
    routeAirfields({
      points: [
        { latitude: 0, longitude: 0 },
        { latitude: 2, longitude: 2 },
      ],
    })
  ).toEqual({
    departure: { latitude: 0, longitude: 0 },
    arrival: { latitude: 2, longitude: 2 },
  });
  expect(routeAirfields()).toEqual({});
});

it('deduplicates shared airfields and excludes reports beyond 10 km across the dateline', () => {
  const close = station();
  close.geometry.coordinates = [-179.99, 0];
  const distant = station();
  distant.id = 'far';
  distant.properties.station_id = 'FAR';
  distant.geometry.coordinates = [179, 0];
  const data = parseAviationFeatures(collection([close, distant]), 'metar');
  const selected = airfieldCollection(
    data,
    'metar',
    {
      metar: false,
      taf: false,
      sigmet: false,
      departure_weather: true,
      arrival_weather: true,
      revision: 1,
    },
    {
      departure: { latitude: 0, longitude: 179.99 },
      arrival: { latitude: 0, longitude: -179.98 },
    }
  );
  expect(selected.features.map((f) => f.id)).toEqual(['test-station']);
});
