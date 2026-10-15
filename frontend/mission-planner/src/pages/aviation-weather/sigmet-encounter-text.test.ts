import { expect, it } from 'vitest';
import { routeSnapshot } from '@/test/route-sigmet-fixtures';
import { parseRouteSigmetSnapshot } from '@/services/route-sigmets';
import { formatSigmetEncounter } from './sigmet-encounter-text';
const now = Date.parse('2026-10-30T12:00:00Z');
function entry(start = '2026-10-30T14:20:00Z', end = '2026-10-30T14:32:00Z') {
  const e = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  return {
    ...e,
    encounter: {
      spans: [
        {
          entry_ms: Date.parse(start),
          exit_ms: Date.parse(end),
          status: 'overlap' as const,
          reason: null,
        },
      ],
      status: 'overlap' as const,
      unknown_count: 0,
      reason: null,
    },
  };
}
it('formats planned UTC passage independently of the local timezone', () => {
  expect(formatSigmetEncounter(entry(), now)).toEqual([
    'Planned passage 14:20–14:32 UTC · Time overlap',
  ]);
});
it('includes dates across midnight and on historical routes', () => {
  expect(
    formatSigmetEncounter(
      entry('2026-10-29T23:55:00Z', '2026-10-30T00:05:00Z'),
      now
    )[0]
  ).toContain('2026-10-29 23:55–2026-10-30 00:05 UTC');
});
it('rounds summary minutes without changing exact evidence classification', () => {
  const e = entry('2026-10-30T14:20:59.999Z');
  expect(formatSigmetEncounter(e, now)[0]).toContain('14:21–14:32');
  expect(e.encounter.spans[0].entry_ms).toBe(
    Date.parse('2026-10-30T14:20:59.999Z')
  );
});
it('labels disjoint summaries and preserves unknown counts', () => {
  const e = entry();
  const evidence = {
    ...e.encounter,
    unknown_count: 1,
    spans: [
      ...e.encounter.spans,
      {
        entry_ms: null,
        exit_ms: null,
        status: 'unknown' as const,
        reason: 'missing-timing' as const,
      },
    ],
  };
  expect(
    formatSigmetEncounter({ ...e, encounter: evidence }, now).join(' ')
  ).toContain('summary');
  expect(
    formatSigmetEncounter({ ...e, encounter: evidence }, now).join(' ')
  ).toContain('1 passage unavailable');
});
it('selected-only and missing timing never invent passage', () => {
  const selected = { ...entry() } as Partial<ReturnType<typeof entry>>;
  delete selected.spans;
  delete selected.encounter;
  expect(
    formatSigmetEncounter(
      selected as import('@/services/route-sigmets').SelectedSigmetEntry,
      now
    )
  ).toEqual(['Encounter unavailable — no route intersection']);
  const e = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  expect(formatSigmetEncounter(e, now)).toEqual([
    'Planned passage unavailable · Missing waypoint times',
  ]);
});

it('adds dates when rounded passage endpoints roll into tomorrow', () => {
  const e = entry('2026-10-30T23:59:20Z', '2026-10-30T23:59:40Z');
  expect(formatSigmetEncounter(e, now)[0]).toContain(
    '2026-10-30 23:59–2026-10-31 00:00 UTC'
  );
});
