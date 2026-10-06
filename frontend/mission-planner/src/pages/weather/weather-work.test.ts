import { expect, it } from 'vitest';
import { WeatherWork } from './weather-work';
const flush = async () => {
  for (let n = 0; n < 10; n++) await Promise.resolve();
};
it('limits shared work to four/two detail and admits queued coarse first', async () => {
  const work = new WeatherWork(),
    signal = new AbortController().signal;
  const finish: (() => void)[] = [],
    starts: string[] = [];
  const run = (id: string, kind: 'coarse' | 'detail') =>
    work.run(
      kind,
      signal,
      () =>
        new Promise<void>((resolve) => {
          starts.push(id);
          finish.push(resolve);
        })
    );
  const jobs = [
    run('d1', 'detail'),
    run('d2', 'detail'),
    run('d3', 'detail'),
    run('c1', 'coarse'),
    run('c2', 'coarse'),
  ];
  await flush();
  expect(starts).toEqual(['d1', 'd2', 'c1', 'c2']);
  jobs.push(run('c3', 'coarse'));
  finish.shift()!();
  await flush();
  expect(starts[4]).toBe('c3');
  while (finish.length) {
    finish.shift()!();
    await flush();
  }
  await Promise.all(jobs);
  expect(work.snapshot().active).toBe(0);
});
it('counts reservations before native decoding and releases them exactly once', () => {
  const work = new WeatherWork(),
    capacity = 96 * 1024 * 1024;
  const release = work.reserveDecoded(capacity);
  expect(work.snapshot().decodedBytes).toBe(capacity);
  expect(() => work.reserveDecoded(1)).toThrow();
  release();
  release();
  expect(work.snapshot().decodedBytes).toBe(0);
});
it('removes cancelled queued jobs without stealing an active operation', async () => {
  const work = new WeatherWork(),
    abort = new AbortController();
  const finishes: (() => void)[] = [];
  const signal = new AbortController().signal;
  const jobs = [0, 1].map(() =>
    work.run(
      'detail',
      signal,
      () =>
        new Promise<void>((resolve) => {
          finishes.push(resolve);
        })
    )
  );
  const queued = work
    .run('detail', abort.signal, async () => {
      throw new Error('must not start');
    })
    .catch((error) => error);
  abort.abort();
  expect((await queued).name).toBe('AbortError');
  // Each active operation retains its own completion; no queued cancellation credit.
  expect(work.snapshot().active).toBe(2);
  finishes.shift()!();
  await flush();
  expect(work.snapshot().active).toBe(1);
  finishes.shift()!();
  await Promise.all(jobs);
});
