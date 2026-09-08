export const TERMINATOR_HALF_WIDTH = 0.15;

function smoothstep(
  lowerEdge: number,
  upperEdge: number,
  value: number
): number {
  const progress = Math.min(
    1,
    Math.max(0, (value - lowerEdge) / (upperEdge - lowerEdge))
  );

  return progress * progress * (3 - 2 * progress);
}

export function nightSideFactor(sunFacing: number): number {
  return smoothstep(-TERMINATOR_HALF_WIDTH, TERMINATOR_HALF_WIDTH, -sunFacing);
}
