export type BloomView = 'final' | 'bright' | 'bloom';
export type BloomMode = 'current' | 'output' | 'bloom';
export interface BloomSettings {
  strength: number;
  threshold: number;
  radius: number;
  maxDimension: number;
  exposure: number;
  view: BloomView;
}
export const DEFAULT_BLOOM: BloomSettings = {
  strength: 0.4,
  threshold: 1.2,
  radius: 0.2,
  maxDimension: 960,
  exposure: 1,
  view: 'final',
};

// Input sizes are actual drawing-buffer pixels, never CSS pixels.
export function bloomSize(
  width: number,
  height: number,
  maxDimension: number
): [number, number] {
  const scale = Math.min(1, maxDimension / Math.max(1, width, height));
  return [
    Math.max(1, Math.round(width * scale)),
    Math.max(1, Math.round(height * scale)),
  ];
}
export function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}
export function frameSummary(samples: readonly number[]) {
  if (!samples.length) return null;
  const sorted = [...samples].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return {
    count: sorted.length,
    medianMs:
      sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2,
    p95Ms: sorted[Math.ceil(sorted.length * 0.95) - 1],
    durationMs: samples.reduce((sum, value) => sum + value, 0),
  };
}
export function allowRequest(input: string, method: string, origin: string) {
  const url = new URL(input, origin);
  return (
    ['GET', 'HEAD'].includes(method.toUpperCase()) &&
    url.origin === origin &&
    ['http:', 'https:'].includes(url.protocol) &&
    (url.pathname.startsWith('/assets/') ||
      ['/earth-day-hi.jpg', '/city-lights-mask.png'].includes(url.pathname))
  );
}

export interface ViewportSignature {
  css: number[];
  drawing: number[];
  dpr: number;
}
export function capturePhase(
  expected: ViewportSignature,
  actual: ViewportSignature,
  frame: number
) {
  if (
    expected.dpr !== actual.dpr ||
    expected.css.some((v, i) => v !== actual.css[i]) ||
    expected.drawing.some((v, i) => v !== actual.drawing[i])
  )
    return 'changed';
  return frame <= 60 ? 'warmup' : 'sample';
}
