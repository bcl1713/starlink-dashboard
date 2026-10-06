import { describe, expect, it } from 'vitest';
import {
  calloutLeader,
  disclosureBounds,
  layoutOverviewLabels,
  type ProjectedOverviewLabel,
} from './overview-label-layout';

function label(id: string, width = 96): ProjectedOverviewLabel {
  return {
    id,
    bounds: { x: 900, y: 500, width, height: 20 },
  };
}

function overlaps(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number }
) {
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}

describe('layoutOverviewLabels', () => {
  it('keeps the 27-02 Exit label east of Enter at full-route zoom', () => {
    const labels = [
      {
        id: 'commka-enter',
        bounds: { x: 978, y: 564, width: 112, height: 28 },
      },
      { id: 'commka-exit', bounds: { x: 982, y: 565, width: 100, height: 28 } },
    ];
    const result = layoutOverviewLabels(labels, { width: 1920, height: 1080 });
    const enterCenter = 978 + result.offsets['commka-enter'][0] + 56;
    const exitCenter = 982 + result.offsets['commka-exit'][0] + 50;
    expect(exitCenter).toBeGreaterThanOrEqual(enterCenter);
  });

  it('preserves an unrelated label when a distant crowded group cannot fit', () => {
    const result = layoutOverviewLabels(
      [
        { id: 'crowded', bounds: { x: 50, y: 50, width: 500, height: 28 } },
        { id: 'unrelated', bounds: { x: 290, y: 200, width: 60, height: 28 } },
      ],
      { width: 390, height: 280 }
    );
    expect(result.offsets.unrelated).toBeDefined();
  });

  it('places eight projected generated labels without reusing an occupied box', () => {
    const result = layoutOverviewLabels(
      [
        'departure',
        'arrival',
        'x-band',
        'ka-entry',
        'ka-exit',
        'ka-swap',
        'aar-start',
        'aar-end',
      ].map((id, index) => label(id, 70 + index * 4)),
      { width: 1920, height: 1080 }
    );

    expect([
      ...new Set([
        ...Object.keys(result.offsets),
        ...result.groups.flatMap((g) => g.ids),
      ]),
    ]).toHaveLength(8);

    const boxes = Object.values(result.placements).map((p) => p.bounds);

    for (let index = 0; index < boxes.length; index += 1) {
      for (let other = index + 1; other < boxes.length; other += 1) {
        expect(overlaps(boxes[index], boxes[other])).toBe(false);
      }
    }
  });

  it('discloses only a crowded group while keeping all of its identities available', () => {
    const labels = Array.from({ length: 12 }, (_, index) => ({
      id: String(index),
      bounds: { x: 80, y: 80, width: 110, height: 28 },
    }));
    const result = layoutOverviewLabels(labels, { width: 220, height: 160 });
    expect(result.groups.length).toBeGreaterThan(0);
    const disclosed = result.groups.flatMap((group) => group.ids);
    const individual = Object.keys(result.offsets).filter(
      (id) => !disclosed.includes(id)
    );
    expect([...disclosed, ...individual].sort()).toEqual(
      labels.map((l) => l.id).sort()
    );
  });
});

it('ends a connecting line at the bubble border and leaves space around the marker', () => {
  expect(
    calloutLeader({ x: 100, y: 100 }, { x: 130, y: 80, width: 100, height: 40 })
  ).toEqual({ start: { x: 106, y: 100 }, end: { x: 130, y: 100 } });
});

it('keeps a valid previous placement when nearby points move slightly', () => {
  const labels = [
    { id: 'stable', bounds: { x: 200, y: 150, width: 90, height: 28 } },
  ];
  const first = layoutOverviewLabels(labels, { width: 800, height: 600 });
  const moved = layoutOverviewLabels(
    [{ ...labels[0], bounds: { ...labels[0].bounds, x: 202, y: 151 } }],
    { width: 800, height: 600 },
    [],
    first.offsets
  );
  expect(moved.offsets.stable).toEqual(first.offsets.stable);
});

it('shortens a stranded long stick after framing opens a nearby placement', () => {
  const result = layoutOverviewLabels(
    [{ id: 'airport', bounds: { x: 300, y: 200, width: 60, height: 28 } }],
    { width: 800, height: 600 },
    [],
    { airport: [180, -14] }
  );
  expect(Math.abs(result.offsets.airport[0])).toBeLessThan(60);
});

it('retains fifty ADS-B identities without collapsing them into a POI group', () => {
  const labels = Array.from({ length: 50 }, (_, index) => ({
    id: `adsb:${index}`,
    retainIdentity: true,
    bounds: { x: 400, y: 250, width: 120, height: 28 },
  }));
  const result = layoutOverviewLabels(labels, { width: 1920, height: 1080 });
  expect(result.groups).toEqual([]);
  expect(Object.keys(result.offsets)).toHaveLength(50);
  expect(
    new Set(Object.values(result.offsets).map((offset) => offset.join(',')))
      .size
  ).toBe(50);
});

it('flips and clamps an expanded disclosure inside the map viewport', () => {
  expect(
    disclosureBounds(
      { x: 250, y: 150, width: 96, height: 28 },
      { width: 220, height: 100 },
      { width: 320, height: 200 }
    )
  ).toEqual({ x: 94, y: 44, width: 220, height: 100 });
});

