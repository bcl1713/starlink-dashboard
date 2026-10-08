import { test } from 'node:test';
import assert from 'node:assert/strict';
export function registerMapTests({ run, clean, root, assetRoot }) {
  test('map failure reclaims card', async () => {
    const r = await run('map-failure', 'map');
    assert.equal(r.status, 'success', JSON.stringify(r));
    assert.equal(r.map.status, 'unavailable');
    assert.equal(r.fit.mapCount, 0);
    clean(r);
  });
  test('map cutoff preserves PDF reserve', async () => {
    const r = await run('hung-map', 'map-hang', false, {
      budgetMs: 12000,
      pdfReserveMs: 7000,
      cleanupReserveMs: 1000,
    });
    assert.equal(r.status, 'success', JSON.stringify(r));
    assert.equal(r.map.status, 'unavailable');
    assert.ok(r.totalMs < 12000);
    clean(r);
  });
}
