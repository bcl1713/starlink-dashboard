import { describe, expect, it } from 'vitest';
import { WeatherBudget } from './weather-budget';
const MiB = 1024 ** 2;
describe('shared optional-weather ownership', () => {
  it('accounts old, candidate and highlights together before allocation', () => {
    const budget = new WeatherBudget();
    const bulletin = budget.reserve('bulletin', {
      encoded: 2 * MiB,
      decoded: 8 * MiB,
      gpu: 4 * MiB,
    });
    const old = budget.reserve('old-grid', {
      encoded: 4 * MiB,
      decoded: 8 * MiB,
      gpu: 4 * MiB,
    });
    const candidate = budget.reserve('candidate', {
      encoded: 4 * MiB,
      decoded: 8 * MiB,
      gpu: 4 * MiB,
    });
    const highlight = budget.reserve('highlight', {
      encoded: 0,
      decoded: 4 * MiB,
      gpu: 4 * MiB,
    });
    expect(budget.snapshot().gpu).toBe(16 * MiB);
    expect(() =>
      budget.reserve('overflow', { encoded: 0, decoded: 0, gpu: 1 })
    ).toThrow();
    for (const lease of [bulletin, old, candidate, highlight]) {
      lease.release();
      lease.release();
    }
    expect(budget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    });
    expect(budget.snapshot().peaks.gpu).toBe(16 * MiB);
  });
  it('reference counts immutable siblings without releasing their shared allocation', () => {
    const budget = new WeatherBudget();
    const bytes = { encoded: 100, decoded: 200, gpu: 300 };
    const wind = budget.reserve('same-buffer', bytes),
      temperature = budget.reserve('same-buffer', bytes);
    expect(budget.snapshot()).toMatchObject(bytes);
    wind.release();
    expect(budget.snapshot()).toMatchObject(bytes);
    temperature.release();
    expect(budget.snapshot()).toMatchObject({ encoded: 0, decoded: 0, gpu: 0 });
    expect(() =>
      budget.reserve('bad', { encoded: NaN, decoded: 0, gpu: 0 })
    ).toThrow();
  });
  it('queues the fifth operation and removes aborted waiters', async () => {
    const budget = new WeatherBudget(),
      signal = new AbortController();
    const leases = await Promise.all(
      Array.from({ length: 4 }, () => budget.acquire(signal.signal))
    );
    let entered = false;
    const fifth = budget.acquire(signal.signal).then((release) => {
      entered = true;
      return release;
    });
    await Promise.resolve();
    expect(entered).toBe(false);
    expect(budget.snapshot().slots).toBe(4);
    const cancelled = new AbortController();
    const waiting = budget.acquire(cancelled.signal);
    cancelled.abort();
    await expect(waiting).rejects.toMatchObject({ name: 'AbortError' });
    leases[0]();
    const releaseFifth = await fifth;
    expect(entered).toBe(true);
    for (const release of leases) release();
    releaseFifth();
    releaseFifth();
    expect(budget.snapshot()).toMatchObject({ slots: 0, waiting: 0 });
  });
});
