/** Shared, copyable controls for the aircraft chevron experiment. Sizes are CSS pixels. */
export interface ChevronSettings {
  ownSizePixels: number;
  trafficSizePixels: number;
  coreWhiteness: number;
  coreWidthPixels: number;
  /** Glow width is each aircraft's CSS-pixel size divided by this value. */
  glowWidthDivisor: number;
  glowStrength: number;
}
export const DEFAULT_CHEVRON_SETTINGS: Readonly<ChevronSettings> = {
  ownSizePixels: 15,
  trafficSizePixels: 10,
  coreWhiteness: 0.45,
  coreWidthPixels: 0.4,
  glowWidthDivisor: 3,
  glowStrength: 0.6,
};
