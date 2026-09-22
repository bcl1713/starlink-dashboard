import { describe, expect, it } from 'vitest';
import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';
import { overviewPoiLabelOffsets } from './overview-poi-label-layout';

function poi(poi_id: string): OverviewUpcomingPoi {
  return {
    poi_id,
    name: poi_id,
    kind: 'x_band_transition',
    latitude: 0,
    longitude: -50,
    expected_arrival_time: null,
    eta_seconds: 60,
    estimated_arrival_time: '2026-09-22T12:01:00.000Z',
    eta_type: 'estimated',
    upcoming: true,
    map_retained: true,
  };
}

describe('overviewPoiLabelOffsets', () => {
  it('assigns distinct deterministic callouts to a generated POI cluster', () => {
    const offsets = overviewPoiLabelOffsets([
      poi('x-band'),
      poi('aar-start'),
      poi('ka-entry'),
    ]);

    expect(offsets).toEqual({
      'aar-start': [14, -16],
      'ka-entry': [-58, -16],
      'x-band': [14, 16],
    });
  });
});
