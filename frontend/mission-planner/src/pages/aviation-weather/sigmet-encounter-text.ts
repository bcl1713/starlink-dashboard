import type {
  RouteSigmetEntry,
  SelectedSigmetEntry,
} from '@/services/route-sigmets';
export const passageReasons = {
  'missing-timing': 'Missing waypoint times',
  'invalid-timing': 'Invalid waypoint times',
  'ambiguous-association': 'Route association unavailable',
  'unavailable-plan': 'Plan timing unavailable',
};
export function formatSigmetEncounter(
  entry: RouteSigmetEntry | SelectedSigmetEntry,
  nowMs: number
): string[] {
  if (!('encounter' in entry))
    return ['Encounter unavailable — no route intersection'];
  const evidence = entry.encounter;
  const known = evidence.spans.filter(
    (p) => p.entry_ms !== null && p.exit_ms !== null
  );
  if (!known.length)
    return [
      `Planned passage unavailable · ${passageReasons[evidence.reason ?? 'unavailable-plan']}`,
    ];
  let start = Infinity,
    end = -Infinity;
  for (const span of known) {
    start = Math.min(start, span.entry_ms!);
    end = Math.max(end, span.exit_ms!);
  }
  const day = (ms: number) => new Date(ms).toISOString().slice(0, 10);
  const roundedStart = Math.round(start / 60000) * 60000;
  const roundedEnd = Math.round(end / 60000) * 60000;
  const dates =
    day(start) !== day(nowMs) ||
    day(end) !== day(nowMs) ||
    day(roundedStart) !== day(nowMs) ||
    day(roundedEnd) !== day(nowMs);
  const format = (ms: number) => {
    const iso = new Date(Math.round(ms / 60000) * 60000).toISOString();
    return dates ? iso.slice(0, 16).replace('T', ' ') : iso.slice(11, 16);
  };
  const status =
    evidence.status === 'overlap'
      ? 'Time overlap'
      : evidence.status === 'no-overlap'
        ? 'No time overlap'
        : 'Time overlap unknown';
  const lines = [
    `Planned passage${evidence.spans.length > 1 ? ' summary' : ''} ${format(start)}–${format(end)} UTC · ${status}`,
  ];
  if (evidence.unknown_count)
    lines.push(
      `${evidence.unknown_count} passage${evidence.unknown_count === 1 ? '' : 's'} unavailable`
    );
  return lines;
}
