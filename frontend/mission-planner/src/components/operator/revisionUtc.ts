// Keep fractional precision intact and never convert UTC through local time.
export const revisionUtc = (value: string | null) =>
  value ? `${value.replace('T', ' ').replace(/Z$/, '')} Zulu` : 'Unknown';
