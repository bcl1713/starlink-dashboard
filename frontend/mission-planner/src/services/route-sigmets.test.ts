import { expect, it } from 'vitest';
import { routeSnapshot, hash } from '@/test/route-sigmet-fixtures';
import {
  parseRouteSigmetSnapshot,
  parseNoticeMutation,
  parseNoticeConfirmation,
} from './route-sigmets';

it('strictly admits snapshot identity, original deadlines and known spans', () => {
  const { snapshot } = routeSnapshot();
  expect(
    parseRouteSigmetSnapshot(snapshot).entries[0].spans[0].start_fraction
  ).toBe(0.25);
  for (const change of [
    { extra: true },
    { truncated: true },
    { complete: false },
    { state_revision: true },
    { context: null },
    { generation_id: 'old' },
    { unresolved: [{ feature_id: 'unknown', reason: 'unlocated' }] },
  ])
    expect(() =>
      parseRouteSigmetSnapshot({ ...snapshot, ...change })
    ).toThrow();
});
it('rejects aggregate identity duplicates, invalid spans and non-SIGMET products', () => {
  const { snapshot } = routeSnapshot();
  expect(() =>
    parseRouteSigmetSnapshot({
      ...snapshot,
      entries: [...snapshot.entries, ...snapshot.entries],
    })
  ).toThrow();
  snapshot.entries[0].spans[0].end_fraction = 0.1;
  expect(() => parseRouteSigmetSnapshot(snapshot)).toThrow();
  const other = routeSnapshot().snapshot;
  other.sigmet_product.product_type = 'metar-speci';
  expect(() => parseRouteSigmetSnapshot(other)).toThrow();
});
it('admits only exact mutation and confirmed revision fields', () => {
  const mutation = {
    context_key: hash('c'),
    notice_key: hash('d'),
    semantic_digest: hash('f'),
    acknowledged: true,
  };
  expect(parseNoticeMutation(mutation).acknowledged).toBe(true);
  expect(() =>
    parseNoticeMutation({ ...mutation, state_revision: 2 })
  ).toThrow();
  expect(() => parseNoticeMutation({ ...mutation, acknowledged: 1 })).toThrow();
  expect(
    parseNoticeConfirmation({
      ...mutation,
      state_revision: 2,
      attention_order: 1,
    }).state_revision
  ).toBe(2);
  expect(() =>
    parseNoticeConfirmation({
      ...mutation,
      state_revision: -1,
      attention_order: 1,
    })
  ).toThrow();
});
