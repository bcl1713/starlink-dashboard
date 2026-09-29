export interface MotionOptions {
  elapsedSeconds: number;
  widthPixels: number;
  windowSeconds: number;
  bufferSeconds: number;
}

/** Translate real samples only; stop when the fresh-data overscan is exhausted. */
export function motionOffsetPixels({
  elapsedSeconds,
  widthPixels,
  windowSeconds,
  bufferSeconds,
}: MotionOptions): number {
  if (
    ![elapsedSeconds, widthPixels, windowSeconds, bufferSeconds].every(
      Number.isFinite
    ) ||
    elapsedSeconds <= 0 ||
    widthPixels <= 0 ||
    windowSeconds <= 0 ||
    bufferSeconds <= 0
  )
    return 0;
  return (
    -(Math.min(elapsedSeconds, bufferSeconds) / windowSeconds) * widthPixels
  );
}
