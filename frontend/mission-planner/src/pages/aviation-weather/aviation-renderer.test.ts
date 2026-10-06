import { describe, expect, it, vi } from 'vitest';
import { earthPoint, createAviationDrawing } from './aviation-renderer';
import { parseAviationFeatures } from '@/services/aviation-features';
import { NOW, station, advisory, collection } from './fixtures';
describe('native aviation geometry', () => {
  it('matches the native coordinate handedness', () => {
    expect(earthPoint(0, 0).toArray()).toEqual([2.026, 0, -0]);
    expect(earthPoint(0, 90).z).toBeCloseTo(-2.026);
    expect(earthPoint(90, 0).y).toBeCloseTo(2.026);
  });
  it('bounds station drawing and distinguishes forecast diamonds', () => {
    const metar = createAviationDrawing(
      parseAviationFeatures(collection([station()]), 'metar'),
      'metar',
      NOW
    );
    const taf = createAviationDrawing(
      parseAviationFeatures(collection([station(true)]), 'taf'),
      'taf',
      NOW
    );
    expect(metar.bytes).toBeGreaterThan(0);
    expect(taf.bytes).toBeGreaterThan(0);
    expect(metar.object.type).toBe('Points');
    expect(taf.object.type).toBe('LineSegments');
    metar.dispose();
    taf.dispose();
  });
  it('keeps polygon holes empty and triangles above the globe, disposes allocations', () => {
    const d = createAviationDrawing(
      parseAviationFeatures(collection([advisory()]), 'sigmet'),
      'sigmet',
      NOW
    );
    const mesh = d.object as import('three').Mesh;
    const positions = mesh.geometry.getAttribute('position');
    for (let i = 0; i < positions.count; i += 3) {
      const projected = [0, 1, 2].map((n) => {
        const x = positions.getX(i + n),
          y = positions.getY(i + n),
          z = positions.getZ(i + n);
        return [
          (Math.atan2(-z, x) * 180) / Math.PI,
          (Math.asin(y / Math.hypot(x, y, z)) * 180) / Math.PI,
        ];
      });
      const x = projected.reduce((s, p) => s + p[0], 0) / 3,
        y = projected.reduce((s, p) => s + p[1], 0) / 3;
      expect(x > 1.001 && x < 2.999 && y > 1.001 && y < 2.999).toBe(false);
    }
    const dispose = vi.spyOn(mesh.geometry, 'dispose');
    d.dispose();
    expect(dispose).toHaveBeenCalledOnce();
    const expired = createAviationDrawing(
      parseAviationFeatures(collection([advisory()]), 'sigmet'),
      'sigmet',
      NOW + 3600000
    );
    expect(
      (expired.object as import('three').Mesh).geometry.getAttribute('position')
        .count
    ).toBe(0);
    expired.dispose();
  });
  it('rejects geometry exceeding rendered vertex admission', () => {
    const a = advisory();
    a.geometry.coordinates = [
      [
        [0, -80],
        [179, -80],
        [179, 80],
        [0, 80],
        [0, -80],
      ],
    ];
    expect(() =>
      createAviationDrawing(
        parseAviationFeatures(
          collection([a, { ...a, id: 'second-advisory' }]),
          'sigmet'
        ),
        'sigmet',
        NOW
      )
    ).toThrow(/budget/);
  });
});

it('rejects self-intersecting and exterior holes before Canvas attachment', () => {
  const a = advisory();
  a.geometry.coordinates = [
    [
      [0, 0],
      [4, 4],
      [4, 0],
      [0, 4],
      [0, 0],
    ],
  ];
  expect(() =>
    createAviationDrawing(
      parseAviationFeatures(collection([a]), 'sigmet'),
      'sigmet',
      NOW
    )
  ).toThrow();
  a.geometry.coordinates = [
    [
      [0, 0],
      [4, 0],
      [4, 4],
      [0, 4],
      [0, 0],
    ],
    [
      [5, 5],
      [5, 6],
      [6, 6],
      [6, 5],
      [5, 5],
    ],
  ];
  expect(() =>
    createAviationDrawing(
      parseAviationFeatures(collection([a]), 'sigmet'),
      'sigmet',
      NOW
    )
  ).toThrow();
});
