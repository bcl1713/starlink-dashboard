// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { createSigmetHighlights } from './route-sigmet-highlights';
import { WeatherBudget } from './weather-budget';
import { parseAviationFeatures } from '@/services/aviation-features';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import { routeSnapshot } from '@/test/route-sigmet-fixtures';
import { earthPoint } from './aviation-renderer';
afterEach(() => vi.restoreAllMocks());
it('samples fractions on the original high-latitude great circle and never joins disjoint spans', () => {
  const f = routeSnapshot(),
    entry = routeSigmetSnapshotSchema.parse(f.snapshot).entries[0];
  entry.spans = [
    { ...entry.spans[0], start_fraction: 0.25, end_fraction: 0.4 },
    { ...entry.spans[0], start_fraction: 0.6, end_fraction: 0.75 },
  ];
  const feature = parseAviationFeatures(f.data, 'sigmet').features[0];
  const budget = new WeatherBudget();
  const drawing = createSigmetHighlights(
    {
      entry,
      reports: [feature],
      label: 'TEST 1 · eeeeeeee',
      color: '#7dd3fc',
      intersectionUnknown: true,
    },
    [
      { longitude: -60, latitude: 60 },
      { longitude: 60, latitude: 60 },
    ],
    budget
  );
  const spans = drawing.object.children.filter(
    (o) => o.name === 'Confirmed route span'
  ) as THREE.Line[];
  expect(spans).toHaveLength(2);
  const start = new THREE.Vector3()
    .fromBufferAttribute(spans[0].geometry.getAttribute('position'), 0)
    .normalize();
  // Independent quarter point from two normalized endpoint midpoints.
  expect((Math.asin(start.y) * 180) / Math.PI).toBeCloseTo(69.518, 2);
  expect((Math.atan2(-start.z, start.x) * 180) / Math.PI).toBeCloseTo(
    -39.389777,
    2
  );
  expect((spans[0].material as THREE.LineBasicMaterial).depthTest).toBe(true);
  expect(drawing.object.children.some((o) => o.type === 'Sprite')).toBe(false);
  expect(drawing.labelPosition).toHaveLength(3);
  expect(new THREE.Vector3(...drawing.labelPosition).length()).toBeCloseTo(
    2.033
  );
  drawing.dispose();
  drawing.dispose();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
it('keeps an antimeridian span at the seam and a point contact finite', () => {
  const f = routeSnapshot(),
    entry = routeSigmetSnapshotSchema.parse(f.snapshot).entries[0];
  entry.spans = [{ ...entry.spans[0], start_fraction: 0.5, end_fraction: 0.5 }];
  const drawing = createSigmetHighlights(
    {
      entry,
      reports: parseAviationFeatures(f.data, 'sigmet').features,
      label: 'seam',
      color: '#7dd3fc',
      intersectionUnknown: false,
    },
    [
      { longitude: 170, latitude: 0 },
      { longitude: -170, latitude: 0 },
    ],
    new WeatherBudget()
  );
  const line = drawing.object.getObjectByName(
    'Confirmed route span'
  ) as THREE.Line;
  const first = new THREE.Vector3().fromBufferAttribute(
    line.geometry.getAttribute('position'),
    0
  );
  expect(first.distanceTo(earthPoint(0, 180, 2.033))).toBeLessThan(1e-6);
  drawing.dispose();
});
it('rejects ambiguous antipodal arcs without allocating invented highlights', () => {
  const f = routeSnapshot(),
    entry = routeSigmetSnapshotSchema.parse(f.snapshot).entries[0],
    budget = new WeatherBudget();
  expect(() =>
    createSigmetHighlights(
      {
        entry,
        reports: parseAviationFeatures(f.data, 'sigmet').features,
        label: 'ambiguous',
        color: '#fff',
        intersectionUnknown: false,
      },
      [
        { longitude: 0, latitude: 0 },
        { longitude: 180, latitude: 0 },
      ],
      budget
    )
  ).toThrow();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
it('keeps valid near-antipodal arcs finite and original fractional positions on the unit sphere', () => {
  const f = routeSnapshot(),
    entry = routeSigmetSnapshotSchema.parse(f.snapshot).entries[0];
  const drawing = createSigmetHighlights(
    {
      entry,
      reports: parseAviationFeatures(f.data, 'sigmet').features,
      label: 'long arc',
      color: '#fff',
      intersectionUnknown: false,
    },
    [
      { longitude: 0, latitude: 0 },
      { longitude: 179.99999, latitude: 0 },
    ],
    new WeatherBudget()
  );
  const line = drawing.object.getObjectByName(
    'Confirmed route span'
  ) as THREE.Line;
  const positions = line.geometry.getAttribute('position');
  const first = new THREE.Vector3().fromBufferAttribute(positions, 0);
  const last = new THREE.Vector3().fromBufferAttribute(
    positions,
    positions.count - 1
  );
  expect(first.distanceTo(earthPoint(0, 44.9999975, 2.033))).toBeLessThan(1e-6);
  expect(last.distanceTo(earthPoint(0, 134.9999925, 2.033))).toBeLessThan(1e-6);
  drawing.dispose();
});
it('rejects excessive per-span native object overhead within the shared decoded budget', () => {
  const f = routeSnapshot(),
    entry = routeSigmetSnapshotSchema.parse(f.snapshot).entries[0],
    budget = new WeatherBudget();
  entry.spans = Array.from({ length: 10000 }, () => ({
    ...entry.spans[0],
    start_fraction: 0.5,
    end_fraction: 0.5,
  }));
  let drawing: ReturnType<typeof createSigmetHighlights> | undefined;
  try {
    expect(() => {
      drawing = createSigmetHighlights(
        {
          entry,
          reports: parseAviationFeatures(f.data, 'sigmet').features,
          label: 'large',
          color: '#fff',
          intersectionUnknown: false,
        },
        [
          { longitude: 0, latitude: 0 },
          { longitude: 10, latitude: 0 },
        ],
        budget
      );
    }).toThrow(/budget/i);
  } finally {
    drawing?.dispose();
  }
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});

it('highlights a selected polygon without route spans', () => {
  const f = routeSnapshot();
  const entry = JSON.parse(
    JSON.stringify(routeSigmetSnapshotSchema.parse(f.snapshot).entries[0])
  );
  delete entry.spans;
  const feature = parseAviationFeatures(f.data, 'sigmet').features[0];
  const budget = new WeatherBudget();
  const drawing = createSigmetHighlights(
    { entry, reports: [feature], label: 'Selected', color: '#7dd3fc' },
    [],
    budget
  );
  try {
    expect(
      drawing.object.getObjectByName('Route advisory outline')
    ).toBeDefined();
    expect(
      drawing.object.getObjectByName('Route advisory span')
    ).toBeUndefined();
  } finally {
    drawing.dispose();
  }
  expect(budget.snapshot().gpu).toBe(0);
});
