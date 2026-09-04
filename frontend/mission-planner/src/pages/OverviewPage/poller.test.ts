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

  it.each([2, 10, 30] as const)(
    'uses the production %s-second cadence without an early start',
    async (cadence) => {
      vi.useFakeTimers();
      const run = vi.fn(async () => {});
      const poller = new CompletionPoller(run, cadence);
      poller.start();

      await vi.advanceTimersByTimeAsync(cadence * 1000 - 1);
      expect(run).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(1);
      expect(run).toHaveBeenCalledTimes(1);
      poller.stop();
    }
  );

  it('pins the five-second no-before-4.5s and by-5.5s oracle', async () => {
    vi.useFakeTimers();
    const run = vi.fn(async () => {});
    const poller = new CompletionPoller(run, 5);
    poller.start();

    await vi.advanceTimersByTimeAsync(4500);
    expect(run).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    expect(run).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it('recovers its production schedule after a rejected request', async () => {
    vi.useFakeTimers();
    const run = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error('failed'))
      .mockResolvedValue(undefined);
    const poller = new CompletionPoller(run, 1);
    poller.start();

    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1000);
    expect(run).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it('coalesces active visible resume into one immediate post-settlement run', async () => {
    vi.useFakeTimers();
    let release: (() => void) | undefined;
    const run = vi.fn(
      () => new Promise<void>((resolve) => (release = resolve))
    );
    const poller = new CompletionPoller(run, 30);
    poller.start();
    void poller.manual();
    await flush();

    poller.setVisible(false);
    poller.setVisible(true);
    poller.setVisible(true);
    await flush();
    expect(run).toHaveBeenCalledTimes(1);
    release?.();
    await flush();
    expect(run).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(29_999);
    expect(run).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it.each(['stop', 'hide', 'pause'] as const)(
    'clears active visible intent on %s before settlement',
    async (action) => {
      vi.useFakeTimers();
      let release: (() => void) | undefined;
      const run = vi.fn(
        () => new Promise<void>((resolve) => (release = resolve))
      );
      const poller = new CompletionPoller(run, 30);
      poller.start();
      void poller.manual();
      await flush();
      poller.setVisible(false);
      poller.setVisible(true);

      if (action === 'stop') poller.stop();
      if (action === 'hide') poller.setVisible(false);
      if (action === 'pause') poller.setCadence('paused');
      release?.();
      await flush();
      await vi.advanceTimersByTimeAsync(60_000);
      expect(run).toHaveBeenCalledTimes(1);
      poller.stop();
    }
  );

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

  it('stops without a replay after a large monotonic clock jump', async () => {
    vi.useFakeTimers();
    const run = vi.fn(async () => {});
    const poller = new CompletionPoller(run, 1);
    poller.start();

    vi.setSystemTime(new Date(Date.now() + 60 * 60 * 1000));
    await vi.runOnlyPendingTimersAsync();
    expect(run).toHaveBeenCalledTimes(1);
    poller.stop();
  });
});
