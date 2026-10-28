import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';

/** Real browser pointer events, outside screenshot/timing capture. */
export async function verifyPoiPicking(page, frames, snapshot) {
  const mode = page.getByLabel('Mode', { exact: true });
  const samples = [];
  for (const value of ['current', 'bloom', 'current']) {
    await mode.selectOption(value);
    await frames(page);
    const state = await snapshot(page);
    const box = await page.locator('canvas').boundingBox();
    const camera = new PerspectiveCamera(45, box.width / box.height, 0.1, 100);
    camera.position.fromArray(state.camera);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    const pixel = (latitude, longitude, offset = 0) => {
      const lat = (latitude * Math.PI) / 180,
        lon = (longitude * Math.PI) / 180;
      const p = new Vector3(
        2.000001 * Math.cos(lat) * Math.cos(lon),
        2.000001 * Math.sin(lat),
        -2.000001 * Math.cos(lat) * Math.sin(lon)
      ).project(camera);
      return {
        x: box.x + ((p.x + 1) * box.width) / 2 + offset,
        y: box.y + ((1 - p.y) * box.height) / 2,
      };
    };
    const status = page.locator('footer [role=status]');
    const beforeFar = await status.textContent();
    const far = pixel(0, 90);
    await page.mouse.click(far.x, far.y);
    assert.equal(
      await status.textContent(),
      beforeFar,
      'far-side POI must not receive a click'
    );
    const selected = [];
    for (const [lat, lon, offset] of [
      [16, -65, 0],
      [16, -65, 8],
      [35, -90, 0],
      [35, -90, 8],
    ]) {
      // Force a distinct result before every sample. A missing offset event
      // must not inherit the preceding center click's successful status.
      const sentinel = pixel(42, -30);
      await page.mouse.click(sentinel.x, sentinel.y);
      await status
        .filter({ hasText: /^Picked synthetic POI: bravo$/ })
        .waitFor();
      const p = pixel(lat, lon, offset);
      await page.mouse.click(p.x, p.y);
      await status
        .filter({
          hasText:
            lat === 16
              ? /^Picked synthetic POI: charlie$/
              : /^Picked synthetic POI: (alpha|overlap)$/,
        })
        .waitFor();
      selected.push({
        pixel: p,
        id: (await status.textContent()).replace('Picked synthetic POI: ', ''),
      });
    }
    assert.equal(selected[0].id, 'charlie');
    assert.equal(selected[1].id, 'charlie');
    assert.ok(['alpha', 'overlap'].includes(selected[2].id));
    assert.ok(['alpha', 'overlap'].includes(selected[3].id));
    samples.push({
      mode: value,
      selected,
      farSide: { pixel: far, selected: false },
    });
  }
  assert.deepEqual(samples[1].selected, samples[0].selected);
  assert.deepEqual(samples[2].selected, samples[0].selected);
  return samples;
}
