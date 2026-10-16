export type OverviewLayoutMode = 'desktop' | 'landscape' | 'stacked';
export interface OverviewLayoutInput {
  width: number;
  height: number;
  rootFontSize: number;
  clockHeight: number;
  overlayHeight: number;
  overflow?: boolean;
  fullscreen?: boolean;
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
}: OverviewLayoutInput): OverviewLayoutMode {
  const scale = Math.max(1, rootFontSize / 16);
  if (width >= 1500 * scale && height >= 1012 * scale) return 'desktop';
  // Keep enough room for readable metrics, a map and its controls. Short or
  // narrow windows use page flow in either orientation, without content latches.
  if (width >= 1100 * scale && height >= 500 * scale) return 'landscape';
  return 'stacked';
}
