const STATUS_STALE_AFTER_MS = 5_000;

export function isStatusStale(timestamp: string, now: number) {
  return now - Date.parse(timestamp) >= STATUS_STALE_AFTER_MS;
}
