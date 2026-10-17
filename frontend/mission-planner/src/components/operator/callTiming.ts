import type { RecordTime, SavedRecord } from '@/types/operator';
export function preparationAt(record: SavedRecord): string | null {
  const p = record.payload;
  if (
    record.deleted ||
    p.entry_type !== 'call' ||
    !['tentative', 'scheduled', 'delayed'].includes(p.status) ||
    p.prep_lead_minutes == null ||
    !record.time.planned_start_at
  )
    return null;
  const start = Date.parse(record.time.planned_start_at);
  const lead = p.prep_lead_minutes;
  if (
    !Number.isFinite(start) ||
    !Number.isInteger(lead) ||
    lead < 0 ||
    lead > 10080
  )
    return null;
  return new Date(start - lead * 60000).toISOString();
}
export function shiftCallTime(time: RecordTime, minutes: number): RecordTime {
  if (
    !Number.isInteger(minutes) ||
    Math.abs(minutes) > 525600 ||
    !time.planned_start_at
  )
    throw new Error(
      'Enter a whole-minute shift within one year and a known planned start.'
    );
  const shift = (value: string) => {
    const result = new Date(Date.parse(value) + minutes * 60000);
    if (
      !Number.isFinite(result.getTime()) ||
      result.getUTCFullYear() < 1 ||
      result.getUTCFullYear() > 9999
    )
      throw new Error('Shift produces an invalid UTC time.');
    return result.toISOString();
  };
  return {
    ...time,
    planned_start_at: shift(time.planned_start_at),
    planned_end_at: time.planned_end_at ? shift(time.planned_end_at) : null,
  };
}
