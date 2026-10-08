import { test } from 'node:test';
import assert from 'node:assert/strict';
export function registerDocumentTests({ run, clean, root, assetRoot }) {
  test('one launch two isolated contexts; dimensions fonts narrow red callout', async () => {
    const r = await run('primary');
    assert.equal(r.status, 'success', JSON.stringify(r));
    assert.equal(r.launchCount, 1);
    assert.equal(r.sharedBrowser, true);
    assert.equal(r.map.status, 'primary');
    assert.equal(r.cleanup.contextCount, 2);
    assert.equal(r.fit.page.width, 1280);
    assert.equal(r.fit.page.height, 720);
    assert.equal(r.fit.redFraction, 5 / 480);
    assert.deepEqual(r.fit.fonts, ['Briefing 400', 'Briefing 700']);
    assert.equal(r.fit.overflow.length, 0);
    clean(r);
  });
  test('unknown X keeps confirmed risks', async () => {
    const r = await run('incomplete', null, true);
    assert.equal(r.status, 'success', JSON.stringify(r));
    assert.equal(r.fit.noticeCount, 1);
    assert.equal(
      r.fit.labels.filter((l) => l.text === '1 confirmed').length,
      2
    );
    assert.equal(
      r.fit.labels.filter((l) => l.text === '0 confirmed').length,
      1
    );
    assert.equal(
      r.fit.postures.filter((p) => p === 'Communications unavailable').length,
      0
    );
    clean(r);
  });
  for (const [fault, code] of [
    ['startup', 'startup'],
    ['font', 'font'],
    ['image', 'image'],
    ['print', 'print'],
    ['overflow-title', 'fit'],
    ['overflow-table', 'fit'],
    ['remote', 'resource'],
    ['traversal', 'resource'],
    ['cleanup', 'cleanup'],
  ]) {
    test(`${fault} failure omits artifacts and cleans owner`, async () => {
      const r = await run(fault, fault);
      assert.equal(r.status, 'failed', JSON.stringify(r));
      assert.equal(r.errorCode, code);
      assert.equal(r.artifacts, null);
      clean(r);
    });
  }
  test('hung print deadline cleans owner', async () => {
    const r = await run('hung-print', 'print-hang', false, {
      budgetMs: 8000,
      pdfReserveMs: 4500,
      cleanupReserveMs: 1000,
    });
    assert.equal(r.status, 'failed');
    assert.equal(r.errorCode, 'deadline');
    assert.equal(r.artifacts, null);
    assert.ok(r.totalMs < 9000);
    clean(r);
  });
}
