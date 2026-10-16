import { describe, it, expect } from 'vitest';
import { resolveOverviewLayout } from './overview-responsive-layout';

describe('available Overview viewport', () => {
  it.each([
    [1920, 1080, 16, 'desktop'],
    [1920, 1015, 16, 'desktop'],
    [1366, 703, 16, 'landscape'],
    [1440, 835, 16, 'landscape'],
    [1920, 835, 16, 'landscape'],
    [1100, 500, 16, 'landscape'],
    [1024, 768, 16, 'stacked'],
    [844, 325, 16, 'stacked'],
    [390, 779, 16, 'stacked'],
    [360, 735, 16, 'stacked'],
    [2000, 1268, 24, 'landscape'],
    [1366, 703, 24, 'stacked'],
    [1920, 1015, 32, 'stacked'],
  ])('uses %sx%s at root %s for %s', (width, height, rootFontSize, want) => {
    expect(
      resolveOverviewLayout({
        width,
        height,
        rootFontSize,
        clockHeight: 56,
        overlayHeight: 90,
      })
    ).toBe(want);
  });

  it('does not change composition when legend or feed content grows', () => {
    for (const overlayHeight of [0, 90, 500]) {
      for (const fullscreen of [false, true]) {
        expect(
          resolveOverviewLayout({
            width: 1366,
            height: 703,
            rootFontSize: 16,
            clockHeight: 56,
            overlayHeight,
            fullscreen,
            overflow: true,
          })
        ).toBe('landscape');
      }
    }
  });
});
