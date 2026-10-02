export type OverviewLayoutMode = 'desktop' | 'landscape' | 'stacked';
export interface OverviewLayoutInput {
  width: number;
  height: number;
  rootFontSize: number;
  clockHeight: number;
  overlayHeight: number;
  overflow?: boolean;
}
export interface OverviewSafeRect {
  x: number;
  y: number;
  width: number;
  height: number;
}
/** Only available CSS space and readable text budgets select a layout. */
export function resolveOverviewLayout({
  width,
  height,
  rootFontSize,
  clockHeight,
  overlayHeight,
  overflow,
}: OverviewLayoutInput): OverviewLayoutMode {
  if (overflow) return 'stacked';
  const scale = Math.max(1, rootFontSize / 16);
  if (
    width >= Math.max(1500, 93.75 * rootFontSize) &&
    height >= Math.max(1012, 63.25 * rootFontSize)
  )
    return 'desktop';
  const usable = width - 24;
  const rail = Math.min(240 * scale, Math.max(210 * scale, usable * 0.28));
  const stageHeight = height - clockHeight - 34;
  if (
    usable >= 800 * scale &&
    height >= 300 * scale &&
    height <= 600 &&
    usable - rail - 12 >= 560 * scale &&
    stageHeight >= 220 * scale &&
    stageHeight - overlayHeight - 24 >= 120 * scale
  )
    return 'landscape';
  return 'stacked';
}
