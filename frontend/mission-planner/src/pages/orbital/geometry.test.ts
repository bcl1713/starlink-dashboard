import { expect, it } from 'vitest';
import { elevationDegrees, segmentClearanceKm } from './geometry';

it('analytic chord clearance catches Earth crossing despite elevated vertices', () => {
  expect(segmentClearanceKm([7000, 0, 0], [-7000, 0, 0])).toBeCloseTo(
    -6378.137,
    8
  );
  expect(segmentClearanceKm([7000, 0, 0], [7000, 1000, 0])).toBeCloseTo(
    621.863,
    8
  );
  expect(segmentClearanceKm([7000, 0, 0], [7000, 0, 0])).toBeCloseTo(
    621.863,
    8
  );
});
it('uses radial elevation at aircraft altitude and the pole', () => {
  expect(elevationDegrees([6388.137, 0, 0], [7000, 0, 0])).toBeCloseTo(90, 8);
  expect(elevationDegrees([0, 0, 6378.137], [0, 0, 7000])).toBeCloseTo(90, 8);
});
