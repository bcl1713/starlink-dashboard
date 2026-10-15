import { describe, it, expect } from 'vitest';
import {
  decodePayload,
  labels,
  Allocation,
  type Descriptor,
} from '../../tests/e2e/support/aviation-weather-proof/model';
import {
  sampleGrid,
  barb,
} from '../../tests/e2e/support/aviation-weather-proof/sampling';
const grid = {
  width: 720,
  height: 361,
  longitude_start: -180,
  longitude_step: 0.5,
  latitude_start: 90,
  latitude_step: -0.5,
};
const descriptor = {
  schema: 'aviation-weather-v1',
  representation: 'latlon-grid-v1',
  grid,
  components: {
    t: {
      scale: 0.01,
      offset: 273.15,
      units: 'K',
      byte_size: 519840,
      sha256: '0'.repeat(64),
    },
  },
  mask: { byte_size: 259920, sha256: '0'.repeat(64) },
} as Descriptor;
describe('aviation native proof', () => {
  it('test_grid_length_and_hash_rejection', async () => {
    const bytes = new Uint8Array([255, 255, 0, 128]);
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
    )
      .map((x) => x.toString(16).padStart(2, '0'))
      .join('');
    expect([
      ...(await decodePayload(
        bytes.buffer,
        { byte_size: 4, sha256: hash, dtype: 'int16-le' },
        2
      )),
    ]).toEqual([-1, -32768]);
    await expect(
      decodePayload(
        bytes.buffer,
        { byte_size: 3, sha256: hash, dtype: 'int16-le' },
        2
      )
    ).rejects.toThrow(/length/);
    await expect(
      decodePayload(
        bytes.buffer,
        { byte_size: 4, sha256: '0'.repeat(64), dtype: 'int16-le' },
        2
      )
    ).rejects.toThrow(/hash/);
  });
  it('test_cpu_seam_pole_and_masks', () => {
    const values = new Int16Array(720 * 361).fill(-100),
      mask = new Uint8Array(values.length);
    values[719] = 100;
    expect(sampleGrid(descriptor, values, mask, 90, 179.75).value).toBeCloseTo(
      273.15
    );
    expect(sampleGrid(descriptor, values, mask, -90, 0).value).toBeCloseTo(
      272.15
    );
    mask[361] = 3; // zero-weight neighbor still invalid
    expect(sampleGrid(descriptor, values, mask, 90, 0)).toEqual({
      value: null,
      mask: 3,
    });
    expect(
      sampleGrid(
        { ...descriptor, grid: { ...grid, width: 2, height: 2 } },
        new Int16Array(4),
        new Uint8Array(4),
        0,
        0
      ).mask
    ).toBe(1);
  });
  it('test_scan_interval_label', () => {
    const text = labels({
      ...descriptor,
      source_id: 'GOES19',
      scan_start_ms: 1791244820900,
      scan_end_ms: 1791245392800,
    });
    expect(text).toContain('2026-10-06T00:00:20.900Z');
    expect(text).toContain('2026-10-06T00:09:52.800Z');
    expect(text).toContain('brightness temperature');
  });
  it('test_mosaic_lists_each_scan', () => {
    const text = labels({
      ...descriptor,
      region_intervals: [
        { region: 'A', scan_start_ms: 0, scan_end_ms: 1000 },
        { region: 'B', scan_start_ms: 2000, scan_end_ms: 3000 },
      ],
    });
    expect(text).toContain('A: 1970-01-01T00:00:00.000Z');
    expect(text).toContain('B: 1970-01-01T00:00:02.000Z');
  });
  it('test_empty_advisory_label', () => {
    const text = labels({
      ...descriptor,
      representation: 'advisory-v1',
      diagnostic_replay_at_ms: 1791288447898,
      coverage: { completeness: 'unverified' },
    });
    expect(text).toContain('Coverage unverified');
    expect(text).toContain('2026-10-06T12:07:27.898Z');
    expect(text).not.toMatch(/no hazards|worldwide clear/i);
  });
  it('test_allocation_and_failed_install_cleanup', () => {
    const pool = new Allocation();
    const old = pool.reserve(8e6, 8e6, 4e6);
    expect(() => pool.reserve(9e6, 8e6, 4e6)).toThrow(/budget/);
    expect(() => pool.reserve(1, 26e6, 1)).toThrow(/budget/);
    expect(() => pool.reserve(1, 1, 13e6)).toThrow(/budget/);
    expect(pool.current).toEqual({ encoded: 8e6, decoded: 8e6, gpu: 4e6 });
    old();
    old();
    expect(pool.current).toEqual({ encoded: 0, decoded: 0, gpu: 0 });
  });
  it('wind barbs use FROM direction and knots nearest five', () => {
    expect(barb(10, 0)).toEqual({ fromEast: -1, fromNorth: 0, knots: 20 });
    expect(barb(0, -10).fromNorth).toBe(1);
  });
});

