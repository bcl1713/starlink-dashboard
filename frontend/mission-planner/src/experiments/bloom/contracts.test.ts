import { describe, expect, it } from 'vitest';
import {
  bloomSize,
  frameSummary,
  seededRandom,
  allowRequest,
} from './contracts';

describe('offline bloom experiment contracts', () => {
  it('bounds bloom independently of main resolution, including portrait', () => {
    expect(bloomSize(3840, 2160, 960)).toEqual([960, 540]);
    expect(bloomSize(600, 1200, 960)).toEqual([480, 960]);
    expect(bloomSize(400, 300, 960)).toEqual([400, 300]);
  });
  it('rejects APIs, mutations, external destinations and socket schemes', () => {
    const origin = 'http://127.0.0.1:4290';
    expect(allowRequest('/earth-day-hi.jpg', 'GET', origin)).toBe(true);
    expect(allowRequest('/assets/chunk.js', 'GET', origin)).toBe(true);
    for (const [url, method] of [
      ['/api/status', 'GET'],
      ['/api/missions', 'POST'],
      ['/earth-day-hi.jpg', 'PUT'],
      ['https://example.com/a', 'GET'],
      ['ws://127.0.0.1:4290', 'GET'],
      ['//example.com/asset', 'GET'],
    ])
      expect(allowRequest(url, method, origin)).toBe(false);
  });
  it('replays the same random sequence without touching global random', () => {
    const a = seededRandom(429),
      b = seededRandom(429);
    expect(Array.from({ length: 100 }, a)).toEqual(
      Array.from({ length: 100 }, b)
    );
  });
  it('reports frame intervals rather than GPU times and handles empty captures', () => {
    expect(frameSummary([])).toBeNull();
    expect(frameSummary([10, 20, 30, 40])).toEqual({
      count: 4,
      medianMs: 25,
      p95Ms: 40,
      durationMs: 100,
    });
  });
});

it('rejects viewport changes before warm-up and detects DPR changes at equal buffer size', async () => {
  const { capturePhase } = await import('./contracts');
  const expected = { css: [1000, 800], drawing: [2000, 1600], dpr: 2 };
  expect(capturePhase(expected, { ...expected, css: [1100, 800] }, 1)).toBe(
    'changed'
  );
  expect(capturePhase(expected, { ...expected, dpr: 1 }, 1)).toBe('changed');
  expect(capturePhase(expected, expected, 1)).toBe('warmup');
  expect(capturePhase(expected, expected, 61)).toBe('sample');
});
