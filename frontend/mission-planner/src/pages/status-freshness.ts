const STATUS_STALE_AFTER_MS = 5_000;

export function isStatusStale(timestamp: string, now: number) {
  const observedAt = Date.parse(timestamp);

  return (
    !Number.isFinite(observedAt) || now - observedAt >= STATUS_STALE_AFTER_MS
  );
}
