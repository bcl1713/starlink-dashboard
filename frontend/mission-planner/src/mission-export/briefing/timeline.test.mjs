import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
export const payload = {
  schemaVersion: 1,
  legId: 'leg',
  snapshotFingerprint: 'fixed',
  header: {
    title: 'LEG 1 OF 1 — KADW → PAED',
    date: '25 Oct 2026',
    timing: 'DEP 10:00 ET | ARR 18:00 ET | 8h 00m',
    notice: null,
  },
  flight: { startUtc: '2026-10-25T14:00:00Z', endUtc: '2026-10-25T22:00:00Z' },
  intervals: [
    {
      startUtc: '2026-10-25T14:00:00Z',
      endUtc: '2026-10-25T16:25:00Z',
      posture: 'Nominal',
      decisions: ['Up', 'Up', 'Up'],
      restrictionLabels: ['Takeoff SOF'],
    },
    {
      startUtc: '2026-10-25T16:25:00Z',
      endUtc: '2026-10-25T16:30:00Z',
      posture: 'Communications unavailable',
      decisions: ['Down', 'Down', 'Down'],
      restrictionLabels: [],
    },
    {
      startUtc: '2026-10-25T16:30:00Z',
      endUtc: '2026-10-25T22:00:00Z',
      posture: 'Nominal',
      decisions: ['Up', 'Up', 'Up'],
      restrictionLabels: ['Landing SOF'],
    },
  ],
  rows: [],
};
async function renderer() {
  assert.ok(
    existsSync(new URL('./timeline.mjs', import.meta.url)),
    'timeline contract absent'
  );
  return (await import('./timeline.mjs')).renderTimeline;
}
test('exact red geometry', async () => {
  const svg = (await renderer())(payload);
  const red = svg.match(
    /data-posture="Communications unavailable"[^>]*width="([^"]+)"/
  );
  assert.ok(red);
  assert.equal(Number(red[1]) / 960, 5 / 480);
  assert.doesNotMatch(svg, /Takeoff SOF|Landing SOF|data-restriction-label/);
  assert.equal((svg.match(/data-restriction width=/g) || []).length, 2);
  assert.doesNotMatch(svg, /data-callout/);
});
test('unknown has neutral confirmed capability', async () => {
  const p = structuredClone(payload);
  p.intervals.forEach((i) => {
    i.posture = 'Posture uncertain';
    i.decisions[2] = '?';
  });
  const svg = (await renderer())(p);
  assert.match(svg, /confirmed/);
  assert.doesNotMatch(svg, /fill="#b72e36"/);
  assert.match(svg, />\?<\/text>/);
});
test('short-flight overlapping SOF retains its exact band without floating labels', async () => {
  const p = structuredClone(payload);
  p.flight.endUtc = '2026-10-25T14:10:00Z';
  p.intervals = [
    {
      startUtc: p.flight.startUtc,
      endUtc: p.flight.endUtc,
      posture: 'Nominal',
      decisions: ['Up', 'Up', 'Up'],
      restrictionLabels: ['Takeoff SOF', 'Landing SOF'],
    },
  ];
  const svg = (await renderer())(p);
  assert.match(svg, /data-restriction width="960"/);
  assert.doesNotMatch(svg, /Takeoff SOF|Landing SOF|data-restriction-label/);
});
test('fall-back axis distinguishes repeated Eastern clock hours without changing geometry', async () => {
  const p = structuredClone(payload);
  p.flight = {
    startUtc: '2026-11-01T05:00:00Z',
    endUtc: '2026-11-01T09:00:00Z',
  };
  p.intervals = [{ ...p.intervals[0], ...p.flight, restrictionLabels: [] }];
  const svg = (await renderer())(p);
  assert.match(svg, />01:00 EDT<\/text>/);
  assert.match(svg, />01:00 EST<\/text>/);
  assert.equal((svg.match(/class="axis"/g) || []).length, 5);
  assert.equal((svg.match(/M\d+ 224v5/g) || []).length, 9);
  assert.match(svg, /data-posture="Nominal"[^>]*width="960"/);
});
test('fractional-minute short-flight ticks retain seconds at their exact positions', async () => {
  const p = structuredClone(payload);
  p.flight.endUtc = '2026-10-25T14:10:00Z';
  p.intervals = [{ ...p.intervals[0], ...p.flight, restrictionLabels: [] }];
  const svg = (await renderer())(p);
  assert.match(svg, />10:01:15<\/text>/);
  assert.match(svg, />10:02:30<\/text>/);
  assert.match(svg, />10:03:45<\/text>/);
  assert.equal((svg.match(/class="axis"/g) || []).length, 9);
});
test('short repeated-hour axis keeps exact clocks readable and measured', async () => {
  const p = structuredClone(payload);
  p.flight = {
    startUtc: '2026-11-01T05:00:00Z',
    endUtc: '2026-11-01T05:10:00Z',
  };
  p.intervals = [{ ...p.intervals[0], ...p.flight, restrictionLabels: [] }];
  const svg = (await renderer())(p);
  assert.equal((svg.match(/M\d+ 224v5/g) || []).length, 9);
  const labels = [
    ...svg.matchAll(/<text x="([^"]+)" y="244" ([^>]+)>([^<]+)<\/text>/g),
  ];
  assert.deepEqual(
    labels.map((m) => Number(m[1])),
    [280, 520, 760, 1000, 1240]
  );
  assert.deepEqual(
    labels.map((m) => m[3]),
    [
      '01:00:00 EDT',
      '01:02:30 EDT',
      '01:05:00 EDT',
      '01:07:30 EDT',
      '01:10:00 EDT',
    ]
  );
  assert.ok(labels.every((m) => m[2].includes('data-svg-label')));
  assert.match(svg, /data-posture="Nominal"[^>]*width="960"/);
});

