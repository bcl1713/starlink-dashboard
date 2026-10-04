import { afterEach, expect, it, vi } from 'vitest';
import { OrbitalWorkerClient } from './worker-client';
import { OrbitalWorkerRuntime } from './worker-protocol';
import type { CatalogEnvelope, OrbitalSnapshot } from './types';
import { referenceOmm } from './test-fixtures';
import * as routing from './routing';

const catalog: CatalogEnvelope = {
  objects: [referenceOmm],
  generation: 'catalog-a',
  acquired_at: referenceOmm.EPOCH,
  last_attempt_at: null,
  retry_after_at: null,
  suspended: false,
  rejected_count: 0,
  truncated_count: 0,
  eligible_count: 1,
  status: 'ready',
};
afterEach(() => vi.useRealTimers());

it('selects at most every five seconds while checking current PoP validity on each snapshot', async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(referenceOmm.EPOCH));
  const selection = vi.spyOn(routing, 'selectRoute');
  const snapshots: OrbitalSnapshot[] = [];
  const runtime = new OrbitalWorkerRuntime((message, transfer) => {
    const cloned = structuredClone(message, { transfer });
    if (cloned.type === 'snapshot') {
      snapshots.push(cloned.snapshot);
      if (snapshots.length > 2) {
        const old = snapshots.shift()!;
        runtime.receive(
          structuredClone(
            { type: 'recycle', generation: 1, snapshot: old },
            { transfer: [old.positionsKm.buffer, old.valid.buffer] }
          )
        );
      }
    }
  });
  try {
    runtime.receive({ type: 'start', generation: 1, catalog });
    const p = snapshots[0].positionsKm;
    const scale = 6378.137 / Math.hypot(...p);
    const ground = [p[0] * scale, p[1] * scale, p[2] * scale] as const;
    runtime.receive({
      type: 'endpoints',
      generation: 1,
      endpoints: { aircraft: ground, pop: ground },
    });
    await vi.advanceTimersByTimeAsync(5000);
    expect(snapshots.at(-1)?.route?.ids).toEqual(['5']);
    expect(selection).toHaveBeenCalledTimes(2);
    runtime.receive({
      type: 'endpoints',
      generation: 1,
      endpoints: {
        aircraft: ground,
        pop: [ground[0], ground[1] + 1, ground[2]],
      },
    });
    await vi.advanceTimersByTimeAsync(1000);
    expect(snapshots.at(-1)?.route).toBeNull();
    expect(selection).toHaveBeenCalledTimes(2);
  } finally {
    runtime.dispose();
    selection.mockRestore();
  }
});

it('one_second_snapshots_and_backpressure drops ticks after three banks and resumes current UTC', async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(referenceOmm.EPOCH));
  const delivered: OrbitalSnapshot[] = [];
  const runtime = new OrbitalWorkerRuntime((message, transfer) => {
    const cloned = structuredClone(message, { transfer });
    if (cloned.type === 'snapshot') delivered.push(cloned.snapshot);
  });
  runtime.receive({ type: 'start', generation: 1, catalog });
  expect(delivered).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(1000);
  expect(delivered).toHaveLength(2);
  await vi.advanceTimersByTimeAsync(1000);
  expect(delivered).toHaveLength(3);
  await vi.advanceTimersByTimeAsync(10000);
  expect(delivered).toHaveLength(3);
  const released = delivered[0];
  runtime.receive(
    structuredClone(
      { type: 'recycle', generation: 1, snapshot: released },
      { transfer: [released.positionsKm.buffer, released.valid.buffer] }
    )
  );
  await vi.advanceTimersByTimeAsync(1000);
  expect(delivered).toHaveLength(4);
  expect(delivered[3].utcMs).toBe(Date.now());
  expect(runtime.allocatedBanks).toBe(3);
  runtime.dispose();
  expect(vi.getTimerCount()).toBe(0);
});

it('client ignores old generations and late snapshot/error after disposal', () => {
  const fake = {
    postMessage: vi.fn(),
    terminate: vi.fn(),
    onmessage: null,
    onerror: null,
  };
  const snapshot = vi.fn(),
    error = vi.fn();
  const client = new OrbitalWorkerClient(4, snapshot, error, () => fake);
  client.start(catalog);
  const message = fake.onmessage as unknown as (event: {
    data: unknown;
  }) => void;
  const failure = fake.onerror as unknown as () => void;
  message({ data: { type: 'snapshot', generation: 3, snapshot: {} } });
  expect(snapshot).not.toHaveBeenCalled();
  expect(error).not.toHaveBeenCalled();
  message({ data: { type: 'snapshot', generation: 4, snapshot: {} } });
  expect(error).toHaveBeenCalledTimes(1);
  client.dispose();
  message({ data: { type: 'snapshot', generation: 4, snapshot: {} } });
  failure();
  expect(error).toHaveBeenCalledTimes(1);
  expect(fake.terminate).toHaveBeenCalledTimes(1);
});

it('catalog generation changes reuse three banks and discard stale ID mapping', async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(referenceOmm.EPOCH));
  const received: OrbitalSnapshot[] = [];
  const runtime = new OrbitalWorkerRuntime((msg) => {
    if (msg.type === 'snapshot') received.push(msg.snapshot);
  });
  runtime.receive({ type: 'start', generation: 1, catalog });
  runtime.receive({
    type: 'start',
    generation: 1,
    catalog: {
      ...catalog,
      generation: 'catalog-b',
      objects: [{ ...referenceOmm, NORAD_CAT_ID: '100001' }],
    },
  });
  expect(received.at(-1)?.catalogGeneration).toBe('catalog-b');
  expect(received.at(-1)?.ids).toEqual(['100001']);
  expect(runtime.allocatedBanks).toBe(3);
  runtime.dispose();
});
