import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { payload } from './timeline.test.mjs';
async function composer() {
  assert.ok(
    existsSync(new URL('./document.mjs', import.meta.url)),
    'HTML contract absent'
  );
  return (await import('./document.mjs')).composeBriefing;
}
const assets = {
  apoDataUrl: 'data:image/png;base64,AA==',
  regularFontDataUrl: 'data:font/ttf;base64,AA==',
  boldFontDataUrl: 'data:font/ttf;base64,AA==',
  cssText: '@page{margin:0}',
};
test('escaped customer strings', async () => {
  const p = structuredClone(payload);
  p.header.title = '<script>customer input</script>';
  const html = (await composer())(p, assets);
  assert.ok(!html.includes('<script>customer input</script>'));
  assert.match(html, /&lt;script&gt;customer input/);
});
test('one incomplete-X notice', async () => {
  const p = structuredClone(payload);
  p.header.notice =
    'X-Band planning incomplete — confirmed transport capability shown below.';
  const html = (await composer())(p, assets);
  assert.equal((html.match(/X-Band planning incomplete/g) || []).length, 1);
  assert.equal((html.match(/class="briefing-page/g) || []).length, 1);
});
test('no map reclaims grid', async () => {
  const html = (await composer())(payload, assets);
  assert.match(html, /without-map/);
  assert.doesNotMatch(html, /class="map-card"/);
});
test('a fitting mission primary preserves the accepted checkpoint page', async () => {
  const compose = await composer();
  const withMap = { ...assets, mapDataUrl: 'data:image/png;base64,AA==' };
  assert.equal(
    compose(payload, withMap, {
      kind: 'primary',
      legPage: 1,
      legPageCount: 1,
      continued: false,
    }),
    compose(payload, withMap)
  );
});
test('renders four canonical display cells as escaped customer text', async () => {
  const p = structuredClone(payload);
  p.rows = [
    {
      id: 'row',
      et: 'old time',
      impact: 'old impact',
      remaining: 'old remaining',
      posture: 'old posture',
      displayCells: [
        '01:30 EDT–01:30 EST',
        '<safe cause>',
        'Ka, Starshield',
        'Incomplete',
      ],
    },
  ];
  p.mapInputDiagnostics = ['PRIVATE map diagnostic'];
  const html = (await composer())(p, assets);
  assert.match(html, /01:30 EDT–01:30 EST/);
  assert.match(html, /&lt;safe cause&gt;/);
  assert.doesNotMatch(
    html,
    /old time|old impact|old remaining|old posture|PRIVATE map diagnostic/
  );
});
test('rejects incomplete canonical display cells', async () => {
  const p = structuredClone(payload);
  p.rows = [
    {
      id: 'row',
      et: '10:00',
      impact: 'SOF',
      remaining: 'Ka',
      posture: 'Nominal',
      displayCells: ['one cell'],
    },
  ];
  const compose = await composer();
  assert.throws(() => compose(p, assets), /four display cells/);
});

test('mission continuation repeats identity clocks and caveat without map or timeline', async () => {
  const module = await import('./document.mjs');
  assert.equal(
    typeof module.composeMissionBriefing,
    'function',
    'Mission composition absent'
  );
  const leg = structuredClone(payload);
  leg.legId = 'leg';
  leg.rows = [0, 1].map((i) => ({
    id: 'row-' + i,
    displayCells: ['≈ 01:30 EDT–01:30 EST', '<impact>', 'Ka', 'Incomplete'],
  }));
  leg.header.notice = 'Assessment incomplete';
  const mission = {
    schemaVersion: 2,
    missionId: 'm',
    snapshotFingerprint: 'f',
    legs: [leg],
  };
  const plan = {
    schemaVersion: 2,
    missionId: 'm',
    snapshotFingerprint: 'f',
    pages: [
      {
        page: 1,
        legId: 'leg',
        kind: 'primary',
        legPage: 1,
        legPageCount: 2,
        rowIds: ['row-0'],
      },
      {
        page: 2,
        legId: 'leg',
        kind: 'continuation',
        legPage: 2,
        legPageCount: 2,
        rowIds: ['row-1'],
      },
    ],
  };
  const html = module.composeMissionBriefing(mission, plan, {
    ...assets,
    maps: { leg: 'data:image/png;base64,AA==' },
  });
  assert.equal((html.match(/class="briefing-page/g) || []).length, 2);
  assert.equal((html.match(/class="timeline"/g) || []).length, 1);
  assert.equal((html.match(/class="map-card"/g) || []).length, 1);
  for (const text of ['Assessment incomplete', 'not a throughput guarantee'])
    assert.equal(html.split(text).length - 1, 2, text);
  assert.equal(
    (html.match(/<td class="et" data-fit>≈ 01:30 EDT–01:30 EST<\/td>/g) || [])
      .length,
    2
  );
  assert.match(html, /Page 2 of 2/);
  assert.match(html, /Coordination windows continued/);
  assert.match(html, /continues on next page/);
  assert.match(html, /&lt;impact&gt;/);
  assert.equal((html.match(/data-row-id="row-0"/g) || []).length, 1);
  assert.equal((html.match(/data-row-id="row-1"/g) || []).length, 1);
  assert.throws(
    () =>
      module.composeMissionBriefing(
        mission,
        { ...plan, snapshotFingerprint: 'wrong' },
        assets
      ),
    /identity/
  );
  const missing = structuredClone(plan);
  missing.pages[1].rowIds = [];
  assert.throws(
    () => module.composeMissionBriefing(mission, missing, assets),
    /coverage/
  );
});
