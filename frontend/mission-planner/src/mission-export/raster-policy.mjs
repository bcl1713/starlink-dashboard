/** Raster pixels per printed inch; placements use 96 CSS pixels per inch. */
export const PRINT_RASTER_PPI = 300;
export function rasterSizeForPlacement({ width, height }) {
  if (![width, height].every((size) => Number.isFinite(size) && size > 0)) {
    throw new RangeError('Raster placement dimensions must be finite and positive');
  }
  return {
    width: Math.ceil((width * PRINT_RASTER_PPI) / 96),
    height: Math.ceil((height * PRINT_RASTER_PPI) / 96),
  };
}
