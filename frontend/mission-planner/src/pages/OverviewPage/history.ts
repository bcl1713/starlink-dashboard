export interface NumericSample {
  timestamp: string;
  value: number;
}

export interface Summary {
  current: number | null;
  min: number | null;
  average: number | null;
  max: number | null;
}

const WINDOW_MS = 30 * 60 * 1000;
const MAX_SAMPLES = 1801;

export function mergeHistory(
  existing: readonly NumericSample[],
  incoming: readonly NumericSample[],
  now: number
): NumericSample[] {
  const earliest = now - WINDOW_MS;
  const byTime = new Map<number, NumericSample>();
  for (const sample of [...existing, ...incoming]) {
    const instant = Date.parse(sample.timestamp);
    if (
      Number.isFinite(instant) &&
      instant >= earliest &&
      instant <= now &&
      Number.isFinite(sample.value)
    ) {
      byTime.set(instant, sample);
    }
  }
  return [...byTime.entries()]
    .sort(([left], [right]) => left - right)
    .slice(-MAX_SAMPLES)
    .map(([, sample]) => sample);
}

export function appendSample(
  existing: readonly NumericSample[],
  sample: NumericSample,
  now: number
): NumericSample[] {
  return mergeHistory(existing, [sample], now);
}

export function summarizeWindow(
  samples: readonly NumericSample[],
  now: number,
  seconds: number
): Summary {
  const values = samples
    .filter((sample) => {
      const instant = Date.parse(sample.timestamp);
      return instant >= now - seconds * 1000 && instant <= now;
    })
    .map(({ value }) => value)
    .filter(Number.isFinite);
  if (values.length === 0) {
    return { current: null, min: null, average: null, max: null };
  }
  return {
    current: values[values.length - 1],
    min: Math.min(...values),
    average: values.reduce((sum, value) => sum + value, 0) / values.length,
    max: Math.max(...values),
  };
}
