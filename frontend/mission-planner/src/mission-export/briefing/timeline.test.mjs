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
  assert.match(svg, /Takeoff SOF/);
  assert.match(svg, /Landing SOF/);
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
test('short-flight overlapping SOF keeps its full-width label inside the exact restriction band', async () => {
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
  const label = svg.match(
    /<text x="([^"]+)" y="216" ([^>]+)>Takeoff SOF \+ Landing SOF<\/text>/
  );
  assert.ok(label);
  assert.ok(Number(label[1]) > 280 && Number(label[1]) < 1240);
  assert.match(label[2], /text-anchor="middle"/);
  assert.match(svg, /data-restriction width="960"/);
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

test('separated refueling windows retain exact bands with readable measured labels', async () => {
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
  const labels = [
    ...svg.matchAll(/<text x="([^"]+)" y="216" ([^>]+)>Air refueling<\/text>/g),
  ];
  assert.equal(labels.length, 2);
  // Reproduce the 92px DejaVu labels measured in the production browser.
  const { positionRestrictionLabels } = await import('./timeline.mjs');
  const positions = positionRestrictionLabels(
    labels.map((label) => ({
      left:
        Number(label[1]) - (label[2].includes('text-anchor="end"') ? 92 : 0),
      width: 92,
    }))
  );
  assert.ok(positions[1] - positions[0] >= 100);
  assert.equal((svg.match(/data-restriction width=/g) || []).length, 2);
});

test('measured restriction labels keep separation near landing without shrinking', async () => {
  const { positionRestrictionLabels } = await import('./timeline.mjs');
  assert.equal(typeof positionRestrictionLabels, 'function');
  const labels = [
    { left: 1074, width: 92 },
    { left: 1105, width: 97 },
  ];
  const positions = positionRestrictionLabels(labels);
  assert.ok(positions[1] - (positions[0] + 92) >= 8);
  assert.ok(positions[0] >= 280);
  assert.ok(positions[1] + 97 <= 1240);
  assert.deepEqual(labels, [
    { left: 1074, width: 92 },
    { left: 1105, width: 97 },
  ]);
});

test('restriction labels retain measured positions when already clear', async () => {
  const { positionRestrictionLabels } = await import('./timeline.mjs');
  assert.equal(typeof positionRestrictionLabels, 'function');
  assert.deepEqual(
    positionRestrictionLabels([
      { left: 320, width: 89 },
      { left: 535, width: 92 },
      { left: 800, width: 92 },
      { left: 1110, width: 97 },
    ]),
    [320, 535, 800, 1110]
  );
});

test('restriction labels reject a lane too crowded for their full measured widths', async () => {
  const { positionRestrictionLabels } = await import('./timeline.mjs');
  assert.equal(typeof positionRestrictionLabels, 'function');
  assert.throws(
    () =>
      positionRestrictionLabels([
        { left: 280, width: 600 },
        { left: 600, width: 600 },
      ]),
    (e) => e.code === 'overflow'
  );
});
