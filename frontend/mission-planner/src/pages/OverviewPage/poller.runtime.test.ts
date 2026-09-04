import { expect, it } from 'vitest';
import { CompletionPoller } from './poller';

it('sustains the one-second cadence for a bounded ten-second runtime', async () => {
  const starts: number[] = [];
  const poller = new CompletionPoller(async () => {
    starts.push(performance.now());
  });
  poller.start();
  await new Promise((resolve) => setTimeout(resolve, 10_200));
  poller.stop();

  const intervals = starts
    .slice(1)
    .map((start, index) => start - starts[index])
    .sort((left, right) => left - right);
  const median = intervals[Math.floor(intervals.length / 2)];
  expect(starts.length).toBeGreaterThanOrEqual(8);
  expect(median).toBeGreaterThanOrEqual(800);
  expect(median).toBeLessThanOrEqual(1300);
}, 12_000);
