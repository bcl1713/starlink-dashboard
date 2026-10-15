import { expect, it } from 'vitest';
import * as THREE from 'three';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import {
  parseAviationFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import { NOW, advisory } from './fixtures';
import { WeatherBudget } from './weather-budget';
import {
  createSigmetPresentation,
  type SigmetPresentationInput,
} from './route-sigmet-presentation';

export function input(): SigmetPresentationInput {
  const fixture = routeSnapshot();
  return {
    source: {
      snapshot: routeSigmetSnapshotSchema.parse(fixture.snapshot),
      collection: parseAviationFeatures(fixture.data, 'sigmet'),
      available: true,
      error: null,
      dataLease: { retain: () => ({ release() {} }) },
      nowMs: NOW,
    },
    localContextKey: hash('c'),
    intersectingOnly: true,
    nowMs: NOW,
    routePoints: [
      { longitude: -2, latitude: 0 },
      { longitude: 6, latitude: 0 },
    ],
  };
}
it('exposes every pending item for navigation and keeps selection separate from route spans', () => {
  const next = multiple([1, 2, 3, 4]);
  const presentation = createSigmetPresentation(next, new WeatherBudget());
  try {
    expect(presentation.attentionItems).toHaveLength(4);
    expect(
      presentation.attentionItems.every((item) => item.kind === 'intersecting')
    ).toBe(true);
  } finally {
    presentation.dispose();
  }
});
it('keeps acknowledged intersections shaded while showing only the three newest attention notices', () => {
  const next = multiple([1, 5, 3, 2, 4]);
  next.source.snapshot!.entries[1].acknowledged = true;
  const budget = new WeatherBudget();
  const presentation = createSigmetPresentation(next, budget);
  try {
    expect(presentation.notices.map((n) => n.entry.attention_order)).toEqual([
      4, 3, 2,
    ]);
    expect(presentation.pendingCount).toBe(4);
    expect(presentation.view.data!.features.map((f) => f.id)).toEqual([
      'report-1',
      'report-5',
      'report-3',
      'report-2',
      'report-4',
    ]);
    expect(presentation.view.drawing).toBeDefined();
  } finally {
    presentation.dispose();
  }
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
it('Show again promotes the acknowledged bulletin without changing normal polygon eligibility', () => {
  const next = multiple([1, 2, 3, 4]);
  next.source.snapshot!.entries[0].attention_order = 5;
  const presentation = createSigmetPresentation(next, new WeatherBudget());
  expect(presentation.notices.map((n) => n.entry.attention_order)).toEqual([
    5, 4, 3,
  ]);
  presentation.dispose();
});
it.each([
  'no-route',
  'wrong-route',
  'evaluating',
  'binding',
  'expired',
] as const)(
  'suppresses intersecting-only geometry and cards when %s',
  (reason) => {
    const next = input();
    if (reason === 'no-route') next.localContextKey = null;
    if (reason === 'wrong-route') next.localContextKey = hash('9');
    if (reason === 'evaluating') next.source.snapshot!.status = 'evaluating';
    if (reason === 'binding') next.source.available = false;
    if (reason === 'expired') next.nowMs += 3600000;
    const presentation = createSigmetPresentation(next, new WeatherBudget());
    expect(presentation.notices).toEqual([]);
    expect(presentation.view.drawing).toBeUndefined();
    expect(presentation.view.data?.features ?? []).toEqual([]);
    presentation.dispose();
  }
);
it('all mode retains ordinary eligible polygons without an evaluated route', () => {
  const next = input();
  next.localContextKey = null;
  next.intersectingOnly = false;
  const presentation = createSigmetPresentation(next, new WeatherBudget());
  expect(presentation.view.data!.features).toHaveLength(1);
  expect(presentation.notices).toEqual([]);
  expect(presentation.statusText).toContain('Route unavailable');
  presentation.dispose();
});
it('filters unrelated polygons without erasing known spans with unresolved portions', () => {
  const next = input();
  const other = parseAviationFeatures(
    { ...next.source.collection!, features: [{ ...advisory(), id: 'other' }] },
    'sigmet'
  ).features[0];
  next.source.collection!.features.push(other);
  next.source.snapshot!.unresolved = [
    { feature_id: 'test-advisory', reason: 'boundary-uncertain' },
  ];
  next.source.snapshot!.complete = false;
  next.source.snapshot!.status = 'incomplete';
  const presentation = createSigmetPresentation(next, new WeatherBudget());
  expect(presentation.view.data!.features.map((f) => f.id)).toEqual([
    'test-advisory',
  ]);
  expect(presentation.notices[0].intersectionUnknown).toBe(true);
  expect(presentation.notices[0].entry.spans).toHaveLength(1);
  expect(presentation.unknownCount).toBe(1);
  presentation.dispose();
});
it('retains text on GPU rejection and accounts simultaneous old/candidate data and drawings until disposal', () => {
  const budget = new WeatherBudget(),
    next = input();
  const sourceOwner = budget.reserve('source', {
    encoded: 0,
    decoded: 1024,
    gpu: 0,
  });
  next.source.dataLease = {
    retain: () =>
      budget.reserve('source', { encoded: 0, decoded: 1024, gpu: 0 }),
  };
  const old = createSigmetPresentation(next, budget);
  sourceOwner.release();
  const occupied = budget.reserve('other-weather', {
    encoded: 0,
    decoded: 0,
    gpu: 16 * 1024 ** 2 - budget.snapshot().gpu,
  });
  const candidate = createSigmetPresentation(next, budget);
  expect(candidate.notices).toHaveLength(1);
  expect(candidate.highlightUnavailable).toBe(true);
  expect(candidate.view.drawing).toBeUndefined();
  let retainedOnGpuDispose = false;
  old.view.drawing!.object.traverse((object) => {
    const geometry = (object as THREE.Mesh).geometry;
    geometry?.addEventListener('dispose', () => {
      retainedOnGpuDispose = budget.snapshot().decoded >= 1024;
    });
  });
  old.dispose();
  candidate.dispose();
  occupied.release();
  expect(retainedOnGpuDispose).toBe(true);
  expect(budget.snapshot()).toMatchObject({ encoded: 0, decoded: 0, gpu: 0 });
});

function multiple(orders: number[]) {
  const next = input(),
    original = next.source.snapshot!.entries[0],
    report = next.source.collection!.features[0];
  next.source.snapshot!.entries = orders.map((order) => ({
    ...original,
    notice_key: String(order).repeat(64),
    bulletin_key: String(order).repeat(64),
    feature_ids: ['report-' + order],
    attention_order: order,
  }));
  next.source.collection!.features = orders.map((order) => ({
    ...report,
    id: 'report-' + order,
  }));
  next.source.snapshot = routeSigmetSnapshotSchema.parse(next.source.snapshot);
  return next;
}
it.each(['future', 'cancelled', 'expired'] as const)(
  'excludes %s reports and notices in all mode',
  (reason) => {
    const next = input();
    next.intersectingOnly = false;
    const report = next.source.collection!.features[0];
    if ('cancelled' in report.properties) {
      if (reason === 'future') report.properties.valid_from_ms = NOW + 1;
      if (reason === 'cancelled') report.properties.cancelled = true;
      if (reason === 'expired') {
        report.properties.valid_to_ms = NOW;
        report.properties.expires_at_ms = NOW;
      }
    }
    const p = createSigmetPresentation(next, new WeatherBudget());
    expect(p.notices).toEqual([]);
    expect(p.view.data!.features).toEqual([]);
    expect(p.view.drawing).toBeUndefined();
    p.dispose();
  }
);
it('rejects a mismatched immutable feed timestamp and retains stale notices only until original expiry', () => {
  const next = input();
  next.source.collection!.retrieved_at_ms++;
  const mismatch = createSigmetPresentation(next, new WeatherBudget());
  expect(mismatch.notices).toEqual([]);
  expect(mismatch.view.drawing).toBeUndefined();
  mismatch.dispose();
  next.source.collection!.retrieved_at_ms--;
  next.source.error = new Error('offline refresh');
  next.nowMs = NOW + 60001;
  const stale = createSigmetPresentation(next, new WeatherBudget());
  expect(stale.notices).toHaveLength(1);
  expect(stale.view.state).toBe('stale');
  stale.dispose();
  next.nowMs = NOW + 3600000;
  const expired = createSigmetPresentation(next, new WeatherBudget());
  expect(expired.notices).toEqual([]);
  expect(expired.view.drawing).toBeUndefined();
  expired.dispose();
});
it('does not retain incompatible source data when intersecting-only has no drawing or notices', () => {
  const budget = new WeatherBudget(),
    next = input();
  const base = budget.reserve('source', { encoded: 0, decoded: 1024, gpu: 0 });
  next.source.dataLease = {
    retain: () =>
      budget.reserve('source', { encoded: 0, decoded: 1024, gpu: 0 }),
  };
  next.localContextKey = hash('9');
  const p = createSigmetPresentation(next, budget);
  base.release();
  try {
    expect(budget.snapshot().decoded).toBe(0);
  } finally {
    p.dispose();
  }
});
it('exposes copied budget observations that remain valid after disposal', () => {
  const budget = new WeatherBudget();
  const presentation = createSigmetPresentation(input(), budget);
  const observe = presentation.view.drawing!.object.userData.routeSigmetBudget;
  try {
    const sample = observe();
    expect(sample.gpu).toBeGreaterThan(0);
    sample.gpu = 999;
    expect(observe().gpu).toBe(budget.snapshot().gpu);
  } finally {
    presentation.dispose();
  }
  expect(observe()).toMatchObject({ gpu: 0, decoded: 0, slots: 0 });
});
it('reports an admitted unavailable source as unavailable rather than endless loading', () => {
  const next = input();
  next.source.available = false;
  next.source.collection = null;
  next.source.dataLease = null;
  next.source.snapshot!.sigmet_product.state = 'unavailable';
  next.source.snapshot!.sigmet_product.payload = null;
  const presentation = createSigmetPresentation(next, new WeatherBudget());
  expect(presentation.view.state).toBe('unavailable');
  expect(presentation.notices).toEqual([]);
  expect(presentation.view.drawing).toBeUndefined();
  presentation.dispose();
});

it.each([true, false])(
  'keeps canonical notice labels stable across provider variant order (canonical=%s)',
  (canonical) => {
    const next = input();
    const first = next.source.collection!.features[0] as AviationAdvisory;
    const variant = {
      ...first,
      id: 'provider-forecast',
      properties: {
        ...first.properties,
        series: 'OSCAR55F',
        bulletin_series: canonical ? 'OSCAR55' : null,
      },
    };
    next.source.collection!.features = [
      variant,
      {
        ...first,
        properties: {
          ...first.properties,
          series: 'OSCAR55',
          bulletin_series: canonical ? 'OSCAR55' : null,
        },
      },
    ];
    const entry = next.source.snapshot!.entries[0];
    entry.feature_ids = ['provider-forecast', 'test-advisory'];
    const originalEntry = structuredClone(entry);
    const originalReports = structuredClone(next.source.collection!.features);
    for (const ids of [
      ['provider-forecast', 'test-advisory'],
      ['test-advisory', 'provider-forecast'],
    ]) {
      entry.feature_ids = ids;
      const presentation = createSigmetPresentation(next, new WeatherBudget());
      try {
        expect(presentation.notices[0].label).toBe('TEST OSCAR55 · eeeeeeee');
        expect(
          presentation.notices[0].reports.map((report) => report.id)
        ).toEqual(ids);
        expect(presentation.notices[0].entry).toEqual({
          ...originalEntry,
          feature_ids: ids,
        });
        expect(next.source.collection!.features).toEqual(originalReports);
      } finally {
        presentation.dispose();
      }
    }
  }
);