it('routes connecting lines clear of other event markers', () => {
  const anchors = [
    { x: 299, y: 291 },
    { x: 331, y: 289 },
    { x: 336, y: 287 },
    { x: 309, y: 296 },
  ];
  const result = layoutOverviewLabels(
    anchors.map((p, i) => ({
      id: String(i),
      bounds: { ...p, width: 90, height: 28 },
    })),
    { width: 700, height: 500 }
  );
  for (const [id, placement] of Object.entries(result.placements)) {
    const line = placement.leader;
    if (!line) continue;
    for (const [index, point] of anchors.entries()) {
      if (index === Number(id)) continue;
      const dx = line.end.x - line.start.x,
        dy = line.end.y - line.start.y;
      const t = Math.max(
        0,
        Math.min(
          1,
          ((point.x - line.start.x) * dx + (point.y - line.start.y) * dy) /
            (dx * dx + dy * dy)
        )
      );
      expect(
        Math.hypot(
          point.x - line.start.x - t * dx,
          point.y - line.start.y - t * dy
        )
      ).toBeGreaterThanOrEqual(4);
    }
  }
});

it('places a stage-local label outside reserved overlay rectangles', () => {
  const source = {
    id: 'next',
    bounds: { x: 120, y: 130, width: 70, height: 20 },
  };
  const blocked = { x: 110, y: 120, width: 120, height: 44 };
  const result = layoutOverviewLabels([source], { width: 390, height: 360 }, [
    blocked,
  ]);
  const offset = result.offsets.next;
  expect(
    overlaps(
      { ...source.bounds, x: 120 + offset[0], y: 130 + offset[1] },
      blocked
    )
  ).toBe(false);
});

it('revalidates an ADS-B previous stick when another marker moves into its path', () => {
  const result = layoutOverviewLabels(
    [
      {
        id: 'a',
        bounds: { x: 100, y: 100, width: 90, height: 28 },
        retainIdentity: true,
      },
      {
        id: 'b',
        bounds: { x: 125, y: 100, width: 90, height: 28 },
        retainIdentity: true,
      },
    ],
    { width: 700, height: 500 },
    [],
    { a: [80, -14] }
  );
  expect(result.offsets.a).not.toEqual([80, -14]);
  expect(result.offsets.b).toBeDefined();
  expect(result.groups).toEqual([]);
});

it('keeps every label kind clear of the full aircraft footprint during movement and text growth', () => {
  let previous = {};
  for (const [width, height] of [
    [1920, 1080],
    [390, 844],
    [844, 390],
  ]) {
    for (let frame = 0; frame < 30; frame++) {
      const aircraft = {
        x: width / 2 + frame - 45,
        y: height / 2 - 30,
        width: 90,
        height: 60,
      };
      const labels = ['adsb', 'poi', 'gep', 'satellite', 'own'].map(
        (kind, i) => ({
          id: kind,
          retainIdentity: kind === 'adsb',
          bounds: {
            x: width / 2 + i,
            y: height / 2,
            width: frame % 2 ? 220 : 100,
            height: frame % 2 ? 56 : 28,
          },
        })
      );
      const result = layoutOverviewLabels(
        labels,
        { width, height },
        [],
        previous,
        { aircraft: [aircraft] }
      );
      for (const placement of Object.values(result.placements))
        expect(overlaps(placement.bounds, aircraft)).toBe(false);
      previous = result.offsets;
    }
  }
});

it.each([true, false])(
  'suppresses an impossible label rather than putting its fallback over the aircraft (retain=%s)',
  (retainIdentity) => {
    const result = layoutOverviewLabels(
      [
        {
          id: 'crowded',
          retainIdentity,
          bounds: { x: 80, y: 80, width: 150, height: 28 },
        },
      ],
      { width: 220, height: 160 },
      [],
      {},
      { aircraft: [{ x: 0, y: 0, width: 220, height: 160 }] }
    );
    expect(result.placements).toEqual({});
    expect(result.groups).toEqual([]);
  }
);

it('prefers a placement clear of a displayed route and a POI halo', () => {
  const result = layoutOverviewLabels(
    [
      {
        id: 'traffic',
        retainIdentity: true,
        bounds: { x: 300, y: 200, width: 150, height: 28 },
      },
    ],
    { width: 700, height: 500 },
    [],
    {},
    {
      aircraft: [],
      markers: [{ x: 310, y: 180, width: 40, height: 40 }],
      paths: [{ start: { x: 330, y: 50 }, end: { x: 330, y: 400 } }],
    }
  );
  const box = result.placements.traffic.bounds;
  expect(box.x + box.width).toBeLessThan(310);
});

it('keeps feasible POI identities individual when only soft route paths obstruct them', () => {
  const labels = [
    { id: 'enter', bounds: { x: 348, y: 260, width: 112, height: 28 } },
    { id: 'exit', bounds: { x: 352, y: 261, width: 100, height: 28 } },
  ];
  const aircraft = { x: 320, y: 340, width: 70, height: 60 };
  const result = layoutOverviewLabels(
    labels,
    { width: 704, height: 500 },
    [],
    {},
    {
      aircraft: [aircraft],
      paths: Array.from({ length: 100 }, (_, i) => ({
        start: { x: 0, y: i * 5 },
        end: { x: 704, y: i * 5 },
      })),
    }
  );
  expect(result.groups).toEqual([]);
  expect(Object.keys(result.offsets).sort()).toEqual(['enter', 'exit']);
  const boxes = Object.values(result.placements).map((p) => p.bounds);
  expect(overlaps(boxes[0], boxes[1])).toBe(false);
  for (const box of boxes) expect(overlaps(box, aircraft)).toBe(false);
});
