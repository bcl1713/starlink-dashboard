import { afterEach, describe, expect, it, vi } from 'vitest';
import { CompletionPoller } from './poller';

afterEach(() => vi.useRealTimers());

async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe('CompletionPoller', () => {
  it('defaults to one second and anchors starts after completion', async () => {
    vi.useFakeTimers();
    const starts: number[] = [];
    const poller = new CompletionPoller(async () => {
      starts.push(performance.now());
      await new Promise((resolve) => setTimeout(resolve, 200));
    });

    poller.start();
    await vi.advanceTimersByTimeAsync(5000);

    expect(starts.length).toBeGreaterThanOrEqual(4);
    expect(starts.slice(1).map((start, i) => start - starts[i])).toEqual(
      starts.slice(1).map(() => 1200)
    );
    poller.stop();
  });

  it('does not overlap and applies a cadence change after settlement', async () => {
    vi.useFakeTimers();
    let release: (() => void) | undefined;
    const starts: number[] = [];
    const poller = new CompletionPoller(() => {
      starts.push(performance.now());
      return new Promise<void>((resolve) => {
        release = resolve;
      });
    }, 5);

    poller.start();
    await vi.advanceTimersByTimeAsync(5000);
    poller.setCadence(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(starts).toHaveLength(1);
    release?.();
    await flush();
    await vi.advanceTimersByTimeAsync(1000);
    expect(starts).toHaveLength(2);
    poller.stop();
  });

  it('pauses while hidden and resumes with one immediate request', async () => {
    vi.useFakeTimers();
    const run = vi.fn(async () => {});
    const poller = new CompletionPoller(run, 1);

    poller.start();
    poller.setVisible(false);
    await vi.advanceTimersByTimeAsync(5000);
    expect(run).not.toHaveBeenCalled();
    poller.setVisible(true);
    await flush();
    expect(run).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('paused manual refresh runs exactly once without overlap', async () => {
    vi.useFakeTimers();
    const run = vi.fn(async () => {});
    const poller = new CompletionPoller(run, 'paused');
    poller.start();

    await Promise.all([poller.manual(), poller.manual()]);
    await vi.advanceTimersByTimeAsync(5000);

    expect(run).toHaveBeenCalledTimes(1);
    poller.stop();
  });
});
