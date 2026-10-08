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
  assert.match(svg, /data-callout/);
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

test('narrow incomplete intervals expose one and zero confirmed without definitive color', async () => {
  const p = structuredClone(payload);
  const at = (h, m) => `2026-10-25T${h}:${m}:00Z`;
  p.intervals = [
    [at('14', '00'), at('16', '00'), ['Up', 'Up', '?']],
    [at('16', '00'), at('16', '15'), ['Down', 'Up', '?']],
    [at('16', '15'), at('16', '45'), ['Down', 'Down', '?']],
    [at('16', '45'), at('17', '00'), ['Down', 'Up', '?']],
    [at('17', '00'), at('22', '00'), ['Up', 'Up', '?']],
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
  assert.doesNotMatch(svg, /fill="#b72e36"/);
});
