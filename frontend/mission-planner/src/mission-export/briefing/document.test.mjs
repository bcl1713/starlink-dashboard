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
