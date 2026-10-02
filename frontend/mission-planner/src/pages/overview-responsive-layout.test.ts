import { describe, it, expect } from 'vitest';
import { resolveOverviewLayout } from './overview-responsive-layout';
describe('available Overview viewport', () => {
  it.each([
    [1920, 1015, 16, 'desktop'],
    [2000, 1268, 16, 'desktop'],
    [2000, 1268, 24, 'stacked'],
    [1500, 1012, 16, 'desktop'],
    [1499, 1012, 16, 'stacked'],
    [1500, 1011, 16, 'stacked'],
    [1920, 835, 16, 'stacked'],
    [390, 779, 16, 'stacked'],
    [360, 735, 16, 'stacked'],
    [844, 325, 16, 'landscape'],
    [844, 235, 16, 'stacked'],
    [704, 835, 16, 'stacked'],
    [844, 325, 24, 'stacked'],
    [1920, 1015, 32, 'stacked'],
  ])(
    'uses measured %sx%s at root %s for %s',
    (width, height, rootFontSize, want) => {
      expect(
        resolveOverviewLayout({
          width,
          height,
          rootFontSize,
          clockHeight: 56,
          overlayHeight: 90,
        })
      ).toBe(want);
    }
  );
  it('escapes landscape when overlays consume the map-safe region', () => {
    expect(
      resolveOverviewLayout({
        width: 844,
        height: 325,
        rootFontSize: 16,
        clockHeight: 56,
        overlayHeight: 200,
      })
    ).toBe('stacked');
  });
});
