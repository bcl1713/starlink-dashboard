import { afterEach, describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { GfsController } from './gfs-controller';
import { WeatherBudget } from './weather-budget';
import {
  parseGridDescriptor,
  type fetchGrid,
  type GridLease,
} from '@/services/aviation-grid';
import type {
  AviationCatalog,
  AviationSettings,
} from '@/services/aviation-weather';
import { GRID_RUN, gridFixture } from '@/test/gfs-grid';
const settings: AviationSettings = {
  metar: false,
  taf: false,
  sigmet: false,
  winds: true,
  temperature: false,
  gfs_selection: {
    vertical: { kind: 'pressure', pressure_pa: 50000 },
    horizon_hours: 0,
  },
  revision: 1,
};
const fakeClock = () => {
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(GRID_RUN);
};
const flush = async () => {
  for (let i = 0; i < 20; i++) await Promise.resolve();
};
function runtime() {
  const fixture = gridFixture(),
    budget = new WeatherBudget();
  const release = vi.fn(),
    dispose = vi.fn();
  const lease = {
    descriptor: parseGridDescriptor(fixture.descriptor),
    u: new Int16Array(fixture.buffers.u.buffer),
    v: new Int16Array(fixture.buffers.v.buffer),
    t: new Int16Array(fixture.buffers.t.buffer),
    mask: fixture.buffers.mask,
    release,
  } satisfies GridLease;
  const catalog: AviationCatalog = {
    schema: 'aviation-weather-v1',
    generated_at_ms: GRID_RUN,
    settings_revision: 1,
    products: [fixture.product],
  };
  const api = { getCatalog: vi.fn(async () => catalog) };
  const load = vi.fn<typeof fetchGrid>(async () => lease);
  const draw = vi.fn(() => ({
    object: new THREE.Group(),
    bytes: { decoded: 0, gpu: 0 },
    dispose,
  }));
  const controller = new GfsController(api, { budget, load, draw });
  return {
    controller,
    api,
    load,
    draw,
    lease,
    release,
    dispose,
    catalog,
    budget,
  };
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});
describe('model generation and monotonic expiry', () => {
  it('rejects a grid after the target crosses the 48-hour run window even with delayed timers', async () => {
    fakeClock();
    let mono = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => mono);
    const r = runtime();
    r.catalog.generated_at_ms = GRID_RUN - 1000;
    let complete!: (lease: GridLease) => void;
    r.load.mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        })
    );
    r.controller.setSettings({
      ...settings,
      gfs_selection: { ...settings.gfs_selection!, horizon_hours: 48 },
    });
    r.controller.start();
    await flush();
    mono = 2000;
    complete(r.lease);
    await flush();
    expect(r.draw).not.toHaveBeenCalled();
    expect(r.release).toHaveBeenCalledTimes(1);
    expect(r.controller.getSnapshot().drawing).toBeUndefined();
    r.controller.stop();
    expect(r.budget.snapshot().slots).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });
  it.each(['catalog', 'grid', 'drawing', 'queue'])(
    'rejects an overdue %s completion even before timeout callbacks run',
    async (phase) => {
      fakeClock();
      let mono = 0;
      vi.spyOn(performance, 'now').mockImplementation(() => mono);
      const r = runtime();
      let complete = () => {};
      const held =
        phase === 'queue'
          ? Array.from(
              { length: 4 },
              () => r.budget.tryAcquire(new AbortController().signal)!
            )
          : [];
      if (phase === 'catalog')
        r.api.getCatalog.mockImplementation(
          () =>
            new Promise((resolve) => {
              complete = () => resolve(r.catalog);
            })
        );
      if (phase === 'grid')
        r.load.mockImplementation(
          () =>
            new Promise((resolve) => {
              complete = () => resolve(r.lease);
            })
        );
      if (phase === 'drawing')
        r.draw.mockImplementation(() => {
          mono = 46000;
          return {
            object: new THREE.Group(),
            bytes: { decoded: 0, gpu: 0 },
            dispose: r.dispose,
          };
        });
      r.controller.setSettings(settings);
      r.controller.start();
      await flush();
      if (phase !== 'drawing') mono = 46000;
      complete();
      held.forEach((release) => release());
      await flush();
      expect(r.controller.getSnapshot().drawing).toBeUndefined();
      expect(r.controller.getSnapshot().state).toBe('unavailable');
      if (phase === 'drawing') expect(r.dispose).toHaveBeenCalledTimes(1);
      else expect(r.draw).not.toHaveBeenCalled();
      if (phase === 'grid' || phase === 'drawing')
        expect(r.release).toHaveBeenCalledTimes(1);
      if (phase === 'queue') expect(r.api.getCatalog).not.toHaveBeenCalled();
      r.controller.stop();
      expect(r.budget.snapshot().slots).toBe(0);
      expect(vi.getTimerCount()).toBe(0);
    }
  );
  it('keeps the confirmed requested level and horizon while the model is unavailable', async () => {
    fakeClock();
    const r = runtime();
    r.api.getCatalog.mockRejectedValue(Error('unavailable'));
    const selection = {
      vertical: { kind: 'flight-level' as const, flight_level: 390 as const },
      horizon_hours: 12 as const,
    };
    r.controller.setSettings({ ...settings, gfs_selection: selection });
    r.controller.start();
    await flush();
    expect(r.controller.getSnapshot()).toMatchObject({
      state: 'unavailable',
      selection,
    });
    r.controller.stop();
  });
  it('removes a retained model on original expiry despite all later polls failing', async () => {
    fakeClock();
    const r = runtime();
    r.controller.setSettings(settings);
    r.controller.start();
    await flush();
    expect(r.controller.getSnapshot().state).toBe('current');
    r.api.getCatalog.mockRejectedValue(Error('source down'));
    await vi.advanceTimersByTimeAsync(9 * 3600000);
    expect(r.controller.getSnapshot().state).toBe('stale');
    await vi.advanceTimersByTimeAsync(9 * 3600000);
    expect(r.controller.getSnapshot().drawing).toBeUndefined();
    expect(r.controller.getSnapshot().state).toBe('unavailable');
    expect(r.release).toHaveBeenCalledTimes(1);
    expect(r.dispose).toHaveBeenCalledTimes(1);
    r.controller.stop();
    expect(vi.getTimerCount()).toBe(0);
  });
  it.each(['hide', 'offline', 'disable', 'revision', 'stop'])(
    'aborts and rejects late work on %s',
    async (reason) => {
      fakeClock();
      const r = runtime();
      let complete!: (lease: GridLease) => void, signal!: AbortSignal;
      r.load.mockImplementation((_p, s) => {
        signal = s;
        return new Promise<GridLease>((resolve) => {
          complete = resolve;
        });
      });
      r.controller.setSettings(settings);
      r.controller.start();
      await flush();
      expect(signal.aborted).toBe(false);
      if (reason === 'hide') r.controller.setVisible(false);
      if (reason === 'offline') r.controller.setOnline(false);
      if (reason === 'disable')
        r.controller.setSettings({ ...settings, winds: false, revision: 2 });
      if (reason === 'revision')
        r.controller.setSettings({
          ...settings,
          gfs_selection: {
            vertical: { kind: 'flight-level', flight_level: 390 },
            horizon_hours: 3,
          },
          revision: 2,
        });
      if (reason === 'stop') r.controller.stop();
      expect(signal.aborted).toBe(true);
      complete(r.lease);
      await flush();
      expect(r.draw).not.toHaveBeenCalled();
      expect(r.release).toHaveBeenCalledTimes(1);
      expect(r.controller.getSnapshot().drawing).toBeUndefined();
      r.controller.stop();
      expect(r.budget.snapshot().slots).toBe(0);
      expect(vi.getTimerCount()).toBe(0);
    }
  );
  it('releases stalled-generation slots after the 45-second deadline', async () => {
    fakeClock();
    const r = runtime();
    r.api.getCatalog.mockImplementation(() => new Promise(() => {}));
    r.controller.setSettings(settings);
    r.controller.start();
    await flush();
    expect(r.budget.snapshot().slots).toBe(1);
    await vi.advanceTimersByTimeAsync(45000);
    expect(r.controller.getSnapshot().state).toBe('unavailable');
    expect(r.budget.snapshot().slots).toBe(0);
    r.controller.stop();
    expect(vi.getTimerCount()).toBe(0);
  });
  it('aborts a download when the original product expires before the generation deadline', async () => {
    fakeClock();
    const r = runtime();
    r.catalog.generated_at_ms = GRID_RUN + 18 * 3600000 - 1000;
    let complete!: (lease: GridLease) => void, signal!: AbortSignal;
    r.load.mockImplementation((_p, s) => {
      signal = s;
      return new Promise<GridLease>((resolve) => {
        complete = resolve;
      });
    });
    r.controller.setSettings(settings);
    r.controller.start();
    await flush();
    await vi.advanceTimersByTimeAsync(2000);
    expect(signal.aborted).toBe(true);
    complete(r.lease);
    await flush();
    expect(r.draw).not.toHaveBeenCalled();
    expect(r.release).toHaveBeenCalledTimes(1);
    r.controller.stop();
    expect(vi.getTimerCount()).toBe(0);
  });
  it('hides incompatible prior selection immediately and disposes owned drawing/data', async () => {
    fakeClock();
    const r = runtime();
    r.controller.setSettings(settings);
    r.controller.start();
    await flush();
    expect(r.draw).toHaveBeenCalledTimes(1);
    r.controller.setSettings({
      ...settings,
      gfs_selection: {
        vertical: { kind: 'pressure', pressure_pa: 30000 },
        horizon_hours: 3,
      },
      revision: 2,
    });
    expect(r.controller.getSnapshot().drawing).toBeUndefined();
    expect(r.dispose).toHaveBeenCalledTimes(1);
    expect(r.release).toHaveBeenCalledTimes(1);
    r.controller.stop();
    await flush();
    expect(r.budget.snapshot().slots).toBe(0);
  });
});
