import { expect, it } from 'vitest';
import { ecefKmToScene, sceneToEcefKm } from './coordinates';

it.each([
  [
    [6378.137, 0, 0],
    [2, 0, 0],
  ],
  [
    [0, 6378.137, 0],
    [0, 0, -2],
  ],
  [
    [0, 0, 6378.137],
    [0, 2, 0],
  ],
] as const)('maps physical ECEF %j to globe axes %j', (physical, scene) => {
  ecefKmToScene(physical).forEach((value, index) =>
    expect(value).toBeCloseTo(scene[index], 12)
  );
  sceneToEcefKm(scene).forEach((value, index) =>
    expect(value).toBeCloseTo(physical[index], 8)
  );
});

it('preserves physical satellite altitude', () => {
  expect(ecefKmToScene([6878.137, 0, 0])[0]).toBeCloseTo(2.15678559, 7);
});