test('narrow incomplete intervals expose one and zero confirmed without definitive color', async () => {
  const p = structuredClone(payload);
  const at = (h, m) => `2026-10-25T${h}:${m}:00Z`;
  p.intervals = [
    [at('14', '00'), at('14', '15'), ['Up', 'Up', '?']],
    [at('14', '15'), at('16', '00'), ['Up', 'Up', '?']],
    [at('16', '00'), at('16', '15'), ['Down', 'Up', '?']],
    [at('16', '15'), at('16', '45'), ['Down', 'Down', '?']],
    [at('16', '45'), at('17', '00'), ['Down', 'Up', '?']],
    [at('17', '00'), at('21', '45'), ['Up', 'Up', '?']],
    [at('21', '45'), at('22', '00'), ['Up', 'Up', '?']],
  ].map(([startUtc, endUtc, decisions]) => ({
    startUtc,
    endUtc,
    decisions,
    posture: 'Posture uncertain',
    restrictionLabels: [],
  }));
  const svg = (await renderer())(p);
  assert.equal((svg.match(/>1 confirmed<\/text>/g) || []).length, 2);
  assert.match(svg, />0 confirmed<\/text>/);
  assert.equal((svg.match(/data-callout/g) || []).length, 3);
  assert.equal((svg.match(/>2 confirmed<\/text>/g) || []).length, 2);
  assert.doesNotMatch(svg, /fill="#b72e36"/);
});

test('separated refueling windows retain exact bands and quiet gaps without floating labels', async () => {
  const p = structuredClone(payload);
  p.flight = {
    startUtc: '2026-10-29T14:00:00Z',
    endUtc: '2026-10-30T06:10:10Z',
  };
  p.intervals = [
    ['2026-10-29T14:00:00Z', '2026-10-29T18:18:29Z', []],
    ['2026-10-29T18:18:29Z', '2026-10-29T19:50:32Z', ['Air refueling']],
    ['2026-10-29T19:50:32Z', '2026-10-29T22:58:53Z', []],
    ['2026-10-29T22:58:53Z', '2026-10-30T00:05:05Z', ['Air refueling']],
    ['2026-10-30T00:05:05Z', '2026-10-30T06:10:10Z', []],
  ].map(([startUtc, endUtc, restrictionLabels]) => ({
    startUtc,
    endUtc,
    restrictionLabels,
    posture: 'Nominal',
    decisions: ['Up', 'Up', 'Up'],
  }));
  const svg = (await renderer())(p);
  const bands = [
    ...svg.matchAll(
      /<rect x="([^"]+)" y="202" data-restriction width="([^"]+)"/g
    ),
  ];
  assert.equal(bands.length, 2);
  const duration = (16 * 3600 + 10 * 60 + 10) * 1000;
  assert.equal(
    Number(bands[0][1]),
    280 + (((4 * 3600 + 18 * 60 + 29) * 1000) / duration) * 960
  );
  assert.equal(
    Number(bands[0][2]),
    (((3600 + 32 * 60 + 3) * 1000) / duration) * 960
  );
  assert.doesNotMatch(svg, /Air refueling|data-restriction-label/);
});
