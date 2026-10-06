/** One browser's actual fetch/decode concurrency and decoded allocation owner. */
export class WeatherWork {
  private active = 0;
  private detailActive = 0;
  private decodedBytes = 0;
  private peakDecodedBytes = 0;
  private waiting: {
    kind: 'coarse' | 'detail';
    start(): void;
    signal: AbortSignal;
    abort(): void;
  }[] = [];
  private evict: ((bytes: number) => void) | null = null;
  setDetailEvictor(evict: ((bytes: number) => void) | null) {
    this.evict = evict;
  }
  snapshot() {
    return {
      active: this.active,
      detailActive: this.detailActive,
      pending: this.waiting.length,
      decodedBytes: this.decodedBytes,
      peakDecodedBytes: this.peakDecodedBytes,
    };
  }
  reserveDecoded(bytes: number): () => void {
    if (!Number.isSafeInteger(bytes) || bytes <= 0 || bytes > 96 * 1024 * 1024)
      throw new Error('Invalid weather reservation');
    if (this.decodedBytes + bytes > 96 * 1024 * 1024)
      this.evict?.(this.decodedBytes + bytes - 96 * 1024 * 1024);
    if (this.decodedBytes + bytes > 96 * 1024 * 1024)
      throw new Error('Weather decoded budget exhausted');
    this.decodedBytes += bytes;
    this.peakDecodedBytes = Math.max(this.peakDecodedBytes, this.decodedBytes);
    let owned = true;
    return () => {
      if (owned) {
        owned = false;
        this.decodedBytes -= bytes;
      }
    };
  }
  run<T>(
    kind: 'coarse' | 'detail',
    signal: AbortSignal,
    operation: () => Promise<T>
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(signal.reason);
        return;
      }
      const ticket = {
        kind,
        signal,
        start: () => {
          signal.removeEventListener('abort', ticket.abort);
          this.active++;
          if (kind === 'detail') this.detailActive++;
          void (async () => {
            try {
              signal.throwIfAborted();
              resolve(await operation());
            } catch (error) {
              reject(error);
            } finally {
              this.active--;
              if (kind === 'detail') this.detailActive--;
              this.drain();
            }
          })();
        },
        abort: () => {
          this.waiting = this.waiting.filter((item) => item !== ticket);
          reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
        },
      };
      this.waiting.push(ticket);
      signal.addEventListener('abort', ticket.abort, { once: true });
      this.drain();
    });
  }
  private drain() {
    while (this.active < 4) {
      const eligible = this.waiting.filter(
        (item) => item.kind === 'coarse' || this.detailActive < 2
      );
      const ticket =
        eligible.find((item) => item.kind === 'coarse') ?? eligible[0];
      if (!ticket) return;
      this.waiting = this.waiting.filter((item) => item !== ticket);
      ticket.start();
    }
  }
}
