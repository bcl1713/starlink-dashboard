export function formatUtcTimestamp(timestamp: string): string {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.[0-9]+)?)?(Z|[+-]\d{2}:\d{2})$/.exec(
      timestamp
    );
  if (!match) return 'Unavailable';
  const [, year, month, day, hour, minute, second = '00', offset] = match;
  if (offset === 'Z' || offset === '+00:00') {
    return `${year}-${month}-${day} ${hour}:${minute}:${second} UTC`;
  }
  const projected = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second)
  );
  const sign = offset[0] === '-' ? -1 : 1;
  const offsetMs =
    sign *
    (Number(offset.slice(1, 3)) * 3_600_000 +
      Number(offset.slice(4, 6)) * 60_000);
  const date = new Date(projected - offsetMs);
  if (!Number.isFinite(date.valueOf())) return 'Unavailable';
  return `${date.getUTCFullYear().toString().padStart(4, '0')}-${String(
    date.getUTCMonth() + 1
  ).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')} ${String(
    date.getUTCHours()
  ).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}:${String(
    date.getUTCSeconds()
  ).padStart(2, '0')} UTC`;
}
