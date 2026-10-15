import type {
  RouteSigmetEntry,
  SelectedSigmetEntry,
} from '@/services/route-sigmets';
type Passage = RouteSigmetEntry['encounter']['spans'][number];

/** Keep separate crossings separate; adjacent route segments share one window. */
export function crossingPassages(entry: RouteSigmetEntry): Passage[] {
  const windows: Passage[] = [];
  for (const span of entry.encounter.spans) {
    const previous = windows.at(-1);
    if (
      previous &&
      previous.status === span.status &&
      previous.entry_ms !== null &&
      previous.exit_ms !== null &&
      span.entry_ms !== null &&
      span.exit_ms !== null &&
      previous.entry_ms <= span.entry_ms &&
      span.entry_ms <= previous.exit_ms
    ) {
      previous.exit_ms = Math.max(previous.exit_ms, span.exit_ms);
    } else windows.push({ ...span });
  }
  return windows;
}

export function formatCrossingTime(
  start: number,
  end: number,
  nowMs: number
): string {
  const roundedStart = Math.round(start / 60000) * 60000;
  const roundedEnd = Math.round(end / 60000) * 60000;
  const day = (ms: number) => new Date(ms).toISOString().slice(0, 10);
  const dates = [start, end, roundedStart, roundedEnd].some(
    (ms) => day(ms) !== day(nowMs)
  );
  const format = (ms: number) => {
    const iso = new Date(Math.round(ms / 60000) * 60000).toISOString();
    return dates ? iso.slice(0, 16).replace('T', ' ') : iso.slice(11, 16);
  };
  return `${format(start)}–${format(end)} UTC`;
}

export function formatSigmetEncounter(
  entry: RouteSigmetEntry | SelectedSigmetEntry,
  nowMs: number
): string[] {
  if (!('encounter' in entry) || entry.encounter.status === 'unknown')
    return ['Crossing time unknown'];
  if (entry.encounter.status === 'no-overlap')
    return ['No crossing expected while valid'];
  const passages = crossingPassages(entry).filter(
    (p) => p.status === 'overlap'
  );
  const first = passages[0];
  const lines = [
    `Crossing expected · ${formatCrossingTime(first.entry_ms!, first.exit_ms!, nowMs)}`,
  ];
  if (passages.length > 1) lines.push(`${passages.length} separate crossings`);
  if (entry.encounter.unknown_count)
    lines.push('Some crossing times unavailable');
  return lines;
}
