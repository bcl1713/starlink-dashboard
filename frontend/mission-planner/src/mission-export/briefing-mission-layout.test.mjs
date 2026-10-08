import { test } from 'node:test';
import assert from 'node:assert/strict';
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
