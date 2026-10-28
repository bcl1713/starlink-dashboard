/** Operational displays use Zulu, including legacy saved clock configurations. */
export function formatOperationalClockTime(
  timestamp: number,
  _timeZone: string
): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
    timeZone: _timeZone === 'UTC' ? _timeZone : 'UTC',
  }).format(timestamp);
}
