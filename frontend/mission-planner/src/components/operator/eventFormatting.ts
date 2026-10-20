export function eventUtc(value: string | null | undefined) {
  return value && Number.isFinite(Date.parse(value))
    ? new Date(value)
        .toISOString()
        .replace('T', ' ')
        .replace(/\.\d+Z$/, ' UTC')
    : 'Time unknown';
}
