import { test } from 'node:test';
import assert from 'node:assert/strict';
test('normal legs reuse their actual batched primary measurement without loading five candidates', async () => {
  const module = await import('./briefing-mission-layout.mjs');
  assert.equal(
    typeof module.cachePrimaryMeasurements,
    'function',
    'Batched measurement reuse absent'
  );
  let probes = 0;
  const measured = Array.from({ length: 5 }, (_, i) => ({
    legId: 'leg-' + i,
    visibleRowIds: ['r'],
    width: 1280,
    height: 720,
    overflow: [],
    labelOverlaps: [],
  }));
  const measure = module.cachePrimaryMeasurements({
    measured,
    measure: async () => {
      probes++;
      return { fits: true };
    },
  });
  for (let i = 0; i < 5; i++)
    assert.equal(
      (
        await measure({
          legId: 'leg-' + i,
          kind: 'primary',
          rowIds: ['r'],
          continued: false,
        })
      ).fits,
      true
    );
  assert.equal(probes, 0);
  await measure({
    legId: 'leg-0',
    kind: 'primary',
    rowIds: ['r'],
    continued: true,
  });
  await measure({
    legId: 'leg-0',
    kind: 'continuation',
    rowIds: ['r'],
    continued: false,
  });
  await measure({
    legId: 'leg-0',
    kind: 'primary',
    rowIds: [],
    continued: false,
  });
  assert.equal(probes, 3);
});
test('measurement keeps one loaded font head while updating candidate page bodies', async () => {
  const module = await import('./briefing-mission-layout.mjs');
  assert.equal(
    typeof module.createMissionDocumentLoader,
    'function',
    'Loaded-font document reuse absent'
  );
  let heads = 0,
    checks = 0;
  const bodies = [];
  const page = {
    setContent: async () => {
      heads++;
    },
    evaluate: async () => ({ fonts: true, images: true }),
    locator: () => ({
      evaluate: async (fn, body) => {
        bodies.push(body);
      },
    }),
  };
  const load = module.createMissionDocumentLoader({
    page,
    budget: { workRemainingMs: () => 1000 },
    check: () => checks++,
    isBlocked: () => false,
  });
  await load('<html><head>font assets</head><body>primary</body></html>');
  await load('<html><head>font assets</head><body>continuation</body></html>');
  await load(
    '<html><head>font assets</head><body>final assembly</body></html>'
  );
  assert.equal(heads, 1);
  assert.deepEqual(bodies, ['continuation', 'final assembly']);
  assert.equal(checks, 6);
});
