import { expect, it } from 'vitest';
import { sigmetAttentionItems, sigmetNoticeColor } from './sigmet-attention';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import { routeSigmetSnapshotSchema } from '@/services/route-sigmets';
import {
  parseAviationFeatures,
  type AviationAdvisory,
} from '@/services/aviation-features';
import { NOW } from './fixtures';

it('unknown-only results never create automatic attention', () => {
  const f = routeSnapshot();
  f.snapshot.entries = [];
  const s = routeSigmetSnapshotSchema.parse(f.snapshot);
  expect(sigmetAttentionItems(s, [], NOW)).toEqual([]);
});
it('joins selected-only reports without inventing spans or counting a bulletin twice', () => {
  const f = routeSnapshot();
  const s = routeSigmetSnapshotSchema.parse(f.snapshot);
  const selected = JSON.parse(JSON.stringify(s.entries[0]));
  delete selected.spans;
  selected.selected = true;
  const reports = parseAviationFeatures(f.data, 'sigmet')
    .features as AviationAdvisory[];
  const onlySelected = { ...s, entries: [], selected_entries: [selected] };
  const items = sigmetAttentionItems(onlySelected, reports, NOW);
  expect(items).toHaveLength(1);
  expect(items[0].kind).toBe('selected');
  expect(items[0].entry).not.toHaveProperty('spans');
  expect(
    sigmetAttentionItems({ ...s, selected_entries: [selected] }, reports, NOW)
  ).toHaveLength(1);
  expect(
    sigmetAttentionItems(
      { ...s, entries: s.entries.map((e) => ({ ...e, acknowledged: true })) },
      reports,
      NOW
    )
  ).toEqual([]);
  expect(sigmetAttentionItems(onlySelected, reports, NOW + 3600001)).toEqual(
    []
  );
});
it('assigns stable colors by bulletin identity instead of display position', () => {
  expect(sigmetNoticeColor(hash('a'))).toBe(sigmetNoticeColor(hash('a')));
  expect(['#7dd3fc', '#f0abfc', '#fde68a']).toContain(
    sigmetNoticeColor(hash('b'))
  );
});
