/** Shared UTC and elapsed-time labels for planning timelines. */
export function formatUtc(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? date.toISOString().slice(0, 19).replace('T', ' ')
    : value;
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return 'N/A';
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  return [
    hours ? `${hours}h` : '',
    minutes ? `${minutes}m` : '',
    remainder || (!hours && !minutes) ? `${remainder}s` : '',
  ]
    .filter(Boolean)
    .join(' ');
}

export function formatElapsed(timestamp: string, start: string): string {
  return `T+${formatDuration((new Date(timestamp).getTime() - new Date(start).getTime()) / 1000)}`;
}
