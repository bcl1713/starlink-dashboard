const STATUS_STALE_AFTER_MS = 10_000;
const STATUS_CLOCK_SKEW_TOLERANCE_MS = 5_000;

/** Keep collection time authoritative while allowing clock skew and render ticks. */
export function statusObservationAgeMs(timestamp: string, now: number) {
  const observedAt = Date.parse(timestamp);
  const age = now - observedAt;
  if (
    !Number.isFinite(observedAt) ||
    !Number.isFinite(age) ||
    age < -STATUS_CLOCK_SKEW_TOLERANCE_MS
  ) {
    return null;
  }
  return Math.max(0, age);
}

export function isStatusStale(timestamp: string, now: number) {
  const age = statusObservationAgeMs(timestamp, now);
  return age === null || age >= STATUS_STALE_AFTER_MS;
}
