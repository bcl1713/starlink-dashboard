export function eventUtc(value: string | null | undefined) {
  return value && Number.isFinite(Date.parse(value))
    ? new Date(value)
        .toISOString()
        .replace('T', ' ')
        .replace(/\.\d+Z$/, ' UTC')
    : 'Time unknown';
}

export function timelineTime(value: string, reference?: string | null) {
  const utc = eventUtc(value);
  return reference && value.slice(0, 10) !== reference.slice(0, 10)
    ? utc.slice(0, 16) + ' UTC'
    : utc.slice(11, 16) + ' UTC';
}
