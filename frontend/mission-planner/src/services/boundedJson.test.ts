import { afterEach, describe, expect, it, vi } from 'vitest';
import { getJson, MAX_JSON_RESPONSE_BYTES } from './boundedJson';
import { fetchStatus } from './monitoring';

const instant = '2026-09-02T12:00:00Z';
const later = '2026-09-02T12:00:01Z';
const status = () => ({
  source: 'live' as const,
  timestamp: instant,
  observed_at: instant,
  received_at: later,
  position: {
    latitude: 0,
    longitude: 180,
    altitude: 1,
    speed: 0,
    heading: 360,
  },
  network: {
    latency_ms: 10,
    throughput_down_mbps: 20,
    throughput_up_mbps: 3,
    packet_loss_percent: 0,
  },
  obstruction: { obstruction_percent: 0 },
  environmental: {
    signal_quality_percent: 100,
    uptime_seconds: 1,
    temperature_celsius: null,
  },
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('bounded monitoring JSON transport', () => {
  it('aborts a request at the four-second bound', async () => {
    vi.useFakeTimers();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        requestSignal = init?.signal ?? undefined;
        return new Promise<Response>((_resolve, reject) => {
          requestSignal?.addEventListener('abort', () =>
            reject(new Error('private abort detail'))
          );
        });
      })
    );

    const request = getJson('/api/status');
    const rejection = expect(request).rejects.toThrow(
      'Monitoring request unavailable'
    );
    await vi.advanceTimersByTimeAsync(3999);
    expect(requestSignal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(requestSignal?.aborted).toBe(true);
    await rejection;
  });

  it('cancels its owned reader when the caller aborts', async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('{'));
      },
      cancel,
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream)));
    const controller = new AbortController();

    const request = getJson('/api/status', controller.signal);
    await Promise.resolve();
    controller.abort();

    await expect(request).rejects.toThrow('Monitoring request unavailable');
    expect(cancel).toHaveBeenCalledOnce();
  });

  it('rejects oversized declared and streamed bodies before parsing', async () => {
    const cancel = vi.fn();
    const oversizedStream = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(new Uint8Array(MAX_JSON_RESPONSE_BYTES));
        controller.enqueue(new Uint8Array([32]));
      },
      cancel,
    });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response('{}', {
            headers: {
              'Content-Length': String(MAX_JSON_RESPONSE_BYTES + 1),
            },
          })
        )
        .mockResolvedValueOnce(new Response(oversizedStream))
    );

    await expect(getJson('/api/status')).rejects.toThrow(
      'Monitoring request unavailable'
    );
    await expect(getJson('/api/status')).rejects.toThrow(
      'Monitoring request unavailable'
    );
    expect(cancel).toHaveBeenCalledOnce();
  });

  it('accepts the exact byte boundary and normal streamed DTOs', async () => {
    const boundaryBody = `null${' '.repeat(MAX_JSON_RESPONSE_BYTES - 4)}`;
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(new Response(boundaryBody))
        .mockResolvedValueOnce(new Response(JSON.stringify(status())))
    );

    await expect(getJson('/api/status')).resolves.toBeNull();
    await expect(fetchStatus()).resolves.toEqual(status());
  });

  it('sanitizes invalid UTF-8 and invalid JSON failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(new Uint8Array([0xc3, 0x28]), {
            headers: { 'Content-Type': 'application/json' },
          })
        )
        .mockResolvedValueOnce(new Response('{private payload'))
    );

    await expect(getJson('/api/status')).rejects.toThrow(
      'Monitoring request unavailable'
    );
    await expect(getJson('/api/status')).rejects.toThrow(
      'Monitoring request unavailable'
    );
  });
});
