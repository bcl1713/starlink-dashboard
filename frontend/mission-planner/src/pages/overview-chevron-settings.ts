/** Shared, copyable controls for the aircraft chevron experiment. Sizes are CSS pixels. */
export interface ChevronSettings {
  ownSizePixels: number;
  trafficSizePixels: number;
  coreWhiteness: number;
  coreWidthPixels: number;
  glowWidthPixels: number;
  glowStrength: number;
}
export const DEFAULT_CHEVRON_SETTINGS: Readonly<ChevronSettings> = {
  ownSizePixels: 12,
  trafficSizePixels: 10,
  coreWhiteness: 0.85,
  coreWidthPixels: 0.7,
  glowWidthPixels: 1.3,
  glowStrength: 0.45,
};
