import { describe, expect, it } from 'vitest';
import { routeContextKey } from './route-sigmet-context';

describe('route context identity', () => {
  it.each([
    [
      'ordinary',
      'route-a',
      null,
      null,
      [
        [0, 0],
        [10, 20],
      ],
      '81b5005f4d0711b931d6b0853b6fc923729764774718cd3f1ec3a582b64534a7',
    ],
    [
      'simulation',
      'røute',
      'runtime-1',
      'run-1',
      [
        [-180, -90],
        [180, 90],
      ],
      'ebb5168797fc4f6cd95dab3937a549ec1cf6ebd7acf6978f07c3ba90df3da05c',
    ],
  ] as const)(
    'matches pinned Python bytes for %s',
    (source, id, runtime, run, points, digest) => {
      expect(routeContextKey(source, id, runtime, run, points)).toBe(digest);
    }
  );
  it('canonicalizes zero and distinguishes reversed geometry and new runs', () => {
    const key = routeContextKey('ordinary', 'route-a', null, null, [
      [0, -0],
      [10, 20],
    ]);
    expect(
      routeContextKey('ordinary', 'route-a', null, null, [
        [-0, 0],
        [10, 20],
      ])
    ).toBe(key);
    expect(
      routeContextKey('ordinary', 'route-a', null, null, [
        [10, 20],
        [0, 0],
      ])
    ).not.toBe(key);
    expect(
      routeContextKey('simulation', 'route-a', 'runtime', 'run-1', [
        [0, 0],
        [10, 20],
      ])
    ).not.toBe(
      routeContextKey('simulation', 'route-a', 'runtime', 'run-2', [
        [0, 0],
        [10, 20],
      ])
    );
  });
  it.each(
    [
      [[181, 0]],
      [[0, 91]],
      [[0, Infinity]],
      Array.from({ length: 20001 }, () => [0, 0]),
    ].map((points) => [points])
  )('rejects invalid or oversized geometry', (points) => {
    expect(() =>
      routeContextKey('ordinary', 'route-a', null, null, points)
    ).toThrow();
  });
});
