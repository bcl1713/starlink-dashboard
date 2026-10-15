import { expect, it } from 'vitest';
import { routeSnapshot } from '@/test/route-sigmet-fixtures';
import {
  type RouteSigmetEntry,
  parseRouteSigmetSnapshot,
} from '@/services/route-sigmets';
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
    'Crossing expected · 14:20–14:32 UTC',
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
it('keeps uncertainty visible beside a confirmed crossing', () => {
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
  ).toContain('Crossing expected');
  expect(
    formatSigmetEncounter({ ...e, encounter: evidence }, now).join(' ')
  ).toContain('Some crossing times unavailable');
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
  ).toEqual(['Crossing time unknown']);
  const e = parseRouteSigmetSnapshot(routeSnapshot().snapshot).entries[0];
  expect(formatSigmetEncounter(e, now)).toEqual(['Crossing time unknown']);
});

it('adds dates when rounded passage endpoints roll into tomorrow', () => {
  const e = entry('2026-10-30T23:59:20Z', '2026-10-30T23:59:40Z');
  expect(formatSigmetEncounter(e, now)[0]).toContain(
    '2026-10-30 23:59–2026-10-31 00:00 UTC'
  );
});

it('gives a direct no-crossing answer for passage outside validity', () => {
  const e: RouteSigmetEntry = entry();
  e.encounter.status = 'no-overlap';
  e.encounter.spans[0].status = 'no-overlap';
  expect(formatSigmetEncounter(e, now)).toEqual([
    'No crossing expected while valid',
  ]);
});

it('merges adjacent passages into one readable crossing window', async () => {
  const { crossingPassages } = await import('./sigmet-encounter-text');
  const e = entry();
  const first = e.encounter.spans[0];
  e.encounter.spans.push({
    ...first,
    entry_ms: first.exit_ms,
    exit_ms: first.exit_ms + 60000,
  });
  const windows = crossingPassages(e);
  expect(windows).toHaveLength(1);
  expect(windows[0].exit_ms).toBe(first.exit_ms + 60000);
  expect(first.exit_ms).toBe(Date.parse('2026-10-30T14:32:00Z'));
});
it('does not turn separate crossings into one continuous passage', async () => {
  const { crossingPassages } = await import('./sigmet-encounter-text');
  const e = entry();
  const first = e.encounter.spans[0];
  e.encounter.spans.push({
    ...first,
    entry_ms: first.exit_ms + 60000,
    exit_ms: first.exit_ms + 120000,
  });
  expect(crossingPassages(e)).toHaveLength(2);
});
