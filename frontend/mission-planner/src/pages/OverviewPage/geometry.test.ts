import { describe, expect, it } from 'vitest';

import type { ActiveXLink, RouteCoordinates } from '../../types/monitoring';
import type { PositionHistoryPoint } from './history';
import {
  adaptActiveLinkSegment,
  adaptPositionHistory,
  adaptRouteCoordinates,
  normalizeLongitude,
  splitActiveLinkSegments,
  splitAtInternationalDateLine,
  type OverviewGeometryPoint,
} from './geometry';

const point = (
  latitude: number,
  longitude: number,
  altitudeMeters: number | null = null,
  timestamp: string | null = '2026-08-29T12:00:00Z'
): OverviewGeometryPoint => ({
  latitude,
  longitude,
  altitudeMeters,
  timestamp,
});

describe('overview geometry utilities', () => {
  it('normalizes finite longitude values and rejects nonfinite values', () => {
    expect(normalizeLongitude(180)).toBe(-180);
    expect(normalizeLongitude(-180)).toBe(-180);
    expect(normalizeLongitude(540)).toBe(-180);
    expect(normalizeLongitude(-540)).toBe(-180);
    expect(normalizeLongitude(181)).toBe(-179);
    expect(normalizeLongitude(-181)).toBe(179);
    expect(Object.is(normalizeLongitude(-0), -0)).toBe(false);
    expect(() => normalizeLongitude(Number.POSITIVE_INFINITY)).toThrow(
      RangeError
    );
  });

  it('splits eastbound and westbound IDL crossings with interpolation', () => {
    expect(
      splitAtInternationalDateLine([point(10, 170), point(20, -170)])
    ).toEqual([
      [point(10, 170), point(15, 180, null, '2026-08-29T12:00:00Z')],
      [point(15, -180, null, '2026-08-29T12:00:00Z'), point(20, -170)],
    ]);
    expect(
      splitAtInternationalDateLine([point(20, -170), point(10, 170)])
    ).toEqual([
      [point(20, -170), point(15, -180, null, '2026-08-29T12:00:00Z')],
      [point(15, 180, null, '2026-08-29T12:00:00Z'), point(10, 170)],
    ]);
  });

  it('handles hard gaps, exact 180 separation, duplicates, and endpoint crossing', () => {
    const segments = splitAtInternationalDateLine([
      point(0, 0),
      null,
      point(1, 10, 100),
      point(1, 10, 100),
      point(2, -170, 200),
      point(2, 10, 200),
      point(3, 180, 300),
    ]);
    expect(segments).toEqual([
      [point(0, 0)],
      [
        point(1, 10, 100),
        point(1, 10, 100),
        point(2, -170, 200),
        point(2, 10, 200),
        point(3, 180, 300),
      ],
      [point(3, -180, 300)],
    ]);
    expect(
      splitAtInternationalDateLine([point(0, -170), point(1, 10)])
    ).toEqual([[point(0, -170), point(1, 10)]]);
    expect(
      splitAtInternationalDateLine([point(0, 170), point(1, 180)])
    ).toEqual([
      [point(0, 170), point(1, 180, null, '2026-08-29T12:00:00Z')],
      [point(1, -180)],
    ]);
  });

  it('uses timestamp and altitude interpolation rules', () => {
    expect(
      splitAtInternationalDateLine([
        point(0, 170, 100, '2026-08-29T12:00:00Z'),
        point(10, -170, 300, '2026-08-29T12:00:01.9999Z'),
      ])
    ).toEqual([
      [
        point(0, 170, 100, '2026-08-29T12:00:00Z'),
        point(5, 180, 200, '2026-08-29T12:00:00.999Z'),
      ],
      [
        point(5, -180, 200, '2026-08-29T12:00:00.999Z'),
        point(10, -170, 300, '2026-08-29T12:00:01.9999Z'),
      ],
    ]);
    expect(
      splitAtInternationalDateLine([
        point(0, 170, 100, 'bad'),
        point(10, -170, null, '2026-08-29T12:00:02Z'),
      ])[0][1]
    ).toMatchObject({ altitudeMeters: null, timestamp: null });
  });

  it('truncates synthetic timestamps exactly at TimeClip boundaries', () => {
    expect(
      splitAtInternationalDateLine([
        point(0, 170, null, '9999-12-31T23:59:59.999999999Z'),
        point(10, -170, null, '9999-12-31T23:59:59.999999999Z'),
      ])[0][1].timestamp
    ).toBe('9999-12-31T23:59:59.999Z');
    expect(
      splitAtInternationalDateLine([
        point(0, 170, null, '0000-01-01T00:00:00.999999999Z'),
        point(10, -170, null, '0000-01-01T00:00:00.999999999Z'),
      ])[0][1].timestamp
    ).toBe('0000-01-01T00:00:01Z');
    expect(
      splitAtInternationalDateLine([
        point(0, 170, null, '1969-12-31T23:59:59.999Z'),
        point(10, -170, null, '1969-12-31T23:59:59.999Z'),
      ])[0][1].timestamp
    ).toBe('1969-12-31T23:59:59.999Z');
    expect(
      splitAtInternationalDateLine([
        point(0, 170, null, '+010000-01-01T00:00:00Z'),
        point(10, -170, null, '+010000-01-01T00:00:00Z'),
      ])[0][1].timestamp
    ).toBeNull();
    for (const [start, end] of [
      ['1969-12-31T23:59:59.999999999Z', '1970-01-01T00:00:00Z'],
      ['1970-01-01T00:00:00Z', '1969-12-31T23:59:59.999999999Z'],
    ]) {
      expect(
        splitAtInternationalDateLine([
          point(0, 170, null, start),
          point(10, -170, null, end),
        ])[0][1].timestamp
      ).toBe('1970-01-01T00:00:00Z');
    }
    expect(
      splitAtInternationalDateLine([
        point(0, 170, null, '1969-12-31T23:59:59.998Z'),
        point(10, -170, null, '1969-12-31T23:59:59.996Z'),
      ])[0][1].timestamp
    ).toBe('1969-12-31T23:59:59.997Z');
  });

  it('keeps extreme altitude interpolation exact and finite', () => {
    for (const altitude of [0, -0, Number.MIN_VALUE, Number.MAX_VALUE]) {
      const boundary = splitAtInternationalDateLine([
        point(0, 170, altitude),
        point(10, -170, altitude),
      ])[0][1].altitudeMeters;
      expect(boundary).toBe(Object.is(altitude, -0) ? 0 : altitude);
      expect(Object.is(boundary, -0)).toBe(false);
    }
    expect(
      splitAtInternationalDateLine([
        point(0, 170, Number.MAX_VALUE),
        point(10, -170, -Number.MAX_VALUE),
      ])[0][1].altitudeMeters
    ).toBe(0);
  });

  it('supports repeated crossings without intra-segment jumps over 180 degrees', () => {
    const segments = splitAtInternationalDateLine([
      point(0, 170),
      point(5, -170),
      point(10, 170),
      point(15, -170),
    ]);
    expect(segments.length).toBeGreaterThanOrEqual(4);
    for (const segment of segments) {
      for (let index = 1; index < segment.length; index += 1) {
        expect(
          Math.abs(segment[index].longitude - segment[index - 1].longitude)
        ).toBeLessThanOrEqual(180);
      }
    }
  });

  it('adapts route, history, and active link DTO coordinates without joining links', () => {
    const route: RouteCoordinates = {
      route_id: 'r1',
      route_name: 'Route',
      revision_at: null,
      generated_at: '2026-08-29T12:00:00Z',
      total: 1,
      coordinates: [
        { latitude: 1, longitude: 181, altitude_meters: 100, sequence: 0 },
      ],
    };
    const history: readonly PositionHistoryPoint[] = [
      { latitude: 1, longitude: 2, altitudeMeters: null, timestamp: 't' },
    ];
    const links: ActiveXLink['links'] = [
      {
        satellite_id: 'a',
        state: 'normal',
        color: 'green',
        relative_azimuth_degrees: 0,
        in_forbidden_window: false,
        coordinates: [
          {
            satellite_id: 'a',
            state: 'normal',
            color: 'green',
            relative_azimuth_degrees: 0,
            in_forbidden_window: false,
            point: 'aircraft',
            sequence: 0,
            latitude: -0,
            longitude: 170,
            observed_at: '2026-08-29T12:00:00Z',
          },
          {
            satellite_id: 'a',
            state: 'normal',
            color: 'green',
            relative_azimuth_degrees: 0,
            in_forbidden_window: false,
            point: 'satellite',
            sequence: 1,
            latitude: 0,
            longitude: -170,
            observed_at: '2026-08-29T12:00:01Z',
          },
        ],
      },
      {
        satellite_id: 'b',
        state: 'warning',
        color: 'yellow',
        relative_azimuth_degrees: 1,
        in_forbidden_window: true,
        coordinates: [],
      },
    ];

    expect(
      adaptRouteCoordinates({
        ...route,
        coordinates: [
          { latitude: -0, longitude: -0, altitude_meters: -0, sequence: 0 },
        ],
      })
    ).toEqual([point(0, 0, 0, null)]);
    expect(adaptRouteCoordinates(route)).toEqual([point(1, -179, 100, null)]);
    expect(adaptPositionHistory([{ ...history[0], latitude: -0 }])).toEqual([
      point(0, 2, null, 't'),
    ]);
    expect(adaptActiveLinkSegment(links[0])).toHaveLength(2);
    expect(Object.is(adaptActiveLinkSegment(links[0])[0].latitude, -0)).toBe(
      false
    );
    const split = splitActiveLinkSegments(links);
    expect(split[0].link).toBe(links[0]);
    expect(split[1].link).toBe(links[1]);
    expect(split[0].segments).toHaveLength(2);
    expect(split[1].segments).toEqual([]);
  });
});
