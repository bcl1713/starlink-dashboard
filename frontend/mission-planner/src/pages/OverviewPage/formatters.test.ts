import { describe, expect, it } from 'vitest';

import type { POIETA } from '../../types/monitoring';
import {
  classifyEtaUrgency,
  classifyLatency,
  classifyObstruction,
  classifyPacketLoss,
  formatAltitudeMeters,
  formatCoordinates,
  formatETA,
  formatLatencyMs,
  formatPercent,
  formatPosition,
  formatThroughputMbps,
  selectApplicablePOIs,
} from './formatters';

const poi = (
  name: string,
  eta_seconds: number | null | undefined,
  overrides: Partial<POIETA> = {}
) =>
  ({
    poi_id: name,
    name,
    latitude: 0,
    longitude: 0,
    category: null,
    icon: 'pin',
    active: true,
    eta_seconds,
    eta_type: 'estimated',
    is_pre_departure: false,
    flight_phase: 'in_flight',
    distance_meters: 0,
    bearing_degrees: null,
    course_status: null,
    is_on_active_route: true,
    projected_latitude: null,
    projected_longitude: null,
    projected_waypoint_index: null,
    projected_route_progress: null,
    route_aware_status: null,
    ...overrides,
  }) satisfies Omit<POIETA, 'eta_seconds'> & {
    readonly eta_seconds: number | null | undefined;
  };

describe('overview formatters and POI utilities', () => {
  it('selects applicable POIs by status, ETA availability, and stable order', () => {
    const input = Object.freeze([
      poi('passed', 10, { route_aware_status: 'already_passed' }),
      poi('behind', 20, { course_status: 'behind' }),
      poi('tie-a', 60, { route_aware_status: 'ahead_on_route' }),
      poi('unavailable-a', -1),
      poi('tie-b', 60, { course_status: 'on_course' }),
      poi('not-on-route', 30, { route_aware_status: 'not_on_route' }),
      poi('pre-departure', 40, { route_aware_status: 'pre_departure' }),
      poi('unavailable-b', Number.NaN),
      poi('sixth-unavailable', undefined),
    ]);

    expect(selectApplicablePOIs(input).map((item) => item.name)).toEqual([
      'not-on-route',
      'pre-departure',
      'tie-a',
      'tie-b',
      'unavailable-a',
    ]);
  });

  it('classifies ETA urgency on exact boundaries', () => {
    expect(classifyEtaUrgency(undefined)).toEqual({
      state: 'unavailable',
      label: 'Unavailable',
    });
    expect(classifyEtaUrgency(0).state).toBe('critical');
    expect(classifyEtaUrgency(899.999).state).toBe('critical');
    expect(classifyEtaUrgency(900).state).toBe('warning');
    expect(classifyEtaUrgency(1800).state).toBe('caution');
    expect(classifyEtaUrgency(3600).state).toBe('normal');
    expect(classifyEtaUrgency(-1).state).toBe('unavailable');
  });

  it('formats ETA and numeric values deterministically', () => {
    expect(formatETA(null)).toBe('—');
    expect(formatETA(0)).toBe('0s');
    expect(formatETA(59)).toBe('59s');
    expect(formatETA(60)).toBe('1m');
    expect(formatETA(3599)).toBe('59m 59s');
    expect(formatETA(3600)).toBe('1h');
    expect(formatETA(86400)).toBe('1d');
    expect(formatETA(90061)).toBe('1d 1h 1m 1s');
    expect(formatLatencyMs(74)).toBe('74 ms');
    expect(formatLatencyMs(74.25)).toBe('74.3 ms');
    expect(formatThroughputMbps(192.4)).toBe('192.4 Mbps');
    expect(formatThroughputMbps(-2.25)).toBe('-2.3 Mbps');
    expect(formatThroughputMbps(-0.04)).toBe('0 Mbps');
    expect(formatPercent(0.3)).toBe('0.3%');
    expect(formatPercent(100.01)).toBe('—');
  });

  it('formats coordinates, altitude, and positions without negative zero', () => {
    expect(formatCoordinates(39, -104)).toBe('39.0000, -104.0000');
    expect(formatCoordinates(-0, 0)).toBe('0.0000, 0.0000');
    expect(formatCoordinates(91, 0)).toBe('—');
    expect(formatAltitudeMeters(10972.6)).toBe('10,973 m');
    expect(formatAltitudeMeters(-1.5)).toBe('-2 m');
    expect(formatAltitudeMeters(Number.NaN)).toBe('—');
    expect(formatPosition(39, -104, 10972.6)).toBe(
      '39.0000, -104.0000 at 10,973 m'
    );
    expect(formatPosition(39, -104, null)).toBe('39.0000, -104.0000 at —');
    expect(formatPosition(39, -181, 0)).toBe('—');
  });

  it('classifies threshold and obstruction boundaries', () => {
    expect(classifyLatency(99.99).state).toBe('ok');
    expect(classifyLatency(100).state).toBe('warning');
    expect(classifyLatency(200).state).toBe('critical');
    expect(classifyPacketLoss(1.99).state).toBe('ok');
    expect(classifyPacketLoss(2).state).toBe('warning');
    expect(classifyPacketLoss(5).state).toBe('critical');
    expect(classifyObstruction(null)).toEqual({
      state: 'unavailable',
      label: 'Unavailable',
      displayValue: null,
      outOfDisplayRange: false,
    });
    expect(classifyObstruction(20)).toMatchObject({
      state: 'critical',
      displayValue: 20,
      outOfDisplayRange: false,
    });
    expect(classifyObstruction(20.01)).toMatchObject({
      state: 'critical',
      displayValue: 20,
      outOfDisplayRange: true,
    });
    expect(classifyObstruction(100)).toMatchObject({
      state: 'critical',
      displayValue: 20,
      outOfDisplayRange: true,
    });
  });
});
