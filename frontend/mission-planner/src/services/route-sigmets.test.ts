import { expect, it } from 'vitest';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import {
  parseRouteSigmetSnapshot,
  parseNoticeMutation,
  parseNoticeConfirmation,
} from './route-sigmets';

it('strictly admits snapshot identity, original deadlines and known spans', () => {
  const { snapshot } = routeSnapshot();
  expect(
    parseRouteSigmetSnapshot(snapshot).entries[0].spans[0].start_fraction
  ).toBe(0.25);
  for (const change of [
    { extra: true },
    { truncated: true },
    { complete: false },
    { state_revision: true },
    { context: null },
    { generation_id: 'old' },
    { unresolved: [{ feature_id: 'unknown', reason: 'unlocated' }] },
  ])
    expect(() =>
      parseRouteSigmetSnapshot({ ...snapshot, ...change })
    ).toThrow();
});
it('rejects aggregate identity duplicates, invalid spans and non-SIGMET products', () => {
  const { snapshot } = routeSnapshot();
  expect(() =>
    parseRouteSigmetSnapshot({
      ...snapshot,
      entries: [...snapshot.entries, ...snapshot.entries],
    })
  ).toThrow();
  snapshot.entries[0].spans[0].end_fraction = 0.1;
  expect(() => parseRouteSigmetSnapshot(snapshot)).toThrow();
  const other = routeSnapshot().snapshot;
  other.sigmet_product.product_type = 'metar-speci';
  expect(() => parseRouteSigmetSnapshot(other)).toThrow();
});
it('admits only exact mutation and confirmed revision fields', () => {
  const mutation = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  expect(parseNoticeMutation(mutation).acknowledged).toBe(true);
  expect(() =>
    parseNoticeMutation({ ...mutation, state_revision: 2 })
  ).toThrow();
  expect(() => parseNoticeMutation({ ...mutation, acknowledged: 1 })).toThrow();
  expect(
    parseNoticeConfirmation({
      ...mutation,
      state_revision: 2,
      attention_order: 1,
    }).state_revision
  ).toBe(2);
  expect(() =>
    parseNoticeConfirmation({
      ...mutation,
      state_revision: -1,
      attention_order: 1,
    })
  ).toThrow();
});

it.each<Record<string, string>>([
  {},
  { 'Content-Encoding': 'gzip', 'Content-Length': '100' },
])(
  'admits chunked/decompressed snapshots alongside retained weather bytes: %j',
  async (headers) => {
    const { WeatherBudget } = await import(
      '@/pages/aviation-weather/weather-budget'
    );
    const { readRouteSigmetSnapshot } = await import('./route-sigmets');
    const budget = new WeatherBudget();
    const station = budget.reserve('other-layer', {
      encoded: 1024,
      decoded: 4096,
      gpu: 1024,
    });
    const text = JSON.stringify(routeSnapshot().snapshot);
    const lease = await readRouteSigmetSnapshot(
      new AbortController().signal,
      budget,
      async () =>
        new Response(text, {
          headers: { 'Content-Type': 'application/json', ...headers },
        })
    );
    expect(lease.data.entries).toHaveLength(1);
    expect(budget.snapshot().peaks.encoded).toBeLessThan(1024 * 1024);
    lease.allocation.release();
    expect(budget.snapshot()).toMatchObject({
      encoded: 1024,
      decoded: 4096,
      gpu: 1024,
      slots: 0,
    });
    station.release();
  }
);
it.each(['oversize', 'abort'] as const)(
  'releases chunked scratch and its operation slot on %s',
  async (failure) => {
    const { WeatherBudget } = await import(
      '@/pages/aviation-weather/weather-budget'
    );
    const { readRouteSigmetSnapshot } = await import('./route-sigmets');
    const budget = new WeatherBudget(),
      owner = new AbortController();
    let cancelled = false,
      pulls = 0;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        pulls++;
        if (failure === 'abort' && pulls === 2) {
          owner.abort();
          return;
        }
        controller.enqueue(
          new Uint8Array(failure === 'oversize' ? 1024 * 1024 : 128)
        );
      },
      cancel() {
        cancelled = true;
      },
    });
    await expect(
      readRouteSigmetSnapshot(
        owner.signal,
        budget,
        async () =>
          new Response(stream, {
            headers: { 'Content-Type': 'application/json' },
          })
      )
    ).rejects.toThrow();
    expect(cancelled).toBe(true);
    expect(budget.snapshot()).toMatchObject({
      encoded: 0,
      decoded: 0,
      gpu: 0,
      slots: 0,
    });
  }
);
