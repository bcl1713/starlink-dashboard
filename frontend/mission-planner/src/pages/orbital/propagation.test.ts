import { expect, it } from 'vitest';
import { CatalogPropagator, propagateCatalog } from './propagation';
import { referenceOmm } from './test-fixtures';

it('admits a future epoch on the same compiled catalog without changing IDs', () => {
  const now = Date.parse(referenceOmm.EPOCH);
  const catalog = new CatalogPropagator([
    { ...referenceOmm, NORAD_CAT_ID: '1' },
    {
      ...referenceOmm,
      NORAD_CAT_ID: '2',
      EPOCH: new Date(now + 600001).toISOString(),
    },
  ]);
  const before = catalog.update(now);
  expect([...before.valid]).toEqual([1, 0]);
  const after = catalog.update(now + 1);
  expect(after.ids).toEqual(['1', '2']);
  expect([...after.valid]).toEqual([1, 1]);
});

// Vallado AIAA 2006-6753 case 5. Published TEME at epoch:
// [7022.46529266, -1400.08296755, 0.03995155] km.
// Independently rotated by the published GMST polynomial, angle
// 3.4691723423794016 rad, to ECEF. Two metre tolerance includes Date precision.

it('omm_reference_coordinates matches independently published propagation', () => {
  const result = propagateCatalog(
    [referenceOmm],
    Date.parse(referenceOmm.EPOCH)
  );
  expect([...result.valid]).toEqual([1]);
  const expected = [-6198.557667319622, 3585.1267686862966, 0.03995155];
  result.positionsKm.forEach((coordinate, i) =>
    expect(Math.abs(coordinate - expected[i])).toBeLessThan(0.002)
  );
});

it.each([-259200001, 600001])(
  'independently rejects epoch age outside the boundary: %s',
  (age) => {
    const now = Date.parse(referenceOmm.EPOCH);
    const result = propagateCatalog(
      [{ ...referenceOmm, EPOCH: new Date(now + age).toISOString() }],
      now
    );
    expect([...result.valid]).toEqual([0]);
    expect([...result.positionsKm]).toEqual([0, 0, 0]);
  }
);

it('filters bad propagation individually and keeps numeric ID order', () => {
  const objects = [
    { ...referenceOmm, NORAD_CAT_ID: '100001' },
    { ...referenceOmm, NORAD_CAT_ID: '3', ECCENTRICITY: 2 },
    { ...referenceOmm, NORAD_CAT_ID: '2', MEAN_MOTION: 100 },
    { ...referenceOmm, NORAD_CAT_ID: '1', BSTAR: NaN },
  ];
  const result = propagateCatalog(objects, Date.parse(referenceOmm.EPOCH));
  expect(result.ids).toEqual(['1', '2', '3', '100001']);
  expect([...result.valid]).toEqual([0, 0, 0, 1]);
});

it.each([90, 0])(
  'propagates polar/equatorial elements at antimeridian node: %s',
  (inclination) => {
    const result = propagateCatalog(
      [{ ...referenceOmm, INCLINATION: inclination, RA_OF_ASC_NODE: 180 }],
      Date.parse(referenceOmm.EPOCH)
    );
    expect([...result.valid]).toEqual([1]);
    expect([...result.positionsKm].every(Number.isFinite)).toBe(true);
    expect(Math.hypot(...result.positionsKm)).toBeGreaterThan(6378.137);
  }
);
