import assert from 'node:assert/strict';
import { test } from 'node:test';
import { rasterSizeForPlacement } from './raster-policy.mjs';

test('raster placement uses 300 printed pixels per inch with independent rounding', () => {
  assert.deepEqual(rasterSizeForPlacement({ width: 84, height: 84 }), {
    width: 263,
    height: 263,
  });
  assert.deepEqual(rasterSizeForPlacement({ width: 280, height: 270 }), {
    width: 875,
    height: 844,
  });
  assert.deepEqual(rasterSizeForPlacement({ width: 280, height: 270.1 }), {
    width: 875,
    height: 845,
  });
  assert.deepEqual(rasterSizeForPlacement({ width: 0.01, height: 0.1 }), {
    width: 1,
    height: 1,
  });
  for (const value of [0, -1, NaN, Infinity, '84', null]) {
    assert.throws(() => rasterSizeForPlacement({ width: value, height: 270 }));
    assert.throws(() => rasterSizeForPlacement({ width: 280, height: value }));
  }
});
