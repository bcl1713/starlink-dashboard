import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OrbitalLifecycle } from './lifecycle';
import type { CatalogEnvelope, OrbitalSnapshot } from './types';
import { referenceOmm } from './test-fixtures';

const enabled = {
  orbital_traffic_enabled: true,
  starshield_link_enabled: true,
  x_band_link_enabled: false,
};
const endpoints = { aircraft: null, pop: null };
const catalog: CatalogEnvelope = {
  objects: [referenceOmm],
  generation: 'g',
  acquired_at: referenceOmm.EPOCH,
  last_attempt_at: null,
  retry_after_at: null,
  suspended: false,
  rejected_count: 0,
  truncated_count: 0,
  eligible_count: 1,
  status: 'ready',
};
const snapshots = () =>
  ({
    generation: 1,
    catalogGeneration: 'g',
    bankId: 0,
    utcMs: Date.now(),
    ids: ['5'],
    positionsKm: new Float64Array([7000, 0, 0]),
    valid: new Uint8Array([1]),
    route: null,
    updateMs: 1,
  }) as OrbitalSnapshot;
function setup() {
  let receive!: (s: OrbitalSnapshot) => void, fail!: (e: Error) => void;
  const worker = {
    start: vi.fn(),
    setEndpoints: vi.fn(),
    recycle: vi.fn(),
    dispose: vi.fn(),
  };
  const api = {
    acquire: vi.fn().mockImplementation(async () => ({
      expires_at: new Date(Date.now() + 75000).toISOString(),
    })),
    release: vi.fn().mockResolvedValue(undefined),
    catalog: vi.fn().mockResolvedValue(catalog),
  };
  const factory = vi.fn((_generation, received, failure) => {
    receive = received;
    fail = failure;
    return worker;
  });
  const refresh = vi.fn().mockResolvedValue(enabled);
  const lifecycle = new OrbitalLifecycle({
    api,
    workerFactory: factory,
    refreshSettings: refresh,
  });
  return {
    lifecycle,
    api,
    factory,
    worker,
    refresh,
    receive: (s = snapshots()) => receive(s),
    fail: () => fail(new Error('broken')),
  };
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(referenceOmm.EPOCH));
});
afterEach(() => vi.useRealTimers());
async function flush() {
  await vi.advanceTimersByTimeAsync(0);
}

