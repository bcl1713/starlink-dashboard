import { describe, expect, it } from 'vitest';
import { globePosition } from './globe-coordinates';
import { projectAircraftHistory } from './overview-history-projection';
describe('projectAircraftHistory', () => {
  it('pairs chronological latitude and longitude samples on the 3D globe', () => {
    const points = projectAircraftHistory(
      {
        starlink_dish_latitude_degrees: [
          [1_782_000_000, 10],
          [1_782_000_001, 10],
        ],
        starlink_dish_longitude_degrees: [
          [1_782_000_000, 175],
          [1_782_000_001, -179],
        ],
      },
      2.02
    );
    expect(points).toEqual([
      globePosition(10, 175, 2.02),
      globePosition(10, -179, 2.02),
    ]);
  });
});
