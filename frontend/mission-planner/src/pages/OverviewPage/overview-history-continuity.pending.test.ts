import { describe, expect, it } from 'vitest';

import type { OverviewStatus } from '../../types/monitoring';
import { HISTORY_MAX_SAMPLES } from './history';
import { buildSlotCommits } from './overview-history-continuity';
import { statusPayload } from './overview-test-harness';

describe('overview history continuity pending telemetry', () => {
  it('bounds and deduplicates telemetry pending before any server history success', () => {
    let pending: OverviewStatus[] = Array.from(
      { length: HISTORY_MAX_SAMPLES + 20 },
      (_, index) => ({
        ...structuredClone(statusPayload),
        timestamp: `2026-08-29T12:${String(Math.floor(index / 60)).padStart(
          2,
          '0'
        )}:${String(index % 60).padStart(2, '0')}Z`,
      })
    );
    const duplicate = {
      ...structuredClone(statusPayload),
      timestamp: pending.at(-1)?.timestamp ?? '2026-08-29T12:30:20Z',
      network: {
        ...statusPayload.network,
        latency_ms: 999,
      },
    };

    const result = buildSlotCommits(
      [
        {
          slot: 'telemetry',
          outcome: { ok: true, data: duplicate },
        },
        {
          slot: 'history',
          outcome: {
            ok: false,
            error: {
              code: 'request-failed',
              message: 'Source refresh failed.',
            },
          },
        },
      ],
      undefined,
      pending,
      1_788_008_220_000
    );

    pending = result.pending;
    expect(result.commits.some(([slot]) => slot === 'history')).toBe(true);
    expect(pending).toHaveLength(HISTORY_MAX_SAMPLES);
    expect(pending.at(0)?.timestamp).toBe('2026-08-29T12:00:20Z');
    expect(pending.at(-1)?.network.latency_ms).toBe(999);
  });

  it('discards malformed and hostile pending telemetry during prolonged history failures', () => {
    const valid = Array.from(
      { length: HISTORY_MAX_SAMPLES + 30 },
      (_, index) => ({
        ...structuredClone(statusPayload),
        timestamp: `2026-08-29T12:${String(Math.floor(index / 60)).padStart(
          2,
          '0'
        )}:${String(index % 60).padStart(2, '0')}Z`,
      })
    );
    const duplicate = {
      ...structuredClone(statusPayload),
      timestamp: valid.at(-1)?.timestamp ?? '2026-08-29T12:30:30Z',
      network: { ...statusPayload.network, latency_ms: 1234 },
    };
    const throwingTimestamp = Object.defineProperty(
      { ...structuredClone(statusPayload) },
      'timestamp',
      {
        get() {
          throw new Error('timestamp revoked');
        },
      }
    ) as OverviewStatus;
    const { proxy, revoke } = Proxy.revocable(
      { ...structuredClone(statusPayload) },
      {}
    );
    revoke();
    const malformed = {
      ...structuredClone(statusPayload),
      timestamp: 'not-a-date',
    };
    let pending: OverviewStatus[] = [
      malformed,
      throwingTimestamp,
      proxy as OverviewStatus,
      ...valid,
      duplicate,
    ];

    for (let attempt = 0; attempt < 3; attempt += 1) {
      const result = buildSlotCommits(
        [
          {
            slot: 'history',
            outcome: {
              ok: false,
              error: {
                code: 'request-failed',
                message: 'Source refresh failed.',
              },
            },
          },
        ],
        undefined,
        pending,
        1_788_008_230_000
      );
      pending = result.pending;
    }

    expect(pending).toHaveLength(HISTORY_MAX_SAMPLES);
    expect(pending.at(0)?.timestamp).toBe('2026-08-29T12:00:30Z');
    expect(pending.at(-1)?.timestamp).toBe('2026-08-29T12:30:30Z');
    expect(pending.at(-1)?.network.latency_ms).toBe(1234);
  });
});
