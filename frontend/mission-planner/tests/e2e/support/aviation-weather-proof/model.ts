/** Test-only normalized artifact contract. No scientific formats enter the app. */
export type Payload = {
  path?: string;
  byte_size: number;
  sha256: string;
  dtype?: string;
  scale?: number;
  offset?: number;
  units?: string;
};
export type Descriptor = {
  schema: string;
  representation: string;
  source_id?: string;
  grid: {
    width: number;
    height: number;
    longitude_start: number;
    longitude_step: number;
    latitude_start: number;
    latitude_step: number;
  };
  components: Record<string, Payload>;
  mask: Payload;
  advisories?: Payload;
  records?: Payload;
  scan_start_ms?: number;
  scan_end_ms?: number;
  valid_at_ms?: number;
  diagnostic_replay_at_ms?: number;
  region_intervals?: {
    region: string;
    scan_start_ms: number;
    scan_end_ms: number;
  }[];
  coverage?: { completeness: string };
  attribution?: string[];
};
export async function decodePayload(
  buffer: ArrayBuffer,
  declaration: Payload,
  cells: number
) {
  const bytes = declaration.dtype === 'int16-le' ? 2 : 1;
  if (
    buffer.byteLength !== cells * bytes ||
    declaration.byte_size !== buffer.byteLength
  )
    throw Error('payload length mismatch');
  const digest = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))
  )
    .map((v) => v.toString(16).padStart(2, '0'))
    .join('');
  if (digest !== declaration.sha256) throw Error('payload hash mismatch');
  if (bytes === 1) return new Uint8Array(buffer);
  const result = new Int16Array(cells),
    view = new DataView(buffer);
  for (let i = 0; i < cells; i++) result[i] = view.getInt16(i * 2, true);
  return result;
}
export function labels(d: Descriptor) {
  const utc = (n: number) => new Date(n).toISOString();
  if (d.representation === 'advisory-v1')
    return `International SIGMET • Coverage ${d.coverage?.completeness ?? 'unverified'} • ${d.diagnostic_replay_at_ms === undefined ? 'UTC validity rechecked' : `Diagnostic replay ${utc(d.diagnostic_replay_at_ms)}`} • Unknown vertical limits remain unknown`;
  if (typeof d.scan_start_ms === 'number' || d.region_intervals)
    return `${d.source_id ?? 'Satellite'} • brightness temperature K (not cloud height) • ${d.scan_start_ms === undefined ? '' : `${utc(d.scan_start_ms)} – ${utc(d.scan_end_ms!)}`} • ${(d.region_intervals ?? []).map((r) => `${r.region}: ${utc(r.scan_start_ms)} – ${utc(r.scan_end_ms)}`).join('; ')}`;
  return `${d.source_id ?? 'GFS'} • 500 hPa model forecast • Temperature K; wind m/s • Valid ${d.valid_at_ms === undefined ? 'unknown' : utc(d.valid_at_ms)} • Barbs: FROM direction; m/s × 1.94384449 → nearest 5 knots`;
}
export class Allocation {
  current = { encoded: 0, decoded: 0, gpu: 0 };
  peak = { ...this.current };
  reserve(encoded: number, decoded: number, gpu: number) {
    const next = {
      encoded: this.current.encoded + encoded,
      decoded: this.current.decoded + decoded,
      gpu: this.current.gpu + gpu,
    };
    if (
      Object.values(next).some((x) => !Number.isFinite(x) || x < 0) ||
      next.encoded > 16 * 1024 ** 2 ||
      next.decoded > 32 * 1024 ** 2 ||
      next.gpu > 16 * 1024 ** 2
    )
      throw Error('proof allocation budget exceeded');
    this.current = next;
    for (const key of ['encoded', 'decoded', 'gpu'] as const)
      this.peak[key] = Math.max(this.peak[key], next[key]);
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.current = {
        encoded: this.current.encoded - encoded,
        decoded: this.current.decoded - decoded,
        gpu: this.current.gpu - gpu,
      };
    };
  }
}

/** Globally serialize generations; cancellation waits for old worker cleanup. */
export class InstallQueue {
  private tail: Promise<unknown> = Promise.resolve();
  private current?: AbortController;
  cancel() {
    this.current?.abort();
  }
  async idle() {
    await this.tail;
  }
  run<T>(work: (signal: AbortSignal) => Promise<T>): Promise<T> {
    this.cancel();
    const controller = new AbortController();
    this.current = controller;
    const timer = setTimeout(() => controller.abort(), 45000);
    const result = this.tail
      .catch(() => {})
      .then(async () => {
        controller.signal.throwIfAborted();
        return work(controller.signal);
      })
      .finally(() => clearTimeout(timer));
    this.tail = result.catch(() => {});
    return result;
  }
}
