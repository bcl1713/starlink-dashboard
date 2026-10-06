/** One owner for the optional allowance shared by bulletins, models and picking. */
export type WeatherBytes = { encoded: number; decoded: number; gpu: number };
export type Reservation = { release(): void };
const limits: WeatherBytes = {
  encoded: 16 * 1024 ** 2,
  decoded: 32 * 1024 ** 2,
  gpu: 16 * 1024 ** 2,
};
const dimensions = ['encoded', 'decoded', 'gpu'] as const;
let sequence = 0;
export const weatherKey = (prefix: string) => `${prefix}:${++sequence}`;
export async function abortable<T>(
  work: Promise<T>,
  signal: AbortSignal
): Promise<T> {
  signal.throwIfAborted();
  let abort = () => {};
  const cancelled = new Promise<T>((_, reject) => {
    abort = () =>
      reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
  });
  try {
    return await Promise.race([work, cancelled]);
  } finally {
    signal.removeEventListener('abort', abort);
  }
}
export class WeatherBudget {
  private amounts: WeatherBytes = { encoded: 0, decoded: 0, gpu: 0 };
  private peaks = { encoded: 0, decoded: 0, gpu: 0, slots: 0 };
  private records = new Map<string, { bytes: WeatherBytes; owners: number }>();
  private slots = 0;
  private queue: {
    signal: AbortSignal;
    resolve: (release: () => void) => void;
    reject: (error: unknown) => void;
    abort: () => void;
  }[] = [];
  snapshot() {
    return {
      ...this.amounts,
      slots: this.slots,
      waiting: this.queue.length,
      peaks: { ...this.peaks },
    };
  }
  reserve(key: string, bytes: WeatherBytes): Reservation {
    if (
      !key ||
      dimensions.some((d) => !Number.isSafeInteger(bytes[d]) || bytes[d] < 0)
    )
      throw Error('Invalid weather reservation');
    let record = this.records.get(key);
    if (record) {
      if (dimensions.some((d) => record!.bytes[d] !== bytes[d]))
        throw Error('Inconsistent immutable allocation');
      record.owners++;
    } else {
      if (dimensions.some((d) => this.amounts[d] + bytes[d] > limits[d]))
        throw Error('Shared weather resource budget');
      record = { bytes: { ...bytes }, owners: 1 };
      this.records.set(key, record);
      for (const d of dimensions) {
        this.amounts[d] += bytes[d];
        this.peaks[d] = Math.max(this.peaks[d], this.amounts[d]);
      }
    }
    let owned = true;
    return {
      release: () => {
        if (!owned) return;
        owned = false;
        if (--record!.owners === 0) {
          this.records.delete(key);
          for (const d of dimensions) this.amounts[d] -= record!.bytes[d];
        }
      },
    };
  }
  private enter() {
    this.slots++;
    this.peaks.slots = Math.max(this.peaks.slots, this.slots);
    let owned = true;
    return () => {
      if (!owned) return;
      owned = false;
      this.slots--;
      while (this.slots < 4 && this.queue.length) {
        const waiter = this.queue.shift()!;
        waiter.signal.removeEventListener('abort', waiter.abort);
        if (waiter.signal.aborted) {
          waiter.reject(waiter.signal.reason);
          continue;
        }
        waiter.resolve(this.enter());
      }
    };
  }
  tryAcquire(signal: AbortSignal): (() => void) | null {
    signal.throwIfAborted();
    return this.slots < 4 && !this.queue.length ? this.enter() : null;
  }
  async acquire(signal: AbortSignal): Promise<() => void> {
    const immediate = this.tryAcquire(signal);
    if (immediate) return immediate;
    return new Promise((resolve, reject) => {
      const waiter = { signal, resolve, reject, abort: () => {} };
      waiter.abort = () => {
        this.queue = this.queue.filter((w) => w !== waiter);
        reject(signal.reason);
      };
      this.queue.push(waiter);
      signal.addEventListener('abort', waiter.abort, { once: true });
    });
  }
}
export const optionalWeatherBudget = new WeatherBudget();