it.each([
  undefined,
  { ...enabled, orbital_traffic_enabled: false },
  { ...enabled, starshield_link_enabled: false },
])('inactive_means_no_orbital_resources: %j', async (settings) => {
  const f = setup();
  f.lifecycle.update(settings, endpoints);
  await flush();
  expect(f.api.acquire).not.toHaveBeenCalled();
  expect(f.api.catalog).not.toHaveBeenCalled();
  expect(f.factory).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
  f.lifecycle.dispose();
});
it('initially hidden does no work; visible resume rechecks settings before acquiring', async () => {
  const f = setup();
  f.lifecycle.setVisible(false);
  f.lifecycle.update(enabled, endpoints);
  await flush();
  expect(f.api.acquire).not.toHaveBeenCalled();
  f.refresh.mockResolvedValue({ ...enabled, orbital_traffic_enabled: false });
  f.lifecycle.setVisible(true);
  await flush();
  expect(f.refresh).toHaveBeenCalledTimes(1);
  expect(f.api.acquire).not.toHaveBeenCalled();
  f.lifecycle.dispose();
});
it('polls and renews only while active; unchanged catalogs do not reinstall elements', async () => {
  const f = setup();
  f.lifecycle.update(enabled, endpoints);
  await flush();
  expect(f.factory).toHaveBeenCalledTimes(1);
  // Worker heartbeat is controlled here; test the real lease/catalog clocks.
  const heartbeat = setInterval(() => f.receive(), 1000);
  await vi.advanceTimersByTimeAsync(60000);
  expect(f.api.acquire).toHaveBeenCalledTimes(3);
  expect(f.api.catalog).toHaveBeenCalledTimes(2);
  expect(f.worker.start).toHaveBeenCalledTimes(1);
  clearInterval(heartbeat);
  f.lifecycle.dispose();
  expect(vi.getTimerCount()).toBe(0);
  expect(f.worker.dispose).toHaveBeenCalledTimes(1);
});
it('hidden_disable_unmount_invalidate_every_generation including late lease success', async () => {
  const f = setup();
  let finish!: (value: { expires_at: string }) => void;
  f.api.acquire.mockReturnValue(
    new Promise((done) => {
      finish = done;
    })
  );
  f.lifecycle.update(enabled, endpoints);
  const signal = f.api.acquire.mock.calls[0][1] as AbortSignal;
  f.lifecycle.update({ ...enabled, orbital_traffic_enabled: false }, endpoints);
  expect(signal.aborted).toBe(true);
  finish({ expires_at: new Date(Date.now() + 75000).toISOString() });
  await flush();
  expect(f.api.catalog).not.toHaveBeenCalled();
  expect(f.factory).not.toHaveBeenCalled();
  expect(f.api.release).toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
  f.lifecycle.dispose();
});
it('late catalog and worker callbacks cannot recreate resources after teardown', async () => {
  const f = setup();
  let finish!: (value: CatalogEnvelope) => void;
  f.api.catalog.mockReturnValueOnce(
    new Promise((done) => {
      finish = done;
    })
  );
  f.lifecycle.update(enabled, endpoints);
  await flush();
  f.lifecycle.dispose();
  finish(catalog);
  await flush();
  expect(f.factory).not.toHaveBeenCalled();
  const g = setup();
  g.lifecycle.update(enabled, endpoints);
  await flush();
  g.lifecycle.dispose();
  g.receive();
  g.fail();
  expect(g.lifecycle.getState().current).toBeNull();
  expect(g.lifecycle.getState().status.kind).toBe('off');
});
it('worker_failure_latches_until_explicit_retry and survives visibility changes', async () => {
  const f = setup();
  f.lifecycle.update(enabled, endpoints);
  await flush();
  f.fail();
  expect(f.lifecycle.getState().status.kind).toBe('worker-failed');
  expect(f.worker.dispose).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
  f.lifecycle.setVisible(false);
  f.lifecycle.setVisible(true);
  await flush();
  expect(f.factory).toHaveBeenCalledTimes(1);
  f.lifecycle.update({ ...enabled, orbital_traffic_enabled: false }, endpoints);
  f.lifecycle.update(enabled, endpoints);
  await flush();
  expect(f.factory).toHaveBeenCalledTimes(2);
  f.lifecycle.dispose();
});
it('watchdog timeout and construction failure both latch and release demand', async () => {
  const f = setup();
  f.lifecycle.update(enabled, endpoints);
  await flush();
  await vi.advanceTimersByTimeAsync(5000);
  expect(f.lifecycle.getState().status.kind).toBe('worker-failed');
  expect(vi.getTimerCount()).toBe(0);
  const g = setup();
  g.factory.mockImplementation(() => {
    throw new Error('cannot construct');
  });
  g.lifecycle.update(enabled, endpoints);
  await flush();
  expect(g.lifecycle.getState().status.kind).toBe('worker-failed');
  expect(g.api.release).toHaveBeenCalled();
  f.lifecycle.dispose();
  g.lifecycle.dispose();
});
it('fifty toggles and StrictMode setup-cleanup-setup release all owned timers', async () => {
  const f = setup();
  for (let i = 0; i < 50; i++) {
    f.lifecycle.mount();
    f.lifecycle.update(enabled, endpoints);
    await flush();
    f.lifecycle.update(
      { ...enabled, orbital_traffic_enabled: false },
      endpoints
    );
    expect(vi.getTimerCount()).toBe(0);
  }
  f.lifecycle.dispose();
  f.lifecycle.mount();
  f.lifecycle.update(enabled, endpoints);
  await flush();
  f.lifecycle.dispose();
  expect(vi.getTimerCount()).toBe(0);
  expect(f.factory.mock.calls.length).toBe(f.worker.dispose.mock.calls.length);
});
it('failed lease renewal never keeps worker beyond the last confirmed expiry', async () => {
  const f = setup();
  f.lifecycle.update(enabled, endpoints);
  await flush();
  const heartbeat = setInterval(() => f.receive(), 1000);
  f.api.acquire.mockRejectedValue(new Error('lease failure'));
  await vi.advanceTimersByTimeAsync(75000);
  expect(f.worker.dispose).toHaveBeenCalledTimes(1);
  expect(f.lifecycle.getState().spritesReady).toBe(false);
  clearInterval(heartbeat);
  f.lifecycle.dispose();
  expect(vi.getTimerCount()).toBe(0);
});

it('initial lease failure recovers on renewal without requiring a worker retry toggle', async () => {
  const f = setup();
  f.api.acquire.mockRejectedValueOnce(new Error('temporarily unavailable'));
  f.lifecycle.update(enabled, endpoints);
  await flush();
  expect(f.factory).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(30000);
  expect(f.factory).toHaveBeenCalledTimes(1);
  f.lifecycle.dispose();
  expect(vi.getTimerCount()).toBe(0);
});
