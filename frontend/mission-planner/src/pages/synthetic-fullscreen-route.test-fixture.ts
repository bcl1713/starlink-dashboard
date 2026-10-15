/** Invented issue #272 geometry; contains no operator mission coordinates. */
export const syntheticFullscreenCoordinates = [
  { latitude: 48, longitude: -135 },
  { latitude: 52, longitude: -172 },
  { latitude: 52, longitude: -180 },
  { latitude: 49, longitude: 170 },
  { latitude: 31, longitude: 145 },
  ...Array.from({ length: 12 }, (_, i) => ({
    latitude: 25 - i,
    longitude: 140 - i * 5,
  })),
];
