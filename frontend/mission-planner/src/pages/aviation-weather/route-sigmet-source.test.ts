// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { QueryClient, focusManager } from '@tanstack/react-query';
import { RouteSigmetSource, getRouteSigmetSource } from './route-sigmet-source';
import { WeatherBudget } from './weather-budget';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { NOW } from './fixtures';
import { weatherDigest } from '@/services/aviation-grid';
const settings = { metar: false, taf: false, sigmet: true, revision: 1 };
const json = (data: unknown, status = 200) => {
  const text = JSON.stringify(data);
  return new Response(text, {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': String(new TextEncoder().encode(text).length),
    },
  });
};
const settle = async () => {
  for (let i = 0; i < 40; i++) await Promise.resolve();
};
const owned: { source: RouteSigmetSource; client: QueryClient }[] = [];
beforeEach(() => {
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  vi.setSystemTime(NOW);
});
afterEach(async () => {
  for (const { source, client } of owned.splice(0)) {
    source.dispose();
    client.clear();
  }
  await settle();
  await vi.advanceTimersByTimeAsync(0);
  expect(vi.getTimerCount()).toBe(0);
  focusManager.setFocused(undefined);
  vi.restoreAllMocks();
  vi.useRealTimers();
});
function setup(
  custom?: (path: RequestInfo | URL, init?: RequestInit) => Promise<Response>
) {
  const fixture = routeSnapshot();
  const fetcher = vi.fn(
    custom ??
      (async (path: RequestInfo | URL) =>
        String(path).endsWith('sigmet.json')
          ? new Response(fixture.bytes, {
              headers: { 'Content-Type': 'application/geo+json' },
            })
          : json(fixture.snapshot))
  );
  const client = new QueryClient();
  const budget = new WeatherBudget();
  const source = new RouteSigmetSource(client, { fetcher, budget });
  owned.push({ source, client });
  source.setSettings(settings);
  return { source, client, budget, fetcher, ...fixture };
}
it('manual selection is confirmed by the shared source and released on disposal', async () => {
  const fixture = routeSnapshot();
  let selected = false;
  const { source, budget } = setup(async (path, init) => {
    if (String(path).endsWith('sigmet.json'))
      return new Response(fixture.bytes, {
        headers: { 'Content-Type': 'application/geo+json' },
      });
    if (String(path).endsWith('/selection') && init?.method === 'PUT')
      selected = true;
    return json({
      ...fixture.snapshot,
      state_revision: selected ? 2 : 1,
      entries: fixture.snapshot.entries.map((e) => ({ ...e, selected })),
    });
  });
  const unsubscribe = source.subscribe(() => {});
  await settle();
  const confirmation = await source.setSelection({
    context_key: hash('c'),
    bulletin_key: hash('e'),
    semantic_digest: hash('f'),
  });
  expect(confirmation).not.toHaveProperty('entries');
  expect(confirmation).not.toHaveProperty('sigmet_product');
  expect(confirmation.notice_key).toBe(hash('d'));
  expect(source.snapshot().snapshot?.entries[0].selected).toBe(true);
  unsubscribe();
  expect(budget.snapshot().decoded).toBe(0);
});
it('two_consumers_share_source_and_poll_while_visible_but_unfocused', async () => {
  const { source, client, budget, fetcher } = setup();
  expect(getRouteSigmetSource(client)).toBe(getRouteSigmetSource(client));
  focusManager.setFocused(false);
  const one = source.subscribe(() => {}),
    two = source.subscribe(() => {});
  await settle();
  expect(source.snapshot().collection?.features).toHaveLength(1);
  expect(
    fetcher.mock.calls.filter(([p]) => !String(p).endsWith('.json'))
  ).toHaveLength(1);
  await vi.advanceTimersByTimeAsync(5000);
  expect(
    fetcher.mock.calls.filter(([p]) => !String(p).endsWith('.json'))
  ).toHaveLength(2);
  expect(
    fetcher.mock.calls.filter(([p]) => String(p).endsWith('.json'))
  ).toHaveLength(1);
  one();
  expect(source.snapshot().available).toBe(true);
  two();
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    gpu: 0,
    slots: 0,
    waiting: 0,
  });
  expect(
    client
      .getQueryCache()
      .findAll({ queryKey: ['aviation-weather', 'route-sigmets'] })
  ).toHaveLength(0);
});
it('cancels hidden/offline/disabled work and catches up immediately on resume', async () => {
  const { source, fetcher, budget } = setup();
  const off = source.subscribe(() => {});
  await settle();
  source.setVisible(false);
  await settle();
  expect(source.snapshot().collection).toBeNull();
  expect(budget.snapshot().decoded).toBe(0);
  await vi.advanceTimersByTimeAsync(10000);
  expect(
    fetcher.mock.calls.filter(([p]) => !String(p).endsWith('.json'))
  ).toHaveLength(1);
  source.setVisible(true);
  await settle();
  expect(source.snapshot().available).toBe(true);
  source.setOnline(false);
  await settle();
  source.setOnline(true);
  await settle();
  expect(source.snapshot().available).toBe(true);
  source.setSettings({ ...settings, sigmet: false, revision: 2 });
  await settle();
  expect(source.snapshot().collection).toBeNull();
  expect(budget.snapshot().decoded).toBe(0);
  off();
});
it('fetches a new immutable product immediately and never binds a missing replacement to old reports', async () => {
  const { source, fetcher, snapshot, budget } = setup();
  source.subscribe(() => {});
  await settle();
  snapshot.sigmet_product.instance_id = hash('9');
  snapshot.sigmet_product.payload.path = `/api/aviation-weather/v1/products/${hash('9')}/sigmet.json`;
  snapshot.generation_id = hash('8');
  fetcher.mockImplementation(async (p) =>
    String(p).endsWith('.json')
      ? new Response('', { status: 404 })
      : json(snapshot)
  );
  await source.refresh();
  await settle();
  expect(fetcher.mock.calls.some(([p]) => String(p).includes(hash('9')))).toBe(
    true
  );
  expect(source.snapshot().snapshot?.generation_id).toBe(hash('8'));
  expect(source.snapshot().collection).toBeNull();
  expect(source.snapshot().available).toBe(false);
  expect(source.snapshot().error).toBeTruthy();
  expect(budget.snapshot().slots).toBe(0);
});
it('confirmed clear survives an earlier GET with tied revision and changed generation', async () => {
  const { source, fetcher, snapshot } = setup();
  source.subscribe(() => {});
  await settle();
  let late!: (r: Response) => void;
  fetcher.mockImplementation(async (p) =>
    String(p).endsWith('acknowledgement')
      ? json({
          context_key: hash('c'),
          notice_key: hash('d'),
          semantic_digest: hash('f'),
          acknowledged: true,
          state_revision: 2,
          attention_order: 1,
        })
      : new Promise((r) => {
          late = r;
        })
  );
  const read = source.refresh();
  await settle();
  const change = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  await source.setAcknowledgement(change);
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(true);
  snapshot.state_revision = 2;
  snapshot.generation_id = hash('7');
  late(json(snapshot));
  await read;
  await settle();
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(true);
  expect(source.snapshot().snapshot?.generation_id).toBe(hash('b'));
});
it('does not acknowledge failed writes and refetches current context after conflict', async () => {
  const { source, fetcher, snapshot } = setup();
  source.subscribe(() => {});
  await settle();
  const change = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  fetcher.mockImplementation(async () => json({}, 503));
  await expect(source.setAcknowledgement(change)).rejects.toThrow();
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(false);
  snapshot.context.context_key = hash('6');
  snapshot.generation_id = hash('5');
  fetcher.mockImplementation(async (p) =>
    String(p).endsWith('acknowledgement') ? json({}, 409) : json(snapshot)
  );
  await expect(source.setAcknowledgement(change)).rejects.toThrow();
  await settle();
  expect(source.snapshot().snapshot?.context?.context_key).toBe(hash('6'));
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(false);
});
it('uses anchored UTC and expires locally even when browser wall time moves backwards', async () => {
  const { source, snapshot, budget } = setup();
  snapshot.entries[0].expires_at_ms = NOW + 1000;
  source.subscribe(() => {});
  await settle();
  vi.setSystemTime(NOW - 86400000);
  await vi.advanceTimersByTimeAsync(1001);
  expect(source.snapshot().nowMs).toBeGreaterThanOrEqual(NOW + 1000);
  expect(source.snapshot().snapshot?.entries).toHaveLength(0);
  await vi.advanceTimersByTimeAsync(3600000);
  expect(source.snapshot().collection).toBeNull();
  expect(budget.snapshot().decoded).toBe(0);
});
it('times out hung route reads and releases operation slots', async () => {
  const { source, budget } = setup(async () => new Promise(() => {}));
  source.subscribe(() => {});
  await settle();
  expect(budget.snapshot().slots).toBe(1);
  await vi.advanceTimersByTimeAsync(10001);
  expect(budget.snapshot().slots).toBe(0);
  expect(source.snapshot().error).toBeTruthy();
});
it('keeps old parsed data accounted until its presentation releases the retained lease', async () => {
  const { source, budget, snapshot, fetcher } = setup();
  const unsubscribe = source.subscribe(() => {});
  await settle();
  const retained = source.snapshot().dataLease!.retain();
  const oldBytes = budget.snapshot().decoded;
  snapshot.sigmet_product.instance_id = hash('2');
  snapshot.sigmet_product.payload.path = `/api/aviation-weather/v1/products/${hash('2')}/sigmet.json`;
  const bytes = routeSnapshot().bytes;
  fetcher.mockImplementation(async (p) =>
    String(p).endsWith('.json')
      ? new Response(bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
      : json(snapshot)
  );
  await source.refresh();
  await settle();
  expect(budget.snapshot().decoded).toBeGreaterThan(oldBytes);
  unsubscribe();
  await settle();
  expect(budget.snapshot().decoded).toBe(oldBytes);
  retained.release();
  expect(budget.snapshot().decoded).toBe(0);
});
it('rejects same-instance report references that do not exist in the admitted collection', async () => {
  const { source, snapshot } = setup();
  source.subscribe(() => {});
  await settle();
  snapshot.entries[0].feature_ids = ['wrong-generation-feature'];
  await source.refresh();
  await settle();
  expect(source.snapshot().available).toBe(false);
  expect(source.snapshot().collection).toBeNull();
});
it('retains the exact old collection when retaining a previously observed view after replacement', async () => {
  const { source, budget, snapshot, fetcher, data } = setup();
  const unsubscribe = source.subscribe(() => {});
  await settle();
  const old = source.snapshot().dataLease!;
  const oldSize = budget.snapshot().decoded;
  data.features[0].properties.raw_text = 'large report '.repeat(1000);
  const bytes = new TextEncoder().encode(JSON.stringify(data));
  snapshot.sigmet_product.payload.sha256 = weatherDigest(bytes);
  snapshot.sigmet_product.payload.encoded_bytes = bytes.length;
  snapshot.sigmet_product.payload.decoded_bytes = bytes.length * 4;
  snapshot.sigmet_product.instance_id = hash('2');
  snapshot.sigmet_product.payload.path = `/api/aviation-weather/v1/products/${hash('2')}/sigmet.json`;
  fetcher.mockImplementation(async (p) =>
    String(p).endsWith('.json')
      ? new Response(bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
      : json(snapshot)
  );
  await source.refresh();
  await settle();
  const retained = old.retain();
  unsubscribe();
  await settle();
  expect(budget.snapshot().decoded).toBe(oldSize);
  retained.release();
  expect(budget.snapshot().decoded).toBe(0);
});
it('keeps confirmed revisions monotonic across later reads and tied generations', async () => {
  const { source, snapshot, fetcher } = setup();
  source.subscribe(() => {});
  await settle();
  const change = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  fetcher.mockImplementation(async () =>
    json({ ...change, state_revision: 3, attention_order: 1 })
  );
  await source.setAcknowledgement(change);
  fetcher.mockImplementation(async () => json(snapshot));
  await source.refresh();
  expect(source.snapshot().snapshot?.state_revision).toBe(3);
  snapshot.state_revision = 3;
  snapshot.generation_id = hash('4');
  await source.refresh();
  expect(source.snapshot().snapshot?.generation_id).toBe(hash('4'));
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(true);
});
it('admits unavailable state without forgetting confirmed acknowledgement fences', async () => {
  const { source, snapshot, fetcher, budget, bytes } = setup();
  source.subscribe(() => {});
  await settle();
  const change = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  fetcher.mockImplementation(async () =>
    json({ ...change, state_revision: 3, attention_order: 1 })
  );
  await source.setAcknowledgement(change);
  const unavailable = {
    ...snapshot,
    state_revision: 0,
    generation_id: hash('7'),
    status: 'unavailable',
    complete: false,
    entries: [],
    unresolved: [],
    sigmet_product: {
      ...snapshot.sigmet_product,
      state: 'unavailable',
      ...Object.fromEntries(
        [
          'instance_id',
          'payload',
          'radar',
          'grid',
          'coverage',
          'observed_at_ms',
          'issued_at_ms',
          'scan_start_ms',
          'scan_end_ms',
          'valid_at_ms',
          'valid_from_ms',
          'valid_to_ms',
          'run_at_ms',
          'lead_seconds',
          'retrieved_at_ms',
          'fresh_until_ms',
          'expires_at_ms',
        ].map((key) => [key, null])
      ),
    },
  };
  fetcher.mockImplementation(async () => json(unavailable));
  await source.refresh();
  expect(source.snapshot().snapshot?.status).toBe('unavailable');
  expect(source.snapshot().collection).toBeNull();
  expect(source.snapshot().snapshot?.entries).toHaveLength(0);
  expect(budget.snapshot().encoded).toBe(0);
  fetcher.mockImplementation(async () => json(snapshot));
  await source.refresh();
  expect(source.snapshot().snapshot?.status).toBe('unavailable');
  snapshot.state_revision = 3;
  fetcher.mockImplementation(async (path) =>
    String(path).endsWith('sigmet.json')
      ? new Response(bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
      : json(snapshot)
  );
  await source.refresh();
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(true);
  expect(source.snapshot().available).toBe(true);
});
it('accounts immutable transfer bytes and releases them after cancellation', async () => {
  const fixture = routeSnapshot();
  const { source, budget } = setup(async (p) =>
    String(p).endsWith('.json') ? new Promise(() => {}) : json(fixture.snapshot)
  );
  const unsubscribe = source.subscribe(() => {});
  await settle();
  expect(budget.snapshot().encoded).toBeGreaterThanOrEqual(
    fixture.bytes.length
  );
  unsubscribe();
  await settle();
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    slots: 0,
    waiting: 0,
  });
});
it('rechecks browser visibility when a previously idle source gains a subscriber', async () => {
  const { source, fetcher } = setup();
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  source.subscribe(() => {});
  await settle();
  expect(fetcher).not.toHaveBeenCalled();
  hidden.mockReturnValue(false);
  document.dispatchEvent(new Event('visibilitychange'));
  await settle();
  expect(source.snapshot().available).toBe(true);
  online.mockReturnValue(false);
  window.dispatchEvent(new Event('offline'));
  await settle();
  expect(source.snapshot().collection).toBeNull();
  online.mockReturnValue(true);
  window.dispatchEvent(new Event('online'));
  await settle();
  expect(source.snapshot().available).toBe(true);
});
it('expires notices and the product while an acknowledgement PUT is still pending', async () => {
  const { source, snapshot, fetcher, budget } = setup();
  snapshot.entries[0].expires_at_ms = NOW + 1000;
  snapshot.sigmet_product.fresh_until_ms = NOW + 1500;
  snapshot.sigmet_product.expires_at_ms = NOW + 2000;
  source.subscribe(() => {});
  await settle();
  let confirm!: (response: Response) => void;
  fetcher.mockImplementation(
    async () =>
      new Promise((resolve) => {
        confirm = resolve;
      })
  );
  const change = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  const write = source.setAcknowledgement(change).then(
    (data) => ({ data }),
    (error) => ({ error })
  );
  await settle();
  expect(source.snapshot().snapshot?.entries[0].acknowledged).toBe(false);
  await vi.advanceTimersByTimeAsync(1001);
  expect(source.snapshot().snapshot?.entries).toHaveLength(0);
  expect(source.snapshot().available).toBe(true);
  await vi.advanceTimersByTimeAsync(1000);
  expect(source.snapshot().snapshot).toBeNull();
  expect(source.snapshot().collection).toBeNull();
  expect(source.snapshot().available).toBe(false);
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    slots: 0,
    waiting: 0,
  });
  confirm(json({ ...change, state_revision: 2, attention_order: 1 }));
  expect(await write).toHaveProperty('error');
  await settle();
  expect(source.snapshot().snapshot).toBeNull();
  expect(source.snapshot().collection).toBeNull();
});
it('never admits a delayed immutable payload after its product has expired', async () => {
  const fixture = routeSnapshot();
  fixture.snapshot.sigmet_product.fresh_until_ms = NOW + 500;
  fixture.snapshot.sigmet_product.expires_at_ms = NOW + 1000;
  fixture.snapshot.entries[0].expires_at_ms = NOW + 1000;
  let deliver!: (response: Response) => void;
  const { source, budget } = setup(async (p) =>
    String(p).endsWith('.json')
      ? new Promise((resolve) => {
          deliver = resolve;
        })
      : json(fixture.snapshot)
  );
  source.subscribe(() => {});
  await settle();
  expect(source.snapshot().snapshot).not.toBeNull();
  expect(budget.snapshot().slots).toBe(1);
  await vi.advanceTimersByTimeAsync(1001);
  expect(source.snapshot().snapshot).toBeNull();
  deliver(
    new Response(fixture.bytes, {
      headers: { 'Content-Type': 'application/geo+json' },
    })
  );
  await settle();
  expect(source.snapshot().available).toBe(false);
  expect(source.snapshot().snapshot).toBeNull();
  expect(source.snapshot().collection).toBeNull();
  expect(source.snapshot().error?.message).toContain('expired');
  expect(budget.snapshot()).toMatchObject({
    encoded: 0,
    decoded: 0,
    gpu: 0,
    slots: 0,
    waiting: 0,
  });
});

it('rejects older timing observations even when acknowledgement revision ties', async () => {
  const fixture = routeSnapshot();
  let observation = 2;
  const { source } = setup(async (path) =>
    String(path).endsWith('sigmet.json')
      ? new Response(fixture.bytes, {
          headers: { 'Content-Type': 'application/geo+json' },
        })
      : json({ ...fixture.snapshot, observation_revision: observation })
  );
  const off = source.subscribe(() => {});
  await settle();
  expect(source.snapshot().snapshot?.observation_revision).toBe(2);
  observation = 1;
  await vi.advanceTimersByTimeAsync(5000);
  await settle();
  expect(source.snapshot().snapshot?.observation_revision).toBe(2);
  expect(source.snapshot().error?.message).toContain('Obsolete');
  off();
});
