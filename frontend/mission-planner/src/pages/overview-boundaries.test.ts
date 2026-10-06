import { describe, expect, it } from 'vitest';
import { parseBoundaries, projectBoundaries } from './overview-boundaries';

const data = (points: number[][], disputed = false) => ({
  version: 1,
  lines: [{ points, disputed }],
});
describe('boundary geometry', () => {
  it('takes the short path across the International Date Line', () => {
    const { standard } = projectBoundaries(
      parseBoundaries(
        data([
          [179, 0],
          [-179, 0],
        ])
      )
    );
    expect(standard.length).toBeGreaterThan(6);
    for (let i = 0; i < standard.length; i += 3) {
      expect(standard[i]).toBeLessThan(-1.99);
      expect(Math.abs(standard[i + 2])).toBeLessThan(0.04);
    }
  });
  it('densifies polar parallels without cutting through the globe', () => {
    const { standard } = projectBoundaries(
      parseBoundaries(
        data([
          [-45, 80],
          [45, 80],
        ])
      )
    );
    for (let i = 0; i < standard.length; i += 6) {
      const a = standard.slice(i, i + 3),
        b = standard.slice(i + 3, i + 6);
      expect(a[1]).toBeCloseTo(1.9698, 3);
      expect(Math.hypot(...a)).toBeGreaterThan(2);
      expect(
        Math.hypot(...a.map((value, j) => (value + b[j]) / 2))
      ).toBeGreaterThan(2);
    }
  });
  it('never joins separate features and separates disputed linework', () => {
    const projected = projectBoundaries(
      parseBoundaries({
        version: 1,
        lines: [
          {
            points: [
              [0, 0],
              [0.1, 0],
            ],
            disputed: false,
          },
          {
            points: [
              [150, 0],
              [150.1, 0],
            ],
            disputed: false,
          },
          {
            points: [
              [10, 10],
              [10.1, 10],
            ],
            disputed: true,
          },
        ],
      })
    );
    expect(projected.standard).toHaveLength(12);
    expect(projected.disputed).toHaveLength(6);
  });
  it.each([
    {},
    { version: 2, lines: [] },
    data([
      [0, 91],
      [1, 0],
    ]),
    data([
      [181, 0],
      [0, 0],
    ]),
    data([
      [NaN, 0],
      [0, 0],
    ]),
    data([[0, 0]]),
    {
      version: 1,
      lines: [
        {
          points: [
            [0, 0],
            [1, 0],
          ],
          disputed: 'true',
        },
      ],
    },
  ])('rejects malformed data instead of disrupting the globe: %j', (input) => {
    expect(() => parseBoundaries(input)).toThrow();
  });
  it('rejects data exceeding the point budget', () => {
    expect(() =>
      parseBoundaries(data(Array.from({ length: 120001 }, () => [0, 0])))
    ).toThrow();
  });
});

it('projects the shipped worldwide data within geometry budgets', async () => {
  const { readFileSync } = await import('node:fs');
  for (const kind of ['countries', 'subdivisions']) {
    const source = readFileSync(
      new URL(`../../public/boundaries/${kind}.json`, import.meta.url),
      'utf8'
    );
    expect(source.length).toBeLessThan(4_000_000);
    const parsed = parseBoundaries(JSON.parse(source));
    const { standard, disputed } = projectBoundaries(parsed);
    expect(standard.length + disputed.length).toBeGreaterThan(1000);
    expect(standard.length + disputed.length).toBeLessThan(1_500_000);
  }
});
