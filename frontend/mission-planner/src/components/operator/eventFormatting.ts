/** Fixed 24-hour Zulu presentation, independent of browser locale. */
export function eventUtc(value: string | null | undefined) {
  return value && Number.isFinite(Date.parse(value))
    ? new Date(value)
        .toISOString()
        .replace('T', ' ')
        .replace(/\.\d+Z$/, ' Zulu')
    : 'Time Unknown';
}

export function timelineTime(value: string, reference?: string | null) {
  const zulu = eventUtc(value);
  if (zulu === 'Time Unknown') return zulu;
  const referenceZulu = reference ? eventUtc(reference) : null;
  return referenceZulu && zulu.slice(0, 10) !== referenceZulu.slice(0, 10)
    ? zulu.slice(0, 16) + ' Zulu'
    : zulu.slice(11, 16) + ' Zulu';
}