it('triangle planes describe the actual tessellated mesh within the reserved geometry budget', async () => {
  const { gridMesh, geometryBytes } = await import(
    '../../tests/e2e/support/aviation-weather-proof/grid-renderer'
  );
  const owned = gridMesh(
    descriptor,
    new Int16Array(720 * 361),
    new Uint8Array(720 * 361)
  );
  try {
    const positions = owned.mesh.geometry.getAttribute('position');
    const planes = owned.mesh.geometry.getAttribute('trianglePlane');
    expect(planes).toBeDefined();
    expect(geometryBytes(owned.mesh.geometry)).toBeLessThan(3_000_000);
    for (let i = 0; i < positions.count; i++) {
      const residual =
        positions.getX(i) * planes.getX(i) +
        positions.getY(i) * planes.getY(i) +
        positions.getZ(i) * planes.getZ(i) -
        planes.getW(i);
      expect(Math.abs(residual)).toBeLessThan(0.000001);
    }
  } finally {
    owned.dispose();
  }
});

it('replacement waits for obsolete work cleanup and cancels stale generations', async () => {
  const { InstallQueue } = await import(
    '../../tests/e2e/support/aviation-weather-proof/model'
  );
  const queue = new InstallQueue();
  let release!: () => void;
  let started!: () => void;
  const ready = new Promise<void>((resolve) => {
    started = resolve;
  });
  let active = 0,
    peak = 0;
  const first = queue.run(async (signal) => {
    active++;
    peak = Math.max(peak, active);
    started();
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    active--;
    signal.throwIfAborted();
    return 'stale';
  });
  await ready;
  const rejected = expect(first).rejects.toThrow();
  const last = queue.run(async () => {
    active++;
    peak = Math.max(peak, active);
    active--;
    return 'current';
  });
  release();
  await rejected;
  expect(await last).toBe('current');
  expect(peak).toBe(1);
});

it('outlines exterior and hole rings with tessellation, accounting and disposal', async () => {
  const { advisoryMesh } = await import(
    '../../tests/e2e/support/aviation-weather-proof/advisory-renderer'
  );
  const owned = advisoryMesh(
    [
      {
        id: 'hole',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [0, 0],
              [10, 0],
              [10, 10],
              [0, 10],
              [0, 0],
            ],
            [
              [2, 2],
              [2, 4],
              [4, 4],
              [4, 2],
              [2, 2],
            ],
          ],
        },
        properties: {
          validity: { start_ms: 0, end_ms: 10 },
          cancellation: { cancelled: false },
          status: 'active',
        },
      },
    ],
    5
  );
  try {
    const outline = owned.mesh.children.find(
      (o) => o.type === 'LineSegments'
    ) as import('three').LineSegments;
    expect(outline).toBeDefined();
    expect(outline.geometry.getAttribute('position').count).toBe(96); // 80 exterior + 16 hole vertices at one-degree segments
    expect(owned.bytes).toBe(
      owned.mesh.geometry.getAttribute('position').array.byteLength +
        outline.geometry.getAttribute('position').array.byteLength
    );
    let disposed = 0;
    outline.geometry.addEventListener('dispose', () => disposed++);
    owned.dispose();
    expect(disposed).toBe(1);
  } finally {
    owned.dispose();
  }
});
it('labels the selected bulletin identity, half-open validity and explicit vertical context', async () => {
  const module = await import(
    '../../tests/e2e/support/aviation-weather-proof/advisory-renderer'
  );
  expect('advisoryContext' in module).toBe(true);
  const f = {
    id: 'selected',
    geometry: null,
    properties: {
      issuer: 'PHFO',
      fir_id: 'KZAK',
      series_id: 'VICTOR 6',
      hazard: 'TC',
      qualifier: 'KOGUMA',
      validity: { start_ms: 1791271800000, end_ms: 1791293400000 },
      cancellation: { cancelled: false },
      status: 'active',
      vertical: { status: 'unknown' },
    },
  };
  const label = (
    module as unknown as { advisoryContext: (f: unknown) => string }
  ).advisoryContext(f);
  for (const part of [
    'PHFO',
    'KZAK',
    'VICTOR 6',
    'TC',
    'KOGUMA',
    '[2026-10-06T07:30:00.000Z, 2026-10-06T13:30:00.000Z)',
    'vertical unknown',
  ])
    expect(label).toContain(part);
});
it.each([
  [1, 3, 0, 0, 3],
  [1, 2, 0, 0, 2],
  [2, 1, 3, 0, 3],
])(
  'uses categorical maximum for mixed masks %s %s %s %s',
  (a, b, c, d, want) => {
    expect(
      sampleGrid(
        { ...descriptor, grid: { ...grid, width: 2, height: 2 } },
        new Int16Array(4),
        new Uint8Array([a, b, c, d]),
        89.75,
        -179.75
      )
    ).toEqual({ value: null, mask: want });
  }
);

it('retains known advisory vertical units and reference', async () => {
  const { advisoryContext } = await import(
    '../../tests/e2e/support/aviation-weather-proof/advisory-renderer'
  );
  const label = advisoryContext({
    id: 'known',
    geometry: null,
    properties: {
      validity: { start_ms: 0, end_ms: 10 },
      status: 'active',
      cancellation: { cancelled: false },
      vertical: {
        status: 'known',
        base: {
          kind: 'flight-level',
          value: 200,
          units: 'hundreds-of-feet',
          reference: 'standard-pressure',
        },
        top: {
          kind: 'flight-level',
          value: 300,
          units: 'hundreds-of-feet',
          reference: 'standard-pressure',
        },
      },
    },
  });
  expect(label).toContain(
    'flight-level 200 hundreds-of-feet standard-pressure → flight-level 300 hundreds-of-feet standard-pressure'
  );
});
